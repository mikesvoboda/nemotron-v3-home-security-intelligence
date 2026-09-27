#!/usr/bin/env python3
"""R3: does this llama.cpp endpoint actually TOOL-CALL, or only accept the
``tools`` parameter?

The spec's R3 line is that llama.cpp stays the agent-capable engine, so the
bake-off owes one measured answer per candidate. Built like
``enforcement.py``, on the one rule that page's whole existence teaches (S-1,
[V], from E5): **the status code carries no support information.** A server
that ignores ``tools`` answers 200 with prose, and a prose answer looks fine
in a log. So this asks for a tool call that is the ONLY sensible reply, then
judges the parsed body.

Arms (``/v1/chat/completions``; ``--image`` adds the multimodal intersection,
which is the shape the vlm path would actually use — S-2's lesson is that the
independent variables' INTERSECTION is what must be proven, not each alone):

  preflight  read /props build_info. With --expect-build, a mismatch is ERROR
             BEFORE any request (S-2: a proof from another build launders).
  A          tools=[report_token(token: string, required)], prompt supplies a
             fresh uuid4 the reply can only get by calling the tool.
             -> tool_calls present, name matches, arguments parse, and the
                token equals the nonce => SUPPORTED
             -> tool_calls present but arguments lack/misfill `token` =>
                REQUIRED_ARG_DROPPED: the schema was accepted, its required
                key was not honoured.
             -> no tool_calls at all (prose, or a code block) => IGNORED
  B          strict:true on the same tool, same nonce. A strict-mode server
             that genuinely validates answers differently from a permissive
             one; reporting both is how a candidate that only works in
             permissive mode shows up as that, rather than as "tool calling
             works".

Verdicts: SUPPORTED / IGNORED / ERROR (the plan's vocabulary, so R3's answer is
comparable across candidates), plus `required_arg_honoured` and
`strict_arm_supported` — the plan's second question, kept OUT of the verdict so
a candidate that calls but drops the required argument is visible as exactly
that, rather than as a fourth verdict. Exit 0 requires BOTH the call and the
argument, because the capability R3 guards is "an agent could use this", and a
call with no arguments is not that. Fail closed otherwise.

    uv run python scripts/vlm_probes/tool_calls.py \
        --url http://host.docker.internal:<port> --expect-build b7972 \
        --image some-synthetic.png
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PROBE_TIMEOUT_SECONDS = 60.0
TOOL_NAME = "report_token"


def _build_info_text(raw: Any) -> str:
    """normalize /props build_info: a plain string on llama.cpp pins, but
    tolerate a structured dict so a different server shape cannot fake a build
    match by str() weirdness (same reason enforcement.py does this)."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return " ".join(str(v) for v in raw.values())
    return str(raw or "")


def _tool_schema(*, strict: bool) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {"token": {"type": "string", "description": "The token from the prompt."}},
        "required": ["token"],
    }
    if strict:
        # strict mode forbids additionalProperties in OpenAI's grammar; it is
        # sent on arm B and judged by behaviour, never by acceptance.
        schema["additionalProperties"] = False
    tool: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": "Report the token exactly as given in the prompt.",
            "parameters": schema,
        },
    }
    if strict:
        tool["function"]["strict"] = True
    return tool


