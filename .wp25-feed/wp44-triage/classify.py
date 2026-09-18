import json, re

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
    return mut_src[idx:end]

orig_blocks = {}
for base, suffix, idx in def_starts:
    if suffix == 'orig':
        orig_blocks[base] = block_lines(idx)

recs = json.load(open('eb_records.json'))

def enclosing_context(fn, old):
    """Find the innermost construct enclosing the mutated line(s) by scanning
    the orig block lines corresponding to hunk ctx_before + old."""
    # locate old lines in orig block
    block = orig_blocks[fn]
    olines = [l.strip() for l in old.split(' | ')]
    # find position: search for the first old line
    pos = -1
    for i in range(len(block)):
        if block[i].strip() == olines[0]:
            # verify subsequent
            if all(j < len(block) and block[j].strip() == o for j, o in zip(range(i, i + len(olines)), olines)):
                pos = i
                break
    if pos < 0:
        return '?', None
    # walk backward tracking bracket balance from pos-1
    bal = 0
    for j in range(pos - 1, max(0, pos - 40), -1):
        l = block[j]
        bal += -l.count('(') + l.count(')') + -l.count('{') + l.count('}') + -l.count('[') + l.count(']')
        # actually balance of stuff ABOVE j: we need open count at line pos. Compute open = sum over lines[ j+1 .. pos-1] + partial.
        # simpler: cumulative opens from start to pos
    # recompute: opens at position pos
    def opens_upto(k):
        s = 0
        for l in block[:k]:
            s += l.count('(') - l.count(')') + l.count('{') - l.count('}') + l.count('[') - l.count(']')
        return s
    target = opens_upto(pos)
    # walk backward; maintain running open count at line j (=opens_upto(j)); find smallest j where opens_upto(j) < target
    for j in range(pos - 1, max(-1, pos - 40), -1):
        if opens_upto(j) < target:
            return 'construct', block[j].strip()
    return 'top', None

out = []
for r in recs:
    for h in r['hunks']:
        kind, ctx = enclosing_context(r['fn'], h['old'])
        out.append({'key': r['key'], 'fn': r['fn'], 'old': h['old'], 'new': h['new'], 'ctx': ctx})

json.dump(out, open('eb_classified.json', 'w'), indent=0)
import collections
c = collections.Counter()
for o in out:
    ctx = o['ctx'] or 'TOP'
    # normalize ctx
    ctx = re.sub(r'\s+', ' ', ctx)[:70]
    c[(o['fn'], ctx)] += 1
print(len(c), 'distinct (fn, enclosing-construct) pairs')
for k, v in c.most_common(60):
    print(v, k)
