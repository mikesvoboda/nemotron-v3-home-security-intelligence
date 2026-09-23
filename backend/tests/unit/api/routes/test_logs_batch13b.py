"""Batch-13b mutation-kill battery: ``_log_frontend_entry`` full-extra-dict pins.

Target: the 61 survivors in the frozen WP4.4 dossier
``archive/wp25-feed/wp44-triage/logs.md`` / ``logs_surv_keys.txt`` (module
``backend/api/routes/logs.py``). The dossier's stated weakness: shipped tests
assert SUBSTRING membership in the log text and never pin the FULL ``extra``
dict — so key renames, CASE renames, value→None swaps, sanitize-cap tweaks, and
the context item/size-budget arithmetic all survived. This battery pins the
EXACT extra dict, EXACT truncation shapes, and the budget/cap boundaries.

Red-check outcome (13b lane, this session): 50 KILLED / 11 SURVIVED — the 11
are the 8 SCHEMA-SHIELDED + 2 dossier EQUIVALENT + key 83, whose kill needs
NON-uniform item sizes so reset-vs-accumulate diverge (the first run's
uniform-size test missed it; ``test_budget_accumulates_not_resets`` now pins
the measured shipped shape).

Disposition per the frozen dossier: 8 keys are SCHEMA-SHIELDED equivalent
(component cap 100 vs schema max_length=100; entry-UA cap vs schema 500;
ctx-key cap vs the >50 loop filter; label cap vs component≤100) and 2 are
EQUIVALENT (C14 level-map default unreachable; C12 None-value admission needs a
>50-char key the filter already drops); C11 (key 66, ``str(None)`` feeding size
math only) stays LOW-VALUE. Everything else is asserted here.

EVERY expected value MEASURED this session against shipped production via
``/tmp/b13b-harness.py`` (→ ``/tmp/b13b-probes.json``; truncation suffix via a
direct ``sanitize_log_value`` probe). Production was NOT bent to any mutant.
No kill tallies claimed here — those come only from the 13b lane red-check.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.api.routes.logs import _log_frontend_entry
from backend.api.schemas.logs import FrontendLogEntry, FrontendLogLevel

pytestmark = pytest.mark.unit

LOGS = "backend.api.routes.logs"
TS = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)  # MEASURED full.ts isoformat pin


def entry(**kw):
    kw.setdefault("level", FrontendLogLevel.ERROR)
    kw.setdefault("message", "hello")
    return FrontendLogEntry(**kw)


def run(e, request=None):
    """Drive the helper; return (ok, level, text, extra) from the MEASURED call."""
    with patch(f"{LOGS}.frontend_logger", autospec=True) as fl:
        ok = _log_frontend_entry(e, request)
    call = fl.log.call_args
    return ok, call.args[0], call.args[1], dict(call.kwargs["extra"])


def mkreq(headers):
    r = MagicMock(name="request")
    r.headers = headers
    return r


class TestFullExtraDict:
    """C1/C2/C3/C15: EXACT extra dict — every key, every value (probe full)."""

    def test_full_entry_exact_dict(self):
        e = entry(
            component="Dashboard",
            url="http://x/",
            user_agent="UA-entry",
            timestamp=TS,
            context={"alpha": 1, "beta": None, "k" * 51: "skipme", "k" * 50: "keepme"},
        )
        ok, level, text, extra = run(e)
        assert ok is True
        assert level == 40  # logging.ERROR
        assert text == "[Dashboard] hello"
        assert extra == {
            "source": "frontend",
            "frontend_component": "Dashboard",
            "frontend_url": "http://x/",
            "frontend_user_agent": "UA-entry",
            "frontend_timestamp": "2026-01-02T03:04:05+00:00",
            "ctx_alpha": "1",  # str() cast through sanitize
            f"ctx_{'k' * 50}": "keepme",  # 50-char key admitted
            # "beta" (None value) and the 51-char key dropped by the loop filter
        }

    def test_all_five_levels(self):
        expected = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        for lv, want in expected.items():
            _, level, _, _ = run(entry(level=FrontendLogLevel(lv)))
            assert level == want  # _LOG_LEVEL_MAP verbatim


class TestMinimalEntryFallbacks:
    """C3 15/16/48/49/51: unknown fallback + aware UTC now()."""

    def test_no_component_unknown_and_label(self):
        ok, level, text, extra = run(entry())
        assert extra["source"] == "frontend"
        assert extra["frontend_component"] == "unknown"
        # C5: message label fallback `or "frontend"` pinned EXACT (kills XX/case)
        assert text == "[frontend] hello"
        assert "frontend_url" not in extra  # URL only when provided
        assert "frontend_user_agent" not in extra

    def test_timestamp_fallback_is_aware_utc(self):
        # C3-51: datetime.now(None) is naive LOCAL — pin aware ISO under a
        # patched clock so wall time can't leak into the assert.
        with patch(f"{LOGS}.datetime", autospec=True) as dtm:
            dtm.now.return_value = datetime(2025, 12, 23, 14, 30, tzinfo=UTC)
            dtm.UTC = UTC
            _, _, _, extra = run(entry())
            dtm.now.assert_called_once_with(UTC)  # aware UTC, not now(None)
        assert extra["frontend_timestamp"] == "2025-12-23T14:30:00+00:00"


class TestSanitizeCaps:
    """C6 killable subset (9 keys): url, header-UA, ctx-value, message caps."""

    def test_url_and_message_and_ua_caps(self):
        e = entry(url="u" * 600, user_agent="a" * 500, message="m" * 9000, component="c" * 100)
        _, _, text, extra = run(e)
        assert extra["frontend_url"] == "u" * 500 + "...[truncated]"  # cap 500 MEASURED
        assert extra["frontend_user_agent"] == "a" * 500  # exactly 500 → intact
        assert extra["frontend_component"] == "c" * 100  # schema max == cap → intact
        assert text.startswith("[" + "c" * 100 + "] ")
        assert text.endswith("m" * 5000 + "...[truncated]")  # cap applied BEFORE suffix
        assert (
            len(text) == 103 + 5014
        )  # "[<100c>] " (103) + 5000-char msg + 14 suffix = 5117 MEASURED

    def test_header_user_agent_cap_and_paths(self):
        # header path bypasses the 500 schema cap → the 500 sanitize cap bites
        _, _, _, extra = run(entry(), request=mkreq({"user-agent": "h" * 600}))
        assert extra["frontend_user_agent"] == "h" * 500 + "...[truncated]"
        # header present but entry UA absent + header empty → key omitted
        _, _, _, extra = run(entry(), request=mkreq({}))
        assert "frontend_user_agent" not in extra
        # entry UA wins over header (elif)
        _, _, _, extra = run(entry(user_agent="ENTRY"), request=mkreq({"user-agent": "HEADER"}))
        assert extra["frontend_user_agent"] == "ENTRY"

    def test_ctx_value_cap_1000(self):
        _, _, _, extra = run(entry(context={"short": "v" * 1500}))
        assert (
            extra["ctx_short"] == "v" * 1000 + "...[truncated]"
        )  # 1000 intact + suffix = 1014 MEASURED


class TestContextLimits:
    """C7/C8/C9/C10: 20-item cap, key-length boundary, 10KB budget arithmetic."""

    def test_twenty_item_cap_exactly(self):
        ctx = {f"k{i:02d}": "v" for i in range(25)}
        _, _, _, extra = run(entry(context=ctx))
        stored = sorted(k for k in extra if k.startswith("ctx_"))
        assert stored == [f"ctx_k{i:02d}" for i in range(20)]  # k00..k19, k20.. k24 dropped

    def test_key_length_boundary_50(self):
        _, _, _, extra = run(entry(context={"k" * 50: "a", "k" * 51: "b"}))
        assert f"ctx_{'k' * 50}" in extra  # <=50 admits exactly-50 (kills `<`)
        assert f"ctx_{'k' * 51}" not in extra  # 51 excluded (kills `<=51`)

    def test_budget_equality_boundary(self):
        # two items of EXACTLY 5000 bytes each: sum == 10000, `>` admits both
        eq = {"k0000": "v" * 4995, "k0001": "v" * 4995}
        _, _, _, extra = run(entry(context=eq))
        assert sum(1 for k in extra if k.startswith("ctx_")) == 2
        # over-by-one on the second item: 10001 > 10000 → only first stored
        over = {"k0000": "v" * 4995, "k0001": "v" * 4996}
        _, _, _, extra = run(entry(context=over))
        assert sorted(k for k in extra if k.startswith("ctx_")) == ["ctx_k0000"]

    def test_budget_accumulates_not_resets(self):
        # 4 items x 4000 bytes (MEASURED: shipped stores exactly k000,k001 —
        # 4000+4000+4000=12000>10000 breaks at the third). A last-item-only
        # accumulator (`context_size = item_size` reset, key 83) sees 8000 and
        # `context_size -= item_size` (key 84) sees 0 — both would store all
        # 4, so `== 2` kills reset AND accumulate at once. (The uniform-5003
        # pattern cannot do this: its first accumulation == reset, so it only
        # kills the -= mutant.)
        seq = {f"k{i:03d}": "v" * 3996 for i in range(4)}
        _, _, _, extra = run(entry(context=seq))
        assert sorted(k for k in extra if k.startswith("ctx_")) == ["ctx_k000", "ctx_k001"]

    def test_budget_breaks_loop(self):
        # 5 items x 5006 bytes ("ctx_k0"=6 + 5000): shipped stops at 1
        # (5006; 5006+5006=10012 > 10000 breaks at the second). Kills the
        # `size -= item` accumulator (would store all 5).
        few = {f"k{i}": "v" * 5000 for i in range(5)}
        _, _, _, extra = run(entry(context=few))
        assert sum(1 for k in extra if k.startswith("ctx_")) == 1

    def test_no_context_key_when_context_none(self):
        _, _, _, extra = run(entry())
        assert not [k for k in extra if k.startswith("ctx_")]


class TestExceptionPath:
    """C13 (key 115): warning text pinned, helper swallows and returns False."""

    def test_exception_returns_false_with_message(self):
        import backend.api.routes.logs as lgm

        with patch(f"{LOGS}.frontend_logger", autospec=True) as fl:
            fl.log.side_effect = RuntimeError("boom")
            with patch.object(lgm.logger, "warning", autospec=True) as warn:
                ok = _log_frontend_entry(entry())
        assert ok is False
        assert warn.call_args.args[0] == "Failed to process frontend log entry: boom"
