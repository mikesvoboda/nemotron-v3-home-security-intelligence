import json, re, difflib, ast, textwrap, sys

SEP='ǁ'
MUT='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py'
META='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py.meta'

d=json.load(open(META))
surv=sorted(k for k,v in d['exit_code_by_key'].items() if v==0)

src=open(MUT).read()
lines=src.splitlines(keepends=True)

DEF_RE=re.compile(r'^(?P<ind>[ \t]*)(?:async\s+)?def x'+re.escape(SEP)+r'(?P<cls>\w+)'+re.escape(SEP)+r'(?P<fn>\w+)__mutmut_(?P<num>\w+)\(')

starts=[]
for i,l in enumerate(lines):
    m=DEF_RE.match(l)
    if m:
        starts.append((i, m.group('fn'), m.group('num'), len(m.group('ind')), bool(re.match(r'^\s*async\s', l))))

def get_block(idx, indent):
    end=len(lines)
    for j in range(idx+1,len(lines)):
        l=lines[j]
        if not l.strip(): continue
        ind=len(l)-len(l.lstrip())
        if ind<=indent:
            end=j; break
    return ''.join(lines[idx:end])

def norm_block(text, async_expected):
    text=text.replace(SEP,'_')
    text=textwrap.dedent(text)
    # normalize def name -> 'def FN('
    text=re.sub(r'(?:async\s+)?def \S+?__mutmut_\w+\(', 'XXX_DEF(', text, count=1)
    text=re.sub(r'async XXX_DEF\(','XXX_ADEF(',text,count=1)
    text=text.replace('XXX_DEF(','def FN(',1).replace('XXX_ADEF(','async def FN(',1)
    tree=ast.parse(text)
    fn=tree.body[0]
    # signature line(s): reconstruct from source segment of fn minus body
    seg=ast.get_source_segment(text, fn)
    sig_end=fn.body[0].lineno - fn.lineno
    seg_lines=seg.splitlines()
    # def line(s) = lines until body starts (dedent relative)
    # find where body starts: first stmt lineno
    body_start_off=fn.body[0].lineno-fn.lineno
    sig='\n'.join(seg_lines[:body_start_off])
    body=[]
    for st in fn.body:
        if isinstance(st,ast.Expr) and isinstance(st.value,ast.Constant) and isinstance(st.value.value,str):
            continue
        s=ast.get_source_segment(text, st)
        body.extend(s.splitlines())
    return sig, body

def variant_text(idx, indent, num):
    blk=get_block(idx,indent)
    return norm_block(blk, num)

index={}
for (i,fn,num,ind,is_async) in starts:
    index[(fn,num)]=(i,ind)

out={}
unresolved=[]
for key in surv:
    tail=key.rsplit('.',1)[-1]
    m=re.match(r'x'+re.escape(SEP)+r'(?P<cls>\w+)'+re.escape(SEP)+r'(?P<fn>\w+)__mutmut_(?P<num>\d+)$', tail)
    fn,num=m.group('fn'),m.group('num')
    v=index[(fn,num)]
    o=index.get((fn,'orig'))
    if not v or not o:
        unresolved.append(key); continue
    vs, vb = variant_text(*v, num)
    os_, ob = variant_text(*o, 'orig')
    dlines=[dl for dl in difflib.unified_diff(([l for l in os_.splitlines()]+ob), ([l for l in vs.splitlines()]+vb), lineterm='', n=0)
            if dl.startswith(('+','-')) and not dl.startswith(('+++','---'))]
    out[key]={'func':fn,'num':int(num),'diff':dlines}

json.dump(out, open('/tmp/wp25/wp44-triage-work/diffs.json','w'), indent=1)
print("resolved:",len(out),"unresolved:",len(unresolved), file=sys.stderr)
if unresolved: print(unresolved[:5], file=sys.stderr)
