# APPEND to scripts/test_fast_select.py (commit A version — contracts class only;
# commit B widens PATTERNS to the f4 top-level class and renames test_utils.py)
def test_contract_policy_files_define_tests():
    """Fast-tier contract: every file the contracts directory-policy can
    contribute must DEFINE tests.

    Red-first evidence (WP2.5 measured run 2026-09-16): probing
    backend/api/routes/alerts.py made the directory policy contribute
    contracts/test_schemathesis_contracts.py — a zero-test docstring stub —
    and the WP2.3 manifest correctly CANNOT-RUN'd the push-tier run (rc=1,
    named defect). fast_select.py's own header blessed over-selection as
    "harmless under an advisory tier"; WP2.1 promoted the selector to a
    GATE, and the stub outlived the ruling. The registry classifies it
    `retired` (delete-by-expiry, R-M2-COLLECTION-FINDINGS) — the queued
    remediation is delete, so this guard pins the post-state: a retired
    file may not ride the policy into every API-touching push.
    """
    import re

    repo = Path(__file__).resolve().parent.parent
    contrib = sorted((repo / "backend/tests/contracts").glob("test_*.py"))
    assert contrib, "contracts tier vanished — this guard would pass vacuously"
    # Mirror fast-backend-runner.sh detector 1 verbatim:
    #   grep -qE '^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+test_|^[[:space:]]*class[[:space:]]+Test'
    defines = re.compile(r"^\s*(async\s+)?def\s+test_|^\s*class\s+Test", re.M)
    missing = [
        str(p.relative_to(repo))
        for p in contrib
        if not defines.search(p.read_text(encoding="utf-8"))
    ]
    assert not missing, f"zero-test files ride the contracts directory-policy: {missing}"
