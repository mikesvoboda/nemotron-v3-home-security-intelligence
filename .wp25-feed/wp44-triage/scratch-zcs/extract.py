import json, re, difflib, collections

text = open('/agents/agent-nemo2/workspace/mutants/backend/services/zone_crossing_service.py').read()
lines = text.splitlines(keepends=True)

# find def blocks: name pattern x<...>__mutmut_(orig|N)
defpat = re.compile(r'^(\s*)(?:async )?def (x.*?__mutmut_(orig|\d+))\(')
blocks = {}  # (qualname, variant) -> list of lines
cur = None
for i, ln in enumerate(lines):
    m = defpat.match(ln)
    if m:
        indent, name = m.group(1), m.group(2)
        # split name into qual + variant
        mm = re.match(r'(x.*?__mutmut)_(orig|\d+)', name)
        qual, var = mm.group(1), mm.group(2)
        cur = (qual, var)
        blocks[cur] = [ln]
    else:
        if cur is not None:
            ind, nm = blocks[cur][0][:len(blocks[cur][0].lstrip())], None
            base_indent = len(blocks[cur][0]) - len(blocks[cur][0].lstrip())
            # end block when a non-blank line has indent <= base_indent and isn't continuation
            if ln.strip() and (len(ln) - len(ln.lstrip())) <= base_indent:
                cur = None
            else:
                blocks[cur].append(ln)

meta = json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/zone_crossing_service.py.meta'))
surv = [k for k, v in meta['exit_code_by_key'].items() if v == 0]

out = {}
missing = []
for k in surv:
    # key: backend.services.zone_crossing_service.<qual>__mutmut_N
    tail = k.rsplit('.', 1)[1]
    mm = re.match(r'(x.*?__mutmut)_(\d+)', tail)
    qual, var = mm.group(1), mm.group(2)
    if (qual, var) not in blocks or (qual, 'orig') not in blocks:
        missing.append(k); continue
    orig = blocks[(qual, 'orig')]
    mut = blocks[(qual, var)]
    # trim common leading (def line differs only in name); diff rest
    a = ''.join(orig[1:]); b = ''.join(mut[1:])
    if a == b:
        # sometimes mutation is in the def line (default args) — include it normalized
        a = orig[0].replace('__mutmut_orig','') + a
        b = mut[0].replace(f'__mutmut_{var}','') + b
    d = list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm='', n=1))
    d = [dl for dl in d if not dl.startswith(('---','+++','@@'))]
    fn = qual.replace('xǁ','').replace('ǁ','.')
    out.setdefault(fn, []).append({'key': k, 'diff': '\n'.join(d)})

json.dump(out, open('/tmp/wp25/wp44-triage/scratch-zcs/diffs.json','w'), indent=1)
print('survivors', len(surv), 'extracted', sum(len(v) for v in out.values()), 'missing', len(missing))
if missing: print('MISSING:', missing[:10])
