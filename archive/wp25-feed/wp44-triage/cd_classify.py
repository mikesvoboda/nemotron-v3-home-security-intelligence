import ast, json, difflib, collections, re

path='/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py'
src=open(path).read()
tree=ast.parse(src)
funcs={}
def walk(node):
    for n in ast.iter_child_nodes(node):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            funcs[n.name]=ast.get_source_segment(src,n)
        walk(n)
walk(tree)

meta=json.load(open(path+'.meta'))
ebd=meta['exit_code_by_key']
NOISE = {'),', ')', '}', '},'}

def diff_of(fn):
    base,num=fn.rsplit('__mutmut_',1)
    a=funcs[base+'__mutmut_orig'].splitlines()
    b=funcs[fn].splitlines()
    a[0]=a[0].replace('__mutmut_orig','')
    b[0]=b[0].replace('__mutmut_'+num,'')
    return [l for l in difflib.unified_diff(a,b,lineterm='',n=0)
            if l[:1] in '+-' and l[:3] not in ('---','+++')]

def classify_pair(rm, ad):
    old=rm[0] if rm else ''
    new=ad[0] if ad else ''
    m=re.match(r'"([^"]+)": ServiceConfig\($', old)
    if m:
        m2=re.match(r'"([^"]+)": ServiceConfig\($', new)
        if m2:
            o,n=m.group(1),m2.group(1)
            if n=='XX'+o+'XX': return ('dict-key','XXwrap')
            if n.upper()==o.upper(): return ('dict-key','case')
            return ('dict-key','other')
    m=re.match(r'^(\w+)=(.*),$', old)
    if m:
        k,v1=m.group(1),m.group(2)
        if not new: return (k,'removed')
        m2=re.match(r'^(\w+)=(.*),$', new)
        if m2 and m2.group(1)==k:
            v2=m2.group(2)
            if v2=='None': return (k,'to_None')
            if v2=='': return (k,'argdrop')
            if v2=='XX'+v1+'XX': return (k,'XXwrap')
            if v1.startswith('"') and v2.strip('"').upper()==v1.strip('"').upper(): return (k,'case')
            try:
                if float(v2)==float(v1)+1: return (k,'plus1')
            except ValueError: pass
            return (k,'other:'+v2)
        return (k,'otherline')
    m=re.match(r'^(\w+) = settings\.(\w+) if settings else (\S+)$', old)
    if m:
        name=m.group(1)
        if 'and False' in new: return ('ternary:'+name,'forced_default')
        if 'or True' in new: return ('ternary:'+name,'forced_settings')
        if new.endswith('= None'): return ('ternary:'+name,'whole_None')
        try:
            n=re.search(r'else (\S+)$',new).group(1)
            if float(n)==float(m.group(3))+1: return ('ternary:'+name,'default_plus1')
        except Exception: pass
        return ('ternary:'+name,'other')
    return ('line','other')

def classify(fn):
    d=diff_of(fn)
    rm=[l[1:].strip() for l in d if l[0]=='-' and l[1:].strip() not in NOISE]
    ad=[l[1:].strip() for l in d if l[0]=='+' and l[1:].strip() not in NOISE]
    return classify_pair(rm,ad)

out=collections.Counter(); members=collections.defaultdict(list)
for k,v in ebd.items():
    if v!=0: continue
    fn=k.split('.')[-1]
    fnm=fn.rsplit('__mutmut_',1)[0]
    fnm=fnm.replace('xǁContainerDiscoveryServiceǁ','CDService.').replace('x_','')
    tgt,kind_=classify(fn)
    key=(fnm,tgt,kind_)
    out[key]+=1; members[key].append(k)

for (fnm,tgt,kind_),c in sorted(out.items(), key=lambda x:(-x[1],x[0],x[1])):
    print(f"{c:4d}  {fnm:40s} {tgt:36s} {kind_}")
print('TOTAL', sum(out.values()))
json.dump({a+'||'+b+'||'+c: v for (a,b,c),v in members.items()},
          open('/tmp/wp25/wp44-triage/cd_members.json','w'), indent=0)
