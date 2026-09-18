import json, re

WS = '/agents/agent-nemo2/workspace'
sp = json.load(open(WS + '/mutants/backend/services/nemotron_analyzer.py.spans'))['spans']
lines = open(WS + '/mutants/backend/services/nemotron_analyzer.py', errors='replace').read().split('\n')
fam = json.load(open('/tmp/wp25/wp44-triage/final.json'))


def vblock(mangled):
    a, b = sp[mangled]
    return [re.sub(r'__mutmut_[A-Za-z0-9]+', '__MUT__', l) for l in lines[a:b]]


def strip_comment(l):
    # crude: remove trailing // or # comment outside quotes
    out, q = [], None
    i = 0
    while i < len(l):
        c = l[i]
        if q:
            if c == '\\':
                i += 2
                continue
            if c == q:
                q = None
        else:
            if c in '"\'':
                q = c
            elif c == '#':
                break
        out.append(c)
        i += 1
    return ''.join(out)


CHAIN_CACHE = {}


def chain_at(mangled, new_line_stripped):
    """Return bracket chain (list of open scopes, innermost first) at the line."""
    if mangled in CHAIN_CACHE:
        blk = CHAIN_CACHE[mangled]
    else:
        blk = vblock(mangled)
        CHAIN_CACHE[mangled] = blk
    j = None
    for k, l in enumerate(blk):
        if l.strip() == new_line_stripped:
            j = k
            break
    if j is None:
        return None
    stack = []  # (call_name_or_'DICT', line_no)
    for k in range(0, j + 1):
        l = strip_comment(blk[k])
        i = 0
        while i < len(l):
            c = l[i]
            if c in '"\'':
                q = c
                i += 1
                while i < len(l):
                    if l[i] == '\\':
                        i += 2
                        continue
                    if l[i] == q:
                        break
                    i += 1
            elif c in '([{':
                pre = l[:i].rstrip()
                m = re.search(r'([A-Za-z_][\w.]*)$', pre)
                name = m.group(1) if m else 'DICT'
                stack.append((name, k))
            elif c in ')]}':
                if stack:
                    stack.pop()
            i += 1
    # chain at line j AFTER processing line j's opening brackets up to the
    # mutated line's own content; approximate: use stack as-is
    return [s[0] for s in stack[::-1]]


OBS_ROOTS = {
    'logger': None,
}
OBS_CALLS = {'debug', 'info', 'warning', 'error', 'exception', 'log_context',
             'record_exception', 'add_span_attributes', 'add_span_event',
             'record_pipeline_error', 'set_pipeline_context_attributes',
             'set_llm_inference_attributes', 'set_inference_result_attributes',
             'observe_risk_score', 'observe_risk_score_distribution',
             'observe_ai_request_duration', 'record_event_by_risk_level',
             'record_prompt_template_used', 'record_nemotron_tokens',
             'increment_event_count', 'track_llm_usage', 'set_on_span',
             'record_cost', 'record_pipeline_latency', 'record_event',
             'set_llm_call_attributes'}

FUNC_MARK = re.compile(r'(post|execute|add|flush|commit|scalar|where|select|enqueue|broadcast|publish|send|webhook|raise|Event\(|LLMInteraction\(|payload|http_client|session)')

out = []
for f, rows in fam.items():
    for r in rows:
        func = r['func']
        if func.startswith('x__') or func.startswith('x_'):
            mangled = func
        else:
            cls, fn = func.split('.', 1)
            mangled = f'xǁ{cls}ǁ{fn}'
        vn = f'{mangled}__mutmut_{r["idx"]}'
        nl = r['new'][0].strip() if r['new'] and r['new'][0].strip() else (r['old'][0].strip() if r['old'] else '')
        ch = chain_at(vn, nl) if nl else None
        if ch is None:
            out.append({'func': func, 'idx': r['idx'], 'family': f, 'chain': 'NOTFOUND', 'sink': 'UNK'})
            continue
        root = None
        for name in ch:
            last = name.split('.')[-1]
            if name.startswith('logger') or last in OBS_CALLS:
                root = 'OBS'
                break
        if root is None:
            joined = '>'.join(ch)
            if 'ASSIGN' in joined:
                root = 'DATA'
            elif FUNC_MARK.search(joined) or any(x in ch for x in ('post', 'execute', 'add', 'flush')):
                root = 'FUNC'
            else:
                root = 'ASSIGN'
        out.append({'func': func, 'idx': r['idx'], 'family': f,
                    'chain': '>'.join(ch[:6]), 'sink': root})

json.dump(out, open('/tmp/wp25/wp44-triage/sinks.json', 'w'))
from collections import Counter
print('rows', len(out), 'notfound', sum(1 for r in out if r['chain'] == 'NOTFOUND'))
c = Counter((r['family'], r['sink']) for r in out)
for (f, s), n in sorted(c.items()):
    print(f'{n:5d} {f:42s} {s}')
