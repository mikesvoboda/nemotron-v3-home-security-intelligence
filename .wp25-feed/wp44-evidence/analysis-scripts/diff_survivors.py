import json, re, difflib

mut_path = '/agents/agent-nemo2/workspace/mutants/backend/services/enrichment_client.py'
text = open(mut_path).read()

pat = re.compile(r'^[ \t]*(?:async )?def (x[ǁ][A-Za-z_]+[ǁ][A-Za-z_]+__mutmut_(?:orig|\d+))\(', re.M)
matches = list(pat.finditer(text))

end_pat = re.compile(r'^(\S| *@_mutmut_mutated| *(?:async )?def (?!x[ǁ]))')
blocks = {}
for i, m in enumerate(matches):
    start = m.start()
    end = matches[i+1].start() if i+1 < len(matches) else len(text)
    lines = text[start:end].split('\n')
    cut = len(lines)
    for j, l in enumerate(lines[1:], 1):
        if end_pat.match(l):
            cut = j
            break
    blocks[m.group(1)] = '\n'.join(lines[:cut])

meta = json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/enrichment_client.py.meta'))
surv = sorted(k for k, v in meta['exit_code_by_key'].items() if v == 0)

out = []
for k in surv:
    vname = k.split('.')[-1]
    orig = re.sub(r'__mutmut_\d+$', '__mutmut_orig', vname)
    vb, ob = blocks.get(vname), blocks.get(orig)
    if not vb or not ob:
        out.append((k, 'MISSING BLOCK')); continue
    d = [l for l in difflib.unified_diff(ob.splitlines()[1:], vb.splitlines()[1:], lineterm='', n=0)
         if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]
    out.append((k, '\n'.join(d)))

with open('/tmp/wp25/survivor_diffs.txt', 'w') as f:
    for k, d in out:
        f.write('=== %s\n%s\n' % (k, d))
print('wrote', len(out), 'missing', sum(1 for _, d in out if d == 'MISSING BLOCK'))
