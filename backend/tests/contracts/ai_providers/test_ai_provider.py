"""WP8.1: the declared AIProvider interface + import-time contract checks.

Plan P WP8.1 Done-when, executed literally: "adding a provider that omits a
declared operation fails a test AT IMPORT TIME, naming the operation."
Registration is what import does; these tests drive the same
register_provider() the providers module calls at import, with deliberately
broken stubs, and require ProviderContractError to name the operation.

The check is inspect.signature-based, not attribute-presence-based:
presence is exactly what let AIServiceProtocol rot (see the DECIDE test at
the bottom - the protocol is removed, not repaired).
"""

import pytest
from backend.ai_contract.operations import OPERATIONS
from backend.ai_contract.provider import (
    PROVIDER_SLOT,
    AIProvider,
    ProviderContractError,
    ProviderId,
    operations_for_slot,
    register_provider,
    registered_providers,
)


def _async_op(payload, *, params=None):
    async def _call(payload, *, params=None):
        return {"op": "stub"}

    return _call


def _provider_ops(provider_id: ProviderId) -> dict:
    """The full declared op set for a single-app provider slot, as async stubs."""
    slot = PROVIDER_SLOT[provider_id]
    return {op_id: _async_op(None) for op_id in operations_for_slot(slot, OPERATIONS)}


class TestProviderContract:
    def test_registered_providers_satisfy_the_protocol(self) -> None:
        """runtime_checkable presence check - cheap identity, not the
        conformance mechanism (the signature checks below are)."""
        providers = registered_providers()
        assert providers, "no providers registered at import of backend.ai_contract"
        for pid, rec in providers.items():
            assert isinstance(rec, AIProvider), f"{pid} is not an AIProvider"
            ops = rec.operations()
            assert all(callable(fn) for fn in ops.values())

    def test_gateway_provider_covers_gateway_slot(self) -> None:
        """The gateway is a single app (ai/gateway/main.py mounts every
        adapter): its declared set must equal the gateway column - 31 ops."""
        rec = registered_providers()["gateway"]
        required = set(operations_for_slot("gateway", OPERATIONS))
        assert set(rec.operations()) == required

    def test_gateway_light_provider_covers_its_slot(self) -> None:
        rec = registered_providers()["gateway_light"]
        assert set(rec.operations()) == set(
            operations_for_slot("enrichment_light_adapter", OPERATIONS)
        )

    def test_llamacpp_provider_declares_only_llm_ops(self) -> None:
        """The per_model_server column is the UNION across per-model servers;
        llamacpp is one app in it. Its declared set is its own subset -
        registration must reject ops the matrix marks unavailable for its
        slot, and accept exactly the LLM pair."""
        rec = registered_providers()["llamacpp_llm"]
        assert set(rec.operations()) == {"llm_completion", "llm_chat_completion"}

    def test_per_model_http_declares_undeployed_36(self) -> None:
        """per-model-http is matrix-declared UNDEPLOYED (plan); its op set is
        the whole per_model_server column (36), dispatched by URL prefix."""
        rec = registered_providers()["per_model_http"]
        assert rec.deployed is False
        assert set(rec.operations()) == set(operations_for_slot("per_model_server", OPERATIONS))

    def test_missing_operation_fails_at_registration_naming_it(self) -> None:
        """The Done-when. Drop one gateway op; registration must raise and
        the message must name it. Failed registration never stores anything,
        so the live gateway provider is untouched regardless of test order
        (pytest-randomly)."""
        ops = _provider_ops(ProviderId.GATEWAY)
        dropped = "yolo26_detect"
        del ops[dropped]
        with pytest.raises(ProviderContractError) as excinfo:
            register_provider(ProviderId.GATEWAY, ops, OPERATIONS)
        assert excinfo.value.operation_id == dropped
        assert dropped in str(excinfo.value)

    def test_missing_operation_error_names_the_missing_op(self) -> None:
        """Sharper form: full light set minus one, registered as light -
        the error must name exactly the dropped operation."""
        ops = _provider_ops(ProviderId.GATEWAY_LIGHT)
        dropped = "enrich_lt_pet_classify"
        del ops[dropped]
        with pytest.raises(ProviderContractError) as excinfo:
            register_provider(ProviderId.GATEWAY_LIGHT, ops, OPERATIONS)
        assert excinfo.value.operation_id == dropped

    def test_sync_callable_rejected_by_signature_check(self) -> None:
        """inspect.signature over presence: every operation is an HTTP round
        trip; a sync def would block the event loop in real clients. Presence
        checks pass this; the contract check must not."""

        def sync_op(payload, *, params=None):
            return {}

        ops = _provider_ops(ProviderId.GATEWAY_LIGHT)
        victim = sorted(ops)[0]
        ops[victim] = sync_op
        with pytest.raises(ProviderContractError) as excinfo:
            register_provider(ProviderId.GATEWAY_LIGHT, ops, OPERATIONS)
        assert excinfo.value.operation_id == victim

    def test_positional_only_signature_rejected(self) -> None:
        """Signature drift the presence checks miss: the conformance driver
        dispatches payload fields as keyword args. A client refactor that
        makes a parameter POSITIONAL-ONLY (adds `/`) silently un-drives the
        whole suite for that op - inspect.signature catches it at
        registration. (The uniform fn(payload) shape belongs to the
        FakeProvider, WP8.2; client-bound callables keep their real
        signatures, so payload-binding is not what's pinned here.)"""

        async def positional_only(payload, /):
            return {}

        ops = _provider_ops(ProviderId.GATEWAY_LIGHT)
        victim = sorted(ops)[0]
        ops[victim] = positional_only
        with pytest.raises(ProviderContractError) as excinfo:
            register_provider(ProviderId.GATEWAY_LIGHT, ops, OPERATIONS)
        assert excinfo.value.operation_id == victim
        assert "positional-only" in str(excinfo.value)

    def test_invented_operation_id_rejected(self) -> None:
        ops = _provider_ops(ProviderId.GATEWAY_LIGHT)
        ops["gateway_teleport"] = _async_op(None)
        with pytest.raises(ProviderContractError) as excinfo:
            register_provider(ProviderId.GATEWAY_LIGHT, ops, OPERATIONS)
        assert excinfo.value.operation_id == "gateway_teleport"


