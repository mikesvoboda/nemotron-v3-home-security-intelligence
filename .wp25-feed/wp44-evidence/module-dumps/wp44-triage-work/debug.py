import re
SEP='ǁ'
MUT='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py'
lines=open(MUT).read().splitlines()
names=set()
for l in lines:
    m=re.match(r'^(\s*)(?:async\s+)?def (x'+SEP+r'\S+'+SEP+r'(\w+?)__mutmut_(\w+)\()', l)
    if m: names.add((m.group(2),m.group(3)))
funcs={}
for f,n in names: funcs.setdefault(f,[]).append(n)
for f in sorted(funcs): print(f, sorted(funcs[f], key=lambda x:(x!='orig',x)))
