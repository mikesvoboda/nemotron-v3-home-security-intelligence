"""Validation battery for the accepted-survivors file (B2.1 / `01` M3).

M3's Done-when: "the validation test passes with one sample entry and fails
with a malformed one." The file itself (backend/tests/mutation/
accepted_survivors.toml) ships empty — EQUIVALENT residue moves in only when
a battery is consolidated — so the fail-path is exercised two ways: against
fixtures (every malformed shape in _SHAPE_CHECKS), and against the real file
through an always-run loop: when the file carries entries they go through the
same battery the fixtures prove, and the structural checks run on it whatever
it holds, so a future file cannot pass by being shaped wrong at the top level
(a mistyped table name once hid entries from every entry-level check).

The schema contract lives as the TOML's header comment; this file is its
teeth. Field meanings are stated once, there; here the field names are bare
assertion targets on purpose — a test that re-prose a schema rots twice.

The teeth are only real if a wrong file cannot pass by being shaped slightly
differently than the checks expect, so the structural checks (table name,
unknown fields, duplicates, module path confinement) are as deliberately
tested as the field checks: see _MALFORMED_FILES, which feeds the battery
whole documents rather than single entries.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SURVIVORS_PATH = REPO_ROOT / "backend" / "tests" / "mutation" / "accepted_survivors.toml"

REQUIRED_FIELDS = ("module", "mutant", "body_sha256", "kind", "reason", "date")
ALLOWED_FIELDS = frozenset(REQUIRED_FIELDS)
KINDS = {"equivalent", "below-bar"}
HEX64 = re.compile(r"[0-9a-f]{64}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _entries_from(data: dict[str, object]) -> list[dict[str, object]]:
    # Only the `survivor` key may carry entries. A sibling key would mean a
    # mistyped table name ([[survivors]]) holding entries the battery would
    # otherwise never look at — the exact typo the TOML header promises cannot
    # quietly make a survivor "accepted".
    unexpected = sorted(set(data) - {"survivor"})
    assert not unexpected, (
        "accepted_survivors.toml has top-level key(s) the schema does not define: "
        f"{unexpected}. Entries live in [[survivor]] tables (singular)."
    )
    # An absent key means zero entries — the file's created-empty state is
    # legal. A PRESENT non-list means someone wrote the wrong table form.
    entries = data.get("survivor", [])
    assert isinstance(entries, list), (
        "accepted_survivors.toml must carry entries as [[survivor]] tables "
        f"(got {type(entries).__name__} at the top level)"
    )
    return entries


def _entries() -> list[dict[str, object]]:
    with SURVIVORS_PATH.open("rb") as fh:
        return _entries_from(tomllib.load(fh))


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


# -- whole-document checks ---------------------------------------------------


def _check_no_duplicate_entries(document: str, entries: list[dict[str, object]]) -> None:
    # An entry is a claim about one mutant; the same claim twice would
    # double-count once the weekly scorer (M2) reports scores with and without
    # accepted survivors. Keyed on the identity fields, not the reason.
    seen: dict[tuple[object, object, object], int] = {}
    for i, entry in enumerate(entries):
        key = (entry.get("module"), entry.get("mutant"), entry.get("body_sha256"))
        assert key not in seen, (
            f"{document}: entry[{i}] duplicates entry[{seen[key]}] "
            f"(module, mutant, body_sha256 all equal): {key}"
        )
        seen[key] = i


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

    impossible_date = _good()
    impossible_date["date"] = "2026-13-45"  # right shape, not a real day

    blank_reason = _good()
    blank_reason["reason"] = "   "

    blank_mutant = _good()
    blank_mutant["mutant"] = "  "

    unknown_field = _good()
    unknown_field["killed_by"] = "test_old_kill"  # not a schema field

    outside_repo = _good()
    outside_repo["module"] = "....tmp.outside_mod"  # escapes REPO_ROOT via pathlib

    test_module = _good()
    test_module["module"] = "backend.tests.unit.test_accepted_survivors"

    return [
        ("missing-field", missing),
        ("bad-kind", bad_kind),
        ("bad-sha256", bad_hash),
        ("module-not-found", dead_module),
        ("module-outside-repo", outside_repo),
        ("module-is-a-test-file", test_module),
        ("bad-date", bad_date),
        ("impossible-date", impossible_date),
        ("blank-reason", blank_reason),
        ("blank-mutant", blank_mutant),
        ("unknown-field", unknown_field),
    ]


# The whole-document shapes: mistakes about the FILE, not about one field. Each
# feeds a raw TOML string through the same parse → validate path the real file
# takes, and must raise. A typo'd table name is the most likely of these and the
# one that would hide an entry from every other check, so it is checked first.
_MALFORMED_FILES: list[tuple[str, str]] = [
    (
        "plural-table-name",
        """
