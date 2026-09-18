import json, re, sys, difflib, collections

MF = 'mutants/backend/services/batch_aggregator.py'
src = open(MF, encoding='utf-8').read().splitlines()

# index def lines: name -> (start, end)
defre = re.compile(r'^(\s*)(?:async\s+)?def\s+(x\S+?__mutmut_(?:orig|\d+))\s*\(')
defs = []
for i, line in enumerate(src):
    m = defre.match(line)
    if m:
        defs.append((i, m.group(2)))

# block end: next def of ANY family, or registry line
blocks = {}
for j, (start, name) in enumerate(defs):
    end = len(src)
    if j + 1 < len(defs):
        end = defs[j+1][0]
    # trim to registry line if inside
    body = src[start:end]
    for k, l in enumerate(body):
        if l.startswith('mutants_'):
            body = body[:k]
            break
    blocks[name] = body

def fam(name):
    return name.rsplit('__mutmut_', 1)[0]

def strip_defline(body):
    # drop def signature line(s): lines until one ends with ':' continuation handled crudely;
    # signature may span multiple lines; find line ending with '):' or '): -> ...:'
    out = []
    started = False
    depth = 0
    for l in body:
        if not started:
            depth += l.count('(') - l.count(')')
            if depth <= 0 and l.rstrip().endswith(':'):
                started = True
            continue
        out.append(l)
    while out and not out[-1].strip():
        out.pop()
    return out

surv = json.load(open('/tmp/wp25/wp44-triage/surv_batch.json'))
results = []
missing = []
for key in surv:
    tail = key.rsplit('.', 1)[-1]
    f = fam(tail)
    orig = blocks.get(f + '__mutmut_orig')
    var = blocks.get(tail)
    if orig is None or var is None:
        missing.append(key); continue
    ob, vb = strip_defline(orig), strip_defline(var)
    if ob == vb:
        results.append((key, fam(tail), 'NO textual change', ''))
        continue
    sm = difflib.SequenceMatcher(None, ob, vb)
    frags = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        o = ' | '.join(x.strip() for x in ob[i1:i2])
        v = ' | '.join(x.strip() for x in vb[j1:j2])
        frags.append(f'{o} ==> {v}')
    results.append((key, fam(tail), 'diff', ' ;; '.join(frags)))

json.dump({'results': results, 'missing': missing}, open('/tmp/wp25/wp44-triage/deltas.json','w'))
print('missing', len(missing), 'diffed', len(results))
# aggregate by (family, delta-signature)
agg = collections.Counter()
for key, f, kind, delta in results:
    agg[(f, delta[:200])] += 1
for (f, d), n in sorted(agg.items(), key=lambda x: (-x[1])):
    print(n, '|', f, '|', d[:160])