class TestAIServiceProtocolDecide:
    """WP8.1 DECIDE (recorded in PR + ledger): DEPRECATE, not repair.

    Evidence (census 2026-09-19): zero implementers, zero consumers outside
    the re-export; of its three NAMED implementers the docstrings claim
    ("Implements AIServiceProtocol"), DetectorClient/NemotronAnalyzer expose
    1 of 3 members (health_check) and EnrichmentClient 0 of 3 - the protocol
    rotted precisely because attribute presence was never verified against
    a real contract. A Protocol nothing implements is worse than none, and
    the decorative one must not survive: it is removed. Its replacement for
    AI-tier typing is this package's AIProvider, built from deployed
    surfaces.
    """

    def test_protocol_removed_from_core(self) -> None:
        from backend.core import protocols

        assert not hasattr(protocols, "AIServiceProtocol")
        assert not hasattr(protocols, "AIServiceWithLifecycle")
        assert "AIServiceProtocol" not in protocols.__all__

    def test_no_lingering_imports_in_python(self) -> None:
        """Nothing may still BIND the removed names - the explanatory DECIDE
        notes elsewhere legitimately NAME them (docstrings are constants;
        the AST scan cannot see them, which is exactly the point). Code
        references would AttributeError at runtime now that the class is
        gone. AST precedent in this suite: _public_client_methods()."""
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        names = {"AIServiceProtocol", "AIServiceWithLifecycle"}
        hits = []
        for py in (root / "backend").rglob("*.py"):
            if "tests" in py.parts:
                continue  # this file's own census prose is allowed
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                bound = None
                if isinstance(node, ast.ImportFrom):
                    bound = next((a.asname or a.name for a in node.names if a.name in names), None)
                elif isinstance(node, ast.Name) and node.id in names:
                    bound = node.id
                elif isinstance(node, ast.Attribute) and node.attr in names:
                    bound = node.attr
                if bound:
                    hits.append(f"{py.relative_to(root)}:{getattr(node, 'lineno', '?')} {bound}")
        assert hits == [], f"removed protocol still bound in: {hits}"
        import backend.core  # must import clean without the removed exports

        assert not hasattr(backend.core, "AIServiceProtocol")
