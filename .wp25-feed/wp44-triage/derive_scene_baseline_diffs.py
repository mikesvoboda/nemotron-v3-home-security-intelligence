"""Derive mutmut diffs for backend/services/scene_baseline.py without touching the repo cache.

Replicates mutmut 3.8 create_mutations + per-function mutant naming (deep_replace on the
function copy, index = position in per-function mutation group). Writes a JSON map
{full_key: diff_string} to stdout-ish file. Read-only w.r.t. the repo.
"""
import json, sys
from difflib import unified_diff
from collections import defaultdict

import libcst as cst
from mutmut.mutation.file_mutation import deep_replace, get_ignored_lines

sys.path.insert(0, "/agents/agent-nemo2/workspace/.venv/lib/python3.14/site-packages")

from mutmut.mutation.mutators import mutation_operators
from mutmut.mutation.trampoline_templates import CLASS_NAME_SEPARATOR

SRC = "/agents/agent-nemo2/workspace/backend/services/scene_baseline.py"
MODULE = "backend.services.scene_baseline"

def mangle(name, class_name):
    prefix = f"x{CLASS_NAME_SEPARATOR}{class_name}{CLASS_NAME_SEPARATOR}" if class_name else "x_"
    return f"{prefix}{name}"

def collect_methods(module):
    """yield (function_node, class_name or None) in module order, mirroring combine_mutations_to_source"""
    for stmt in module.body:
        if isinstance(stmt, cst.FunctionDef):
            yield stmt, None
        elif isinstance(stmt, cst.ClassDef) and isinstance(stmt.body, cst.IndentedBlock):
            for meth in stmt.body.body:
                if isinstance(meth, cst.FunctionDef):
                    yield meth, stmt.name.value

def operators_for(node):
    out = []
    for t, op in mutation_operators:
        if isinstance(node, t):
            out.append((node, op))
    return out

def gen_mutations_for_function(func):
    """Return list of (original_node, mutated_node) in the same order as combine groups them.

    combine_mutations_to_source groups mutations via group_by_top_level_node which uses
    Mutation.contained_by_top_level_function. MutationVisitor.on_visit is a plain CSTVisitor
    traversal (parents before children, children in code order). Mutations created anywhere
    inside a method (incl. nested funcs like check_yolo26) belong to the enclosing method,
    since OuterFunctionProvider marks all descendants of the top-level method.
    """
    muts = []
    def walk(node):
        for t, op in operators_for(node):
            for mutated in op(node):
                muts.append((node, mutated))
        for child in node.children:
            if isinstance(child, cst.CSTNode):
                walk(child)
            elif isinstance(child, (list, tuple)):
                for item in child:
                    if isinstance(item, cst.CSTNode):
                        walk(item)
    walk(func)
    return muts

def main():
    code = open(SRC).read()
    module = cst.parse_module(code)
    result = {}
    for func, class_name in collect_methods(module):
        muts = gen_mutations_for_function(func)
        mangled = mangle(func.name.value, class_name)
        for i, (orig_node, mut_node) in enumerate(muts):
            key = f"{MODULE}.x{CLASS_NAME_SEPARATOR if class_name else '_'}"
            key = f"{MODULE}.{mangled}__mutmut_{i+1}"
            mutated_func = deep_replace(func, orig_node, mut_node)
            mutated_func = mutated_func.with_changes(name=cst.Name(func.name.value))
            orig_func = func.with_changes(name=cst.Name(func.name.value))
            # strip docstring-only leading_lines differences: code both
            o = cst.Module([orig_func]).code
            m = cst.Module([mutated_func]).code
            diff = "\n".join(l for l in unified_diff(o.split("\n"), m.split("\n"), lineterm=""))
            result[key] = diff
    json.dump(result, open("/tmp/wp25/wp44-triage/scene_baseline_mutant_diffs.json", "w"))
    print("generated", len(result))
    # sanity vs meta
    meta = json.load(open("/agents/agent-nemo2/workspace/mutants/backend/services/scene_baseline.py.meta"))
    mk = set(meta["exit_code_by_key"])
    gk = set(result)
    print("meta keys:", len(mk), "generated:", len(gk))
    print("in meta not generated:", sorted(mk - gk)[:20])
    print("in generated not meta:", sorted(gk - mk)[:20])

main()
