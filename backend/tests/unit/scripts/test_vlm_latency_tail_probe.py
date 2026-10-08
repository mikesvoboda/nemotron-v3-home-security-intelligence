"""Pins for `scripts/vlm_probes/latency_tail.py` (B1.1's MEASURE tool).

The probe is the tool the operator runs to post the S4 p95 and the reply
tail on the PR, which means its judgement code decides what "measured"
means on a real GPU run - and a measurement tool whose classification is
wrong is worse than no measurement, because the wrong label is what gets
posted. So the pins here are about WHICH BUCKET a wire outcome lands in
and WHICH EXIT a summary earns, all driven through an injected transport
(no GPU, no socket - the same doctrine as `test_vlm_enforcement_probe.py`):

  * a read timeout is BUDGET, never FAULT - D1's ruling read back through
    the harness: the breaker's question is "stop calling this engine?", a
    slow reply answers NO, so an all-timeout run must exit 1 ("this
    cap+timeout cannot carry this corpus"), not hide in exit 2;
  * a refused connection is FAULT and can starve a run to INCONCLUSIVE
    (exit 2) - a fault endpoint proves nothing about the engine;
  * one assess call per OK rep, and the §6 fast-fault retry (a refused
    first call, then success) does NOT count as a re-ask - both arms are
    pinned, since a guard that only ever fires is as useless as one that
    never fires;
  * the reply tail counts the server's `usage.completion_tokens` and falls
    back to the labelled tiktoken proxy only when usage is absent;
  * the probe leg's chat call (its own larger max_tokens) is filtered OUT
    of the reply-tail sample and the re-ask count - without that filter
    --warm-reps 0 would feed a probe reply into the verdict tail;
  * the p95 formula is the corrected nearest-rank, and the --cap check
    compares against the max (a proposal any real reply outran is a
    failed proposal).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.services.circuit_breaker import get_circuit_breaker
from backend.services.vlm_client import _PROBE_MAX_TOKENS

_PROBE_PATH = Path(__file__).resolve().parents[4] / "scripts" / "vlm_probes" / "latency_tail.py"


def _load_probe_module():
    assert _PROBE_PATH.exists(), f"missing probe CLI: {_PROBE_PATH}"
    spec = importlib.util.spec_from_file_location("vss_latency_tail_cli", _PROBE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lt = _load_probe_module()

BUILD = "b7972-e06088da0"

# A complete, valid VlmVerdict. The client rewrites `provenance` from /props,
# so only the parse matters here.
_VERDICT = json.dumps(
    {
        "verdict": "confirmed",
        "risk_score": 72,
        "summary": "A person walks the porch path.",
        "reasoning": "Loitering posture, no delivery cue.",
        "description": "Adult in dark jacket on porch.",
        "criteria": [{"name": "presence", "passed": True, "evidence": "on porch"}],
        "provenance": {"engine": "x", "model_id": "y"},
    }
)


class _ScriptedTransport(httpx.AsyncBaseTransport):
    """A llama.cpp stand-in with per-call behaviour the test controls.

    `script` answers each ASSESS chat call in order; the probe leg (its own
    larger max_tokens, sent once per client lifetime) answers from `probe`;
    `/props` always serves the pinned build.
    """

    def __init__(
        self,
        script: list[str],
        *,
        probe: str = "enforced",
        usage: bool = True,
        predicted: float | None = 57.0,
    ) -> None:
        self._script = list(script)
        self._probe_mode = probe
        self._usage = usage
        self._predicted = predicted
        self.assess_calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/props":
            return httpx.Response(200, json={"build_info": BUILD})
        assert request.url.path == lt.CHAT_PATH, f"unexpected call {request.url.path}"
        body = json.loads(bytes(await request.aread()))
        is_probe = body["max_tokens"] == _PROBE_MAX_TOKENS
        if is_probe:
            mode = self._probe_mode
            content: dict[str, Any] = {
                "probe_const": self._nonce(body),
                **json.loads(_VERDICT),
            }
            n_tokens = 350
        else:
            self.assess_calls += 1
            mode = self._script.pop(0) if len(self._script) > 1 else self._script[0]
            content = json.loads(_VERDICT)
            n_tokens = 800
        if mode == "timeout":
            raise httpx.ReadTimeout("read timeout")
        if mode == "refused":
            raise httpx.ConnectError("connection refused")
        if mode == "http500":
            return httpx.Response(500, json={"error": "boom"})
        assert mode in {"ok", "enforced"}, f"unknown script mode {mode!r}"
        payload: dict[str, Any] = {
            "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "eos"}]
        }
        if self._usage:
            payload["usage"] = {"completion_tokens": n_tokens}
        if self._predicted is not None:
            payload["timings"] = {"predicted_per_second": self._predicted}
        return httpx.Response(200, json=payload)

    @staticmethod
    def _nonce(body: dict[str, Any]) -> str:
        """Echo the nonce the probe actually put on the wire - a fake that
        hardcoded a const would pass even if none were sent (the lesson
        `test_vlm_enforcement_probe.py` learned)."""
        props = (body.get("response_format") or {}).get("json_schema", {}).get("schema", {})
        const = ((props.get("properties") or {}).get("probe_const") or {}).get("const", "")
        assert isinstance(const, str)
        return const


def _stills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    path = tmp_path / "a.jpg"
    path.write_bytes(b"\xff\xd8\xff" + b"\x00" * 64)
    # The client's root guard reads the settings singleton; monkeypatch is
    # the house override (restored after the test).
    from backend.services.vlm_client import get_settings

    monkeypatch.setattr(get_settings(), "foscam_base_path", str(tmp_path), raising=False)
    return [str(path)]


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **kw: Any) -> dict[str, Any]:
    kw.setdefault("url", "http://fake-vlm:8098")
    kw.setdefault("camera", "front_door")
    kw.setdefault("stills", _stills(tmp_path, monkeypatch))
    kw.setdefault("reps", 3)
    kw.setdefault("warm_reps", 0)
    kw.setdefault("probe", False)
    kw.setdefault("min_completed", 1)
    return asyncio.run(lt.run(**kw))


class TestSurface:
    def test_the_cli_has_the_probe_contract(self) -> None:
        for attr in ("run", "main"):
            assert hasattr(lt, attr), f"scripts/vlm_probes/latency_tail.py lacks {attr}()"

    def test_main_points_the_clients_root_at_dir(self, monkeypatch, tmp_path) -> None:
        """--dir IS the deployment's capture root (the operator's test stack
        points FOSCAM_BASE_PATH at a fresh dir, operator.md; the default is
        /export/foscam, the LIVE folder). _stills filters against --dir, but
        the client re-checks every path against settings.foscam_base_path —
        if run() does not point that root at --dir, a mismatch faults ALL
        reps (VlmImageError -> FAULT -> exit 2 'nothing was measured') before
        the engine is ever asked, and the operator's run proves nothing. The
        other exit-ladder tests only pass because they monkeypatch the root
        to tmp_path; this is the un-patched real-CLI path. A red test here is
        a red measurement tool — fix the tool, never the test."""
        captured: dict[str, Any] = {}
        real_run = lt.run

        async def _capture(*args: Any, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            # Run the REAL measurement through an injected transport, so the
            # exit code main returns is the real ladder over a real summary.
            return await real_run(*args, transport=_ScriptedTransport(["ok"]), **kwargs)

        still = tmp_path / "s.jpg"
        still.write_bytes(b"\xff\xd8\xff\x00")
        monkeypatch.setattr(lt, "run", _capture)
        # The real CLI path: NO foscam_base_path monkeypatch anywhere.
        code = lt.main(
            ["--url", "http://x:1", "--camera", "c", "--dir", str(tmp_path), "--frames", "1"]
        )
        assert code == 0, f"main exited {code} instead of running the capture"
        assert captured.get("capture_root") == str(tmp_path.resolve()), (
            "run() was not told --dir is the capture root; the client would check "
            "every path against the settings root (default /export/foscam, the live "
            "folder) and fault all reps before the engine is asked"
        )

    def test_the_client_root_follows_capture_root_not_the_default(self, monkeypatch, tmp_path) -> None:
        """The seam the RED test above drives: pass capture_root explicitly
        and the shipped VlmClient's `_image_parts` must accept a still under
        it WITHOUT the test-only settings-root monkeypatch — proving the root
        the client enforces is the root the operator passed as --dir."""
        other = tmp_path / "capture"
        other.mkdir()
        still = other / "s.jpg"
        still.write_bytes(b"\xff\xd8\xff" + b"\x00" * 64)
        # Deliberately do NOT monkeypatch foscam_base_path: it stays at the
        # default /export/foscam, which 'other' is NOT under.
        out = _run(
            monkeypatch,
            tmp_path,
            stills=[str(still)],
            capture_root=str(other.resolve()),
            transport=_ScriptedTransport(["ok", "ok", "ok"]),
        )
        assert out["outcomes"]["FAULT"] == 0, (
            f"the client faulted every rep: {out['outcome_details']} — its root "
            "check did not follow capture_root"
        )
        assert out["outcomes"]["OK"] == 3


class TestBudgetVsFault:
    def test_a_read_timeout_is_budget_not_fault(self, monkeypatch, tmp_path) -> None:
        """D1 through the harness's own lens: a timed-out reply must NEVER
        land in FAULT. If it did, posting an all-slow run would read as
        "the endpoint is broken" - the misdiagnosis B1.1 exists to end."""
        out = _run(
            monkeypatch,
            tmp_path,
            transport=_ScriptedTransport(["timeout", "timeout", "timeout"]),
        )
        assert out["outcomes"] == {"OK": 0, "BUDGET": 3, "FAULT": 0}
        assert out["breaker_open_after_run"] is False, "a budget never feeds the breaker"
        assert out["measured"] is True, "slowness IS a measurement; only faults are unmeasurable"
        assert out["budget_overruns"] == 3

    def test_a_refused_connection_is_fault(self, monkeypatch, tmp_path) -> None:
        out = _run(
            monkeypatch,
            tmp_path,
            transport=_ScriptedTransport(["refused", "refused", "refused"]),
        )
        assert out["outcomes"] == {"OK": 0, "BUDGET": 0, "FAULT": 3}
        assert out["measured"] is False, "a fault endpoint proves nothing about the engine"

    def test_faults_open_the_breaker_and_the_run_refuses_to_conclude(
        self, monkeypatch, tmp_path
    ) -> None:
        """The breaker is the registry singleton the shipped client uses: a
        run that ends with it OPEN must report itself unmeasured rather
        than pass off a half-refused run's numbers as a reading."""
        out = _run(
            monkeypatch,
            tmp_path,
            reps=5,
            transport=_ScriptedTransport(["refused"] * 5),
        )
        assert get_circuit_breaker("ai-vlm").is_open
        assert out["breaker_open_after_run"] is True
        assert out["measured"] is False


