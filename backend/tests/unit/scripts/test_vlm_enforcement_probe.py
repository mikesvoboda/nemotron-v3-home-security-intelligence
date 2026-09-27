"""Pins for `scripts/vlm_probes/enforcement.py` (finding A's repair).

The probe is the line that decides whether constrained decoding is trusted at
all, and until finding A its judgement had a blind spot in ONE shape: a 200
whose reply was cut off by the token budget fails to parse, the const is
therefore absent, and the probe filed that as `IGNORED` - "measured: the
server does not enforce" - when it had measured nothing. Ledger finding A
measured the consequence on the shipped image: six scenes truncate at 400
tokens with `finish_reason: length`, three of the same four echo the const at
1200, so an under-budgeted probe can read a correctly enforcing endpoint as
not enforcing and eliminate a candidate over a budget.

So the pins here are about WHICH VERDICT WORD a shape earns, and the rule is
symmetric in both directions:

  * a length-limited stop is INCONCLUSIVE (nothing was measured) - never
    IGNORED, because that word is a finding about the server that the server
    never gave;
  * prose at a natural stop is still IGNORED - fail-closed is not weakened,
    a truncated reply never becomes a pass;
  * truncation is only claimed on an EXPLICIT length signal. A reply with no
    stop field at all stays IGNORED: inventing "truncated" without evidence
    is the same error pointed the other way;
  * an echo beats the budget - if the const arrived, the grammar produced it,
    which is the only question the probe asks.

Driven through an injected transport, the same shape
`test_vlm_tool_calls_probe.py` uses (load the CLI by path: `scripts/` is not
an importable package).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import httpx

_PROBE_PATH = Path(__file__).resolve().parents[4] / "scripts" / "vlm_probes" / "enforcement.py"


def _load_probe_module():
    assert _PROBE_PATH.exists(), f"missing probe CLI: {_PROBE_PATH}"
    spec = importlib.util.spec_from_file_location("vss_enforcement_cli", _PROBE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enf = _load_probe_module()

BUILD = "b7972-e06088da0"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _const_from(request: httpx.Request) -> str | None:
    """Read the nonce the probe actually put on the wire. A fake that
    hardcoded a const would pass even if the probe never sent one - the same
    reason tool_calls' probe pulls its nonce back out of the request."""
    body = json.loads(request.content)
    schema = (body.get("json_schema") or {}).get("properties", {}) or {}
    return (schema.get("probe_const") or {}).get("const")


