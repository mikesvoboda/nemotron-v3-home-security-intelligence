import json, collections
d = json.load(open('/tmp/wp25/wp44-triage/export_service_diffs.json'))
by_fn = collections.defaultdict(list)
for k, v in d.items():
    tail = k.split('export_service.')[1]
    fn = tail.rsplit('__mutmut_', 1)[0]
    by_fn[fn].append((k, v))
for fn in sorted(by_fn):
    print('='*100)
    print(fn, len(by_fn[fn]))
    # group by diff text
    bydiff = collections.defaultdict(list)
    for k, v in by_fn[fn]:
        bydiff[v].append(k)
    for diff, keys in sorted(bydiff.items(), key=lambda x: -len(x[1])):
        print('--- count', len(keys), '|', keys[:4])
        print(diff)
