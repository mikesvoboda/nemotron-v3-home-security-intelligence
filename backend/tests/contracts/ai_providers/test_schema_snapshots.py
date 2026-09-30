"""WP7.2: golden wire payloads + shape snapshots for every AI contract operation.

The generator (scripts/gen-ai-contract.py) derives two artifacts per
operation side that has a schema, straight from the contract models:

    golden/snapshots/<op>.<side>.snapshot.json   a shape digest (key -> type
        tokens, required list, $defs names) - the thing that makes a KEY
        RENAME a named failure rather than a 4000-line blob diff
    golden/payloads/<op>.<side>.example.json     a valid wire payload - the
        reference instance both provider-side (WP8.2 FakeProvider) and
        consumer-side tests import INSTEAD of hand-written dicts (census:
        572 dict literals across 110 backend test files)

Done-when this file enforces: renaming a key in a contract model reddens CI
with a message that NAMES the key. test_rename_reddens_naming_the_key proves
the mechanism on a tmp copy, so the naming is verified, not assumed.

Generated artifacts are marked (generated_by in every snapshot, README in the
golden dir) and never hand-edited; scripts/test_gen_ai_contract.py's fixpoint
tests cover prettier for them too, so the commit hooks leave them alone.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from backend.ai_contract.operations import OPERATIONS

# parents[4]: ai_providers -> contracts -> tests -> backend -> repo root (the
# registry test's parents[3] vacuous-glob bug is why this one starts at [4])
REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"
GOLDEN_DIR = Path(__file__).parent / "golden"
SNAP_DIR = GOLDEN_DIR / "snapshots"
PAYLOAD_DIR = GOLDEN_DIR / "payloads"


def _contract_schema(op_id: str, side: str) -> dict | None:
    path = SCHEMA_DIR / f"{op_id}.{side}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _type_token(node: dict) -> str:
    """Normalize a property schema to a comparable type token.

    Structural enough that a type change (str -> list, number -> string) is a
    named diff, simple enough that a description edit is NOT.
    """
    if "$ref" in node:
        return f"ref({node['$ref'].rsplit('/', 1)[-1]})"
    if "enum" in node:
        return "enum"
    if "anyOf" in node:
        return "anyOf(" + ",".join(sorted(_type_token(s) for s in node["anyOf"])) + ")"
    t = node.get("type", "any")
    if t == "array":
        items = node.get("items")
        return f"array<{_type_token(items)}>" if items else "array"
    if t == "object" and "contentEncoding" in node:
        return "binary"
    return t


def _digest(op_id: str, side: str, schema: dict) -> dict:
    return {
        "generated_by": "scripts/gen-ai-contract.py",
        "op": op_id,
        "side": side,
        "required": sorted(schema.get("required", [])),
        "properties": {k: _type_token(v) for k, v in schema.get("properties", {}).items()},
        "defs": sorted(schema.get("$defs", {})),
    }


def _sides_with_schemas() -> list[tuple[str, str]]:
    return [
        (op_id, side)
        for op_id in sorted(OPERATIONS)
        for side in ("request", "response")
        if _contract_schema(op_id, side) is not None
    ]


#: A key the rename ratchet can rename: present in a live response schema AND in
#: that op's golden payload example. inference_time_ms is the natural choice (it
#: is a real emitted field on every lane that reports timing), but the candidate
#: set is not hardcoded to one name -- any key shared by schema and payload works,
#: so a future rename of inference_time_ms itself cannot silently disarm the proof.
def _rename_subject() -> tuple[str, str, str]:
    """(op_id, side, key) for the ratchet, derived from the shipped goldens."""
    candidates: list[tuple[str, str, str]] = []
    for op_id, side in _sides_with_schemas():
        payload_path = PAYLOAD_DIR / f"{op_id}.{side}.example.json"
        if not payload_path.exists():
            continue
        schema = _contract_schema(op_id, side) or {}
        props = set(schema.get("properties", {}))
        if not props:
            continue
        # Keys actually present in the example payload.
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        # Rename a REQUIRED key. That is what makes the payload leg bite: a
        # renamed required key fails validation with "'<old>' is a required
        # property", which names the old spelling — the assertion below. Rename
        # an OPTIONAL key on a schema that permits extras (the three yolo26
        # response schemas set additionalProperties: true) and validation stays
        # silent, the payload leg produces no message, and the ratchet's proof
        # evaporates without anyone touching a contract. Measured: the two
        # /enrich-lt responses and vlm_assess are the schemas whose required keys
        # also appear in their golden payloads.
        shared = sorted(set(schema.get("required", [])) & props & set(payload))[:1]
        candidates += [(op_id, side, k) for k in shared]
    assert candidates, (
        "no live op has a response key that also appears in its golden payload — "
        "the rename ratchet cannot prove itself; this is a golden-artifact gap"
    )
    # Prefer the timing key when it still exists (it was the committed choice),
    # else take the deterministic first candidate.
    for op_id, side, key in candidates:
        if key == "inference_time_ms":
            return op_id, side, key
    return candidates[0]


class TestGoldenArtifactsPresent:
    def test_golden_dir_exists_and_is_marked_generated(self) -> None:
        readme = GOLDEN_DIR / "README.md"
        assert GOLDEN_DIR.is_dir() and readme.exists(), (
            "golden/ must exist with a README marking every file GENERATED - "
            "run scripts/gen-ai-contract.py --goldens"
        )
        assert "GENERATED" in readme.read_text(encoding="utf-8")

    def test_every_schema_side_has_a_snapshot_and_a_payload(self) -> None:
        sides = _sides_with_schemas()
        assert sides, "no contract schemas found - generator broken"
        missing = [
            f"{op}.{side}"
            for op, side in sides
            if not (SNAP_DIR / f"{op}.{side}.snapshot.json").exists()
            or not (PAYLOAD_DIR / f"{op}.{side}.example.json").exists()
        ]
        assert not missing, f"golden artifacts missing for: {missing}"


class TestPayloadsValidate:
    """The swap guard proper: a provider payload that renames, drops or
    mistypes a contract key fails HERE, and the message names the key."""

    @pytest.mark.parametrize(("op_id", "side"), _sides_with_schemas(), ids=lambda v: str(v))
    def test_golden_payload_validates_against_contract(self, op_id: str, side: str) -> None:
        schema = _contract_schema(op_id, side)
        payload = json.loads(
            (PAYLOAD_DIR / f"{op_id}.{side}.example.json").read_text(encoding="utf-8")
        )
        if schema.get("type") != "object":
            # multipart marker roots (yolo26 image uploads) are a bare
            # binary-string schema - structural checks are vacuous there
            assert isinstance(payload, str)
            return
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(payload), key=lambda e: str(e.path))
        if errors:
            named = "; ".join(f"{op_id}.{side}: {e.message[:160]}" for e in errors[:6])
            pytest.fail(named)

    @pytest.mark.parametrize(("op_id", "side"), _sides_with_schemas(), ids=lambda v: str(v))
    def test_golden_payload_exercises_every_contract_key(self, op_id: str, side: str) -> None:
        """Every declared property must appear in the golden payload: a key a
        payload omits is a key no consumer test ever sends, so renaming it
        would slip past the payload check and only trip the snapshot."""
        schema = _contract_schema(op_id, side)
        payload = json.loads(
            (PAYLOAD_DIR / f"{op_id}.{side}.example.json").read_text(encoding="utf-8")
        )
        uncovered = sorted(set(schema.get("properties", {})) - set(payload))
        assert not uncovered, f"{op_id}.{side}: contract keys absent from golden: {uncovered}"


class TestSnapshotsAreShapeDiffs:
    @pytest.mark.parametrize(("op_id", "side"), _sides_with_schemas(), ids=lambda v: str(v))
    def test_snapshot_matches_contract_shape(self, op_id: str, side: str) -> None:
        schema = _contract_schema(op_id, side)
        committed = json.loads(
            (SNAP_DIR / f"{op_id}.{side}.snapshot.json").read_text(encoding="utf-8")
        )
        mine = _digest(op_id, side, schema)
        if committed == mine:
            return
        # Name the keys, don't dump the blobs - Done-when is a NAMED failure.
        added = sorted(set(mine["properties"]) - set(committed["properties"]))
        removed = sorted(set(committed["properties"]) - set(mine["properties"]))
        retyped = sorted(
            k
            for k in set(mine["properties"]) & set(committed["properties"])
            if mine["properties"][k] != committed["properties"][k]
        )
        parts = []
        if added:
            parts.append(f"keys added to contract (renamed IN): {added}")
        if removed:
            parts.append(f"keys removed from contract (renamed AWAY): {removed}")
        if retyped:
            parts.append(
                "keys retyped: "
                + ", ".join(
                    f"{k}: {committed['properties'][k]}->{mine['properties'][k]}" for k in retyped
                )
            )
        if mine["required"] != committed["required"]:
            parts.append(f"required changed: {committed['required']} -> {mine['required']}")
        pytest.fail(f"{op_id}.{side} snapshot drift: " + "; ".join(parts))

    def test_rename_reddens_naming_the_key(self) -> None:
        """Prove the mechanism, not just the current green: copy a committed
        snapshot, rename one key in the CONTRACT it is diffed against, and
        show the failure message names BOTH key spellings. This is the
        Done-when statement executed as an assertion.

        The subject is DERIVED, not named. This test used to hardcode
        ``op_id = "clip_embed"``, which made the ratchet's own proof a
        single-point-of-failure on one op's continued existence: R8 S3 pruned
        CLIP (owner ruling 5), _contract_schema returned None for it, and the
        test died with an AttributeError inside the digest helper -- a crash in
        the mechanism that is supposed to REPORT drift, which is a worse
        outcome than the drift itself. It now walks the live schema directory
        and takes the first response schema whose key ALSO appears in that op's
        golden payload (the payload leg below needs the key present in the
        example, and that pairing is not universal: yolo26_detect.response.json
        declares inference_time_ms but its example payload omits it). A ratchet
        that must survive every future prune cannot name a subject.
        """
        op_id, side, old = _rename_subject()
        schema = _contract_schema(op_id, side)
        assert schema is not None, f"{op_id}.{side} vanished mid-test"
        committed = _digest(op_id, side, schema)
        renamed = dict(schema)
        props = dict(schema["properties"])
        # The tamper name is derived from the derived subject, so this leg stays
        # wired to whatever _rename_subject picked.
        new = f"{old}_millis"
        assert new not in props, f"{new} already in {op_id}.{side} - pick another tamper"
        props[new] = props.pop(old)
        renamed["properties"] = props
        tampered = _digest(op_id, side, renamed)

        added = sorted(set(tampered["properties"]) - set(committed["properties"]))
        removed = sorted(set(committed["properties"]) - set(tampered["properties"]))
        assert added == [new], added
        assert removed == [old], removed
        # and the digest change is enough to break payload validation too:
        tampered_payload = dict(
            json.loads((PAYLOAD_DIR / f"{op_id}.{side}.example.json").read_text(encoding="utf-8"))
        )
        tampered_payload[new] = tampered_payload.pop(old)
        errors = list(jsonschema.Draft202012Validator(renamed).iter_errors(tampered_payload))
        joined = " ".join(e.message for e in errors)
        assert old in joined, (
            f"validation failure must name the contract key {old!r}, got: {joined[:300]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