def _fake_endpoint(mode: str):
    """A `/props` + `/completion` pair whose stop signal and content are set
    independently, because finding A is exactly the case where the two
    disagree: content without the const, and a stop that says WHY."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/props":
            return httpx.Response(200, json={"build_info": BUILD})

        const = _const_from(request)
        # The shape of each reply, per arm. `stop_type` is llama.cpp's
        # /completion field; `finish_reason` is the chat-completions one.
        if mode == "enforced":
            stop, content = "eos", json.dumps({"probe_const": const, "risk_level": "low"})
        elif mode == "ignored_prose":
            stop, content = "eos", "A person walks up the driveway."
        elif mode == "truncated":
            # Mid-object, no const: the reply finding A measured at 400 tokens.
            stop, content = "length", '{"risk_level": "me'
        elif mode == "truncated_with_const":
            # Hit the limit AND produced the const first - the grammar did its
            # job, so the budget is irrelevant to THIS question.
            stop, content = "length", json.dumps({"probe_const": const})
        elif mode == "no_stop_signal":
            # A server that reports no stop field at all: the probe cannot
            # claim truncation it has no evidence for.
            stop, content = None, '{"risk_level": "me'
        else:  # pragma: no cover - guard against a typo'd arm reading as a verdict
            raise AssertionError(f"unknown fake mode {mode!r}")

        payload: dict[str, Any] = {"content": content, "tokens_predicted": 400}
        if stop is not None:
            payload["stop_type"] = stop
        return httpx.Response(200, json=payload)

    return handler


class TestSurface:
    def test_the_cli_has_the_probe_contract(self) -> None:
        for attr in ("run_probe", "main"):
            assert hasattr(enf, attr), f"scripts/vlm_probes/enforcement.py lacks {attr}()"


class TestTruncationIsNotIgnored:
    async def test_a_length_limited_stop_is_inconclusive_never_ignored(self) -> None:
        """The finding-A pin. `IGNORED` is a statement about the server's
        grammar; a truncated reply licenses no such statement. Fail-closed is
        untouched - INCONCLUSIVE still exits 1 and still refuses to score."""
        async with _client(_fake_endpoint("truncated")) as client:
            out = await enf.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "INCONCLUSIVE"
        assert out["verdict"] != "IGNORED"
        assert out["build_info"] == BUILD  # the build WAS read; only the verdict is undetermined

    async def test_the_truncation_says_so_rather_than_hiding_behind_a_generic_why(
        self,
    ) -> None:
        """A report that says "could not measure" without naming the budget
        sends the operator to debug the model. The reason must be findable."""
        async with _client(_fake_endpoint("truncated")) as client:
            out = await enf.run_probe("http://x:1/", client=client)
        blob = json.dumps(out).lower()
        assert "truncat" in blob or "budget" in blob, out

    async def test_prose_at_a_natural_stop_is_still_ignored(self) -> None:
        """The other half, and the one that keeps fail-closed honest: a
        complete reply without the const IS the E5-class evidence and must
        stay IGNORED. Truncation-aware triage that also forgave prose would
        be a downgrade of the probe, not a repair of it."""
        async with _client(_fake_endpoint("ignored_prose")) as client:
            out = await enf.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "IGNORED"

    async def test_no_stop_field_is_not_invented_truncation(self) -> None:
        """Claiming "truncated" without a length signal would launder a real
        IGNORED into an INCONCLUSIVE - the same fabrication, mirrored."""
        async with _client(_fake_endpoint("no_stop_signal")) as client:
            out = await enf.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "IGNORED"

    async def test_an_echo_beats_the_budget(self) -> None:
        """The probe asks one question: did the grammar produce a value the
        prompt never contained? If it did, a stop reason is not evidence
        against enforcement - and this must not become a new way to lose a
        real ENFORCED."""
        async with _client(_fake_endpoint("truncated_with_const")) as client:
            out = await enf.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "ENFORCED"


class TestEnforcementStillWorks:
    async def test_a_const_echo_is_enforced(self) -> None:
        async with _client(_fake_endpoint("enforced")) as client:
            out = await enf.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "ENFORCED"
        assert out["build_info"] == BUILD

    def test_every_non_enforced_verdict_exits_nonzero(self, monkeypatch) -> None:
        """Exit 0 belongs to ENFORCED alone: CI fails closed on INCONCLUSIVE
        too, so renaming a truncation away from IGNORED cannot turn a red
        probe green. SYNC on purpose - main() drives its own asyncio.run, so
        an async test would collide with the runner's loop and prove nothing."""

        async def fake_run_probe(url: str, **kw) -> dict[str, Any]:
            return fake_run_probe.out  # type: ignore[attr-defined]

        monkeypatch.setattr(enf, "run_probe", fake_run_probe)
        for verdict in ("IGNORED", "INCONCLUSIVE"):
            fake_run_probe.out = {"verdict": verdict}  # type: ignore[attr-defined]
            assert enf.main(["--url", "http://x"]) == 1, f"{verdict} must not exit 0"

    async def test_the_verdict_vocabulary_stays_three_words(self) -> None:
        """2.2.5 prints one line per candidate, and the Brev checklist reads
        the same words - a fourth verdict would not compare. Truncation rides
        as a REASON inside INCONCLUSIVE, never as a new verdict."""
        allowed = {"ENFORCED", "IGNORED", "INCONCLUSIVE"}
        seen = []
        for mode in ("enforced", "ignored_prose", "truncated", "truncated_with_const"):
            async with _client(_fake_endpoint(mode)) as client:
                out = await enf.run_probe("http://x:1/", client=client)
            seen.append(out["verdict"])
        assert set(seen) <= allowed, seen
        # and the four shapes were not all flattened into one word
        assert set(seen) == {"ENFORCED", "IGNORED", "INCONCLUSIVE"}, seen
