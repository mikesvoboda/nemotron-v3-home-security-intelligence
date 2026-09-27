"""Pins for `scripts/vlm_probes/tool_calls.py` (Phase 2, task 2.2.1).

The probe is the line that keeps R3 open or closes it per candidate, so the
part under test is its JUDGEMENT, not a GPU. Every test drives `run_probe`
through an injected `httpx.MockTransport` — the same shape
`test_p03_constrained_verdict.py` uses for `enforcement.py` (load the CLI by
path: `scripts/` is not an importable package).

The pins that matter are the ones a convenient implementation would break:
a 200-with-prose is IGNORED and never a pass (S-1: the status code carries no
support information — the whole reason `enforcement.py` exists); a 5xx is
ERROR and never IGNORED (that would be a finding the server never gave); and
a call whose required argument did not survive is visible as itself, not
rounded up to SUPPORTED.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

_PROBE_PATH = Path(__file__).resolve().parents[4] / "scripts" / "vlm_probes" / "tool_calls.py"


def _load_probe_module():
    assert _PROBE_PATH.exists(), f"missing probe CLI: {_PROBE_PATH}"
    spec = importlib.util.spec_from_file_location("vss_tool_calls_cli", _PROBE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tc = _load_probe_module()

BUILD = "b7972-e06088da0"


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_transport(handler))


def _props_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/props":
        return httpx.Response(200, json={"build_info": BUILD})
    return httpx.Response(404)


def _completion_handler(reply: dict[str, Any], *, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/props":
            return httpx.Response(200, json={"build_info": BUILD})
        return httpx.Response(status, json=reply)

    return handler


def _call_reply(nonce: str, *, name: str = "report_token", args: dict[str, Any] | None = None):
    payload = {"token": nonce} if args is None else args
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(payload),
                            },
                        }
                    ],
                },
            }
        ]
    }


def _prose_reply() -> dict[str, Any]:
    """The E5 shape generalized: 200, plausible, and no tool call at all."""
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "A person walks up."},
            }
        ]
    }


def _nonce_from(request: httpx.Request) -> str:
    """Pull the nonce back out of the request the probe built, so the fake's
    answer is the value the probe actually asked for (a test that hardcoded a
    nonce would pass even if the probe never sent one)."""
    body = json.loads(request.content)
    text = body["messages"][0]["content"][-1]["text"]
    return text.split("token=")[1].split(".")[0]


class TestSurface:
    def test_the_cli_has_the_probe_contract(self) -> None:
        for attr in ("run_probe", "main", "_judge"):
            assert hasattr(tc, attr), f"scripts/vlm_probes/tool_calls.py lacks {attr}()"


class TestJudgement:
    async def test_a_real_call_is_supported(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(200, json={"build_info": BUILD})
            nonce = _nonce_from(request)
            seen.append(nonce)
            return httpx.Response(200, json=_call_reply(nonce))

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "SUPPORTED"
        assert out["required_arg_honoured"] is True
        assert out["strict_arm_verdict"] == "SUPPORTED"
        assert out["build_info"] == BUILD
        # each arm asks with its OWN nonce, so a cached reply cannot pass twice
        assert len(seen) == 2 and seen[0] != seen[1]

    async def test_prose_at_200_is_ignored_never_a_pass(self) -> None:
        """S-1 [V]: the status code carries no support information. This is the
        one response shape that a logging-only probe would call success."""
        async with _client(_completion_handler(_prose_reply())) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "IGNORED"
        assert out["required_arg_honoured"] is False
        assert "no tool_calls" in out["arms"]["permissive"]["why"]

    async def test_a_call_that_drops_the_required_argument_is_visible_as_that(
        self,
    ) -> None:
        """R3's answer is comparable across candidates ONLY if the verdict
        vocabulary stays the plan's three words, so the defect rides in its own
        field instead of becoming a fourth verdict — and exit 0 still refuses."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(200, json={"build_info": BUILD})
            seen.append(_nonce_from(request))
            return httpx.Response(200, json=_call_reply(seen[-1], args={"other": "x"}))

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "SUPPORTED"  # it DID call
        assert out["required_arg_honoured"] is False  # and it did NOT carry
        assert "REQUIRED" in out["arms"]["permissive"]["why"]

    def test_the_exit_code_refuses_a_call_without_the_argument(self, monkeypatch) -> None:
        """The capability R3 guards is "an agent could use this", so a call
        whose argument did not survive must not exit 0 — even though its
        verdict is the comparable word SUPPORTED. The gate lives in the exit
        code, which is why the verdict stays three words."""

        async def fake_run_probe(url: str, **kw) -> dict[str, Any]:
            return {
                "verdict": "SUPPORTED",
                "required_arg_honoured": False,
                "arms": {},
            }

        monkeypatch.setattr(tc, "run_probe", fake_run_probe)
        assert tc.main(["--url", "http://x"]) == 1

    def test_the_exit_code_passes_only_on_a_call_with_the_argument(self, monkeypatch) -> None:
        async def fake_run_probe(url: str, **kw) -> dict[str, Any]:
            return {
                "verdict": "SUPPORTED",
                "required_arg_honoured": True,
                "arms": {},
            }

        monkeypatch.setattr(tc, "run_probe", fake_run_probe)
        assert tc.main(["--url", "http://x"]) == 0

    async def test_the_wrong_tool_name_is_not_a_pass(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(200, json={"build_info": BUILD})
            return httpx.Response(200, json=_call_reply("ignored", name="weather"))

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["required_arg_honoured"] is False
        assert out["arms"]["permissive"]["verdict"] == "REQUIRED_ARG_DROPPED"

    async def test_arguments_that_are_not_json_are_reported_not_swallowed(
        self,
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(200, json={"build_info": BUILD})
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "report_token",
                                            "arguments": "{not json",
                                        }
                                    }
                                ]
                            },
                        }
                    ]
                },
            )

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["required_arg_honoured"] is False
        assert out["arms"]["permissive"]["verdict"] == "REQUIRED_ARG_DROPPED"


