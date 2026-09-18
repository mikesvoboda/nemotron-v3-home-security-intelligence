import re, json, difflib, collections, sys, ast

SRC = 'mutants/backend/services/prompts.py'
text = open(SRC).read()
lines = text.split('\n')

# index of function block starts
def_re = re.compile(r'^def (x.+?)__mutmut_(orig|\d+)\(')
blocks = {}   # (fn, id) -> (start_line_idx, end_line_idx)
starts = []
for i, l in enumerate(lines):
    m = def_re.match(l)
    if m:
        starts.append((i, m.group(1), m.group(2)))
for j, (i, fn, mid) in enumerate(starts):
    end = starts[j+1][0] if j+1 < len(starts) else len(lines)
    # trim trailing assignment lines (mutants_x...[...] = ...) and blanks
    e = end
    while e > i+1:
        s = lines[e-1].strip()
        if s == '' or s.startswith('mutants_') or s.startswith('@'):
            e -= 1
        else:
            break
    blocks[(fn, mid)] = (i, e)

surv = [l.strip() for l in open('/tmp/wp25/wp44-triage/survivor_keys.txt') if l.strip()]
byfn = collections.defaultdict(list)
for k in surv:
    m = re.match(r'^backend\.services\.prompts\.(.+?)__mutmut_(\d+)$', k)
    byfn[m.group(1)].append((int(m.group(2)), k))

def block_lines(fn, mid):
    s, e = blocks[(fn, mid)]
    return lines[s:e]

out = []
missing = []
for fn, items in sorted(byfn.items()):
    if (fn, 'orig') not in blocks:
        missing.append(fn); continue
    ob = block_lines(fn, 'orig')
    for num, key in sorted(items):
        if (fn, str(num)) not in blocks:
            missing.append(key); continue
        mb = block_lines(fn, str(num))
        sm = difflib.SequenceMatcher(None, ob, mb)
        hunks = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal': continue
            ol = '\n'.join(ob[i1:i2]); ml = '\n'.join(mb[j1:j2])
            hunks.append((tag, ol, ml))
        out.append({'fn': fn, 'num': num, 'key': key, 'hunks': hunks})

json.dump(out, open('/tmp/wp25/wp44-triage/raw_diffs.json','w'))
print('survivors', len(surv), 'diffed', len(out), 'missing', len(missing), missing[:10])
# how many have empty hunks (no textual diff = suspicious)
print('no-text-diff:', sum(1 for o in out if not o['hunks']))
# distribution of hunk sizes
print('hunk count hist', collections.Counter(len(o['hunks']) for o in out).most_common(8))