class TestReaskGuard:
    def test_one_assess_call_per_ok_rep_is_not_a_reask(self, monkeypatch, tmp_path) -> None:
        out = _run(monkeypatch, tmp_path, transport=_ScriptedTransport(["ok", "ok", "ok"]))
        assert out["reasked_reps"] == 0
        assert out["outcomes"]["OK"] == 3

    def test_a_fast_fault_then_success_is_the_ladder_not_a_reask(
        self, monkeypatch, tmp_path
    ) -> None:
        """The other arm: a refused first call earns the §6 retry BY DESIGN.
        A guard that counted this would accuse every legitimate retry, and
        the operator would learn to ignore the flag."""
        out = _run(monkeypatch, tmp_path, reps=1, transport=_ScriptedTransport(["refused", "ok"]))
        assert out["reasked_reps"] == 0, "the sanctioned fast-fault retry is not a re-ask"
        assert out["outcomes"]["OK"] == 1

    def test_the_first_call_decides_reask_or_ladder(self) -> None:
        """The classifier `reasked_reps` is built on, pinned directly. A
        post-timeout re-ask cannot be produced end-to-end through `run`:
        the B1.1 client itself never re-asks a timeout, so the only binary
        that puts a second call after one is a PRE-B1.1 build running this
        harness - and its wire pattern is exactly these records. The
        FIRST call decides: a read timeout first (or a success first)
        makes any later call an illegitimate re-ask; only a fast failure
        (connection refused) or a 5xx earns the second call."""

        def call(error: str | None = None, status: int | None = 200) -> dict[str, Any]:
            return {"error": error, "status": status, "max_tokens": 0}

        # Timeout first: never legitimate (the B1.1 ruling, as a guard).
        assert lt._legitimate_retry([call(error="ReadTimeout"), call()]) is False
        # Success first: a second call after a good reply is a re-ask too.
        assert lt._legitimate_retry([call(), call()]) is False
        # Fast fault first: the §6 ladder's sanctioned retry.
        assert lt._legitimate_retry([call(error="ConnectError"), call()]) is True
        assert lt._legitimate_retry([call(status=500), call()]) is True


