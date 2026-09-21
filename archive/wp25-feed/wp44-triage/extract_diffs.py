import json, re, difflib, collections, pickle

src = open('/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py').read().splitlines()

# find all def lines matching x<fn>__mutmut_N or x<fn>__mutmut_orig (module-level or class-level indented)
def_re = re.compile(r'^(\s*)def (x.+?__mutmut(?:_orig|_(\d+)))\(')
defs = []  # (indent, name, variant_num_or_None, lineno)
for i,l in enumerate(src):
    m = def_re.match(l)
    if m:
        indent = len(m.group(1))
        name = m.group(2)
        num = m.group(3)
        defs.append((indent, name, num, i))

# Determine body end for each def: the line index before the next def/class at same-or-less indent that starts a new top-level construct.
# Simpler: bodies are separated by the next def line at same indent.
blocks = {}
for idx,(indent,name,num,i) in enumerate(defs):
    # find end: next def at same indent
    end = len(src)
    for j in range(idx+1, len(defs)):
        if defs[j][0] <= indent:
            end = defs[j][3]
            break
    # strip trailing decorator/back lines of next block: decorators appear before def; include them out.
    body = src[i+1:end]
    # remove trailing lines that belong to next def's decorators/blank/comment
    # find last line of actual body: cut trailing lines starting with '@' or blank or comment-only at the end
    while body and (body[-1].strip()=='' or body[-1].strip().startswith('@') or (body[-1].strip().startswith('#') and not body[-1].strip().startswith('# type'))):
        body.pop()
    # also cut trailing comment lines like "# ... mutmut"? keep simple
    # base fn name
    m2 = re.match(r'x(.+?)__mutmut', name)
    base = m2.group(1)
    if num is None: continue
    blocks[(base, int(num))] = (indent, body)

# originals: use __mutmut_orig body per base
orig_body = {}
for idx,(indent,name,num,i) in enumerate(defs):
    if num is None:
        m2 = re.match(r'x(.+?)__mutmut', name)
        base = m2.group(1)
        end = len(src)
        for j in range(idx+1, len(defs)):
            if defs[j][0] <= indent:
                end = defs[j][3]
                break
        body = src[i+1:end]
        while body and (body[-1].strip()=='' or body[-1].strip().startswith('@')):
            body.pop()
        orig_body[base] = body

print('bases:', {b: len(v) for b,v in orig_body.items()})
print('variants found:', collections.Counter(b for b,_ in blocks))

out = {}
for (base,num), (indent, body) in blocks.items():
    ob = orig_body[base]
    sm = difflib.SequenceMatcher(None, ob, body)
    changes = []
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=='equal': continue
        old = [x.strip() for x in ob[i1:i2]]
        new = [x.strip() for x in body[j1:j2]]
        changes.append((old,new))
    key_base = 'backend.services.container_discovery.x'+base
    out[(base,num)] = changes

pickle.dump(out, open('/tmp/wp25/wp44-triage/blocks.pkl','wb'))

# summarize changed line pairs
pat = collections.Counter()
for (base,num), changes in out.items():
    if len(changes)==1:
        old,new = changes[0]
        pat[(base, tuple(old), tuple(new))]+=1
    else:
        pat[(base,'MULTI', str(len(changes)))]+=1

print('total variants with diffs:', len(out))
print('unique (base,old,new) patterns:', len(pat))
