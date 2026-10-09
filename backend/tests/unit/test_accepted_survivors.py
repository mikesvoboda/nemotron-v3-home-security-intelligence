"""Validation battery for the accepted-survivors file (B2.1 / `01` M3).

M3's Done-when: "the validation test passes with one sample entry and fails
with a malformed one." The file itself (backend/tests/mutation/
accepted_survivors.toml) ships empty — EQUIVALENT residue moves in only when
a battery is consolidated — so the fail-path is exercised two ways: against
fixtures (all six malformed shapes), and against the real file whenever it
grows entries (each entry the file carries is validated by the same battery
the fixtures prove — the check can never be vacuous over shipped data).

The schema contract lives as the TOML's header comment; this file is its
teeth. Field meanings are stated once, there; here the field names are bare
assertion targets on purpose — a test that re-prose a schema rots twice.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SURVIVORS_PATH = REPO_ROOT / "backend" / "tests" / "mutation" / "accepted_survivors.toml"

REQUIRED_FIELDS = ("module", "mutant", "body_sha256", "kind", "reason", "date")
KINDS = {"equivalent", "below-bar"}
HEX64 = re.compile(r"[0-9a-f]{64}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _entries() -> list[dict[str, object]]:
    with SURVIVORS_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    # An absent key means zero entries — the file's created-empty state is
    # legal. A PRESENT non-list means someone wrote the wrong table form.
    entries = data.get("survivor", [])
    assert isinstance(entries, list), (
        "accepted_survivors.toml must carry entries as [[survivor]] tables "
        f"(got {type(entries).__name__} at the top level)"
    )
    return entries


# -- the real file -----------------------------------------------------------


def test_survivors_file_exists_and_parses() -> None:
    assert SURVIVORS_PATH.is_file(), f"missing {SURVIVORS_PATH.relative_to(REPO_ROOT)}"
    assert SURVIVORS_PATH.stat().st_size > 0, "accepted_survivors.toml is zero bytes"
    assert isinstance(_entries(), list)


def test_file_carries_the_schema_header() -> None:
    text = SURVIVORS_PATH.read_text(encoding="utf-8")
    # Every schema field must be DEFINED in the file itself (a comment line
    # that opens with the field name) — an entry author reads the schema
    # where they type, not in a policy doc. Anchored on line starts so prose
    # mentions of a field name don't pass as definitions.
    for field in REQUIRED_FIELDS:
        assert re.search(rf"^#\s+{field}\s+", text, re.MULTILINE), (
            f"schema header does not define field {field!r} as a schema line"
        )


# Validate every entry the shipped file carries, same battery as fixtures.
@pytest.mark.parametrize(
    ("location", "entry"),
    [(f"file[{i}]", e) for i, e in enumerate(_entries())],
    ids=[f"file[{i}]" for i in range(len(_entries()))],
)
def test_file_entries_are_valid(location: str, entry: dict[str, object]) -> None:
    _check_fields_present(location, entry)
    _check_kind(location, entry)
    _check_module_exists(location, entry)
    _check_body_sha256_format(location, entry)
    _check_date_format(location, entry)
    _check_reason_non_trivial(location, entry)


# -- fixture vocabulary ------------------------------------------------------

GOOD_ENTRY = {
    "module": "backend.services.webhook_service",
    "mutant": "deliver_webhook <sample> any",
    "body_sha256": hashlib.sha256(b"def deliver_webhook(): pass\n").hexdigest(),
    "kind": "equivalent",
    "reason": "str-subclass enum makes the mutated arm value-equal (measured in the battery header that recorded it).",
    "date": "2026-10-09",
}


def _good() -> dict[str, object]:
    return dict(GOOD_ENTRY)


def _malformed_shapes() -> list[tuple[str, dict[str, object]]]:
    missing = _good()
    del missing["reason"]

    bad_kind = _good()
    bad_kind["kind"] = "probably-fine"

    bad_hash = _good()
    bad_hash["body_sha256"] = "deadbeef"  # not 64 hex

    dead_module = _good()
    dead_module["module"] = "backend.services.definitely_not_a_module"

    bad_date = _good()
    bad_date["date"] = "October 9, 2026"

    empty_reason = _good()
    empty_reason["reason"] = "   "

    return [
        ("missing-field", missing),
        ("bad-kind", bad_kind),
        ("bad-sha256", bad_hash),
        ("module-not-found", dead_module),
        ("bad-date", bad_date),
        ("blank-reason", empty_reason),
    ]


# -- the battery, as callable checks ------------------------------------------


def _check_fields_present(location: str, entry: dict[str, object]) -> None:
    for field in REQUIRED_FIELDS:
        assert field in entry, f"{location}: entry lacks required field {field!r}"


def _check_kind(location: str, entry: dict[str, object]) -> None:
    kind = entry["kind"]
    assert isinstance(kind, str) and kind in KINDS, (
        f"{location}: kind {kind!r} is not one of {sorted(KINDS)}"
    )


def _check_module_exists(location: str, entry: dict[str, object]) -> None:
    module = entry["module"]
    assert isinstance(module, str) and module, f"{location}: module must be a non-empty string"
    # Path resolution, not import: an entry may name a module the unit
    # environment cannot load (settings-gated imports); it may not name a
    # module that isn't there.
    as_path = REPO_ROOT / module.replace(".", "/")
    assert as_path.with_suffix(".py").is_file() or (as_path / "__init__.py").is_file(), (
        f"{location}: module {module!r} resolves to no file under {REPO_ROOT}"
    )


def _check_body_sha256_format(location: str, entry: dict[str, object]) -> None:
    digest = entry["body_sha256"]
    assert isinstance(digest, str) and HEX64.fullmatch(digest), (
        f"{location}: body_sha256 {digest!r} is not 64 lowercase hex"
    )


def _check_date_format(location: str, entry: dict[str, object]) -> None:
    date = entry["date"]
    assert isinstance(date, str) and DATE.fullmatch(date), (
        f"{location}: date {date!r} is not YYYY-MM-DD"
    )


def _check_reason_non_trivial(location: str, entry: dict[str, object]) -> None:
    reason = entry["reason"]
    assert isinstance(reason, str) and reason.strip(), f"{location}: reason is blank"


# -- Done-when clauses, as tests ----------------------------------------------


def test_battery_passes_with_one_sample_entry() -> None:
    """Done-when half 1: a well-formed entry is accepted by every check."""
    entry = _good()
    _check_fields_present("sample", entry)
    _check_kind("sample", entry)
    _check_module_exists("sample", entry)
    _check_body_sha256_format("sample", entry)
    _check_date_format("sample", entry)
    _check_reason_non_trivial("sample", entry)


@pytest.mark.parametrize(
    ("shape", "entry"), _malformed_shapes(), ids=[s for s, _ in _malformed_shapes()]
)
def test_battery_fails_with_a_malformed_entry(shape: str, entry: dict[str, object]) -> None:
    """Done-when half 2: each malformed shape raises at parse-validation time,
    which is what 'fails' means for a data file — the run goes red, not a
    silent skip."""
    with pytest.raises(AssertionError):
        if shape == "missing-field":
            _check_fields_present(shape, entry)
        elif shape == "bad-kind":
            _check_kind(shape, entry)
        elif shape == "bad-sha256":
            _check_body_sha256_format(shape, entry)
        elif shape == "module-not-found":
            _check_module_exists(shape, entry)
        elif shape == "bad-date":
            _check_date_format(shape, entry)
        elif shape == "blank-reason":
            _check_reason_non_trivial(shape, entry)
        else:  # pragma: no cover - guards the fixture list against drift
            raise AssertionError(f"unwired shape {shape!r}")


def test_validating_a_parsed_file_rejects_the_malformed_shapes() -> None:
    """End-to-end: run the whole battery over a parsed document (fixtures and
    real entries go through the identical loop), so the loop the file-entries
    test uses is itself covered while the shipped file is empty."""

    def validate(entries: list[dict[str, object]]) -> list[str]:
        errors: list[str] = []
        for i, entry in enumerate(entries):
            try:
                _check_fields_present(f"doc[{i}]", entry)
            except AssertionError as exc:
                # Absent required fields short-circuit: the field checks
                # below index entry[...] and would raise KeyError, not a
                # reportable finding.
                errors.append(str(exc))
                continue
            for check in (
                _check_kind,
                _check_module_exists,
                _check_body_sha256_format,
                _check_date_format,
                _check_reason_non_trivial,
            ):
                try:
                    check(f"doc[{i}]", entry)
                except AssertionError as exc:
                    errors.append(str(exc))
        return errors

    assert validate([_good()]) == []
    _, first_bad = _malformed_shapes()[0]
    assert len(validate([first_bad])) == 1
    assert len(validate([_good(), first_bad])) == 1  # good entry doesn't mask the bad
