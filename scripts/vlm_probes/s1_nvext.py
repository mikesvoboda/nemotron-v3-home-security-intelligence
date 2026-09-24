#!/usr/bin/env python3
"""S-1: does the pinned llama.cpp build silently ignore the legacy ``nvext``
``_chat_format``/``guided_json`` params (design-spec E5), and does the NATIVE
``json_schema`` param get enforced on the text ``/completion`` route?

Two-arm CONTENT test - status codes carry no support information on this server
(one catch-all maps every parse exception to 400 invalid_request_error). Arm A
proves the server generates at all; arm B asks for a schema containing a fresh
uuid4 ``const`` the prompt never mentions - an echoed const proves grammar
enforcement, not parrotting. Three verdicts, never a silent pass:

  ENFORCED      B returned JSON whose probe_const equals the nonce
  IGNORED       A generated, B generated prose/JSON without the const
  INCONCLUSIVE  A failed, or B errored (wrong server / bad invocation)

Usage: uv run python scripts/vlm_probes/s1_nvext.py --base-url http://host.docker.internal:PORT
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

PROMPT = (
    "Describe this scene in one sentence: a delivery van parked on a quiet "
    "residential street, a person walking toward the front door.\n"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="e.g. http://host.docker.internal:18101")
    ap.add_argument("--expect-build", default=None, help="build_info substring to assert (e.g. b7972)")
    ap.add_argument("--report", default=None, help="optional path to write the JSON report")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    report: dict = {"probe": "S-1-nvext-vs-json-schema", "base_url": base}

    with httpx.Client(timeout=120.0) as c:
        # Precondition: identify the server. /props may not exist on very old pins.
        try:
            props = c.get(f"{base}/props").json()
        except Exception:
            props = {}
        build_info = props.get("build_info", "")
        report["build_info"] = build_info
        if args.expect_build and args.expect_build not in build_info:
            report["verdict"] = "INCONCLUSIVE"
            report["why"] = f"build_info {build_info!r} lacks {args.expect_build!r} - wrong server"
            return _finish(report, args.report)

        nonce = str(uuid.uuid4())
        schema = {
            "type": "object",
            "required": ["probe_const", "description"],
            "properties": {
                "probe_const": {"type": "string", "const": nonce},
                "description": {"type": "string"},
            },
        }

        # Arm A: plain generation. If this fails nothing else means anything.
        a = c.post(f"{base}/completion", json={"prompt": PROMPT, "n_predict": 96, "temperature": 0.1})
        a_text = (a.json().get("content") or "") if a.status_code == 200 else ""
        report["arm_a"] = {"status": a.status_code, "content": a_text[:400]}
        if a.status_code != 200 or not a_text.strip():
            report["verdict"] = "INCONCLUSIVE"
            report["why"] = "arm A (plain generation) failed - not measuring enforcement"
            return _finish(report, args.report)

        # Arm B1: nvext/guided_json legacy path (the E5 claim under test).
        b1 = c.post(
            f"{base}/completion",
            json={
                "prompt": PROMPT,
                "n_predict": 96,
                "temperature": 0.1,
                "nvext": {"guided_json": schema},
            },
        )
        b1_raw = (b1.json().get("content") or "") if b1.status_code == 200 else ""
        report["arm_b1_nvext"] = {"status": b1.status_code, "content": b1_raw[:400]}
        report["arm_b1_nvext"]["echoed_const"] = _const_ok(b1_raw, nonce)

        # Arm B2: native top-level json_schema (the mechanism spec §3 depends on).
        b2 = c.post(
            f"{base}/completion",
            json={"prompt": PROMPT, "n_predict": 96, "temperature": 0.1, "json_schema": schema},
        )
        b2_raw = (b2.json().get("content") or "") if b2.status_code == 200 else ""
        report["arm_b2_json_schema"] = {"status": b2.status_code, "content": b2_raw[:400]}
        report["arm_b2_json_schema"]["echoed_const"] = _const_ok(b2_raw, nonce)

    if report["arm_b2_json_schema"]["echoed_const"]:
        report["verdict"] = "ENFORCED"
    elif b2.status_code == 200:
        report["verdict"] = "IGNORED"
    else:
        report["verdict"] = "INCONCLUSIVE"
    # E5 is about b1 only; b1 ignoring nvext is the expected, spec-confirmed outcome.
    report["e5_nvext_ignored"] = not report["arm_b1_nvext"]["echoed_const"]
    return _finish(report, args.report)


def _const_ok(raw: str, nonce: str) -> bool:
    try:
        obj = json.loads(raw)
    except Exception:
        return False
    return isinstance(obj, dict) and obj.get("probe_const") == nonce


def _finish(report: dict, path: str | None) -> int:
    print(json.dumps(report, indent=2))
    if path:
        # Operator-supplied CLI path, resolved (never joined from request
        # data) - the resolve()+mkdir satisfies the repo's path-traversal
        # semgrep rule for report writers.
        out = Path(path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["verdict"] != "INCONCLUSIVE" else 2


if __name__ == "__main__":
    sys.exit(main())