class TestTails:
    def test_reply_tail_uses_the_servers_usage(self, monkeypatch, tmp_path) -> None:
        out = _run(monkeypatch, tmp_path, reps=1, transport=_ScriptedTransport(["ok"]))
        assert out["reply_tokens"]["n"] == 1
        assert out["reply_tokens"]["max"] == 800  # the fake's usage.completion_tokens
        assert out["reply_tokens"]["tiktoken_fallback_replies"] == 0
        assert out["decode_tok_s"]["median"] == 57.0  # the engine's own number

    def test_a_usage_less_reply_falls_back_to_the_labelled_proxy(
        self, monkeypatch, tmp_path
    ) -> None:
        out = _run(
            monkeypatch,
            tmp_path,
            reps=1,
            transport=_ScriptedTransport(["ok"], usage=False, predicted=None),
        )
        assert out["reply_tokens"]["n"] == 1
        assert out["reply_tokens"]["max"] > 0, "the tiktoken proxy still sizes the reply"
        assert out["reply_tokens"]["tiktoken_fallback_replies"] == 1
        assert out["decode_tok_s"]["median"] is None, "no engine rate, no rate - no invented one"

    def test_the_probe_leg_call_never_enters_the_reply_tail(self, monkeypatch, tmp_path) -> None:
        """Without the max_tokens filter, --warm-reps 0 with the probe ON
        would feed the probe's 350-token reply into the VERDICT tail - the
        very number an operator then uses to size the cap."""
        out = _run(
            monkeypatch,
            tmp_path,
            reps=2,
            warm_reps=0,
            probe=True,
            transport=_ScriptedTransport(["ok", "ok"], probe="enforced"),
        )
        assert out["outcomes"]["OK"] == 2
        assert out["reply_tokens"]["n"] == 2, "two assess replies; the probe call is filtered out"
        assert out["reply_tokens"]["max"] == 800, "no 350-token probe sample mixed into the tail"
        assert out["reasked_reps"] == 0, "the probe call must not read as a rep's second call"

    def test_nearest_rank_p95_is_the_corrected_formula(self) -> None:
        # The bug vlm_replay fixed: int(n*q) sits one rank high at n=20.
        assert lt._nearest_rank(list(range(1, 21)), 0.95) == 19
        assert lt._nearest_rank([5], 0.95) == 5


