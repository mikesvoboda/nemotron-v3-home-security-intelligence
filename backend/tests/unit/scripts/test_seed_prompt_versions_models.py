"""Guard: ``seed_prompt_versions`` must seed every AIModel member it can iterate.

B3.3 box 4 (#7322) narrowed ``AIModel`` to a single member (``NEMOTRON``), but
``scripts/seed-events.py`` kept four retired entries (``FLORENCE2``,
``YOLO_WORLD``, ``XCLIP``, ``FASHION_CLIP``) in ``seed_prompt_versions``'s
``version_templates`` dict — attribute access on a retired ``AIModel`` member
raises ``AttributeError`` the moment the function is called, AFTER phases 1-4
have already written (the function runs in phase 5 of ``main`` under ``if not
args.minimal``). The fix dropped the four entries; this file pins the shape so
a future retired member cannot leave a dead template entry behind.

The pin is behavioural on the dict, not source text: the module is loaded by
path (the way ``test_audit_slow_list_liveness.py`` loads its subject) and the
template keys are compared against ``AIModel``'s members. An entry keyed by a
name that is no longer a member, or a template key that misses an existing
member, reddens.
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "seed-events.py"

# Loaded by path so the SHIPPED seeder is what gets exercised, not a
# reimplementation of it. Import succeeds (the templates dict is function-local)
# — which is exactly why the defect survived until the function was called.
_spec = importlib.util.spec_from_file_location("_seed_events_under_test", SCRIPT)
assert _spec is not None and _spec.loader is not None
_seed_events = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_seed_events)


def _version_template_keys() -> list[str]:
    """The keys of ``seed_prompt_versions``'s ``version_templates`` dict.

    Read from the AST (calling the function would need a database): the dict
    literal is the only one inside the function, and its keys are
    ``AIModel.<NAME>`` attribute accesses.
    """
    func = _seed_events.seed_prompt_versions
    tree = ast.parse(inspect_source(func))
    # The outer dict is the one ASSIGNED to `version_templates` — the inner
    # per-template `{"config": ..., "change": ...}` literals are also
    # ast.Dict nodes, so the assignment anchor is what makes this unique.
    assigned = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(
            getattr(node, "target", None) or getattr(node, "targets", [None])[0], ast.Name
        )
        and (
            (getattr(node, "target", None) or getattr(node, "targets", [None])[0]).id
            == "version_templates"
        )
        and isinstance(node.value, ast.Dict)
    ]
    assert len(assigned) == 1, (
        f"expected exactly one dict literal assigned to version_templates, found {len(assigned)}"
    )
    keys = []
    for key_node in assigned[0].keys:
        assert isinstance(key_node, ast.Attribute), (
            f"version_templates key is not an AIModel.<NAME> attribute: {ast.dump(key_node)}"
        )
        assert key_node.value.id == "AIModel", (
            f"version_templates key does not name AIModel: {ast.dump(key_node)}"
        )
        keys.append(key_node.attr)
    return keys


def inspect_source(func) -> str:
    import inspect

    return inspect.getsource(func)


class TestSeedPromptVersionsTemplates:
    """seed_prompt_versions' template keys must all be live AIModel members."""

    def test_template_keys_are_all_ai_model_members(self) -> None:
        members = {m.name for m in _seed_events.AIModel}
        keys = _version_template_keys()
        assert keys, "seed_prompt_versions lost its version_templates dict entirely"
        for key in keys:
            assert key in members, (
                f"version_templates key {key!r} is not an AIModel member "
                f"(members: {sorted(members)}) — the seed raises AttributeError "
                f"the moment it runs"
            )

    def test_every_member_has_templates(self) -> None:
        """The loop ``for model in AIModel`` covers every member; a member with
        no template entry seeds zero versions for it — legal, but a silent
        regression when a member is added, so pinned."""
        members = {m.name for m in _seed_events.AIModel}
        keys = set(_version_template_keys())
        missing = members - keys
        assert not missing, (
            f"AIModel members with no version template: {sorted(missing)} — "
            f"either add a template or shrink the loop"
        )

    def test_no_retired_member_strings_in_the_function(self) -> None:
        """Belt-and-braces source check: the four names this fix deleted must
        not return inside the function body (the AST pin above already fails
        on a retired key, but a retired string in a nested template would
        slip past it while still seeding ghost rows for the wrong model)."""
        func = _seed_events.seed_prompt_versions
        source = inspect_source(func)
        for retired in ("FLORENCE2", "YOLO_WORLD", "XCLIP", "FASHION_CLIP"):
            assert not re.search(rf"AIModel\.{retired}\b", source), (
                f"AIModel.{retired} reappeared in seed_prompt_versions"
            )
