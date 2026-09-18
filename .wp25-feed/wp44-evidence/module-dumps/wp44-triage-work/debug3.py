import re, textwrap
SEP='ǁ'
MUT='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py'
lines=open(MUT).read().splitlines(keepends=True)
DEF_RE=re.compile(r'^(?P<ind>[ \t]*)(?:async\s+)?def x'+re.escape(SEP)+r'(?P<cls>\w+)'+re.escape(SEP)+r'(?P<fn>\w+)__mutmut_(?P<num>\w+)\(')
starts=[]
for i,l in enumerate(lines):
    m=DEF_RE.match(l)
    if m: starts.append((i,m.group('fn'),m.group('num'),len(m.group('ind'))))
idx=[s for s in starts if s[1]=='get_active_version' and s[2]=='orig'][0]
i,fn,num,ind=idx
print('def line:',lines[i])
# print next 6 lines
for j in range(i+1,i+8): print(j, repr(lines[j][:80]))
