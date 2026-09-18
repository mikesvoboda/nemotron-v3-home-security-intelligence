import re, difflib

src = open('/agents/agent-nemo2/workspace/mutants/backend/services/mqtt_client.py').read().splitlines()

defpat = re.compile(r'^(\s*)(?:async\s+)?def\s+(x\S*?__mutmut_(orig|\d+))\s*\(')
defs = []
for i, line in enumerate(src):
    m = defpat.match(line)
    if m:
        defs.append((i, m.group(2), len(m.group(1))))

segs = {}
for idx, (ln, name, indent) in enumerate(defs):
    end = len(src)
    for j in range(ln+1, len(src)):
        l = src[j]
        if l.strip() == '':
            continue
        cur = len(l) - len(l.lstrip())
        if cur <= indent:
            end = j
            break
    segs[name] = src[ln:end]

survivors = open('/tmp/wp25/wp44-triage/mqtt_client_survivors.txt').read().split()
out = []
for key in survivors:
    vname = key.split('.', 3)[-1]
    oname = re.sub(r'__mutmut_\d+$', '__mutmut_orig', vname)
    v = segs.get(vname); o = segs.get(oname)
    if v is None or o is None:
        out.append(f'### {key}\n  MISSING v={v is not None} o={o is not None}')
        continue
    # drop the def line difference, compare body only
    ob = [l.strip() for l in o[1:]]
    vb = [l.strip() for l in v[1:]]
    sm = difflib.SequenceMatcher(None, ob, vb, autojunk=False)
    parts = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        olines = [l for l in ob[i1:i2]]
        vlines = [l for l in vb[j1:j2]]
        parts.append('- ' + ' | '.join(olines) if olines else '- (nothing)')
        parts.append('+ ' + ' | '.join(vlines) if vlines else '+ (nothing)')
    if not parts:
        parts.append('  (identical to orig)')
    out.append(f'### {key}\n' + '\n'.join(parts))

open('/tmp/wp25/wp44-triage/mqtt_client_diffs.txt','w').write('\n'.join(out) + '\n')
print('wrote', len(out))
