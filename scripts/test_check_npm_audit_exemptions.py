#!/usr/bin/env python3
"""Tests for scripts/check-npm-audit-exemptions.py (the npm-audit gate).

The gate replaces a bare `npm audit --audit-level=high` in ci.yml, so its
failure modes ARE the gate's teeth: every case below is a mini audit report
fed through a fake `npm` on PATH (the registry is JSON-in/JSON-out, so no
network and no real node_modules are involved). Run explicitly (outside
testpaths):

    uv run python -m pytest scripts/test_check_npm_audit_exemptions.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
CHECKER = REPO / "check-npm-audit-exemptions.py"

FAKE_NPM = """#!/usr/bin/env bash
cat "$NPM_AUDIT_JSON"
exit ${NPM_AUDIT_RC:-1}
"""


def audit_doc(advisories: list[dict]) -> str:
    """advisories: [{pkg, gid, sev, title, fix}] -> npm audit --json shape."""
    vulns = {}
    for a in advisories:
        via = {
            "source": 1,
            "name": a["pkg"],
            "dependency": a["pkg"],
            "title": a.get("title", "t"),
            "url": f"https://github.com/advisories/{a['gid']}",
            "severity": a["sev"],
            "cwe": [],
            "cvss": {"score": 7.5, "vectorString": ""},
            "range": "<=9.9.9",
        }
        fix = a.get("fix", {"name": "root", "version": "99.0.0", "isSemVerMajor": True})
        via["fixAvailable"] = fix
        vulns[a["pkg"]] = {
            "name": a["pkg"],
            "severity": a["sev"],
            "isDirect": False,
            "via": [via],
            "effects": [],
            "range": "<=9.9.9",
            "fixAvailable": fix,
        }
    total = len(advisories)
    return json.dumps(
        {
            "auditReportVersion": 2,
            "vulnerabilities": vulns,
            "metadata": {
                "vulnerabilities": {
                    "info": 0,
                    "low": 0,
                    "moderate": 0,
                    "high": total,
                    "critical": 0,
                    "total": total,
                }
            },
        }
    )


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        npm = self.bin / "npm"
        npm.write_text(FAKE_NPM)
        npm.chmod(0o755)
        self.frontend = tmp_path / "frontend"
        self.frontend.mkdir()

    def run(
        self,
        audit_json: str,
        registry: dict | None,
        registry_exists: bool = True,
        seed: int | None = None,
    ):
        reg = self.frontend / ".npm-audit-exemptions.json"
        if registry_exists:
            reg.write_text(json.dumps(registry if registry is not None else {"exceptions": []}))
        doc = self.tmp / "audit.json"
        doc.write_text(audit_json)
        env = {
            "PATH": f"{self.bin}:{'/usr/bin:/bin'}",
            "NPM_AUDIT_JSON": str(doc),
            "NPM_AUDIT_RC": "1"
            if json.loads(audit_json)["metadata"]["vulnerabilities"]["total"]
            else "0",
        }
        if seed is not None:
            # Fix str-hash order for this child; without it each run randomizes.
            env["PYTHONHASHSEED"] = str(seed)
        return subprocess.run(  # noqa: PLW1510 - the whole point is checking rc
            [
                sys.executable,
                str(CHECKER),
                "--frontend",
                str(self.frontend),
                "--warn-days",
                "14",
            ],
            capture_output=True,
            text=True,
            env=env,
        )


FUTURE = "2099-01-01"

# A GHSA id must be 4-4-4 base36 chars to survive the checker's parse.
G1 = "GHSA-aaaa-bbbb-cccc"  # braces-style: no released fix, major migration path
G2 = "GHSA-dddd-eeee-ffff"  # serialize-javascript-style: real in-range fix


def entry(gid: str, pkg: str, review: str = FUTURE) -> dict:
    return {"id": gid, "package": pkg, "severity": "high", "reviewBy": review}


BRACES = [
    {
        "pkg": "braces",
        "gid": G1,
        "sev": "high",
        "fix": {"name": "tailwindcss", "version": "4.3.3", "isSemVerMajor": True},
    }
]


def test_clean_finding_without_registry_fails_closed(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc(BRACES), None, registry_exists=False)
    assert r.returncode == 1
    assert "fails closed" in r.stderr


def test_unexempted_finding_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc(BRACES), {"exceptions": []})
    assert r.returncode == 1
    assert "UNEXEMPTED" in r.stderr


def test_valid_major_only_exemption_is_green(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc(BRACES), {"exceptions": [entry(G1, "braces")]})
    assert r.returncode == 0, r.stderr


def test_expired_review_by_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc(BRACES), {"exceptions": [entry(G1, "braces", "2020-01-01")]})
    assert r.returncode == 1
    assert "PASSED" in r.stderr


def test_missing_review_by_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(
        audit_doc(BRACES),
        {"exceptions": [{k: v for k, v in entry(G1, "braces").items() if k != "reviewBy"}]},
    )
    assert r.returncode == 1
    assert "reviewBy" in r.stderr


def test_stale_exemption_is_red(tmp_path: Path) -> None:
    """Registry entry whose advisory no longer appears in the audit."""
    h = Harness(tmp_path)
    r = h.run(audit_doc([]), {"exceptions": [entry(G2, "gone-pkg")]})
    assert r.returncode == 1
    assert "stale" in r.stderr


def test_in_range_fix_appearing_invalidates_exemption(tmp_path: Path) -> None:
    """The premise of an exception is 'the only fix path is a major migration'.
    When npm starts reporting an in-range fix, the exception must die."""
    h = Harness(tmp_path)
    in_range = [{"pkg": "braces", "gid": G1, "sev": "high", "fix": True}]
    r = h.run(audit_doc(in_range), {"exceptions": [entry(G1, "braces")]})
    assert r.returncode == 1
    assert "premise broken" in r.stderr


def test_not_fixable_per_npm_keeps_exemption_valid(tmp_path: Path) -> None:
    """npm's advisory-level fixAvailable reads null when the fix lives at the
    vulnerability level (the real braces shape); null alone is NOT a premise
    break - otherwise the registry could never cover the case it exists for."""
    h = Harness(tmp_path)
    nope = [{"pkg": "braces", "gid": G1, "sev": "high", "fix": None}]
    r = h.run(audit_doc(nope), {"exceptions": [entry(G1, "braces")]})
    assert r.returncode == 0, r.stderr


def test_major_fix_at_vuln_level_keeps_exemption_valid(tmp_path: Path) -> None:
    """npm puts the real (major) fix on the vulnerability entry while the
    advisory via reads null - exactly the live braces report shape."""
    h = Harness(tmp_path)
    doc = json.loads(audit_doc([{"pkg": "braces", "gid": G1, "sev": "high", "fix": None}]))
    doc["vulnerabilities"]["braces"]["fixAvailable"] = {
        "name": "tailwindcss",
        "version": "4.3.3",
        "isSemVerMajor": True,
    }
    r = h.run(json.dumps(doc), {"exceptions": [entry(G1, "braces")]})
    assert r.returncode == 0, r.stderr


def test_in_range_fix_at_vuln_level_breaks_exemption(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    doc = json.loads(audit_doc([{"pkg": "braces", "gid": G1, "sev": "high", "fix": None}]))
    doc["vulnerabilities"]["braces"]["fixAvailable"] = True
    r = h.run(json.dumps(doc), {"exceptions": [entry(G1, "braces")]})
    assert r.returncode == 1
    assert "premise broken" in r.stderr


def test_package_attribution_mismatch_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc(BRACES), {"exceptions": [entry(G1, "some-other-pkg")]})
    assert r.returncode == 1
    assert "audit attributes" in r.stderr


def test_finding_moving_to_another_package_is_red(tmp_path: Path) -> None:
    """Same advisory, different package than registered -> stale + unexempted."""
    h = Harness(tmp_path)
    moved = [
        {
            "pkg": "micromatch",
            "gid": G1,
            "sev": "high",
            "fix": {"name": "tailwindcss", "version": "4.3.3", "isSemVerMajor": True},
        }
    ]
    r = h.run(audit_doc(moved), {"exceptions": [entry(G1, "braces")]})
    assert r.returncode == 1


def test_mixed_registry_and_multiple_advisories(tmp_path: Path) -> None:
    """G1 exempted (major-only), G2 unexempted with an in-range fix: red naming G2;
    fixing it (empty audit for G2) leaves green for G1."""
    h = Harness(tmp_path)
    both = [*BRACES, {"pkg": "serialize-javascript", "gid": G2, "sev": "low", "fix": True}]
    r = h.run(audit_doc(both), {"exceptions": [entry(G1, "braces")]})
    assert r.returncode == 1
    assert G2 in r.stderr and "UNEXEMPTED" in r.stderr
    r2 = h.run(audit_doc(BRACES), {"exceptions": [entry(G1, "braces")]})
    assert r2.returncode == 0


def test_clean_audit_with_empty_registry_is_green(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc([]), {"exceptions": []})
    assert r.returncode == 0, r.stderr


def test_clean_audit_without_registry_is_red(tmp_path: Path) -> None:
    """The gate is the registry+checker PAIR: without the registry file the
    step cannot prove anything about future findings, so it fails closed."""
    h = Harness(tmp_path)
    r = h.run(audit_doc([]), None, registry_exists=False)
    assert r.returncode == 1
    assert "fails closed" in r.stderr


def test_warn_on_expiry_soon_is_exit_two(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    from datetime import date, timedelta

    soon = (date.today() + timedelta(days=3)).isoformat()
    r = h.run(audit_doc(BRACES), {"exceptions": [entry(G1, "braces", soon)]})
    assert r.returncode == 2
    assert "WARN" in r.stdout


# --- R76: alias matching (R61's twin for the npm checker) --------------------

# A second 4-4-4 id standing in for the advisory's OTHER GHSA (the GitHub
# advisory DB reassigning ids, or one vulnerability published under two
# GHSA entries). A CVE-valued alias would be inert here: every key in the
# checker's `found` map is GHSA-form (GHSA_RE gates parse), so only GHSA
# aliases can ever match. npm audit --json gives no aliases array -
# advisories arrive only as the single GHSA URL in via[].url - so both alias
# directions ruling 76 pins are necessarily expressed registry-side.
G3 = "GHSA-1111-2222-3333"
G4 = "GHSA-5555-6666-7777"


def test_audit_side_alias_covers_registry_primary(tmp_path: Path) -> None:
    """Ruling 76 direction (a): the audit reports the alias, the exemption is
    keyed by the primary. Before R76 this pair was double-red: the GHSA the
    audit reported (alias) printed UNEXEMPTED while the registry-cited id
    printed stale - the SAME advisory slipping the allowlist on id drift.
    Registry-cited G1 with aliases [G3]; audit reports G3."""
    h = Harness(tmp_path)
    e = entry(G1, "braces")
    e["aliases"] = [G3]
    reported = [
        {
            "pkg": "braces",
            "gid": G3,
            "sev": "high",
            "fix": {"name": "tailwindcss", "version": "4.3.3", "isSemVerMajor": True},
        }
    ]
    r = h.run(audit_doc(reported), {"exceptions": [e]})
    assert r.returncode == 0, r.stderr


def test_registry_side_alias_covers_audit_primary(tmp_path: Path) -> None:
    """Ruling 76 direction (b): the audit reports the primary, the exemption
    is keyed by (or cites) the alias. Registry-cited G3 with aliases [G1];
    audit reports G1."""
    h = Harness(tmp_path)
    e = entry(G3, "braces")
    e["aliases"] = [G1]
    r = h.run(audit_doc(BRACES), {"exceptions": [e]})
    assert r.returncode == 0, r.stderr


def test_alias_does_not_overshoot(tmp_path: Path) -> None:
    """Overshoot guard (R61's twin): an entry whose id AND aliases name
    nothing the audit reported stays red both ways - the fix must not turn
    the registry into a wildcard."""
    h = Harness(tmp_path)
    e = entry(G3, "braces")
    e["aliases"] = ["GHSA-9999-8888-7777"]
    r = h.run(audit_doc(BRACES), {"exceptions": [e]})
    assert r.returncode == 1
    assert "stale" in r.stderr and "UNEXEMPTED" in r.stderr


def test_overlapping_alias_adjudicates_deterministically(tmp_path: Path) -> None:
    """Self-review F1 pin: an entry whose {id, aliases} names TWO distinct
    reported advisories must adjudicate identically on every run. The harness
    scrubs env, so each subprocess gets a fresh PYTHONHASHSEED; a bare
    next(...) over the id set picked `hit` by string-hash order and printed
    a DIFFERENT violation list on different seeds (reproduced: 1 error vs 2
    errors across seeds, always rc=1). The checker now prefers the entry's
    own id, so the over-listed alias deterministically leaves the OTHER
    advisory UNEXEMPTED - fail-closed and reproducible.

    Scope note (ops-a review on #6966): this input reports the entry's own id,
    so `gid in found` short-circuits and the 20 runs never reach the set
    fallback. The fallback branch gets its own pin below."""
    h = Harness(tmp_path)
    e = entry(G1, "braces")
    e["aliases"] = [G3]  # G3 is a DIFFERENT advisory actually reported here
    both = [
        {
            "pkg": "braces",
            "gid": G1,
            "sev": "high",
            "fix": {"name": "tailwindcss", "version": "4.3.3", "isSemVerMajor": True},
        },
        {"pkg": "serialize-javascript", "gid": G3, "sev": "low", "fix": True},
    ]
    outs = {
        (r.returncode, r.stderr)
        for r in (h.run(audit_doc(both), {"exceptions": [e]}) for _ in range(20))
    }
    assert len(outs) == 1, f"adjudication varies across hash seeds: {outs}"
    rc, err = next(iter(outs))
    assert rc == 1
    assert f"{G3}" in err and "UNEXEMPTED" in err
    assert "stale" not in err  # G1 is reported and matched as hit, never stale


def test_alias_hit_fallback_adjudicates_deterministically(tmp_path: Path) -> None:
    """ops-a review request on #6966 (reproduced in my shell at 0f39d2ffc):
    the entry's OWN id is not reported, so adjudication falls through to
    `next((i for i in ids if i in found), None)` over a SET - set iteration
    order is PYTHONHASHSEED order, and with two aliases both reported the
    hit wobbled between runs: 12 seed-fixed runs gave the UNEXEMPTED-only
    variant on every seed but 8, where hit landed on the lodash advisory and
    the SAME input printed 2 violations (attribution error on the entry + the
    reported braces advisory printed UNEXEMPTED). rc=1 either way - fail-closed
    held - but a waffling report is the F1 class this PR exists to close, and
    the pin above couldn't reach it because its audit reports the entry's own
    id.
    Fix: `sorted(ids)` gives the fallback a deterministic candidate order
    (digits sort before letters, so G3 leads). Pinned BOTH ways: the two
    formerly-diverging fixed seeds (0 and 8) and 20 fresh-seed runs all print
    the identical list - hit=G3 on braces, G4/lodash UNEXEMPTED, no
    attribution flip, never stale."""
    h = Harness(tmp_path)
    e = entry(G1, "braces")
    e["aliases"] = [G3, G4]  # BOTH are distinct reported advisories
    both = [
        {
            "pkg": "braces",
            "gid": G3,
            "sev": "high",
            "fix": {"name": "tailwindcss", "version": "4.3.3", "isSemVerMajor": True},
        },
        {"pkg": "lodash", "gid": G4, "sev": "low"},
    ]
    doc = audit_doc(both)
    runs = [
        h.run(doc, {"exceptions": [e]}, seed=0),
        h.run(doc, {"exceptions": [e]}, seed=8),  # the divergent seed pre-fix
        *(h.run(doc, {"exceptions": [e]}) for _ in range(20)),
    ]
    outs = {(r.returncode, r.stderr) for r in runs}
    assert len(outs) == 1, f"fallback hit varies across hash seeds: {outs}"
    rc, err = next(iter(outs))
    assert rc == 1  # fail-closed, as before the fix
    assert f"{G4}" in err and "UNEXEMPTED" in err and "lodash" in err
    assert "registered for" not in err  # G3 hit on braces: attribution clean
    assert "stale" not in err  # G1's absence prints nothing - G3 is its alias
