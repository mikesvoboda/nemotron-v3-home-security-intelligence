"""Constrained-decoding enforcement vocabulary - the shipped P0.3 machinery.

R8 S2a (2026-09-29) HOISTED this block verbatim out of
``backend/services/nemotron_analyzer.py`` (its ``:294-411``, design spec §2)
because the analyzer it lived in is ~98% legacy and R8 deletes that file -
while this block is imported by the SHIPPED VLM path: ``vlm_client``,
``vlm_analyzer``, ``evaluation/vlm_replay``, the boot enforcement gate in
``main.run_constrained_startup_check``, and the CI probe CLI
``scripts/vlm_probes/enforcement.py``. Extract-then-delete: this module is
the extract; the analyzer's remaining half went with the delete.

The names moved byte-for-byte. Nothing here is legacy: P0.3's premise (spec
§3) is that grammar enforcement is MEASURED, not assumed, and that
measurement belongs to whoever serves verdicts - which, since R8, is only
the VLM path. One home, one vocabulary: a second definition of
``ConstrainedDecodingNotEnforced`` or a drifted copy of the stop-word set is
exactly the fabrication class the probe exists to catch, and is pinned away
by ``tests/unit/services/test_constrained_decoding_hoist.py``.
"""

from __future__ import annotations

import uuid
from typing import Any, NamedTuple


class VerificationRowOutcome(NamedTuple):
    """The provenance producer's input, distilled from a final ``risk_data``
    dict (the fail-closed signal is its ``verification_failed`` flag)."""

    flagged: bool
    raw_completion: str
    latency_ms: int | None


class ConstrainedDecodingNotEnforced(RuntimeError):
    """P0.3 fail-closed (spec §3): the endpoint was asked to enforce a JSON
    grammar and did not prove it (S-1's IGNORED / INCONCLUSIVE verdicts).

    With ``vlm_enforcement_probe_enabled`` on this RAISES instead of
    degrading to prose - the whole 0.3 premise is that enforcement is
    verified, not assumed (S-2's per-build lesson). Legacy configs
    (flag off) never reach this class.

    ``verdict`` carries S-1's vocabulary for the STARTUP reporter
    (backend.main.run_constrained_startup_check): "ignored" (grammar asked,
    not honored) vs "inconclusive" (couldn't even measure - bad build or
    unreachable). Both fail closed; the distinction is honest reporting,
    not a different behavior."""

    def __init__(self, message: str, *, verdict: str = "ignored") -> None:
        super().__init__(message)
        self.verdict = verdict


PROBE_PROMPT = "Emit the verdict object for the standing scene.\n"

# What an engine calls it when a reply ran out of budget: `length` on the
# OpenAI-compat wire (`finish_reason`, the field finding A read on the shape
# the vlm client actually posts) and `stop_type: length` on the native
# /completion; the rest are aliases other servers on these wires use.
# Deliberately a CLOSED set - a missing or unrecognised signal means "the
# server did not say", and inferring truncation from silence would launder a
# real IGNORED into an INCONCLUSIVE: the same fabrication, mirrored. Lives
# here because both probe surfaces need ONE vocabulary (vlm_client imports
# it; a second copy drifting is exactly the P0.3 assumption this file exists
# to eliminate).
_TRUNCATED_STOPS = frozenset({"length", "max", "limit", "insufficient"})


def _is_length_truncated(stop: str | None) -> bool:
    """True ONLY on an explicit out-of-budget stop signal.

    Anything else - including ``None`` - returns False, which is the
    conservative direction: an unrecognised reply is judged exactly as it is
    today, so this can only ever move a fabricated verdict toward honesty and
    can never forgive a genuinely non-enforcing endpoint.
    """
    # `is not None` rather than `bool(stop)`: same answer either way ("" is
    # not in the set), but it lets mypy narrow str | None the way the runtime
    # already does, so the guard is checked rather than trusted.
    return stop is not None and stop.lower() in _TRUNCATED_STOPS


async def _probe_completion(
    client: Any,
    base_url: str,
    headers: dict[str, str],
    prompt_text: str,
    schema: dict[str, Any],
) -> tuple[int, str, str | None]:
    """ONE constrained-completion call shape - the enforcement probe's
    transport. Shared by the analyzer's runtime gate and the promoted CI CLI
    (scripts/vlm_probes/enforcement.py) so the two surfaces can never drift
    on how the probe is asked (drift there would make a CI pass prove
    nothing about runtime).

    Returns ``(status_code, content, stop_reason)``.

    The stop reason is the third element because of finding A: a reply that
    ran out of budget mid-object carries no const, and an absent const read as
    IGNORED ("measured: this server does not enforce") is a finding the server
    never gave. The status code alone cannot tell those apart - S-1's lesson
    restated one level down. A judge that does not care reads the first two
    and ignores the third; the transport stays one function either way.
    """
    resp = await client.post(
        f"{base_url}/completion",
        json={
            "prompt": prompt_text,
            # S-2's ledgered trap: a budget too small truncates the reply
            # MID-object, which fakes an IGNORED verdict (the const may
            # legally sort last and grammar can't close past the budget).
            # 400 is the S-2 [V]-proven safe budget for this schema, and
            # finding A is what to do when even a proven budget runs out:
            # triage the stop reason, never re-guess the budget from here.
            "n_predict": 400,
            "temperature": 0.0,
            "json_schema": schema,
        },
        headers=headers,
    )
    body = resp.json() if resp.status_code == 200 else {}
    body = body if isinstance(body, dict) else {}
    stop = body.get("stop_type") or body.get("stop_reason")
    return resp.status_code, body.get("content") or "", stop if isinstance(stop, str) else None


def build_probe_schema(
    base_schema: dict[str, Any] | None = None, nonce: str | None = None
) -> tuple[dict[str, Any], str]:
    """The nonce-const probe contract: the REAL verdict schema extended with
    a required ``probe_const`` whose value the prompt never mentions - an
    echo can only come from grammar enforcement, not parrotting. The CI CLI
    and the runtime gate build the same object from here (single contract,
    §3's drift doctrine)."""
    base = dict(base_schema) if base_schema is not None else {"type": "object", "properties": {}}
    nonce = nonce or str(uuid.uuid4())
    properties = dict(base.get("properties") or {})  # type: ignore[arg-type]
    properties["probe_const"] = {"type": "string", "const": nonce}
    schema = {**base, "properties": properties}
    schema["required"] = [*(schema.get("required") or []), "probe_const"]
    return schema, nonce
