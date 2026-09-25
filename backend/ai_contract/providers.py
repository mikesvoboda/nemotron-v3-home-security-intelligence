"""The provider registrations (WP8.1) - executed at import of this module.

Importing this module IS the contract check: if a provider stops covering a
declared operation, `import backend.ai_contract` raises ProviderContractError
naming the operation. That is the plan's Done-when, mechanized: adding an
operation to the registry without wiring the provider behind it - or
deleting the client method a provider is built from - fails at import, not
at the moment someone notices a hole in a hand-written Protocol.

The no-ai-at-runtime rule (see __init__.py) constrains HOW providers are
built, not that they may not exist:

  * gateway / gateway_light: ai/gateway/main.py is ONE app mounting every
    adapter (prefixes /yolo26 /clip /florence /enrichment /enrich-lt,
    ai/gateway/main.py:181-185); its availability column is exactly the ops
    its adapters implement. The gateway's backend-reachable behavior IS the
    bound client methods - the clients switch their base URL to the gateway
    under settings.use_ai_gateway - so a gateway provider callable is the
    bound client method itself.
  * per_model_http: the same client-bound callables dispatched through the
    native-host URLs; matrix-declared UNDEPLOYED in prod compose.
  * llamacpp_llm: llama.cpp serve speaks /completion and /chat/completions
    (OpenAI-compatible); the registry's ai/nemotron evidence marks exactly
    that pair, so the op set is DERIVED from evidence, not hand-listed, and
    passed as the provider's own `required` (one app inside the
    per_model_server union column).
  * fake: WP8.2's conformance app - NOT registered here; the fake column is
    a spec (all 38), and registering a fake that doesn't exist would repeat
    the AIServiceProtocol sin (docstring-implementers that aren't real).
"""

from __future__ import annotations

from typing import Any

from backend.ai_contract.operations import OPERATIONS
from backend.ai_contract.provider import (
    PROVIDER_SLOT,
    ProviderContractError,
    ProviderId,
    operations_for_slot,
    register_provider,
)

# Lazy module map: resolution runs inside register_provider at THIS module's
# import, by which time backend.services is importable. Top-level client
# imports here would run module-level settings/redis singletons before
# contract-test fixtures exist.
_CLIENT_MODULES = {
    "DetectorClient": "backend.services.detector_client",
    "CLIPClient": "backend.services.clip_client",
    "EnrichmentClient": "backend.services.enrichment_client",
    "FlorenceClient": "backend.services.florence_client",
}


