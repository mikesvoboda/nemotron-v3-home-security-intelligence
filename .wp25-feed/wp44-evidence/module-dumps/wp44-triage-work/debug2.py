import json, re
META='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py.meta'
d=json.load(open(META))
surv=sorted(k for k,v in d['exit_code_by_key'].items() if v==0)
tail=surv[0].rsplit('.',1)[-1]
print('tail codepoints:', [hex(ord(c)) for c in tail[:4]], repr(tail))
MUT='/agents/agent-nemo2/workspace/mutants/backend/services/prompt_version_service.py'
lines=open(MUT).read().splitlines()
hit=[l for l in lines if tail+'(' in l or ('def '+tail) in l]
print('exact key tail as def name found in file:', bool(hit))
# try building regex from key's own separator
sep=tail[1]
print('key sep codepoint:', hex(ord(sep)))
m=re.match(r'x'+re.escape(sep)+r'(\w+)'+re.escape(sep)+r'(\w+)__mutmut_(\d+)$', tail)
print('key regex match:', m.groups() if m else None)
