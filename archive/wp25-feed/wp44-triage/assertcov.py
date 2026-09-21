import ast, json, collections, os

ROOT='/agents/agent-nemo2/workspace/'
per=json.load(open('/tmp/wp25/wp44-triage/per_fn_tests.json'))

def collect(f):
    s=set()
    for n in ast.walk(f):
        if isinstance(n,ast.Assert):
            for c in ast.walk(n.test):
                if isinstance(c,ast.Constant) and isinstance(c.value,str):
                    s.add(c.value)
    return s

cache={}
def qual_of(path):
    if path in cache: return cache[path]
    full=ROOT+path
    if not os.path.exists(full):
        cache[path]={}; return cache[path]
    tree=ast.parse(open(full).read())
    qual={}
    for cls in [n for n in ast.walk(tree) if isinstance(n,ast.ClassDef)]:
        for m in [x for x in cls.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]:
            qual[cls.name+'::'+m.name]=m
    for fn in [n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]:
        qual.setdefault(fn.name,fn)
    cache[path]=qual
    return qual

fn_asserts={}
for fn, tests in per.items():
    acc=set()
    for t in tests:
        path,_,name=t.partition('::')
        qual=qual_of(path)
        parts=name.split('::')
        key='::'.join(parts[-2:]) if len(parts)>=2 else name
        node=qual.get(key) or qual.get(parts[-1])
        if node is None: continue
        acc|=collect(node)
    fn_asserts[fn]=acc
json.dump({k:sorted(v) for k,v in fn_asserts.items()}, open('/tmp/wp25/wp44-triage/fn_asserts.json','w'))
print('funcs with zero asserted strings:', [k for k,v in fn_asserts.items() if not v])
print({k:len(v) for k,v in list(fn_asserts.items())[:10]})
