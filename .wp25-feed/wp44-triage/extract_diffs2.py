import json, re, difflib, collections, pickle

src = open('/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py').read().splitlines()

def_re = re.compile(r'^(\s*)(?:async )?def (x.+?__mutmut(?:_orig|_(\d+)))\(')
defs = []
for i,l in enumerate(src):
    m = def_re.match(l)
    if m:
        defs.append((len(m.group(1)), m.group(2), m.group(3), i))

blocks = {}
orig_body = {}
for idx,(indent,name,num,i) in enumerate(defs):
    end = len(src)
    for j in range(idx+1, len(defs)):
        if defs[j][0] <= indent:
            end = defs[j][3]
            break
    body = src[i+1:end]
    while body and (body[-1].strip()=='' or body[-1].strip().startswith('@')):
        body.pop()
    base = re.match(r'x(.+?)__mutmut', name).group(1)
    if num is None:
        orig_body[base] = body
    else:
        blocks[(base,int(num))] = body

out = {}
for (base,num), body in blocks.items():
    ob = orig_body.get(base)
    if ob is None:
        continue
    sm = difflib.SequenceMatcher(None, ob, body)
    changes = []
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=='equal': continue
        old = ' | '.join(x.strip() for x in ob[i1:i2])
        new = ' | '.join(x.strip() for x in body[j1:j2])
        changes.append((old,new))
    out[(base,num)] = changes

json.dump({f'{b}__mutmut_{n}': c for (b,n),c in out.items()},
          open('/tmp/wp25/wp44-triage/diffs.json','w'), indent=1)
print('variants parsed:', len(out))
print('per base:', collections.Counter(b for b,_ in out))
