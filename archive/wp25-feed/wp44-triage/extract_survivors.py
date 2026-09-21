import re, json, difflib

MUT='/agents/agent-nemo2/workspace/mutants/backend/services/health_event_emitter.py'
META='/agents/agent-nemo2/workspace/mutants/backend/services/health_event_emitter.py.meta'

src = open(MUT).read().splitlines()
def_re = re.compile(r'^(\s*)(?:async )?def (.*__mutmut_(?:orig|\d+))\(')
blocks = {}
i, n = 0, len(src)
while i < n:
    m = def_re.match(src[i])
    if m:
        indent, name = m.group(1), m.group(2)
        # consume signature lines until paren depth 0 and line ends with ':'
        j = i
        depth = 0
        while True:
            depth += src[j].count('(') - src[j].count(')')
            if depth == 0 and src[j].rstrip().endswith(':'):
                break
            j += 1
        j += 1  # first body line
        body = src[i:j]
        # body: keep lines while blank or deeper indent
        while j < n:
            line = src[j]
            if line.strip() == '':
                # include only if a deeper-indented line follows
                k = j
                while k < n and src[k].strip() == '': k += 1
                if k < n and src[k].startswith(' ' * (len(indent) + 1)):
                    body.extend(src[j:k]); j = k; continue
                break
            if not line.startswith(' ' * (len(indent) + 1)):
                break
            body.append(line); j += 1
        blocks[name] = body
        i = j
    else:
        i += 1

meta = json.load(open(META))
surv = sorted(k for k, v in meta['exit_code_by_key'].items() if v == 0)

def norm(lines):
    out=[]
    for l in lines:
        s=l.strip()
        if not s: continue
        if s.startswith('"""') or s=='"""': continue  # drop docstrings crudely
        out.append(s)
    return out

for key in surv:
    tail = key.split('.')[-1]
    fn, sep, num = tail.rpartition('__mutmut_')
    fn = fn + '__mutmut_'
    orig_name, var_name = fn + 'orig', fn + num
    print('='*100)
    print('KEY:', key)
    orig, var = blocks.get(orig_name), blocks.get(var_name)
    if orig is None or var is None:
        print('  MISSING:', orig_name, orig is not None, '|', var_name, var is not None)
        continue
    # drop def-name line differences: compare body only, but keep signature lines
    o = norm(orig[1:]); v = norm(var[1:])
    d = list(difflib.unified_diff(o, v, lineterm='', n=1))
    if not d:
        print('  IDENTICAL body')
    else:
        for line in d:
            if line.startswith('---') or line.startswith('+++'): continue
            print('  ' + line)
