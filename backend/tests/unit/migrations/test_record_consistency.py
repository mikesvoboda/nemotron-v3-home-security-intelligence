"""Unit tests for the runner's refusal paths -- the ones that need NO database.

`_verify_consistency` is the whole reason a mis-shaped registry cannot roll over a real
deployment: it runs before any upgrade executes, and what it catches are the two states where
"what this database recorded" and "what this build ships" have come apart:

  * a recorded id the registry no longer lists (an upgrade was deleted or renumbered), and
  * a recorded checksum that no longer matches the file (a shipped upgrade was edited).

Both are `UpgradeDriftError`, and both must refuse the *run*, not skip *one* upgrade -- a
half-trusted history is worse than none, because the runner's safety rests on the record.

These are pure-function tests on purpose. Reproducing drift with a real database would mean
recording a fake id (easy) or shipping an edited file to get a checksum mismatch (impossible,
since the file IS the checksum source) -- so the unit level is not the lazy option here, it is
the only level that can reach the second case at all.
"""

from __future__ import annotations

import datetime as dt

import pytest

from backend.migrations import registry, runner
from backend.migrations.errors import UpgradeDriftError, UpgradeError

pytestmark = pytest.mark.unit

_REAL = registry.UPGRADES


def _record(upgrade: registry.Upgrade, **over) -> runner.Record:
    """A plausible record row for `upgrade`.

    The default checksum is the one the real file digests to today, which is what makes the
    mismatch tests mismatch tests. Ghost upgrades (a file that is not on disk) therefore have to
    pass their own digest -- legitimate, since an orphaned id is rejected before the runner ever
    reads a file, so the value never gets compared.
    """
    values = {
        "id": upgrade.id,
        "applied_at": dt.datetime(2026, 10, 17, 12, 0, tzinfo=dt.UTC),
        "checksum": upgrade.checksum(),
        "executed": True,
        "source": upgrade.source,
    }
    values.update(over)
    return runner.Record(**values)


def _records(*upgrades: registry.Upgrade, ghosts=()) -> dict[str, runner.Record]:
    """Records for `upgrades` (digests read from the shipped files) plus hand-valued `ghosts`."""
    out = {u.id: _record(u) for u in upgrades}
    for ghost_id, digest in ghosts:
        out[ghost_id] = runner.Record(
            id=ghost_id,
            applied_at=dt.datetime(2026, 10, 17, 12, 0, tzinfo=dt.UTC),
            checksum=digest,
            executed=True,
            source="test",
        )
    return out


def _ghost(upgrade_id: str) -> registry.Upgrade:
    """A registry entry whose file does not exist -- how a renumbered upgrade looks to a
    database that recorded the old id: the RECORD survives, the file does not."""
    return registry.Upgrade(id=upgrade_id, filename="not-on-disk.sql", source="test")


# --------------------------------------------------------------------------------------
# Clean history
# --------------------------------------------------------------------------------------


def test_matching_history_passes_silently():
    """The common case must raise nothing: startup runs this on every boot."""
    runner._verify_consistency(_records(*_REAL), _REAL)


def test_partial_history_passes():
    """A database upgraded only through 0002 is normal (a box landed since it restarted)."""
    runner._verify_consistency(_records(*_REAL[:2]), _REAL)


def test_empty_history_passes():
    runner._verify_consistency({}, _REAL)


# --------------------------------------------------------------------------------------
# Orphaned records: the registry lost an upgrade a database already has
# --------------------------------------------------------------------------------------


def test_recorded_upgrade_missing_from_registry_is_drift():
    """Every shipped upgrade matches AND one recorded id is unlisted: still drift.

    The registry here is the full shipped list, so the orphan is the only possible complaint --
    if the check were written to iterate the registry (looking for recorded ids one by one) it
    would find four clean matches and pass, which is the renumbering accident this exists for.
    """
    with pytest.raises(UpgradeDriftError, match="does not list") as excinfo:
        runner._verify_consistency(
            _records(*_REAL, ghosts=[("0005-renumbered-away", "a" * 16)]), _REAL
        )
    # The message must name the id, because the operator has to restore exactly that file.
    assert "0005-renumbered-away" in str(excinfo.value)


def test_orphan_message_tells_the_operator_how_to_fix_it():
    """The refusal has to be actionable from a boot log: restore it, or add a NEW id.

    "Do not renumber" matters because renumbering is the accident that produced this state, and a
    second renumber makes the history unusable in a way nothing downstream can undo.
    """
    with pytest.raises(UpgradeDriftError) as excinfo:
        runner._verify_consistency(_records(*_REAL, ghosts=[("0000-old-first", "b" * 16)]), _REAL)
    message = str(excinfo.value)
    assert "Restore" in message
    assert "NEW upgrade id" in message


