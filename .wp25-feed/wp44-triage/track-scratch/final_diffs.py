"""Final: map every surviving mutant key -> real diff, validated against spans signature."""
import os, json, difflib, collections, functools

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
spans = json.load(open(f'{WS}/mutants/backend/services/track_service.py.spans'))['spans']

def code_lines(func):
    return cst.Module([func]).code.rstrip("\n").split("\n")

def span_len(name):
    sp = spans.get(name)
    return (sp[1] - sp[0] + 1) if sp else None

def funcs():
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef):
            yield None, stmt
        elif isinstance(stmt, cst.ClassDef) and isinstance(stmt.body, cst.IndentedBlock):
            for meth in stmt.body.body:
                if isinstance(meth, cst.FunctionDef):
                    yield stmt.name.value, meth

meta = json.load(open(f'{WS}/mutants/backend/services/track_service.py.meta'))
ebk = meta['exit_code_by_key']
PFX = 'backend.services.track_service.'

def fn_idx(key):
    tail = key[len(PFX):]
    base, idx = tail.rsplit('__mutmut_', 1)
    return base, int(idx)

def norm(lines):
    return [l.rstrip() for l in lines if l.strip() != '']

survivor_diffs = {}
ambig = []
for cls, func in funcs():
    mname = mangle_function_name(name=func.name.value, class_name=cls)
    fmut = groups.get(func)
    if not fmut:
        continue
    entries = sorted(
        [(fn_idx(PFX + mname + '__mutmut_' + str(i))[1], i)
         for i in range(1, len(ebk) + 1) if PFX + mname + '__mutmut_' + str(i) in ebk],
        key=lambda t: t[0])
    # rebuild properly: collect all meta indices for this function
    entries = []
    for k, v in ebk.items():
        if not k.startswith(PFX):
            continue
        f, i = fn_idx(k)
        if f == mname:
            entries.append((i, v))
    entries.sort()

    orig = code_lines(func)
    gens = []  # (gen_idx, diff_lines, nlines)
    for i, mu in enumerate(fmut, 1):
        mf = func.deep_replace(mu.original_node, mu.mutated_node)
        mlines = code_lines(mf)
        d = [l for l in difflib.unified_diff(orig, mlines, lineterm='', n=1)
             if l.startswith(('+', '-')) and not l.startswith(('---', '+++'))]
        gens.append((i, d, len(mlines)))

    n_meta = len(entries)
    if n_meta == len(gens):
        gmap = {g: (d, ln) for g, d, ln in gens}
        assign = {i: i for i, v in entries}  # identity
        # validate signature
        for i, v in entries:
            _, ln = gmap[i]
            if ln != span_len(f"{mname}__mutmut_{i}"):
                ambig.append((mname, i, 'sig-mismatch-identity'))
    else:
        # DP: choose increasing assignment meta i_j -> gen g_j with len match
        cand_by_len = collections.defaultdict(list)
        for g, d, ln in gens:
            cand_by_len[ln].append(g)
        @functools.lru_cache(maxsize=None)
        def solve(j, last):
            if j == n_meta:
                return ()
            i, v = entries[j]
            need = span_len(f"{mname}__mutmut_{i}")
            for g in cand_by_len.get(need, ()):
                if g > last:
                    r = solve(j + 1, g)
                    if r is not None:
                        return (g,) + r
            return None
        # count solutions for uniqueness
        @functools.lru_cache(maxsize=None)
        def count(j, last):
            if j == n_meta:
                return 1
            i, v = entries[j]
            need = span_len(f"{mname}__mutmut_{i}")
            return sum(count(j + 1, g) for g in cand_by_len.get(need, ()) if g > last)
        sol = solve(0, 0)
        n_sol = count(0, 0)
        if sol is None:
            ambig.append((mname, n_meta, 'no-solution'))
            continue
        # verify uniqueness; if multiple, report (heuristic assignment may be wrong)
        if n_sol != 1:
            ambig.append((mname, n_meta, f'{n_sol} solutions'))
        gmap = {g: (d, ln) for g, d, ln in gens}
        assign = {entries[j][0]: sol[j] for j in range(n_meta)}

    for i, v in entries:
        g = assign[i]
        d, ln = gmap[g]
        survivor_diffs[PFX + mname + f'__mutmut_{i}'] = {'v': v, 'gen': g, 'diff': d}

json.dump(survivor_diffs, open('survivor_diffs.json', 'w'), indent=0)
sv = [k for k, e in survivor_diffs.items() if e['v'] == 0]
print('total keys:', len(survivor_diffs), 'survivors:', len(sv))
print('ambiguities:', ambig)
# signature check across all
bad = 0
for k, e in survivor_diffs.items():
    f, i = fn_idx(k)
    if i != e['gen']:
        pass  # filtered function; alignment used lengths
for k, e in survivor_diffs.items():
    f, i = fn_idx(k)
    if f not in ('xǁTrackServiceǁget_tracks_by_camera', 'xǁTrackServiceǁmark_track_lost'):
        assert i == e['gen'], k
print('OK')
