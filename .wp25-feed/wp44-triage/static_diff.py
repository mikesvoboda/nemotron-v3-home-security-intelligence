import ast, difflib, json, re

src = open('mutants/backend/services/transcoding.py').read()
tree = ast.parse(src)
lines = src.splitlines(keepends=True)
funcs = {}
for node in ast.walk(tree):
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and '__mutmut' in node.name:
        m = re.match(r'^(?P<base>.+)__mutmut_(?P<idx>orig|\d+)$', node.name)
        if m:
            funcs[(m.group('base'), m.group('idx'))] = ''.join(lines[node.lineno-1:node.end_lineno])

meta = json.load(open('mutants/backend/services/transcoding.py.meta'))
surv_keys = [k for k,v in meta['exit_code_by_key'].items() if v == 0]

def dedent(seg):
    ls = seg.splitlines()
    ind = min(len(l)-len(l.lstrip()) for l in ls if l.strip())
    return '\n'.join(l[ind:] if l.strip() else '' for l in ls)

out = open('/tmp/wp25/wp44-triage/static_diffs.txt','w')
missing=[]
for key in sorted(surv_keys):
    m = re.match(r'^backend\.services\.transcoding\.(?P<base>.+)__mutmut_(?P<idx>\d+)$', key)
    base, idx = m.group('base'), m.group('idx')
    vseg, oseg = funcs.get((base,idx)), funcs.get((base,'orig'))
    if vseg is None or oseg is None:
        missing.append(key); continue
    vn = dedent(vseg).replace(f'{base}__mutmut_{idx}', f'{base}__mutmut_XXORIG')
    on = dedent(oseg).replace(f'{base}__mutmut_orig', f'{base}__mutmut_XXORIG')
    d = [l for l in difflib.unified_diff(on.splitlines(), vn.splitlines(), lineterm='', n=0)
         if (l.startswith('+') or l.startswith('-')) and not l.startswith(('+++','---'))]
    out.write(f'KEY\t{key}\n')
    for l in d:
        out.write(l + '\n')
    out.write('\n')
out.close()
print('done, missing:', missing)