def test_all_orphans_are_named_in_one_message():
    """Fixing drift is a conversation with a deploy log; listing one of two is a second round trip."""
    records = _records(*_REAL, ghosts=[("aaa", "c" * 16), ("bbb", "d" * 16)])
    with pytest.raises(UpgradeDriftError) as excinfo:
        runner._verify_consistency(records, _REAL)
    message = str(excinfo.value)
    assert "aaa" in message and "bbb" in message


def test_a_ghost_file_that_is_registered_is_not_reported_as_an_orphan():
    """Drift is about the RECORD vs the registry list, not about whether the file is on disk.

    A missing file is a separate, later failure (`Upgrade.read_sql` -> UpgradeError naming the
    COPY remedy). This pins that the two gates do not blur: an unlisted-file-but-listed-id
    database passes `_verify_consistency` and then fails loudly where it should.
    """
    runner._verify_consistency(_records(*_REAL), (*_REAL, _ghost("0099-registered-missing-file")))
    with pytest.raises(UpgradeError, match="COPY"):
        _ghost("0099-registered-missing-file").checksum()


# --------------------------------------------------------------------------------------
# Checksum drift: a shipped file changed under a database that already ran it
# --------------------------------------------------------------------------------------


def test_edited_shipped_file_is_drift():
    """The case no integration test can create: the file IS the digest source.

    A database that recorded digest A must refuse to start against a build whose file now digests
    to B. Silent acceptance is how a two-week-old deployment runs different SQL from a fresh one.
    """
    records = _records(_REAL[0])
    records[_REAL[0].id] = _record(_REAL[0], checksum="0123456789abcdef")
    with pytest.raises(UpgradeDriftError, match="does not match") as excinfo:
        runner._verify_consistency(records, _REAL)
    message = str(excinfo.value)
    # Both digests, so the operator can tell which side moved without a shell.
    assert "0123456789abcdef" in message
    assert _REAL[0].checksum() in message


def test_drift_message_names_the_file_not_just_the_id():
    records = _records(_REAL[1])
    records[_REAL[1].id] = _record(_REAL[1], checksum="ffffffffffffffff")
    with pytest.raises(UpgradeDriftError) as excinfo:
        runner._verify_consistency(records, _REAL)
    assert _REAL[1].filename in str(excinfo.value)


def test_recorded_without_executed_still_requires_the_same_checksum():
    """`executed=False` means "we verified the effect and did not run it", not "the text is free".

    The record's job is to say which text this database's shape came from, and a verified upgrade
    still names a text.
    """
    records = _records(_REAL[2])
    records[_REAL[2].id] = _record(_REAL[2], executed=False, checksum="deadbeefdeadbeef")
    with pytest.raises(UpgradeDriftError):
        runner._verify_consistency(records, _REAL)


def test_drift_is_refused_before_any_upgrade_is_applied():
    """Ordering claim: `apply_all` calls `_verify_consistency` before its loop, not inside it.

    Asserted structurally because the failure mode is per-upgrade: if the check ran inside the
    loop, a drifted 0004 would be preceded by 0001-0003 executing and recording, and the history
    would then contain both the old truth and the refusal.
    """
    import inspect

    source = inspect.getsource(runner.apply_all)
    verify_at = source.index("_verify_consistency(")
    loop_at = source.index("for upgrade in upgrades")
    assert verify_at < loop_at, "the drift gate must precede the apply loop"


# --------------------------------------------------------------------------------------
# The import-time literal-spelling gate
# --------------------------------------------------------------------------------------


def test_record_table_spelling_gate_fires_on_a_renamed_constant(monkeypatch):
    """The statements spell `schema_migrations` as a literal; this is what makes that safe.

    Patching SCHEMA_TABLE simulates someone renaming the constant. Without the gate the module
    would import fine and then read a table it never creates -- a query against a name that
    happens to exist is the definition of a quiet failure.
    """
    monkeypatch.setattr(runner, "SCHEMA_TABLE", "renamed_history_table")
    with pytest.raises(UpgradeError, match="does not name SCHEMA_TABLE"):
        runner._assert_record_table_spelled_consistently()


def test_record_table_spelling_gate_passes_as_shipped():
    runner._assert_record_table_spelled_consistently()


__all__: list[str] = []  # pytest collects tests; nothing here is importable API
