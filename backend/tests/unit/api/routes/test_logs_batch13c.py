"""Batch-13c mutation-kill battery: the 10 logs13b residual survivors.

Target: keys {13,14,31,32,75,76,90,92,103,107} of the frozen WP4.4 logs
feed — every survivor of ``logs13b2`` (``/tmp/redcheck-logs13b.log``, rc=0,
51 KILLED / 10 SURVIVED, all in ``_log_frontend_entry``).

The dossier called the eight cap-kwarg keys SCHEMA-SHIELDED equivalent
(component cap 100 == schema max_length=100, UA cap 500 == schema 500, ctx
key cap 50 vs the len<=50 loop filter, component-or-default cap 100). That
shield claim is FALSE by construction and MEASURED so this session:
``sanitize_log_value`` EXPANDS every ``${x}`` pattern to the 20-char
``[EXPRESSION_REMOVED]`` before truncating, so a schema-valid RAW input can
sanitize LONGER than the cap and hit the truncation path:
- component ``"${a}"*25`` — raw len 100 (schema cap is max_length=100,
  VALID), sanitized 500 chars -> shipped ``max_length=100`` truncates to
  5 whole blocks + "...[truncated]" (MEASURED len 114).
- user_agent ``"${b}"*125`` — raw 500 == schema cap, sanitized 2500 ->
  shipped truncates to exactly 25 whole blocks + suffix (len 515).
- ctx key ``"${c}"*12`` — raw 48 passes the len<=50 loop filter, sanitized
  240 -> shipped truncates to 40 + first 10 chars + suffix inside the
  ``ctx_``-prefixed extra KEY NAME.
Every cap mutant (kwarg REMOVAL -> default 10000, N -> N+1) changes the
emitted string for these inputs (probe /tmp/b13c-harness.py ->
/tmp/b13c-probes.json: all three shipped values distinct from their N+1 and
no-default siblings), so all 8 are GAP kills — corrected per-mutant, not a
blanket reversal (the level-map 2 keys keep the dossier C14 name but at
helper level the defensive default IS the shipped contract and gets pinned).

Keys 90/92 (``_LOG_LEVEL_MAP.get(entry.level.value, logging.INFO)`` default
-> None / removed): through the PUBLIC route the level is enum-validated so
the default is unreachable — the dossier's C14 equivalence holds THERE. The
helper is also the shipped defensive contract for non-enum callers (the
.get default exists precisely for them); a duck level object with
value="TRACE" through the helper takes the default: MEASURED shipped
``frontend_logger.log`` called with level 20 (logging.INFO), ERROR control
40. Both mutants make the level arg None -> the pin kills them at helper
level. Disclosure: duck input is helper-level-only, never via the route.

Every expected value MEASURED against shipped production this session;
production NOT bent to any mutant. No kill tallies claimed here — those
come only from the logs13c lane red-check.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.api.routes.logs import _log_frontend_entry
from backend.api.schemas.logs import FrontendLogEntry, FrontendLogLevel

pytestmark = pytest.mark.unit

LOGS = "backend.api.routes.logs"
TS = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
BLOCK = "[EXPRESSION_REMOVED]"
SUF = "...[truncated]"

# Schema-valid EXPANSION inputs (raw lengths MEASURED: 100 / 500 / 48).
COMP_RAW = "${a}" * 25  # raw 100 == schema cap 100; sanitized 500
UA_RAW = "${b}" * 125  # raw 500 == schema cap 500; sanitized 2500
KEY_RAW = "${c}" * 12  # raw 48 passes the len<=50 loop filter; sanitized 240

# MEASURED shipped truncations at each call site's cap:
COMP_VAL = BLOCK * 5 + SUF  # sanitize(COMP_RAW, 100)  -> 114 chars
UA_VAL = BLOCK * 25 + SUF  # sanitize(UA_RAW, 500)     -> 515 chars
KEY_VAL = (BLOCK * 3)[:50] + SUF  # sanitize(KEY_RAW, 50)   -> 63 chars


def entry(**kw):
    kw.setdefault("level", FrontendLogLevel.ERROR)
    kw.setdefault("message", "hello")
    return FrontendLogEntry(**kw)


def run(e, request=None):
    with patch(f"{LOGS}.frontend_logger", autospec=True) as fl:
        ok = _log_frontend_entry(e, request)
    call = fl.log.call_args
    return ok, call.args[0], call.args[1], dict(call.kwargs["extra"])


class TestSanitizeCapsObservable:
    """Keys 13/14/103/107: component cap 100 observable via extra VALUE and
    message TEXT; keys 31/32 UA; keys 75/76 ctx-key NAME."""

    def test_component_cap_100_exact(self):
        # kills 13 (kwarg removed -> 10000, no suffix) and 14 (101: the 101st
        # char "[" shifts the cut — MEASURED value differs)
        ok, level, text, extra = run(entry(component=COMP_RAW, timestamp=TS))
        assert ok is True and level == 40
        assert extra["frontend_component"] == COMP_VAL
        assert len(COMP_VAL) == 114  # MEASURED shape lock

    def test_component_or_default_cap_100_in_text(self):
        # kills 103 (kwarg removed) / 107 (101) on the line-193 sibling call:
        # the message embeds sanitize(component or "frontend", 100)
        _, _, text, _ = run(entry(component=COMP_RAW, timestamp=TS))
        assert text == f"[{COMP_VAL}] hello"

    def test_user_agent_cap_500_exact(self):
        # kills 31 (-> 10000 default) / 32 (501)
        _, _, _, extra = run(entry(user_agent=UA_RAW, timestamp=TS))
        assert extra["frontend_user_agent"] == UA_VAL

    def test_context_key_cap_50_exact_name(self):
        # kills 75 (-> 10000) / 76 (51): the sanitized ctx KEY is the
        # observable — extra dict keys pin it by exact membership
        _, _, _, extra = run(entry(context={KEY_RAW: "v"}, timestamp=TS))
        assert f"ctx_{KEY_VAL}" in extra
        assert extra[f"ctx_{KEY_VAL}"] == "v"


class TestLevelMapDefault:
    """Keys 90/92 at helper level: shipped default logging.INFO (20)."""

    def test_unmapped_level_falls_back_to_info(self):
        # duck bypasses route validation (helper-level disclosure in the
        # module docstring); .value "TRACE" is NOT in _LOG_LEVEL_MAP.
        e = FrontendLogEntry.model_construct(
            level=SimpleNamespace(value="TRACE"),
            message="hello",
            component=None,
            context=None,
            url=None,
            user_agent=None,
            timestamp=TS,
        )
        ok, level, text, extra = run(e)
        assert ok is True
        assert level == 20  # MEASURED shipped default (logging.INFO)
        assert text == "[frontend] hello"
        assert sorted(extra) == ["frontend_component", "frontend_timestamp", "source"]

    def test_mapped_level_control_still_error(self):
        # belt-and-braces: the map path is unchanged by the default mutants
        _, level, _, _ = run(entry())
        assert level == 40