class TestExitCodes:
    """`main`'s exit ladder over canned summaries - the contract the
    operator's posted result reads against (0 clean, 1 the config must
    change, 2 nothing was measured)."""

    @staticmethod
    def _summary(**over: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "measured": True,
            "reasked_reps": 0,
            "budget_overruns": 0,
            "s4": {"measured_p95_ms": 20_000, "target_p95_ms": 30_000, "within": True},
            "reply_tokens": {"max": 900},
            "outcomes": {"OK": 40, "BUDGET": 0, "FAULT": 0},
            "breaker_open_after_run": False,
            "config": {"read_timeout_s": 25.0},
        }
        base.update(over)
        return base

    def _main(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        summary: dict[str, Any],
        argv_extra: list[str],
    ) -> int:
        still = tmp_path / "s.jpg"
        still.write_bytes(b"\xff\xd8\xff\x00")
        from backend.services.vlm_client import get_settings

        monkeypatch.setattr(get_settings(), "foscam_base_path", str(tmp_path), raising=False)
        # Stub the measurement itself; these pins are about the exit ladder.
        monkeypatch.setattr(lt, "run", lambda *_a, **_k: asyncio.sleep(0, result=summary))
        return lt.main(
            ["--url", "http://x:1", "--camera", "c", "--dir", str(tmp_path), *argv_extra]
        )

    def test_a_clean_run_exits_zero(self, monkeypatch, tmp_path, capsys) -> None:
        assert self._main(monkeypatch, tmp_path, capsys, self._summary(), []) == 0

    def test_a_budget_overrun_exits_one_not_two(self, monkeypatch, tmp_path, capsys) -> None:
        """The all-slow shape: exit 1 "this cap+timeout cannot carry this
        corpus" - loud and about the config, never the shrug of exit 2."""
        code = self._main(
            monkeypatch,
            tmp_path,
            capsys,
            self._summary(
                budget_overruns=2,
                outcomes={"OK": 2, "BUDGET": 2, "FAULT": 0},
            ),
            [],
        )
        assert code == 1
        assert "cannot carry" in capsys.readouterr().err

    def test_a_p95_over_s4_exits_one(self, monkeypatch, tmp_path, capsys) -> None:
        code = self._main(
            monkeypatch,
            tmp_path,
            capsys,
            self._summary(s4={"measured_p95_ms": 31_000, "target_p95_ms": 30_000, "within": False}),
            [],
        )
        assert code == 1
        assert "S4" in capsys.readouterr().err

    def test_the_cap_check_fails_only_for_a_real_violation(
        self, monkeypatch, tmp_path, capsys
    ) -> None:
        assert self._main(monkeypatch, tmp_path, capsys, self._summary(), ["--cap", "1024"]) == 0
        code = self._main(
            monkeypatch,
            tmp_path,
            capsys,
            self._summary(reply_tokens={"max": 1400}),
            ["--cap", "1024"],
        )
        assert code == 1
        assert "finding A" in capsys.readouterr().err, (
            "the failure must say WHY cutting below the tail is the bug"
        )

    def test_a_fault_starved_run_exits_two(self, monkeypatch, tmp_path, capsys) -> None:
        code = self._main(
            monkeypatch,
            tmp_path,
            capsys,
            self._summary(measured=False, outcomes={"OK": 0, "BUDGET": 0, "FAULT": 5}),
            [],
        )
        assert code == 2
        assert "INCONCLUSIVE" in capsys.readouterr().err

    def test_a_reasked_run_exits_one(self, monkeypatch, tmp_path, capsys) -> None:
        code = self._main(monkeypatch, tmp_path, capsys, self._summary(reasked_reps=1), [])
        assert code == 1
        assert "re-ask" in capsys.readouterr().err

    def test_build_pin_without_the_probe_is_refused_before_dialing(
        self, monkeypatch, tmp_path, capsys
    ) -> None:
        """--expect-build is read on the probe leg's /props. Silently
        accepting it with --no-probe would print a config block that
        pretends the build was pinned."""
        with pytest.raises(SystemExit) as caught:
            self._main(
                monkeypatch,
                tmp_path,
                capsys,
                self._summary(),
                ["--no-probe", "--expect-build", "b7972"],
            )
        assert "probe" in str(caught.value).lower()
