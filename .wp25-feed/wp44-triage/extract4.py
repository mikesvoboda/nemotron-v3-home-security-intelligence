import re, difflib, json

path = '/agents/agent-nemo2/workspace/mutants/backend/services/event_broadcaster.py'
mut_src = open(path).read().splitlines()

def_re = re.compile(r'^(\s*)(?:async )?def (x\w+)__mutmut_(orig|\d+)[(\[]')
def_starts = []
for i, l in enumerate(mut_src):
    m = def_re.match(l)
    if m:
        def_starts.append((m.group(2), m.group(3), i))
all_def_lines = [i for _, _, i in def_starts]

def block_lines(idx):
    end = len(mut_src)
    for d in all_def_lines:
        if d > idx:
            end = d
            break
    for k in range(idx + 1, end):
        ls = mut_src[k].lstrip()
        if ls.startswith('@') or ls.startswith('mutants_x'):
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
records = []
for key in surv:
    m = re.match(r'backend\.services\.event_broadcaster\.(x.*)__mutmut_(\d+)$', key)
    base, num = m.group(1), m.group(2)
    o = blocks[(base, 'orig')]
    mu = blocks[(base, num)]
    o = [re.sub(r'__mutmut_(orig|\d+)', '__mutmut_X', l) for l in o]
    mu = [re.sub(r'__mutmut_(orig|\d+)', '__mutmut_X', l) for l in mu]
    sm = difflib.SequenceMatcher(None, o, mu)
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        ctx_before = [x.strip() for x in o[max(0, i1-3):i1]]
        ctx_after = [x.strip() for x in o[i2:i2+2]]
        ol = ' | '.join(x.strip() for x in o[i1:i2])
        nl = ' | '.join(x.strip() for x in mu[j1:j2])
        hunks.append({'old': ol, 'new': nl, 'ctx_before': ctx_before, 'ctx_after': ctx_after})
    records.append({'key': key, 'fn': base, 'hunks': hunks})

json.dump(records, open('/tmp/wp25/wp44-triage/eb_records.json', 'w'), indent=0)
print('records', len(records), 'hunks', sum(len(r['hunks']) for r in records))