def _content_parts(image_data_uri: str | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if image_data_uri:
        # data URI only - a remote URL would be an SSRF surface and
        # nondeterministic (the same rule s2_multimodal_schema.py follows).
        parts.append({"type": "image_url", "image_url": {"url": image_data_uri}})
    return parts


def _verdict(**fields: Any) -> dict[str, Any]:
    return {"probe": "tool_calls", **fields}


def _judge(body: dict[str, Any], nonce: str) -> tuple[str, dict[str, Any]]:
    """The whole probe: parse the reply and decide. Never the status code.

    Returns (arm_verdict, evidence). arm_verdict is one of
    SUPPORTED / REQUIRED_ARG_DROPPED / IGNORED.
    """
    choices = body.get("choices") or []
    if not choices:
        return "IGNORED", {"why": "reply carries no choices"}
    msg = choices[0].get("message") or {}
    calls = msg.get("tool_calls") or []
    if not calls:
        # The E5 shape, generalized: parameter accepted, behaviour absent.
        return "IGNORED", {
            "finish_reason": choices[0].get("finish_reason"),
            "content_head": str(msg.get("content") or "")[:200],
            "why": "no tool_calls in the reply - `tools` accepted, not honoured",
        }
    first = calls[0]
    fn = first.get("function") or {}
    name = fn.get("name")
    raw_args = fn.get("arguments")
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except Exception:
        args = None
    evidence = {
        "finish_reason": choices[0].get("finish_reason"),
        "tool_name": name,
        "arguments_raw": raw_args if isinstance(raw_args, str) else args,
        "n_tool_calls": len(calls),
    }
    if name != TOOL_NAME:
        return "REQUIRED_ARG_DROPPED", {**evidence, "why": f"called {name!r}, not {TOOL_NAME!r}"}
    if not isinstance(args, dict) or "token" not in args:
        return "REQUIRED_ARG_DROPPED", {
            **evidence,
            "why": "the tool was called but the REQUIRED `token` argument is "
            "absent or the arguments are not a JSON object",
        }
    if args["token"] != nonce:
        # The nonce is in the prompt, so a wrong value is a real (if odd)
        # answer; it still fails the const contract the enforcement probe
        # established, because only the call itself is proof.
        return "REQUIRED_ARG_DROPPED", {
            **evidence,
            "why": "`token` present but not the prompted nonce - the argument "
            "was not carried through the schema",
        }
    return "SUPPORTED", evidence


async def run_probe(
    url: str,
    *,
    expect_build: str | None = None,
    api_key: str | None = None,
    image_data_uri: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """One tool-calling probe against ``url`` (base URL, no trailing path).

    ``client`` is the transport seam: tests pass an httpx.MockTransport-backed
    client, so the JUDGEMENT is unit-tested without a GPU (the real endpoint's
    answer is the ledger row, not a test).
    """
    base = url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS)
    try:
        try:
            props = await client.get(f"{base}/props", headers=headers)
            build_info = _build_info_text((props.json() or {}).get("build_info"))
        except Exception as exc:
            return _verdict(
                verdict="ERROR",
                why=f"could not read /props build_info ({exc!r}) while "
                f"--expect-build={expect_build!r} is pinned",
            )
        if expect_build and expect_build not in build_info:
            return _verdict(
                verdict="ERROR",
                build_info=build_info,
                why=f"build_info lacks pinned {expect_build!r} - tool support "
                "varies by build and by chat template; probing completions here "
                "would launder a proof from a different server",
            )

        arms: dict[str, Any] = {}
        for arm, strict in (("permissive", False), ("strict", True)):
            nonce = str(uuid.uuid4())
            text = (
                f"Call the {TOOL_NAME} tool now with token={nonce}. "
                "Do not answer in prose; only the tool call is correct."
            )
            body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            *_content_parts(image_data_uri),
                            {"type": "text", "text": text},
                        ],
                    }
                ],
                "tools": [_tool_schema(strict=strict)],
                "temperature": 0.0,
                "max_tokens": 200,
            }
            try:
                resp = await client.post(f"{base}/v1/chat/completions", json=body, headers=headers)
            except Exception as exc:
                arms[arm] = {"verdict": "ERROR", "why": f"request failed: {exc!r}"}
                continue
            if resp.status_code != 200:
                # ERROR, not IGNORED: a 4xx/5xx is "could not measure", and
                # calling it UNSUPPORTED would be a finding the server never
                # gave (the same arm-A/verdict separation s2 keeps).
                arms[arm] = {
                    "verdict": "ERROR",
                    "status": resp.status_code,
                    "body_head": resp.text[:200],
                    "why": f"HTTP {resp.status_code} - not measurable",
                }
                continue
            try:
                parsed = resp.json()
            except Exception as exc:
                arms[arm] = {"verdict": "ERROR", "why": f"reply is not JSON: {exc!r}"}
                continue
            verdict, evidence = _judge(parsed, nonce)
            arms[arm] = {"verdict": verdict, **evidence}

        permissive = arms["permissive"]["verdict"]
        strict_v = arms["strict"]["verdict"]
        measured = [v for v in (permissive, strict_v) if v != "ERROR"]
        if not measured:
            # Nothing was measurable. Calling that IGNORED would be a finding
            # the server never gave - the same arm-A/verdict separation s2
            # keeps ("never 'unsupported' on a bad A").
            overall = "ERROR"
        elif "SUPPORTED" in measured:
            overall = "SUPPORTED"
        elif "REQUIRED_ARG_DROPPED" in measured:
            # It did call, but the required argument did not survive. R3's
            # question is "can it tool-call", so this IS a call - reported
            # with the defect beside it, never rounded to IGNORED.
            overall = "SUPPORTED"
        else:
            overall = "IGNORED"
        return _verdict(
            verdict=overall,
            build_info=build_info,
            arms=arms,
            multimodal=bool(image_data_uri),
            # The plan's second question, kept OUT of the verdict vocabulary
            # so R3's answer stays comparable across candidates: did the
            # required `token` argument actually arrive? None = never got far
            # enough to ask.
            required_arg_honoured=(
                any(arms[a]["verdict"] == "SUPPORTED" for a in ("permissive", "strict"))
                if measured
                else None
            ),
            strict_arm_verdict=strict_v if strict_v != "ERROR" else None,
            why={
                "SUPPORTED": "at least one arm produced the named tool call "
                "(see `required_arg_honoured` for whether its argument "
                "survived the schema)",
                "IGNORED": "`tools` accepted, no tool_calls in any measured reply",
                "ERROR": "no arm could be measured",
            }[overall],
        )
    finally:
        if own_client:
            await client.aclose()


def _image_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True, help="endpoint base URL, e.g. http://host:8080")
    ap.add_argument(
        "--expect-build",
        default=None,
        help="substring /props build_info must contain (e.g. b7972); "
        "a mismatch is ERROR before any request",
    )
    ap.add_argument("--api-key", default=None, help="bearer token if the endpoint has one")
    ap.add_argument(
        "--image",
        default=None,
        type=Path,
        help="synthetic still to attach (probes the multimodal+tools "
        "intersection the vlm path would use); synthetic only",
    )
    args = ap.parse_args(argv)

    result = asyncio.run(
        run_probe(
            args.url,
            expect_build=args.expect_build,
            api_key=args.api_key,
            image_data_uri=_image_data_uri(args.image) if args.image else None,
        )
    )
    print(json.dumps(result, indent=2))
    # 0 only when the endpoint both CALLED and CARRIED THE ARGUMENT. The
    # verdict stays in the plan's three-word vocabulary for comparability, so
    # the gate lives here rather than in a fourth verdict: R3 asks whether an
    # agent could use this endpoint, and a call with no arguments is not that.
    ok = result["verdict"] == "SUPPORTED" and result["required_arg_honoured"] is True
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