[[survivors]]
module = "backend.services.webhook_service"
mutant = "get_webhook_service <return> Singleton->None"
body_sha256 = "{h}"
kind = "equivalent"
reason = "would be invisible to a battery that only reads [[survivor]]"
date = "2026-10-09"
""".format(h="a" * 64),
    ),
    (
        "duplicate-entries",
        """
[[survivor]]
module = "backend.services.webhook_service"
mutant = "get_webhook_service <return> Singleton->None"
body_sha256 = "{h}"
kind = "equivalent"
reason = "first copy"
date = "2026-10-09"

[[survivor]]
module = "backend.services.webhook_service"
mutant = "get_webhook_service <return> Singleton->None"
body_sha256 = "{h}"
kind = "equivalent"
reason = "second copy, different prose"
date = "2026-10-09"
""".format(h="b" * 64),
    ),
]


# -- the battery, as callable checks ------------------------------------------


def _check_fields_present(location: str, entry: dict[str, object]) -> None:
    for field in REQUIRED_FIELDS:
        assert field in entry, f"{location}: entry lacks required field {field!r}"


def _check_no_unknown_fields(location: str, entry: dict[str, object]) -> None:
    unknown = sorted(set(entry) - ALLOWED_FIELDS)
    assert not unknown, (
        f"{location}: entry has field(s) the schema does not define: {unknown}. "
        "An entry is module/mutant/body_sha256/kind/reason/date — extra prose goes in reason."
    )


def _check_kind(location: str, entry: dict[str, object]) -> None:
    kind = entry["kind"]
    assert isinstance(kind, str) and kind in KINDS, (
        f"{location}: kind {kind!r} is not one of {sorted(KINDS)}"
    )


def _check_module_exists(location: str, entry: dict[str, object]) -> None:
    module = entry["module"]
    assert isinstance(module, str) and module.strip(), (
        f"{location}: module must be a non-empty string"
    )
    # Path resolution, not import: an entry may name a module the unit
    # environment cannot load (settings-gated imports); it may not name a
    # module that isn't there, or one outside this repo.
    candidate = REPO_ROOT / str(module).replace(".", "/")
    for path in (candidate.with_suffix(".py"), candidate / "__init__.py"):
        resolved = path.resolve()
        if not resolved.is_relative_to(REPO_ROOT):
            # A dotted path can carry ".." segments (and pathlib treats a
            # leading "/" as absolute, discarding the root it was joined to).
            # Such a target is not this repo's module, whatever file it hits.
            raise AssertionError(
                f"{location}: module {module!r} resolves outside the repo ({resolved})"
            )
        if resolved.is_file():
            assert "tests" not in resolved.relative_to(REPO_ROOT).parts, (
                f"{location}: module {module!r} is a test module — test files carry no scored "
                "mutants (reachability rule, `01` M1), so they can never hold an accepted survivor"
            )
            return
    raise AssertionError(f"{location}: module {module!r} resolves to no file under {REPO_ROOT}")


def _check_body_sha256_format(location: str, entry: dict[str, object]) -> None:
    digest = entry["body_sha256"]
    assert isinstance(digest, str) and HEX64.fullmatch(digest), (
        f"{location}: body_sha256 {digest!r} is not 64 lowercase hex"
    )


def _check_mutant_non_trivial(location: str, entry: dict[str, object]) -> None:
    mutant = entry["mutant"]
    assert isinstance(mutant, str) and mutant.strip(), (
        f"{location}: mutant is blank — name it as '<function> <expression> <change>'"
    )


def _check_date_format(location: str, entry: dict[str, object]) -> None:
    date = entry["date"]
    assert isinstance(date, str) and DATE.fullmatch(date), (
        f"{location}: date {date!r} is not YYYY-MM-DD"
    )
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise AssertionError(f"{location}: date {date!r} is not a real calendar day") from exc


def _check_reason_non_trivial(location: str, entry: dict[str, object]) -> None:
    reason = entry["reason"]
    assert isinstance(reason, str) and reason.strip(), f"{location}: reason is blank"


# Every check one entry must pass, in order. Fields-present runs first and the
# loop below short-circuits on it: the rest index entry[...] and a missing field
# would raise KeyError, which is not a reportable finding.
ENTRY_CHECKS = (
    _check_fields_present,
    _check_no_unknown_fields,
    _check_kind,
    _check_module_exists,
    _check_body_sha256_format,
    _check_mutant_non_trivial,
    _check_date_format,
    _check_reason_non_trivial,
)


def validate_entries(document: str, entries: list[dict[str, object]]) -> list[str]:
    """Run the whole battery over parsed entries, collecting findings.

    The shipped file and the fixtures go through this one function, so the
    loop cannot rot out of use while the file is empty.
    """
    errors: list[str] = []
    try:
        _check_no_duplicate_entries(document, entries)
    except AssertionError as exc:
        errors.append(str(exc))
    for i, entry in enumerate(entries):
        location = f"{document}[{i}]"
        try:
            _check_fields_present(location, entry)
        except AssertionError as exc:
            errors.append(str(exc))
            continue
        for check in ENTRY_CHECKS[1:]:
            try:
                check(location, entry)
            except AssertionError as exc:
                errors.append(str(exc))
    return errors


# -- Done-when clauses, as tests ----------------------------------------------


def test_battery_passes_with_one_sample_entry() -> None:
    """Done-when half 1: a well-formed entry is accepted by every check."""
    assert validate_entries("sample", [_good()]) == []


# One check per malformed shape, dispatched by name. The map's keys and the
# fixture list must agree — test_every_malformed_shape_is_wired_to_a_check
# enforces that OUTSIDE the pytest.raises block, because an assert inside it
# would pass by failing.
_SHAPE_CHECKS = {
    "missing-field": _check_fields_present,
    "bad-kind": _check_kind,
    "bad-sha256": _check_body_sha256_format,
    "module-not-found": _check_module_exists,
    "module-outside-repo": _check_module_exists,
    "module-is-a-test-file": _check_module_exists,
    "bad-date": _check_date_format,
    "impossible-date": _check_date_format,
    "blank-reason": _check_reason_non_trivial,
    "blank-mutant": _check_mutant_non_trivial,
    "unknown-field": _check_no_unknown_fields,
}


def test_every_malformed_shape_is_wired_to_a_check() -> None:
    """Drift guard: adding a shape without a check (or a check without a
    shape) fails here, where a failure is a failure."""
    shapes = {shape for shape, _ in _malformed_shapes()}
    assert shapes == set(_SHAPE_CHECKS), (
        f"fixture shapes and dispatch map disagree: only-in-fixtures "
        f"{sorted(shapes - set(_SHAPE_CHECKS))}, only-in-map "
        f"{sorted(set(_SHAPE_CHECKS) - shapes)}"
    )


@pytest.mark.parametrize(
    ("shape", "entry"), _malformed_shapes(), ids=[s for s, _ in _malformed_shapes()]
)
def test_battery_fails_with_a_malformed_entry(shape: str, entry: dict[str, object]) -> None:
    """Done-when half 2: each malformed shape raises at parse-validation time,
    which is what 'fails' means for a data file — the run goes red, not a
    silent skip."""
    check = _SHAPE_CHECKS[shape]
    with pytest.raises(AssertionError):
        check(shape, entry)


@pytest.mark.parametrize(("shape", "toml"), _MALFORMED_FILES, ids=[s for s, _ in _MALFORMED_FILES])
def test_battery_fails_with_a_malformed_file(shape: str, toml: str) -> None:
    """Mistakes about the FILE, not a field: a wrong table name hides entries
    from every entry-level check (caught at parse, where a raise is the only
    option — nothing parsed is safe to walk), and a duplicated entry is a
    COLLECTED finding, because the rest of the document is still walkable. Both
    must come back as findings, never as a clean run."""
    try:
        entries = _entries_from(tomllib.loads(toml))
    except AssertionError as exc:
        findings = [str(exc)]  # a parse-stage finding: the file is unusable, stop there
    else:
        findings = validate_entries(shape, entries)
    assert findings, f"{shape}: the battery reported the file clean"


def test_file_entries_are_all_valid_through_the_shared_loop() -> None:
    """The shipped file goes through the identical loop the fixtures prove, so
    'every entry is validated' is true of the real file whenever it has any."""
    assert validate_entries("shipped file", _entries()) == []


def test_shipped_file_has_no_duplicate_entries() -> None:
    _check_no_duplicate_entries("shipped file", _entries())
