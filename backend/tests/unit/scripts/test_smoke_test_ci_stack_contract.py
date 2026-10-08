"""O1.9 (D12): the smoke test must state the CI stack's health contract, not a fictional one.

``Deploy`` has been red on every push to ``main`` since 2026-01-05 (00-audit D12),
and the single red step is ``Smoke Test Deployment`` → ``Perform health check
validation``. Measured at head ``acfe5b56``, run ``37726762316``, job
``113147736764`` — the run's ONLY failing job (``Deploy to Staging`` succeeded,
``Post-Deployment Validation`` was skipped by ``if: success()``):

    /api/system/health/ready → 200
    /api/system/health/full  → 503 {"message":"Critical services unhealthy: yolo26"}

with both AI rows reporting ``"error":"Connection refused"``. Not an outage.
``docker-compose.ci.yml`` starts four services (postgres, redis, backend,
frontend) and its own header says why — line 4: "No GPU requirements (AI
services are mocked/optional)". But ``system.py``'s ``AI_SERVICES_CONFIG``
carries ``yolo26`` with ``critical: True``, so on the CI stack ``/health/full``
MUST answer 503 — the check asserted the shipped stack's contract against the
CI stack and could never pass. An always-red pipeline reports nothing, and each
red opened an "Automated Rollback" issue for a rollback that never happens.

The fix states the contract instead of assuming it, in
``scripts/ci-smoke-contract.json`` beside the check, and these guards pin it:

1. the contract file exists and names both sets WITH the reason for each;
2. the contract agrees with ``docker-compose.ci.yml`` AS PARSED — the compose
   file is the truth, so a service added or removed there must land here too;
3. the check reads the contract and queries ``/health/full`` (kept per the plan);
4. BEHAVIOUR, run against the real payloads this job logged: a healthy-CI-stack
   503 passes; a stack whose redis is down, or whose report silently DROPS a
   service, fails. That is what makes it a check rather than a shrug.

When ``O2.1``'s fake AI stack runs in the smoke test, the contract file goes and
with it guards 1-2; 3-4 keep their shape.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT = REPO_ROOT / "scripts" / "ci-smoke-contract.json"
SMOKE = REPO_ROOT / "scripts" / "ci-smoke-test.sh"
COMPOSE_CI = REPO_ROOT / "docker-compose.ci.yml"
DATA = Path(__file__).resolve().parent / "data"

# The real bodies, pulled from run 37726762316's own job log (lines 673/676) —
# not hand-written: a fixture copied from the incident cannot disagree with it.
CI_STACK_FULL_503 = DATA / "health-full-ci-stack-503.json"
CI_STACK_READY_200 = DATA / "health-ready-ci-stack-200.json"


@pytest.fixture(scope="module")
def contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compose_services() -> set[str]:
    doc = yaml.safe_load(COMPOSE_CI.read_text(encoding="utf-8"))
    return set((doc.get("services") or {}).keys())


def _run_check(payload_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the script's contract check against one recorded payload.

    Unmocked on purpose: the point of the guard is that the shipped shell
    decides the verdict, so mocking the process would test a stub. No network,
    no server, no AI service - the payload is a file and the script is offline
    in this mode, so it runs in milliseconds (same idiom as
    test_check_version_consistency.py:40).
    """
    return subprocess.run(  # noqa: S603  # intentional - tests our own script, offline
        [  # noqa: S607  # partial path OK for test script
            "bash",
            str(SMOKE),
            "--check-contract",
            str(payload_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )


def test_the_contract_file_states_both_sets_with_reasons() -> None:
    assert CONTRACT.is_file(), (
        "scripts/ci-smoke-contract.json is missing — the smoke check's expected "
        "unreachable set must be committed beside it, not inlined in shell"
    )
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract.get("started"), "the contract must name the services the CI stack starts"
    unreachable = contract.get("expected_unreachable")
    assert isinstance(unreachable, dict) and unreachable, (
        "expected_unreachable must map service -> reason; a bare list cannot "
        "carry the 'why is this allowed down' answer the next reader needs"
    )
    for name, reason in unreachable.items():
        assert isinstance(reason, str) and len(reason) > 20, (
            f"{name} needs a real reason, not a placeholder: {reason!r}"
        )
    assert "purpose" in contract, "the file must say why it exists and when it goes"


def test_the_contract_matches_the_compose_file_as_parsed(contract: dict, compose_services) -> None:
    """The contract is checked against the compose file itself, not trusted.

    A reviewer cannot tell from the JSON alone whether ``yolo26`` really is
    absent from the CI stack, so the guard re-parses docker-compose.ci.yml:
    every service the contract expects unreachable must NOT be started there
    (if it were, "expected unreachable" would be masking a real outage), and
    every service it expects healthy must BE started there.
    """
    assert set(contract["started"]) <= compose_services, (
        f"contract expects {sorted(contract['started'])} healthy, but "
        f"docker-compose.ci.yml starts {sorted(compose_services)}"
    )
    ghosts = sorted(set(contract["expected_unreachable"]) & compose_services)
    assert not ghosts, (
        f"docker-compose.ci.yml now starts {ghosts} — they are no longer "
        "'expected unreachable'; either fix the contract or the stack is wrong"
    )


def test_ai_services_expected_unreachable_are_the_ones_the_endpoint_reports(contract) -> None:
    """The recorded payload must report exactly the contract's unreachable set.

    Names drift (nemotron → ai-vlm in R8 S2): this pins the contract to the
    services /health/full actually enumerates on the CI stack, read from the
    incident's own response body.
    """
    payload = json.loads(CI_STACK_FULL_503.read_text(encoding="utf-8"))
    reported = {s["name"] for s in payload["ai_services"]}
    assert reported == set(contract["expected_unreachable"]), (
        f"/health/full reports AI services {sorted(reported)} but the contract "
        f"expects {sorted(contract['expected_unreachable'])}"
    )


def test_the_smoke_script_reads_the_contract_and_hits_full_health() -> None:
    """The check must consume the contract file and keep /health/full (plan box 1)."""
    script = SMOKE.read_text(encoding="utf-8")
    assert "ci-smoke-contract.json" in script, (
        "ci-smoke-test.sh must read the committed contract rather than inline a list"
    )
    assert "/api/system/health/full" in script, (
        "the plan keeps /api/system/health/full in the smoke test"
    )


def test_the_recorded_ci_stack_payload_satisfies_the_contract() -> None:
    """THE regression: this exact 503 is a HEALTHY CI stack and must pass.

    Before the fix the same bytes were fatal (that is D12). The assertion is
    the package's whole thesis in one line: a 503 whose unreachable set is the
    contract's is not a failure.
    """
    result = _run_check(CI_STACK_FULL_503)
    assert result.returncode == 0, (
        f"the contract check rejected a healthy CI stack:\n{result.stdout}\n{result.stderr}"
    )


def test_a_real_infrastructure_outage_still_fails(tmp_path: Path) -> None:
    """The contract must not rubber-stamp: redis down is a failure, not 'unreachable'."""
    payload = json.loads(CI_STACK_FULL_503.read_text(encoding="utf-8"))
    payload["redis"]["status"] = "unhealthy"
    payload["redis"]["message"] = "Connection refused"
    broken = tmp_path / "redis-down.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_check(broken)
    assert result.returncode != 0, (
        "a CI stack with unhealthy redis must fail the smoke test; the contract "
        "is about AI services compose.ci never starts, not about infrastructure"
    )
    assert "redis" in result.stdout + result.stderr, "the failure must name redis"


def test_a_service_silently_missing_from_the_report_fails(tmp_path: Path) -> None:
    """If postgres stops APPEARING in /health/full, that is a failure, not a pass.

    The always-green failure mode this closes: a check that only asserts what
    it expects to see would score a report that dropped a service as fine. The
    assertion names postgres as well as the exit code — a bare non-zero assert
    would pass vacuously while the script rejected the unknown flag outright.
    """
    payload = json.loads(CI_STACK_FULL_503.read_text(encoding="utf-8"))
    del payload["postgres"]
    missing = tmp_path / "no-postgres.json"
    missing.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_check(missing)
    assert result.returncode != 0, (
        "a /health/full report that omits a service the CI stack starts must not pass"
    )
    assert "postgres" in result.stdout + result.stderr, (
        "the failure must name the service it could not find, not just fail loudly"
    )


def test_the_ready_endpoint_payload_is_healthy() -> None:
    """Sanity on the second recorded fixture: /health/ready answered 200+ready."""
    payload = json.loads(CI_STACK_READY_200.read_text(encoding="utf-8"))
    assert payload["ready"] is True, "the recorded ready payload must show ready=true"
