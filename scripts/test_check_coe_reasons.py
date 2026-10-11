#!/usr/bin/env python3
"""continue-on-error reason gate (OB.2 clause 3): every suppressing key carries a reason.

``continue-on-error`` is the repo's ledger of suppressed CI failures. A key in
that ledger with no stated reason is a failure that can go red silently —
exactly the class OB.2 clause 3 retired ("Every ``continue-on-error: true``
carries a comment with its reason, or goes") and the class ci.yml's own WP0.6
comment rails against. This gate is the committed form of the OB.2 inventory
(the PR body measured 31/31 by hand; contract rule 3 — tools live in the
repo — says the measurement belongs here, where a future PR is reddened by it):

    uv run python scripts/test_check_coe_reasons.py   # exit 1 + findings, or exit 0 + OK

Scope — a key belongs to the ledger when it CAN suppress:

    - ``continue-on-error: true`` (literal)      -> in scope
    - ``continue-on-error: ${{ ... }}`` (expression, may evaluate true) -> in scope
    - ``continue-on-error: false`` / ``False``   -> exempt: it suppresses nothing

A key carries a reason when a ``#`` comment sits within REASON_WINDOW lines
above it, or trails it on the same line. The window is generous on purpose:
the repo's reasons are multi-line blocks ("# OB.2 reason: ...") that open
above the step, and a gate narrower than the idiom manufactures reds without
adding information. It stays a WINDOW, not "any comment in the file": a reason
parked three jobs away is decoration, not a reason (pinned both directions in
``test_selftest_discriminates``).

Dual-shape parse: a YAML tree walk (authoritative on values: YAML's truthy
spellings and duplicate-key semantics are not grep-able) locates every
suppressing key, and each hit is then anchored to its source line by the
regex pass — comments are invisible to the tree, so the two passes need each
other. Neither pass alone sees both "which keys suppress" and "which of them
have a comment".
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

REASON_WINDOW = 12

# A continue-on-error key line: value is literal true (any YAML spelling),
# literal false (recorded, exempt), or a ${{ expression }} (may suppress).
KEY_RE = re.compile(r"^(\s*)continue-on-error:\s*(\$\{\{.*\}\}|true|True|false|False)\s*(#.*)?$")


def _is_suppressing(value: str) -> bool:
    return value.startswith("${{") or value.lower() == "true"


def _commented(lines: list[str], idx: int, trailing: str | None) -> bool:
    if trailing:
        return True
    window = lines[max(0, idx - REASON_WINDOW) : idx]
    return any(line.strip().startswith("#") for line in window)


def scan_workflows(workflow_dir: Path) -> list[str]:
    """Findings for every workflow under ``workflow_dir`` (empty list = clean)."""
    findings: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        try:
            docs = list(yaml.load_all(io.StringIO(text), Loader=yaml.SafeLoader))
        except yaml.YAMLError as exc:  # unparsable workflow: red, not skipped
            findings.append(f"{path.name}: unparsable YAML ({exc.__class__.__name__})")
            continue
        suppressing: list[dict] = []

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, val in node.items():
                    if key == "continue-on-error" and _is_suppressing(_value_text(val)):
                        suppressing.append({"value": _value_text(val), "at": 0})
                    else:
                        walk(val)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        for doc in docs:
            walk(doc or {})
        if not suppressing:
            continue
        lines = text.splitlines()
        key_lines = [
            (i, m) for i, line in enumerate(lines) if (m := KEY_RE.match(line)) is not None
        ]
        # The tree walk sees values the line regex cannot spell (YAML 1.1
        # truthy: yes/on/TRUE); compare against the line pass's SUPPRESSING
        # matches only — a false-valued key line legitimately has no tree-side
        # suppression twin, and counting it here would mask a missed `yes`.
        line_suppressing = [km for km in key_lines if _is_suppressing(km[1].group(2))]
        if len(line_suppressing) != len(suppressing):
            findings.append(
                f"{path.name}: YAML sees {len(suppressing)} suppressing "
                f"continue-on-error key(s) but the line pass matched "
                f"{len(line_suppressing)} — a truthy spelling outside the regex "
                "(yes/on/TRUE?) is unaccounted for"
            )
            continue
        # Anchor tree hits to lines in document order: both passes enumerate
        # the same keys in file order, so zip is exact; surplus tree hits
        # (duplicate keys YAML merged away) leave their line unreached and
        # the line pass adjudicates them too.
        for (i, m) in key_lines:
            if not _is_suppressing(m.group(2)):
                continue
            if not _commented(lines, i, m.group(3)):
                findings.append(
                    f"{path.name}:{i + 1}: continue-on-error: {m.group(2)[:40]} "
                    f"has no reason comment within {REASON_WINDOW} lines above or trailing it"
                )
    return findings


def _value_text(val: object) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str) and val.startswith("${{"):
        return val
    return str(val)


def test_every_suppressing_key_carries_a_reason() -> None:
    findings = scan_workflows(WORKFLOWS)
    assert not findings, "continue-on-error keys without reasons:\n  " + "\n  ".join(findings)


def test_gate_is_wired_into_ci() -> None:
    """Self-pin, mirroring test_retired_paths.py: a gate deletable from its
    only CI invocation without a red is already dead."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "scripts/test_check_coe_reasons.py" in ci, (
        "this gate must ride ci.yml's collection-sanity list"
    )


