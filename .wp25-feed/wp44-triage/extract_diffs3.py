import re, difflib

src = open('/agents/agent-nemo2/workspace/mutants/backend/services/mqtt_client.py').read().splitlines()

defpat = re.compile(r'^(\s*)(?:async\s+)?def\s+(x\S*?__mutmut_(orig|\d+))\s*\(')
defs = []
for i, line in enumerate(src):
    m = defpat.match(line)
    if m:
        defs.append((i, m.group(2), len(m.group(1))))

def header_end(ln):
    # find line index where signature parens balance AND line ends with ':'
    bal = 0
    for j in range(ln, len(src)):
        bal += src[j].count('(') - src[j].count(')')
        if bal <= 0 and src[j].rstrip().endswith(':'):
            return j
    return ln

segs = {}
for idx, (ln, name, indent) in enumerate(defs):
    hend = header_end(ln)
    end = len(src)
    for j in range(hend+1, len(src)):
        l = src[j]
        if l.strip() == '':
            continue
        cur = len(l) - len(l.lstrip())
        if cur <= indent:
            end = j
            break
    segs[name] = src[ln:hend+1] + src[hend+1:end]

survivors = open('/tmp/wp25/wp44-triage/mqtt_client_survivors.txt').read().split()
out = []
ident = []
for key in survivors:
    vname = key.split('.', 3)[-1]
    oname = re.sub(r'__mutmut_\d+$', '__mutmut_orig', vname)
    v = segs.get(vname); o = segs.get(oname)
    if v is None or o is None:
        out.append(f'### {key}\n  MISSING v={v is not None} o={o is not None}')
        continue
    # body only: skip signature lines (through header end)
    hv = header_end(src.index(v[0], 0) if False else 0)  # unused
    # find header end within each segment
    def body_of(seg):
        bal = 0
        for j, l in enumerate(seg):
            bal += l.count('(') - l.count(')')
            if bal <= 0 and l.rstrip().endswith(':'):
                return [x.strip() for x in seg[j+1:]]
        return [x.strip() for x in seg[1:]]
    ob, vb = body_of(o), body_of(v)
    sm = difflib.SequenceMatcher(None, ob, vb, autojunk=False)
    parts = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        parts.append('- ' + ' | '.join(ob[i1:i2]) if i2 > i1 else '- (nothing)')
        parts.append('+ ' + ' | '.join(vb[j1:j2]) if j2 > j1 else '+ (nothing)')
    if not parts:
        parts.append('  (identical to orig)')
        ident.append(key)
    out.append(f'### {key}\n' + '\n'.join(parts))

open('/tmp/wp25/wp44-triage/mqtt_client_diffs.txt','w').write('\n'.join(out) + '\n')
print('wrote', len(out), 'identical:', len(ident))
for k in ident: print(' IDENT:', k)
