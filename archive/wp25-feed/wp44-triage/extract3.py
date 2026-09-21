import re, difflib

path = '/agents/agent-nemo2/workspace/mutants/backend/services/event_broadcaster.py'
mut_src = open(path).read().splitlines()

def_re = re.compile(r'^(\s*)(?:async )?def (x\w+)__mutmut_(orig|\d+)[(\[]')
boundary_re = re.compile(
    r'^\s*(?:@_mutmut_mutated|(?:async )?def \w|class \w|mutants_x|@dataclass|from |import )')

def_starts = []  # (base, suffix, lineno)
for i, l in enumerate(mut_src):
    m = def_re.match(l)
    if m:
        def_starts.append((m.group(2), m.group(3), i))

all_def_lines = [i for _, _, i in def_starts]

def block_lines(idx):
    j = idx + 1
    # end at next def line (any indent from def_starts list)
    end = len(mut_src)
    for d in all_def_lines:
        if d > idx:
            end = d
            break
    out = mut_src[idx:end]
    # also cut at a decorator line for the NEXT variant (decorator sits above def; the next def line's decorator is BETWEEN: decorator at end-2 typically). Find first @_mutmut_mutated after idx that isn't at idx-? ; simply cut from first @_mutmut_mutated line strictly > idx
    for k in range(idx + 1, end):
        if mut_src[k].lstrip().startswith('@'):
            end = k
            break
    out = mut_src[idx:end]
    while out and out[-1].strip() == '':
        out.pop()
    return [l.rstrip() for l in out]

blocks = {}
for base, suffix, idx in def_starts:
    blocks[(base, suffix)] = block_lines(idx)

surv = [l.strip() for l in open('/tmp/wp25/wp44-triage/eb_survivors.txt') if l.strip()]
out_lines = []
fails = 0
empty = 0
for key in surv:
    m = re.match(r'backend\.services\.event_broadcaster\.(x.*)__mutmut_(\d+)$', key)
    base, num = m.group(1), m.group(2)
    o = blocks.get((base, 'orig'))
    mu = blocks.get((base, num))
    if o is None or mu is None:
        out_lines.append(f'{key}\t{base}\tEXTRACT_FAIL')
        fails += 1
        continue
    # normalize mutant names
    o = [re.sub(r'__mutmut_(orig|\d+)', '__mutmut_X', l) for l in o]
    mu = [re.sub(r'__mutmut_(orig|\d+)', '__mutmut_X', l) for l in mu]
    sm = difflib.SequenceMatcher(None, o, mu)
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        ol = ' | '.join(x.strip() for x in o[i1:i2])
        nl = ' | '.join(x.strip() for x in mu[j1:j2])
        hunks.append(f'-[{ol}] +[{nl}]')
    if not hunks:
        empty += 1
    out_lines.append(f'{key}\t{base}\t' + ' ;; '.join(hunks))

open('/tmp/wp25/wp44-triage/eb_diffs3.txt', 'w').write('\n'.join(out_lines) + '\n')
print('wrote', len(out_lines), 'fails', fails, 'empty', empty)
