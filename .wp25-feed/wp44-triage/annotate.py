import json, re, difflib
from collections import Counter, defaultdict

WS = '/agents/agent-nemo2/workspace'
meta = json.load(open(WS + '/mutants/backend/services/nemotron_analyzer.py.meta'))
ebk = meta['exit_code_by_key']
sp = json.load(open(WS + '/mutants/backend/services/nemotron_analyzer.py.spans'))['spans']
lines = open(WS + '/mutants/backend/services/nemotron_analyzer.py', errors='replace').read().split('\n')
fam = json.load(open('/tmp/wp25/wp44-triage/final.json'))

family_of = {}
for f, rows in fam.items():
    for r in rows:
        family_of[(r['func'], r['idx'])] = f

def unmangle(f):
    parts = f.split('ǁ')
    if parts[0] == 'x' and len(parts) == 3:
        return parts[1] + '.' + parts[2]
    if parts[0] == 'x' and len(parts) == 2:
        return parts[1]
    return f

cache = {}
def vblock(mangled):
    if mangled not in cache:
        a, b = sp[mangled]
        cache[mangled] = lines[a:b]
    return cache[mangled]

def norm(l):
    return re.sub(r'__mutmut_[A-Za-z0-9]+', '__MUT__', l)

OPEN = '([{‘'
CLOSE = ')]}'

def enclosing(blk, j):
    """Walk up from line j, return (call_name, opener_line)."""
    bal = 0
    for k in range(j - 1, -1, -1):
        l = blk[k]
        o = sum(l.count(c) for c in '([{')
        c = sum(l.count(c) for c in ')]}')
        if c - o > 0:
            bal += c - o
            continue
        if o - c > 0:
            m = re.search(r'([A-Za-z_][\w.]*)\s*\(', l)
            name = m.group(1) if m else l.strip()[:40]
            return name, l.strip()
        if l.strip() == '' :
            continue
        # statement boundary: line with balanced parens and code (assignment/return/raise)
        if bal == 0:
            m = re.search(r'([A-Za-z_][\w.]*)\s*\(', l)
            if m and o - c > 0:
                return m.group(1), l.strip()
            if bal == 0 and (l.strip().startswith(('return', 'raise', 'await', 'yield', 'assert', 'if ', 'elif ', 'else', 'for ', 'async ', 'result', 'payload')) or '=' in l):
                return 'ASSIGN/CTRL', l.strip()[:60]
    return 'TOP', ''

OBS = set('''logger.debug logger.info logger.warning logger.error logger.exception log_context
add_span_attributes record_exception record_pipeline_error set_pipeline_context_attributes
set_llm_inference_attributes set_inference_result_attributes set_on_span observe_risk_score
observe_ai_request_duration observe_risk_score_distribution record_event_by_risk_level
record_prompt_template_used record_nemotron_tokens increment_event_count track_llm_usage
record_cost record_pipeline_latency record_event'''.split())

FUNC_HINT = re.compile(r'payload|http_client\.post|session\.add|session\.execute|select\(|\.where\(|Event\(|LLMInteraction\(|_enqueue_for_evaluation|broadcast|websocket|\.flush\(|scalar_one|\.post\(|raise |return |json=payload|webhook|\.publish\(|_set_idempotency|_check_idempotency|set_cache|redis')

out_rows = []
for (func, idx), f in family_of.items():
    mangled = func.replace('NemotronAnalyzer.', 'xǁNemotronAnalyzerǁ').replace(
        'x__extract_json_objects', 'x__extract_json_objects')
    if func.startswith('x__') or func.startswith('x_'):
        mangled = func
    vname = f'{mangled}__mutmut_{idx}'
    blk = [norm(l) for l in vblock(vname)]
    # locate new lines in variant block
    new0 = fam[f]
    rrow = [r for r in fam[f] if r['func'] == func and r['idx'] == idx][0]
    j = None
    strip_new = [x.strip() for x in rrow['new']]
    if strip_new and strip_new[0] != '':
        for k, l in enumerate(blk):
            if l.strip() == strip_new[0]:
                j = k
                break
    call, opener = ('NOTFOUND', '') if j is None else enclosing(blk, j)
    cat = 'OBS' if call in OBS else ('FUNC' if (FUNC_HINT.search(opener or '') or FUNC_HINT.search(strip_new[0] if strip_new else '')) else 'OTHER')
    out_rows.append({'func': func, 'idx': idx, 'family': f, 'call': call,
                     'opener': (opener or '')[:90], 'cat': cat,
                     'old': rrow['old'], 'new': rrow['new']})

json.dump(out_rows, open('/tmp/wp25/wp44-triage/annotated.json', 'w'))
print('rows:', len(out_rows), 'notfound:', sum(1 for r in out_rows if r['call'] == 'NOTFOUND'))

c = Counter((r['family'], r['cat']) for r in out_rows)
for (f, cat), n in sorted(c.items()):
    print(f'{n:5d}  {f:45s} {cat}')
print()
top = Counter(r['call'] for r in out_rows)
print('top enclosing calls:')
for k, v in top.most_common(30):
    print(f'{v:5d}  {k}')
