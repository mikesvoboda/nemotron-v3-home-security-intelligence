import json, collections, importlib.util, sys

# Re-run the spec module's SPEC by exec'ing its source up to the assignment block,
# so SPEC stays the single source of truth (memory rule: dossier is canonical).
src = open('/tmp/wp25/wp44-triage/tms_spec.py').read()
src = src.split("assign = {}")[0]
ns = {}
exec(src, ns)
SPEC = ns['SPEC']
S = ns['S']
recs = ns['recs']

# Correct line anchors: per (fn, removed-text) -> ALL matching lines in fn range;
# pick the line the mutants on this cluster most plausibly sit on = first occurrence.
LINES = open('/agents/agent-nemo2/workspace/backend/services/threat_monitor_service.py').read().split('\n')
FR = {
 'process_threat_detection': (203, 280),
 'process_multiple_threat_detections': (295, 386),
 '_broadcast_alert_created': (462, 526),
 '_trigger_webhooks': (528, 565),
}
rows = []
structured = []
total = 0
assign = {}
for name, cls_, members in SPEC:
    nums = []
    for fn, ns_ in members:
        for n in ns_:
            assign[(fn, n)] = name
            r = S[(fn, n)]
            t = r['rem'][0] if r['rem'] else ''
            ln = r.get('srcline')
            nums.append((fn, n, r['key'], ln))
    cnt = len(nums)
    total += cnt
    keyl = [k for _, _, k, _ in sorted(nums)[:3]]
    lns = sorted({ln for _, _, _, ln in nums if ln})
    rng = f"{lns[0]}-{lns[-1]}" if lns else "?"
    short = name if len(name) <= 150 else name[:147] + '...'
    rows.append((short, cnt, cls_, keyl, rng))
    structured.append({'pattern': name, 'count': cnt, 'classification': cls_, 'example_keys': keyl})

assert total == len(S) == 220, (total, len(S))
cls_tot = collections.Counter(s['classification'] for s in structured)

with open('/tmp/wp25/wp44-triage/tms_table.md', 'w') as f:
    for short, cnt, cls_, keyl, rng in rows:
        ex = '; '.join(k.split('ǁ')[-1] for k in keyl)
        f.write(f"| {short} | {cnt} | {cls_} | `{rng}` | {ex} |\n")

json.dump(structured, open('/tmp/wp25/wp44-triage/tms_structured_clusters.json', 'w'))
print('class totals', dict(cls_tot), 'clusters', len(structured), 'total', total)
# sanity: every survivor assigned exactly once
assert len(assign) == 220
PYEOF_MARKER_NOT_USED = None