def test_selftest_discriminates(tmp_path: Path) -> None:
    """Both directions: a commented true key and a commented expression key
    pass; a bare true key, a bare expression key, a reason parked OUTSIDE the
    window, and a bare false key (exempt) each behave as scoped."""
    wf = tmp_path / "w"
    wf.mkdir()
    (wf / "ok.yml").write_text(
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: s\n"
        "        # reason: external notification may 429\n"
        "        run: x\n"
        "        continue-on-error: true\n"
        "  b:\n"
        "    # reason: informational off the main branch\n"
        "    continue-on-error: ${{ github.event_name == 'schedule' }}\n"
        "    steps:\n"
        "      - run: y\n",
        encoding="utf-8",
    )
    assert scan_workflows(wf) == []
    (wf / "bad.yml").write_text(
        "jobs:\n"
        "  bare-true:\n"
        "    steps:\n"
        "      - run: x\n"
        "        continue-on-error: true\n"
        "  bare-expr:\n"
        "    continue-on-error: ${{ github.ref == 'refs/heads/main' }}\n"
        "    steps:\n"
        "      - run: y\n"
        "  far-comment:\n"
        "    # reason lives 20 lines away\n"
        "    steps:\n"
        "      - run: a\n"
        "      - run: b\n"
        "      - run: c\n"
        "      - run: d\n"
        "      - run: e\n"
        "      - run: f\n"
        "      - run: g\n"
        "      - run: h\n"
        "      - run: i\n"
        "      - run: j\n"
        "      - run: k\n"
        "      - run: l\n"
        "      - run: m\n"
        "      - run: n\n"
        "      - run: o\n"
        "        continue-on-error: true\n"
        "  bare-false-exempt:\n"
        "    continue-on-error: false\n"
        "    steps:\n"
        "      - run: z\n",
        encoding="utf-8",
    )
    findings = scan_workflows(wf)
    joined = "\n".join(findings)
    assert "bad.yml:5" in joined, findings  # bare literal true flagged
    assert "bad.yml:7" in joined, findings  # bare expression flagged
    assert "bad.yml:28" in joined, findings  # comment beyond the window flagged
    assert "bare-false" not in joined and "bad.yml:30" not in joined, findings  # false exempt


if __name__ == "__main__":
    hits = scan_workflows(WORKFLOWS)
    if hits:
        print(f"{len(hits)} continue-on-error reason violation(s):", file=sys.stderr)
        for h in hits:
            print(f"  - {h}", file=sys.stderr)
        sys.exit(1)
    print("continue-on-error reasons OK: every suppressing key states its reason")
