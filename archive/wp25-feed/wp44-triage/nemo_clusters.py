import json
from collections import Counter, defaultdict

rows = json.load(open('/tmp/wp25/wp44-triage/nemo_rows.json'))
sinks = json.load(open('/tmp/wp25/wp44-triage/sinks.json'))
# sinks keyed by (func, idx) -> family/chain/sink but sinks.json rebuilt earlier from OLD final; recompute family+chain from nemo artifacts
sinkmap = {}
for s in sinks:
    sinkmap[(s['func'], s['idx'])] = s

STRF = ('STR-XXwrap', 'STR-UPPER', 'STR-lower', 'STR-other', 'STR-XXwrap/UPPER-multi')

def oneline(r, key):
    v = r[key]
    return v[0] if v else ''

def cluster(r):
    f = r['func']
    fam = r['family'] if 'family' in r else None
    s = sinkmap.get((f, r['idx']), {})
    fam = fam or s.get('family', '?')
    sink = s.get('sink', 'UNK')
    chain = s.get('chain', '')
    fn = f.split('.')[-1]
    o, n = oneline(r, 'old'), oneline(r, 'new')

    if f == 'x__extract_json_objects':
        return 'C-EXTRACT'
    if fam in STRF and sink == 'OBS':
        return 'C-STR-OBS'
    if fam == 'LOG-exc_info-killed':
        return 'C-EXCINFO'
    if sink == 'OBS':
        return 'C-OBS-DATA'
    if fam.startswith('STR') and ('http_client.post' in chain or 'webhook_service' in chain):
        return 'C-HTTP-KEYS'
    if fn == '_call_llm' and ('attempt < self._max_retries' in o or 'delay = min' in o or 'last_exception' in o or 'last_exception' in n):
        return 'C-RETRY'
    if fn == '_check_guided_json_support' and (fam.startswith('OP-') or fam == 'NUM-tweak' or 'attempt <' in o):
        return 'C-GUIDED-BOUND'
    if fn in ('_trigger_event_created_webhook', '_broadcast_event'):
        return 'C-WEBHOOK'
    if fn == '_build_context_sources':
        return 'C-CTX-FLAGS'
    if fn == '_build_prompt':
        return 'C-PROMPT-GATES'
    if fn == '_parse_llm_response':
        return 'C-PARSE'
    if fn in ('calculate_batch_priority',) or 'label.lower' in o or 't.lower' in o or '& self._priority' in o:
        return 'C-PRIORITY'
    if fn == '__init__' and ('label.lower' in o or 'priority' in o.lower()):
        return 'C-PRIORITY'
    if fn in ('is_cold', 'get_warmth_state'):
        return 'C-COLD'
    if fn == 'record_rollout_analysis':
        return 'C-ROLLOUT'
    if fam in STRF:
        if fn in ('run_shadow_analysis', '_log_shadow_result', '_record_experiment_result', 'get_version_for_analysis', 'set_experiment_config'):
            return 'C-SHADOW'
        return 'C-STR-FUNC'
    if fam.startswith('DATA') or fam.startswith('MULTI'):
        return 'C-DATA-FUNC'
    if fam in ('OP-comparison-flip', 'OP-and-or-flip', 'OP-arith-flip', 'OP-is-flip',
               'COND-andFalse-orTrue', 'COND-isNotNone-flip', 'COND-not-added-removed',
               'BOOL-False-to-True', 'BOOL-True-to-False', 'FLOW-continue-break', 'NUM-tweak'):
        return 'C-LOGIC-FLIP'
    if fam in ('TOK-other:None->""', 'DATA-None-to-expr'):
        return 'C-SENTINEL'
    return 'C-MISC'

# attach family to rows
fammap = {}
final = json.load(open('/tmp/wp25/wp44-triage/nemo_final.json'))
for fam, rs in final.items():
    for r in rs:
        fammap[(r['func'], r['idx'])] = fam
for r in rows:
    r['family'] = fammap.get((r['func'], r['idx']), '?')
    r['chain'] = sinkmap.get((r['func'], r['idx']), {}).get('chain', '')
    r['sink'] = sinkmap.get((r['func'], r['idx']), {}).get('sink', 'UNK')

cl = defaultdict(list)
for r in rows:
    cl[cluster(r)].append(r)

tot = 0
for k in sorted(cl, key=lambda k: -len(cl[k])):
    funcs = Counter(x['func'] for x in cl[k])
    print(f'{len(cl[k]):5d}  {k:15s} topfuncs={funcs.most_common(4)}')
    tot += len(cl[k])
print('TOTAL', tot)
json.dump({k: [{'key': x['key'], 'func': x['func'], 'idx': x['idx'], 'family': x['family'],
                'old': x['old'], 'new': x['new'], 'chain': x['chain'], 'sink': x['sink']} for x in v]
           for k, v in cl.items()},
          open('/tmp/wp25/wp44-triage/nemo_clusters.json', 'w'))

# misc + catch-all inspection
for k in ('C-LOGIC-FLIP', 'C-DATA-FUNC', 'C-STR-FUNC', 'C-MISC', 'C-SHADOW'):
    sub = cl.get(k, [])
    print('=' * 70)
    print(k, len(sub), Counter(x['func'] for x in sub).most_common(12))
