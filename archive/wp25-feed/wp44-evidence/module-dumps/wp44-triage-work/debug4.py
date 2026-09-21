import re
SEP='ǁ'
MUT='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py'
src=open(MUT).read()
lines=src.splitlines(keepends=True)
DEF_RE=re.compile(r'^(?P<ind>[ \t]*)(?:async\s+)?def x'+re.escape(SEP)+r'(?P<cls>\w+)'+re.escape(SEP)+r'(?P<fn>\w+)__mutmut_(?P<num>\w+)\(')
for i,l in enumerate(lines):
    m=DEF_RE.match(l)
    if m and m.group('fn')=='_calculate_diff' and m.group('num')=='33':
        start=i; ind=len(m.group('ind')); break
for j in range(start, start+40):
    print(j, repr(lines[j][:90]))
