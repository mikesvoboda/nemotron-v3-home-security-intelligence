import re, json, difflib, sys

SRC = open('/agents/agent-nemo2/workspace/mutants/backend/services/health_monitor.py').read()
lines = SRC.splitlines(keepends=True)

# find all def lines with their line numbers
defs = []  # (start_idx, qual, name, is_orig)
pat = re.compile(r'^    (?:async )?def (xǁ[^ǁ]*ǁ[^_]+(?:__[a-z]+)?__mutmut_[^\(]*|[^\(]+)\(')
# simpler: match any def
dpat = re.compile(r'^(\s*)(?:async\s+)?def\s+([^\s\(]+)\s*\(')
for i, l in enumerate(lines):
    m = dpat.match(l)
    if m:
        defs.append((i, m.group(2), m.group(1)))

# build blocks: from def line to next def line at same-or-lesser indent that starts a new def (or end)
blocks = {}
for idx, (i, name, indent) in enumerate(defs):
    # find end: next def whose indent <= this indent AND is a class-level def... actually variants are siblings at same indent.
    end = len(lines)
    for j in range(idx+1, len(defs)):
        jname, jindent = defs[j][1], defs[j][2]
        if len(jindent) <= len(indent):
            end = defs[j][0]
            break
    blocks[name] = (i, end)

# load survivors
with open('/agents/agent-nemo2/workspace/mutants/backend/services/health_monitor.py.meta') as f:
    data = json.load(f)
ebk = data['exit_code_by_key']
surv_keys = [k for k,v in ebk.items() if v == 0]

results = {}
unmatched = []
for key in surv_keys:
    m = re.match(r'backend\.services\.health_monitor\.(.+)__mutmut_(\d+)$', key)
    fnpart, n = m.group(1), m.group(2)
    vname = f"{fnpart}__mutmut_{n}"
    oname = f"{fnpart}__mutmut_orig"
    if vname not in blocks:
        unmatched.append(vname); continue
    vs, ve = blocks[vname]; os_, oe = blocks[oname]
    vl = lines[vs:ve]; ol = lines[os_:oe]
    # also strip the def line (names differ)
    vl = vl[1:]; ol = ol[1:]
    # align: skip def-line already; now diff bodies ignoring blank trailing
    d = list(difflib.unified_diff(ol, vl, n=0, lineterm=''))
    # collect only +/- lines, excluding @@
    changes = [x for x in d if (x.startswith('+') or x.startswith('-')) and not x.startswith('+++') and not x.startswith('---')]
    results[key] = changes

print("unmatched:", unmatched, file=sys.stderr)
out = {k: v for k, v in results.items()}
json.dump(out, open('/tmp/wp25/wp44-triage/_hm_diffs.json','w'), indent=1)
print("extracted", len(results), "diffs", file=sys.stderr)