def _not_wired(op_id: str) -> Any:
    """The NOT-WIRED sentinel (shared definition, two users: kept-deployed
    ops with client_methods==[] below, and the VLM engine subsets until
    vlm_client lands in 1.3). Registration still verifies slot membership
    and count, but no live path claims the callable; the call path belongs
    to the FakeProvider (WP8.2) or a live server. Fabricating a bound
    callable here would be another decorative contract."""

    async def _raise(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError(
            f"{op_id}: not wired to a client yet; "
            "drive it through the FakeProvider (WP8.2) or a live server"
        )

    return _raise


def _bound_or_reject(op_id: str) -> Any:
    """Resolve an operation's callable from the registry's own data.

    Census 2026-09-19: every op's client_methods is 0 or 1 entries - the
    two-method case is unreachable and fails LOUD rather than silently
    picking one. Ops with no bound client method (WP7.3 candidates kept as
    deployed surface: yolo26_detect_batch, yolo26_segment (A7.2 - client
    deleted, route stays), the enrich_lt_* trio; florence_analyze_scene
    left the contract entirely under A7.2) get a NOT-WIRED sentinel that
    raises on call:
    registration still verifies their slot membership and count, but no
    live path claims them. The call path is WP8.2 FakeProvider / real
    server territory - fabricating a bound callable here would be another
    decorative contract.
    """
    op = OPERATIONS[op_id]
    if len(op.client_methods) == 1:
        import importlib

        cls_name, meth = op.client_methods[0].split(".")
        module = importlib.import_module(_CLIENT_MODULES[cls_name])
        return getattr(getattr(module, cls_name), meth)
    if len(op.client_methods) == 0:
        return _not_wired(op_id)
    raise ProviderContractError(  # pragma: no cover - census says unreachable
        "registry",
        op_id,
        f"{len(op.client_methods)} client methods bound; provider derivation "
        "supports exactly 0 or 1 (census 2026-09-19: all 38 ops are 0 or 1)",
    )


def _llamacpp_required() -> set[str]:
    """Derive llama.cpp-serve's op set from the registry itself: LLM ops
    (llm_/path prefixes /completion, /chat/completions) whose evidence
    cites ai/nemotron and whose per_model_server column is True.
    llm_slots is evidence-backed llama.cpp surface but matrix-marked False
    in that column (performance_collector observation, not a client-routed
    operation) - so it correctly lands OUTSIDE. A registry rename that
    breaks this derivation turns the import into a named contract error."""
    return {
        op_id
        for op_id, op in OPERATIONS.items()
        if op.availability.get("per_model_server", False) and "ai/nemotron" in op.evidence
    }


def _llamacpp_callable(op_id: str) -> Any:
    """Payload passthrough POST to settings.nemotron_url (the llama.cpp
    serve endpoint; NemotronAnalyzer's own URL for the same app). No bound
    client_methods: the analyzer's payloads are prompt-shaped and its
    public surface is risk analysis, not raw completion - so completion
    conformance is dispatch, not a client method. Live path; the suite's
    deterministic counterpart is the FakeProvider (WP8.2)."""

    async def _post(payload: Any) -> Any:  # pragma: no cover - live path
        import httpx

        from backend.core.config import get_settings

        path = OPERATIONS[op_id].path
        timeout = httpx.Timeout(
            connect=get_settings().ai_connect_timeout, read=get_settings().nemotron_read_timeout
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{get_settings().nemotron_url.rstrip('/')}{path}", json=payload)
            r.raise_for_status()
            return r.json()

    return _post


def _register_all() -> None:
    for pid, deployed in (
        (ProviderId.GATEWAY, True),
        (ProviderId.GATEWAY_LIGHT, True),
        (ProviderId.PER_MODEL_HTTP, False),  # matrix-declared, undeployed in prod
    ):
        slot = PROVIDER_SLOT[pid]
        ops = {op_id: _bound_or_reject(op_id) for op_id in operations_for_slot(slot, OPERATIONS)}
        register_provider(pid, ops, OPERATIONS, deployed=deployed)
    llm_ops = _llamacpp_required()
    if len(llm_ops) < 2:
        raise ProviderContractError(
            ProviderId.LLAMACPP_LLM.value,
            sorted(llm_ops)[0] if llm_ops else "llm_completion",
            f"evidence-derived llama.cpp op set collapsed to {sorted(llm_ops)} - "
            "registry evidence changed shape; fix the derivation, not the assertion",
        )
    register_provider(
        ProviderId.LLAMACPP_LLM,
        {op_id: _llamacpp_callable(op_id) for op_id in llm_ops},
        OPERATIONS,
        deployed=True,
        required=llm_ops,
    )
    # spec §3 Slots: both VLM engines register required={"vlm_assess"} -
    # the llamacpp subset pattern inside the union per_model_server column.
    # 1.1 lands them with the not-wired sentinel (no client exists yet -
    # vlm_client is step 1.3); the call path drives the FakeProvider or a
    # live serve, and calling the sentinel raises naming it. deployed=False:
    # the ai-vlm compose service is step 1.2.
    for vlm_pid in (ProviderId.OPENAI_VLM, ProviderId.RTVI_VLM):
        register_provider(
            vlm_pid,
            {"vlm_assess": _not_wired("vlm_assess")},
            OPERATIONS,
            deployed=False,
            required={"vlm_assess"},
        )


_register_all()
