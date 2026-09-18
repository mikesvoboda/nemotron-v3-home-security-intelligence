import re, difflib

mut_src = open('/agents/agent-nemo2/workspace/mutants/backend/services/event_broadcaster.py').read().splitlines()

def_re = re.compile(r'^(\s*)(?:async )?def (x\w+)__mutmut_(orig|\d+)[(\[]')
defs = []
for i, l in enumerate(mut_src):
    m = def_re.match(l)
    if m:
        defs.append((len(m.group(1)), m.group(2), m.group(3), i))


def block_lines(start_idx, indent):
    out = []
    j = start_idx + 1
    while j < len(mut_src):
        l = mut_src[j]
        if l.strip() == '':
            out.append(l)
            j += 1
            continue
        cur = len(l) - len(l.lstrip())
        if cur <= indent:
            break
        out.append(l)
        j += 1
    while out and out[-1].strip() == '':
        out.pop()
    return out


by_fullname = {}
for indent, base, suffix, lineno in defs:
    by_fullname[(base, suffix)] = block_lines(lineno, indent)

surv = [l.strip() for l in open('/tmp/wp25/wp44-triage/eb_survivors.txt') if l.strip()]
out_lines = []
fails = 0
for key in surv:
    m = re.match(r'backend\.services\.event_broadcaster\.(x.*)__mutmut_(\d+)$', key)
    base, num = m.group(1), m.group(2)
    orig = by_fullname.get((base, 'orig'))
    mut = by_fullname.get((base, num))
    if orig is None or mut is None:
        out_lines.append(f'{key}\t{base}\tEXTRACT_FAIL')
        fails += 1
        continue
    o = [l.rstrip() for l in orig]
    mu = [l.rstrip() for l in mut]
    sm = difflib.SequenceMatcher(None, o, mu)
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        ol = ' | '.join(x.strip() for x in o[i1:i2])
        nl = ' | '.join(x.strip() for x in mu[j1:j2])
        hunks.append(f'-[{ol}] +[{nl}]')
    out_lines.append(f'{key}\t{base}\t' + ' ;; '.join(hunks))

open('/tmp/wp25/wp44-triage/eb_diffs.txt', 'w').write('\n'.join(out_lines) + '\n')
print('wrote', len(out_lines), 'fails', fails)
