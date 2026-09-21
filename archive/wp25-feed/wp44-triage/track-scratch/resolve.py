"""Resolve survivor mutant keys to real diffs for track_service.py.

The live run's expanded mutants file (with __mutmut_N copies) is not on disk;
mutmut 3.8 mutates in place. We regenerate the full (unfiltered) mutation list
with mutmut's own visitor and per-function deep_replace, then pin survivor
indices with the constraint: indices strictly increase with generation order
within a function (numbering = filter of generation order).
"""
import os, json, difflib, collections

WS = '/agents/agent-nemo2/workspace'
os.chdir(WS)
import mutmut.configuration as mc
mc.config()
os.chdir('/tmp/wp25/wp44-triage/track-scratch')

import libcst as cst
from mutmut.mutation.file_mutation import create_mutations, group_by_top_level_node
from mutmut.mutation.trampoline_templates import mangle_function_name

code = open(f'{WS}/backend/services/track_service.py').read()
module, mutations, _, _ = create_mutations('backend/services/track_service.py', code, None, set())
groups = group_by_top_level_node(mutations)

def code_of(func):
    return cst.Module([func]).code.strip()

def norm(lines):
    return [l.rstrip() for l in lines if l.strip() != '']

# ordered per-function generation diffs
func_diffs = {}   # mangled -> list[(gen_idx, diff_lines)]
def walk_funcs():
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef):
            yield None, stmt
        elif isinstance(stmt, cst.ClassDef) and isinstance(stmt.body, cst.IndentedBlock):
            for meth in stmt.body.body:
                if isinstance(meth, cst.FunctionDef):
                    yield stmt.name.value, meth

for cls, func in walk_funcs():
    mname = mangle_function_name(name=func.name.value, class_name=cls)
    fmut = groups.get(func)
    if not fmut:
        continue
    orig = code_of(func).split('\n')
    lst = []
    for i, mu in enumerate(fmut, 1):
        mutated_func = func.deep_replace(mu.original_node, mu.mutated_node)
        mut = code_of(mutated_func).split('\n')
        d = [l for l in difflib.unified_diff(orig, mut, lineterm='', n=1)
             if l.startswith(('+', '-')) and not l.startswith(('---', '+++'))]
        lst.append((i, d))
    func_diffs[mname] = lst

meta = json.load(open(f'{WS}/mutants/backend/services/track_service.py.meta'))
ebk = meta['exit_code_by_key']

def fn_idx(key):
    tail = key.rpartition('.')[2]
    base, idx = tail.rsplit('__mutmut_', 1)
    return base, int(idx)

by_fn = collections.defaultdict(list)
for k, v in ebk.items():
    f, i = fn_idx(k)
    by_fn[f].append((i, v, k))

resolved = {}
report = []
for f, entries in by_fn.items():
    entries.sort()   # meta index asc
    lst = func_diffs[f]
    cands = [g for g, d in lst if norm(d)]   # gen idxs with a real diff
    lo = 0
    ok = True
    for i, v, k in entries:
        # candidate gen idx must be >= previous chosen; pin where index aligns
        pick = None
        for j in range(lo, len(cands)):
            # heuristic strength: if this is the last unresolved alignment freedom, pick first
            pick = cands[j]
            break
        resolved[k] = pick
        lo = cands.index(pick) + 1 if pick is not None else lo
    report.append((f, len(entries), len(cands), len(lst)))

json.dump({k: func_diffs_next(v) if False else None for k, v in resolved.items()}, open('/dev/null', 'w')) if False else None

# For functions with full counts, meta index == gen index directly.
# Only get_tracks_by_camera (83/87) and mark_track_lost (37/39) need alignment.
out = {}
for f, entries in by_fn.items():
    n_meta = len(entries)
    lst = func_diffs[f]
    full = {i: d for i, d in lst}
    if n_meta == len(lst):
        for i, v, k in entries:
            out[k] = {'v': v, 'diff': full.get(i, []), 'gen': i}
    else:
        cands = [i for i, d in lst if norm(d)]
        if len(cands) == n_meta:
            # strictly-increasing bijection between sorted meta indices and
            # sorted gen indices that produce a real diff -> forced alignment
            fullx = dict(lst)
            for (i, v, k), g in zip(entries, cands):
                out[k] = {'v': v, 'diff': fullx[g], 'gen': g}
        else:
            out[f'PENDING::{f}'] = {'v': None, 'diff': [], 'gen': None,
                                    'entries': [(i, v, k) for i, v, k in entries],
                                    'cands': cands}
json.dump(out, open('resolved_direct.json', 'w'))
nz = sum(1 for k, e in out.items() if not k.startswith('PENDING') and norm(e['diff']))
z = sum(1 for k, e in out.items() if not k.startswith('PENDING') and not norm(e['diff']))
sv_nz = sum(1 for k, e in out.items() if not k.startswith('PENDING') and e['v'] == 0 and norm(e['diff']))
sv_z = sum(1 for k, e in out.items() if not k.startswith('PENDING') and e['v'] == 0 and not norm(e['diff']))
print('aligned-direct entries:', len(out) - sum(1 for k in out if k.startswith('PENDING')))
print('non-empty diffs:', nz, 'empty diffs:', z)
print('survivors non-empty:', sv_nz, 'survivors empty:', sv_z)
for k, e in out.items():
    if k.startswith('PENDING'):
        print('pending fn:', k, 'entries', len(e['entries']), 'cands', len(e['cands']))
