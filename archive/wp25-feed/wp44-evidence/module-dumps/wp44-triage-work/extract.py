import json, re, difflib, ast, io, sys

MUT='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py'
ORIG='/agents/agent-nemo2/workspace/backend/services/prompt_version_service.py'
META='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py.meta'

d=json.load(open(META))
surv=sorted(k for k,v in d['exit_code_by_key'].items() if v==0)
print(f"survivors={len(surv)}", file=sys.stderr)

src=open(MUT).read()
lines=src.splitlines(keepends=True)

# find each "def x<U+1C1>...<U+1C1>name__mutmut_N(" start line; block ends at next def line at same indent or module-level
SEP='ǁ'
starts=[]  # (idx, full_name, indent)
for i,l in enumerate(lines):
    m=re.match(r'^(\s*)(?:async\s+)?def (x'+SEP+r'\S+'+SEP+r'(\w+?)__mutmut_(\w+)\()', l)
    if m:
        starts.append((i, m.group(2), m.group(3), len(m.group(1))))

def block_end(start_idx, indent):
    for j in range(start_idx+1, len(lines)):
        l=lines[j]
        if l.strip() and (len(l)-len(l.lstrip()))<=indent and not l.startswith((' ','\t')) if indent==0 else (l.strip() and (len(l)-len(l.lstrip()))<=indent and re.match(r'\s*(async\s+)?def\s', l) or (l.strip() and (len(l)-len(l.lstrip()))<=indent)):
            # crude: end when a line at <= indent that is not inside (part of assignment dicts etc.)
            ind=len(l)-len(l.lstrip())
            if ind<=indent:
                return j
    return len(lines)

def get_block(idx, indent):
    end=len(lines)
    for j in range(idx+1,len(lines)):
        l=lines[j]
        if not l.strip(): continue
        ind=len(l)-len(l.lstrip())
        if ind<=indent:
            end=j; break
    return lines[idx:end]

def body_norm(block_lines):
    """strip def line + docstring, dedent, return code lines"""
    text=''.join(block_lines)
    try:
        tree=ast.parse(text.replace('ǁ','_'))
    except SyntaxError:
        return None
    fn=tree.body[0]
    body=fn.body
    # drop docstring
    if body and isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Constant) and isinstance(body[0].value.value,str):
        body=body[1:]
    out=[]
    for st in body:
        seg=ast.get_source_segment(text.replace('ǁ','_'),st)
        out.extend(seg.splitlines())
    return out

results={}
for key in surv:
    tail=key.rsplit('.',1)[-1]
    m=re.match(r'x'+SEP+r'(\w+)'+SEP+r'(\w+)__mutmut_(\d+)$', tail)
    cls,func,num=m.group(1),m.group(2),m.group(3)
    # locate variant block and orig block
    var_idx=orig_idx=None; indent=4
    for (i,f2,n2,ind) in starts:
        if f2==func and n2==num: var_idx=i; indent=ind
        if f2==func and n2=='orig': orig_idx=i
    vblk=get_block(var_idx,indent); oblk=get_block(orig_idx,indent)
    vb=body_norm(vblk); ob=body_norm(oblk)
    diff=[dl for dl in difflib.unified_diff(ob or [], vb or [], lineterm='', n=1) if dl.startswith(('+','-')) and not dl.startswith(('+++','---'))]
    results[key]={'func':func,'num':num,'diff':diff}

json.dump(results, open('/tmp/wp25/wp44-triage-work/diffs.json','w'), indent=1)
print("wrote diffs", file=sys.stderr)
