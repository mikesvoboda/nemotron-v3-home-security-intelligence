import ast, json, re, collections, io

SRC='/agents/agent-nemo2/workspace/mutants/backend/services/prompts.py'
lines=open(SRC).read().split('\n')
def_re=re.compile(r'^def (x(.+?))__mutmut_(orig|\d+)\(')
starts=[]
for i,l in enumerate(lines):
    m=def_re.match(l)
    if m: starts.append((i,m.group(1),m.group(3)))
blocks={}
for j,(i,fn,mid) in enumerate(starts):
    end=starts[j+1][0] if j+1<len(starts) else len(lines)
    e=end
    while e>i+1:
        s=lines[e-1].strip()
        if s=='' or s.startswith('mutants_'): e-=1
        else: break
    blocks[(fn,mid)]=(i,e)
def block_text(fn,mid):
    s,e=blocks[(fn,mid)]
    txt='\n'.join(lines[s:e])
    return re.sub(r'^def x'+re.escape(fn[1:])+r'__mutmut_(orig|\d+)\(', 'def '+fn[1:]+'(', txt, count=1), s

trees={}
def tree(fn):
    if fn not in trees:
        t,_=block_text(fn,'orig')
        try: trees[fn]=ast.parse(t)
        except Exception as ex: trees[fn]=ex
    return trees[fn]

recs=json.load(open('/tmp/wp25/wp44-triage/line_diffs.json'))

def endln(n): return getattr(n,'end_lineno',n.lineno) or n.lineno

def point_row(fn, num, body_line, mut_num=None):
    # body_line was 1-based line inside block (def=line1). row in block_text = body_line
    return body_line

SEMANTIC=[]
res=collections.Counter()
for r in recs:
    fn=r['fn']; row=r['body_line']
    t=tree(fn)
    if isinstance(t,Exception):
        r['role']='PARSE-ERR'; res[r['role']]+=1; continue
    parents={}
    for node in ast.walk(t):
        for ch in ast.iter_child_nodes(node): parents[ch]=node
    # find string constants covering row
    def col_hit(n):
        return getattr(n,'lineno',None)==row
    hits=[n for n in ast.walk(t)
          if isinstance(n,ast.Constant) and isinstance(n.value,str) and getattr(n,'lineno',None)==row and endln(n)>=row]
    # choose the one containing the mutated fragment
    d=r['del']; i=r['ins']
    def frag_of(n):
        return n.value if isinstance(n.value,str) else ''
    # pick the constant whose value contains d (or whose value equals an f-string literal part)
    dcore=d.strip(chr(39)+chr(34))
    best=None
    for n in hits:
        v=frag_of(n)
        if d and (d in v or (dcore and dcore in v)): best=n; break
        if (not d) and (i in v if i else False): best=n; break
    if best is None and hits:
        # f-string: mutated piece inside JoinedStr; find JoinedStr at row
        js=[n for n in ast.walk(t) if isinstance(n,ast.JoinedStr) and getattr(n,'lineno',None)==row]
        for n in js:
            lits=[p for p in n.values if isinstance(p,ast.Constant)]
            for p in lits:
                if d and (d in (p.value or '') or (dcore and dcore in (p.value or ''))):
                    best=p; best._in_fstring=True; break
            if best is not None: break
        if best is None and js:
            best=js[0]; best._in_fstring=True
    if best is None:
        r['role']='NO-STR-HIT'; r['sem']=False; res['NO-STR-HIT']+=1
        # may be code mutation (not string) - handled by shape already
        continue
    # walk ancestors of best (and for fstring parts, of parent JoinedStr too)
    node=parents.get(best) if getattr(best,'_in_fstring',False) else best
    chain=[]; cur=node
    while cur is not None: chain.append(cur); cur=parents.get(cur)
    role='prose'
    for idx,a in enumerate(chain):
        if isinstance(a,ast.Expr) and isinstance(a.value,ast.Call):
            try: nm=ast.unparse(a.value.func)
            except Exception: nm=''
            if 'logger' in nm or nm.startswith('log'): role='log'; break
        if isinstance(a,(ast.Compare,)):
            # string compared or membership
            role='semantic-compare'; break
        if isinstance(a,ast.Call):
            try: fnm=ast.unparse(a.func)
            except Exception: fnm=''
            try: args=a.args
            except Exception: args=[]
            if fnm in ('getattr','hasattr','setattr','hasattr'):
                # arg 0 is obj, arg 1 is attr name
                try:
                    a1=ast.unparse(a.args[1]) if len(a.args)>1 else ''
                except Exception: a1=''
                try:
                    if best is a.args[1] or (len(a.args)>1 and ast.unparse(best)==a1):
                        role='semantic-attr'; break
                    if idx and parents.get(a.args[1]) is a and best is a.args[1]:
                        role='semantic-attr'; break
                except Exception: pass
                if len(a.args)>1 and best is a.args[1]: role='semantic-attr'; break
            if fnm.endswith('.get') or fnm.endswith('.pop') or fnm in ('dict.get','dict.pop'):
                # key = args[0] is semantic; default is args[1] NOT semantic
                try:
                    if len(a.args)>0 and (a.args[0] is best or ast.unparse(a.args[0])==ast.unparse(best)):
                        role='semantic-key'; break
                    else:
                        role='default-value'; break
                except Exception: pass
        if isinstance(a,ast.Subscript):
            role='semantic-subscript'; break
        if isinstance(a,ast.Dict):
            # key vs value
            for k,v in zip(a.keys,a.values):
                if k is best: role='semantic-key'; break
                if v is best: role='dict-value'; break
            if role=='semantic-key': break
        if isinstance(a,(ast.Return,)): role='prompt-output'; break
        if isinstance(a,ast.Assign):
            try: tgt=ast.unparse(a.targets[0])
            except Exception: tgt=''
            if 'line' in tgt or 'text' in tgt or 'msg' in tgt or 'prompt' in tgt: role='prompt-text'
        if isinstance(a,(ast.BoolOp,)): pass
    if role=='prose' and getattr(best,'_in_fstring',False): role='fstring-literal'
    # docstring: Expr Constant str first stmt of function
    for a in chain:
        if isinstance(a,ast.FunctionDef):
            body=a.body
            if body and isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Constant) and isinstance(body[0].value.value,str):
                ds=body[0].value
                if best is ds or (ds.lineno<=row<=endln(ds)):
                    role='docstring'; break
            break
    r['role']=role
    res[role]+=1
json.dump(recs,open('/tmp/wp25/wp44-triage/line_diffs.json','w'))
print(res.most_common(20))
