import ast, io, json, re, tokenize, collections

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

def src_of(fn,mid):
    s,e=blocks[(fn,mid)]
    txt='\n'.join(lines[s:e])
    # normalize the def name so rename never shows in diffs / offsets align
    return re.sub(r'^def x'+re.escape(fn[1:])+r'__mutmut_(orig|\d+)\(', 'def '+fn[1:]+'(', txt, count=1)

def off_to_rowcol(body,p):
    row=body.count('\n',0,p)+1
    return row, p-(body.rfind('\n',0,p)+1)

def toks_of(fn):
    body=src_of(fn,'orig')
    try:
        return list(tokenize.generate_tokens(io.StringIO(body).readline))
    except Exception:
        return None

def tree_of(fn):
    body=src_of(fn,'orig')
    try:
        return ast.parse(body)
    except Exception:
        return None

def endln(n): return getattr(n,'end_lineno',n.lineno) or n.lineno
def span(n):
    ec=getattr(n,'end_col_offset',None); oc=getattr(n,'col_offset',0)
    return (endln(n)-n.lineno, (ec-oc) if (ec is not None and endln(n)==n.lineno) else 0)

def prefix_suffix(a,b):
    n=min(len(a),len(b)); p=0
    while p<n and a[p]==b[p]: p+=1
    q=0
    while q<(n-p) and a[len(a)-1-q]==b[len(b)-1-q]: q+=1
    return p, a[p:len(a)-q], b[p:len(b)-q]

_cache_t={}; _cache_g={}
def loc(fn,p):
    if fn not in _cache_t:
        _cache_t[fn]=toks_of(fn); _cache_g[fn]=tree_of(fn)
    toks=_cache_t[fn]; tree=_cache_g[fn]
    body=src_of(fn,'orig')
    out={'toktype':None,'toktext':None,'stmt':None,'stmt_src':None,'expr':None,
         'expr_src':None,'kw':None,'near_call':None,'logger':False,'in_return':False,
         'assign':None,'add_target':None,'line_src':None,'rel_line':None,'err':None}
    if toks is None or tree is None:
        out['err']='parse'; return out
    for t in toks:
        a=body.index(t.string, 0) if False else None
        pass
    # compute token offsets
    def tpos():
        # tokenize row/col -> abs offset
        lo=[];acc=0
        for l in body.split('\n'): lo.append(acc); acc+=len(l)+1
        return lambda r,c: (lo[r-1] if 0 <= r-1 < len(lo) else sum(len(x)+1 for x in body.split(chr(10)))+1)+c
    off=tpos()
    for t in toks:
        a=off(*t.start); b=off(*t.end)
        if a<=p<b:
            out['toktype']=tokenize.tok_name[t.type]; out['toktext']=t.string; break
    row,col=off_to_rowcol(body,p)
    out['rel_line']=row
    out['line_src']=body.split('\n')[row-1].strip()[:200]
    parents={}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node): parents[ch]=node
    def hit(n):
        if not hasattr(n,'lineno') or n.lineno is None: return False
        if not (n.lineno<=row<=endln(n)): return False
        if n.lineno==endln(n)==row:
            ec=getattr(n,'end_col_offset',None); oc=getattr(n,'col_offset',0)
            if ec is not None and not (oc<=col<=ec): return False
        return True
    stmts=[n for n in ast.walk(tree) if isinstance(n,ast.stmt) and hit(n)]
    target=None
    for n in stmts:
        if target is None or span(n)<span(target): target=n
    exprs=[n for n in ast.walk(tree) if (isinstance(n,ast.expr) or isinstance(n,ast.keyword)) and hit(n)]
    inexp=None
    for n in exprs:
        if inexp is None or span(n)<span(inexp): inexp=n
    chain=[]; cur=target
    while cur is not None: chain.append(cur); cur=parents.get(cur)
    for a in chain:
        if isinstance(a,ast.Expr) and isinstance(a.value,ast.Call):
            try: nm=ast.unparse(a.value.func)
            except Exception: nm=''
            if 'logger' in nm or nm.startswith('logging') or nm.startswith('log.'): out['logger']=True
        if isinstance(a,ast.Return): out['in_return']=True
        if isinstance(a,ast.Assign):
            try: out['assign']=ast.unparse(a.targets[0])[:60]
            except Exception: pass
        if isinstance(a,ast.AugAssign):
            try: out['assign']='+='+ast.unparse(a.target)[:50]
            except Exception: pass
    if isinstance(inexp,ast.keyword): out['kw']=inexp.arg
    cur=inexp
    while cur is not None:
        if isinstance(cur,ast.Call):
            try: out['near_call']=ast.unparse(cur.func)[:60]
            except Exception: pass
            break
        cur=parents.get(cur)
    if target is not None:
        out['stmt']=type(target).__name__
        try: out['stmt_src']=ast.unparse(target)[:220]
        except Exception: pass
    if inexp is not None:
        out['expr']=type(inexp).__name__
        try: out['expr_src']=ast.unparse(inexp)[:120]
        except Exception: pass
    return out

recs=[]
keys=[l.strip() for l in open('/tmp/wp25/wp44-triage/survivor_keys.txt') if l.strip()]
fnc=collections.Counter()
badp=0
for k in keys:
    fn,num=re.match(r'^backend\.services\.prompts\.(x.+?)__mutmut_(\d+)$',k).groups()
    a=src_of(fn,'orig'); b=src_of(fn,num)
    if len(a)!=len(b): fnc[('lendiff',fn)]+=1
    p,d,i=prefix_suffix(a,b)
    r={'fn':fn,'num':int(num),'key':k,'p':p,'del':d,'ins':i}
    r.update(loc(fn,p))
    recs.append(r)
json.dump(recs,open('/tmp/wp25/wp44-triage/enriched.json','w'))
print('total',len(recs),'parse-err',sum(1 for r in recs if r['err']))
print('no-diff',sum(1 for r in recs if r['del']=='' and r['ins']==''))
print('len-diff funcs', sum(fnc.values()), list(fnc.items())[:5])
print('stmt',collections.Counter(r['stmt'] for r in recs).most_common(12))
print('toktype',collections.Counter(r['toktype'] for r in recs).most_common(10))
print('logger',sum(1 for r in recs if r['logger']),'in_return',sum(1 for r in recs if r['in_return']))
