import json, re, difflib, ast, textwrap, sys, bisect

SEP='ǁ'
MUT='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py'
META='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py.meta'

d=json.load(open(META))
surv=sorted(k for k,v in d['exit_code_by_key'].items() if v==0)

src=open(MUT).read()
lines=src.splitlines(keepends=True)

DEF_RE=re.compile(r'^(?P<ind>[ \t]*)(?:async\s+)?def x'+re.escape(SEP)+r'(?P<cls>\w+)'+re.escape(SEP)+r'(?P<fn>\w+)__mutmut_(?P<num>\w+)\(')

starts=[]
def_lines=[]
for i,l in enumerate(lines):
    m=DEF_RE.match(l)
    if m:
        starts.append((i, m.group('fn'), m.group('num'), len(m.group('ind'))))
        def_lines.append(i)
def_lines.sort()

def get_block(idx, indent):
    end=len(lines)
    nxt=bisect.bisect_right(def_lines, idx)
    if nxt<len(def_lines):
        end=def_lines[nxt]
    # also stop at first module-level (indent 0) non-empty line after start
    for j in range(idx+1,end):
        l=lines[j]
        if l.strip() and (len(l)-len(l.lstrip()))==0:
            end=j; break
    return ''.join(lines[idx:end])

def norm_block(text):
    text=text.replace(SEP,'_')
    text=textwrap.dedent(text)
    text=re.sub(r'async\s+def x_\S+?__mutmut_\w+\(', 'async def FN(', text, count=1)
    text=re.sub(r'(?<!async )(?<! )def x_\S+?__mutmut_\w+\(', 'def FN(', text, count=1)
    tree=ast.parse(text)
    fn=tree.body[0]
    all_lines=text.splitlines()
    head_end=fn.body[0].lineno-1
    sig=all_lines[fn.lineno-1:head_end]
    body=[]
    for st in fn.body:
        if isinstance(st,ast.Expr) and isinstance(st.value,ast.Constant) and isinstance(st.value.value,str):
            continue
        s=ast.get_source_segment(text, st)
        body.extend(s.splitlines())
    return sig, body

index={}
for (i,fn,num,ind) in starts:
    index[(fn,num)]=(i,ind)

out={}
errs=0
for key in surv:
    tail=key.rsplit('.',1)[-1]
    m=re.match(r'x'+re.escape(SEP)+r'(?P<cls>\w+)'+re.escape(SEP)+r'(?P<fn>\w+)__mutmut_(?P<num>\d+)$', tail)
    fn,num=m.group('fn'),m.group('num')
    try:
        vs_,vb = norm_block(get_block(*index[(fn,num)],))
        os_,ob = norm_block(get_block(*index[(fn,'orig')],))
    except Exception as e:
        errs+=1; out[key]={'func':fn,'num':int(num),'diff':['ERR '+str(e)]}; continue
    dlines=[dl for dl in difflib.unified_diff(os_+ob, vs_+vb, lineterm='', n=0)
            if dl.startswith(('+','-')) and not dl.startswith(('+++','---'))]
    out[key]={'func':fn,'num':int(num),'diff':dlines}

json.dump(out, open('/tmp/wp25/wp44-triage-work/diffs.json','w'), indent=1)
print("resolved:",len(out),"errors:",errs)
