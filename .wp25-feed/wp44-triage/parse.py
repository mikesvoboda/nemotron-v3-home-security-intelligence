import collections

txt = open('/tmp/wp25/wp44-triage/diffs.txt').read()
blocks = txt.split('===KEY ')[1:]
rows = []
for b in blocks:
    lines = b.split('\n')
    key = lines[0]
    fn = key.split('ǁ')[-1]
    minus = [l[1:] for l in lines if l.startswith('-') and not l.startswith('---')]
    plus = [l[1:] for l in lines if l.startswith('+') and not l.startswith('+++')]
    rows.append((fn, '|'.join(x.strip() for x in minus), '|'.join(x.strip() for x in plus)))

g = collections.defaultdict(list)
for fn, m, p in rows:
    g[fn.split('__mutmut')[0]].append((fn, m, p))

for fn in sorted(g):
    items = sorted(g[fn], key=lambda x: int(x[0].split('__mutmut_')[-1]))
    print('#### %s  (%d)' % (fn, len(items)))
    for k, m, p in items:
        num = k.split('__mutmut_')[-1]
        print('  %-5s -%s' % (num, m))
        print('        +%s' % p)