class TestErrorIsNotUnsupported:
    async def test_a_5xx_is_error_not_ignored(self) -> None:
        """Calling an unmeasurable endpoint IGNORED would be a finding the
        server never gave - it would close R3 with a 502."""
        async with _client(_completion_handler({}, status=502)) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "ERROR"
        assert out["arms"]["permissive"]["status"] == 502
        assert out["required_arg_honoured"] is None  # never got far enough to ask

    async def test_a_build_mismatch_refuses_before_any_completion(self) -> None:
        """S-2: tool support varies by build AND chat template, so a proof from
        another server launders. Count the requests: none may reach completions."""
        hits: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hits.append(request.url.path)
            return httpx.Response(200, json={"build_info": "b0000-old"})

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", expect_build="b7972", client=client)
        assert out["verdict"] == "ERROR"
        assert hits == ["/props"], "a build mismatch must not probe completions"

    async def test_an_unreachable_props_is_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", expect_build="b7972", client=client)
        assert out["verdict"] == "ERROR"
        assert "build_info" in out["why"]


class TestRequestShape:
    """The judgement only means something if the REQUEST is the one R3 asks
    about - so the request body is pinned too, not just the reply handling."""

    async def test_arms_differ_only_by_strict(self) -> None:
        bodies: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(200, json={"build_info": BUILD})
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json=_call_reply(_nonce_from(request)))

        async with _client(handler) as client:
            await tc.run_probe("http://x:1/", client=client)
        assert len(bodies) == 2
        permissive, strict = bodies
        assert permissive["tools"][0]["function"].get("strict") is None
        assert strict["tools"][0]["function"]["strict"] is True
        # the required-argument claim is IN the schema both arms send
        for b in bodies:
            params = b["tools"][0]["function"]["parameters"]
            assert params["required"] == ["token"]
        # temperature 0: a probe that varies cannot be re-run for comparison
        assert {b["temperature"] for b in bodies} == {0.0}

    async def test_the_image_makes_it_a_multimodal_probe(self) -> None:
        """S-2's lesson: the intersection is what must be proven. Without this
        the bake-off would claim tool calling on the text shape and deploy on
        the image shape."""
        bodies: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(200, json={"build_info": BUILD})
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json=_call_reply(_nonce_from(request)))

        uri = "data:image/png;base64,AAAA"
        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", image_data_uri=uri, client=client)
        assert out["multimodal"] is True
        assert bodies[0]["messages"][0]["content"][0] == {
            "type": "image_url",
            "image_url": {"url": uri},
        }

    async def test_a_wrong_nonce_is_not_const_proof(self) -> None:
        """The const contract, imported from enforcement.py's doctrine: the
        value must be CARRIED, so a reply that calls the right tool with a
        plausible-but-different token is not proof of anything."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/props":
                return httpx.Response(200, json={"build_info": BUILD})
            # a fresh uuid: a real token, the WRONG one
            return httpx.Response(200, json=_call_reply(str(uuid.uuid4())))

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["verdict"] == "SUPPORTED"  # it called
        assert out["required_arg_honoured"] is False  # it did not carry THE token
        assert "nonce" in out["arms"]["permissive"]["why"]

    @pytest.mark.parametrize("reply", ["call", "prose", "boom"])
    async def test_the_verdict_is_always_one_of_the_plans_three_words(self, reply: str) -> None:
        """2.2.1 names exactly SUPPORTED / IGNORED / ERROR, because 2.2.5 prints
        one line per candidate and a fourth word would not compare. Every
        measurable and unmeasurable path must land inside the vocabulary."""
        if reply == "call":

            def handler(request: httpx.Request) -> httpx.Response:
                if request.url.path == "/props":
                    return httpx.Response(200, json={"build_info": BUILD})
                return httpx.Response(200, json=_call_reply(_nonce_from(request)))

        elif reply == "prose":
            handler = _completion_handler(_prose_reply())
        else:
            handler = _completion_handler({}, status=502)

        async with _client(handler) as client:
            out = await tc.run_probe("http://x:1/", client=client)
        assert out["verdict"] in {"SUPPORTED", "IGNORED", "ERROR"}
        # and the arm detail that explains it is always present
        assert set(out["arms"]) == {"permissive", "strict"}
