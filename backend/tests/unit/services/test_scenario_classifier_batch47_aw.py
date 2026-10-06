# TARGET-MODULE: backend.services.scenario_classifier
"""Battery AW - campaign #47 kill battery for backend/services/scenario_classifier.py.

Style (proven AT..AV): every observable an entered branch WRITES is asserted
([[entered-branch-must-assert-every-observable-it-writes]]); log pins ride REAL
LogRecords on the REAL logger with BY-NAME extras access
([[log-context-filter-fakes-extra-kwarg-mutants]]); message asserts are FULL
equality over the FULL ordered DEBUG sequence, never fragments
([[fragment-count-asserts-pass-xx-mutants]]); dicts/dataclasses pinned by
EXACT equality (full metadata dict / full TailgatingIndicator - one row kills
key twins, key drops and value twins); set-valued classifier outputs are
compared as SETS + length (frozenset iteration and set() materialization are
PYTHONHASHSEED-order-dependent - never pin their list order); floats pinned to
EXACT binary values measured by a same-day probe (no approx)
([[helper-none-default-hides-none-polarity-fake-greens]] re-checked: every
"unreachable" claim below was re-derived, not assumed). NO pytest fixtures
([[b30-sweep-no-fixtures-tmp-path-fake-hang-storm]]); timestamps are fixed
epoch floats - never datetime.now().

Measured semantics from the SHIPPED source (read 2026-10-06, lines cited):
- apply_hysteresis (L470-528): prev None -> passthrough; per boundary b in
  29/59/84 buffer (b-3, b+4); prev<=b & new>b -> b (DEBUG staying-below);
  prev>b & new<=b -> b+1 (DEBUG staying-above). Edge table MEASURED against
  the shipped text: (61,58)->59, (62,58)->59 [b+4=63], (63,58)->59 [new==
  buffer_high], (64,58)->64 passthrough, (56,62)->56 [new==buffer_low OUTSIDE,
  strict <], (30,29)->29 [prev==b], (29,29)->29 SILENT [prev>b False],
  (29,28)->29 SILENT [new==b False], (29,31)->30, (61,60)->61 passthrough.
- _has_person_detected (L536-591): obj_type/label str().lower() with ""-get;
  "person" in either -> True; any human/man/woman/individual in either ->
  True; negative 9-tuple -> False; positive 9-tuple -> any.
- classify_scenario (L630-736): sources summary/reasoning lowered + truthy-
  gated str() of object_type/label/description, " ".join; keyword substring
  match logs DEBUG "Scenario {v} matched keyword: {k}" and breaks; action
  fallback ONLY when no keyword matched AND action_result TRUTHY ({} is
  falsy - never consulted): pattern.lower() in action or action in
  pattern.lower(); the DEFAULT "" action is a WILDCARD (empty string is a
  substring of every pattern) -> action_result WITHOUT "detected_action"
  matches EVERY scenario (measured); None value / absent key -> AttributeError
  on .lower(). GRAFFITI: is_historical AND not has_person -> skip (DEBUG
  "NOT classified"), else keep (DEBUG "classified: active vandalism
  (has_person=X, is_historical=Y)"). Matched-keyword DEBUG co-logs BEFORE the
  historical decision (2-message sequence pinned exactly). Nonempty result ->
  INFO "Classified scenarios: {sorted-free list}" extra scenario_count.
- get_scenario_floor_score (L739-758): falsy input -> 0; else max floor.
- apply_scenario_floor (L761-790): floor > score -> (floor, True) + INFO with
  extras {original_score, floor_score, scenarios}; equal/above -> passthrough
  False, SILENT.
- detect_tailgating (L819-896): filter (d.get("object_type") or "").lower()
  == "person"; <2 -> EMPTY indicator (False, 0.0, "", 0, None); zone in
  (entry_point, door, gate, entrance) -> +0.2 capped 0.95; sort key detected_at
  else timestamp else 0 (None fallbacks -> TypeError on mixed sort); loop
  reads detected_at with default 0; gap <= 5.0 counted; base = min(0.5 +
  0.15*entries, 0.9); min gap > 3.0 -> *0.8 elif > 2.0 -> *0.9; description
  f"{entries+1} persons detected entering in quick succession".
- adjust_risk_score (L904-1011): metadata key set EXACTLY {original_score,
  scenarios, floor_applied, floor_score, tailgating, hysteresis_applied};
  floor_score written ONLY when floor_applied (value == get_scenario_floor_
  score(scenarios) - the None-scenarios twin returns 0 via the falsy guard,
  NOT a crash); tailgating subdict key set EXACTLY {detected, confidence,
  description, persons_involved, time_gap_seconds}; escalation int(55*conf)
  STRICT > score -> INFO "Tailgating escalation: {s} -> {e}" extra
  {tailgating_confidence, persons_involved}; hysteresis gated AND previous not
  None, flag only on CHANGE (strict !=) with DEBUG "Hysteresis adjustment:
  {pre} -> {adj} (previous={prev})"; final clamp max(0, min(100, x)).
Measured confidence floats (probe 2026-10-06): e1 gap<=2.0 = 0.65; e1
gap2.5/3.0/5.0 = 0.5850000000000001 / (*0.8 at 5.0) 0.52; e2 gap3.0 =
0.7200000000000001; e2 gap3.5 = 0.6400000000000001; e3+ gap1.5 = 0.9 (cap);
boosted e1 gap1.5 = 0.8500000000000001; boosted cap 0.95. Effective floors:
int(55*0.65) = 35, int(55*0.585...) = 32, int(55*0.85...) = 46, int(55*
0.72...) = 39; /-twins int(55/0.585...) = 94, int(55/0.72...) = 76.
EQUIV DISPOSITIONS (proof sketch per family; to be RE-PROVEN by the 412-key
redcheck sweep + close-sweep attribution - NEVER tolerated):
_has_person_detected m5,m7,m10,m15,m17,m20 - the "" get-defaults twin to
None/XXXX/2-arg ONLY on an ABSENT key, and str(None)="none" / "XXXX"="xxxx"
contain NONE of the match tokens (person/human/man/woman/individual), while a
PRESENT None value already str()s identically in shipped -> unreachable.
_has_person_detected m33,m34,m37,m38 - "human"/"woman" -> XX/UPPER twins:
"man" (present UNCHANGED in every twin tuple) is a SUBSTRING of both "human"
and "woman", so a twin token can never be the sole trigger -> unreachable.
adjust_risk_score m8 - initial "floor_applied": False -> True: the key is
OVERWRITTEN by metadata["floor_applied"] = floor_applied before any read.
classify_scenario m32 - matched=False -> None: both reads are truthiness
tests (not matched / if matched).
detect_tailgating m7 - (get or "") -> (get or "XXXX"): only falsy values
reach the default and neither "" nor "XXXX" equals "person".
detect_tailgating m49,m148 - float("INF") IS float("inf") (same value).
detect_tailgating m144 - or-True on `min_time_gap != inf`: inside the
consecutive_entries > 0 branch min_time_gap is finite, so shipped is True too.
ROW-2 KILLS (worlds that DID diverge, measured by the sweep): sort-key twins
m29,m33,m34 (outer key) / m35,m39,m40 (inner key) / m41 (inner default 1) -
the LOOP always re-reads detected_at, so the twins diverge only where the
SORT SLOT changes adjacency (three worlds added below); get_scenario_floor_
score m6,m8 - UNCLASSIFIED is NOT in the floor table -> list nonempty but the
comprehension EMPTY -> the else branch IS live (m6 raises ValueError, m8
returns 1); classify_scenario m54 - `detected_action in pattern.upper()`:
"limbing over" is a strict lowercase substring of "climbing over fence" only.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import pytest

import backend.services.scenario_classifier as sc
from backend.services.scenario_classifier import (
    ScenarioType,
    adjust_risk_score,
    apply_hysteresis,
    apply_scenario_floor,
    classify_scenario,
    detect_tailgating,
    get_scenario_floor_score,
)

# ============================================================================
# Helpers (fixture-free; b30-sweep calls tests directly)
# ============================================================================

T0 = 1_000_000.0  # fixed epoch base for detected_at pins

# Empty-indicator shape RE-DECLARED from the dataclass defaults (never read
# from sc - the default twins must not be pinned to themselves):
EMPTY_IND = sc.TailgatingIndicator(False, 0.0, "", 0, None)


def persons(*offsets: float) -> list[dict[str, Any]]:
    """Person detections at fixed epoch T0 + offsets."""
    return [{"object_type": "person", "detected_at": T0 + o} for o in offsets]


class _CapturingHandler(logging.Handler):
    def __init__(self, sink: list) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink.append(record)


@contextlib.contextmanager
def logs() -> Any:
    """Capture REAL LogRecords emitted to sc.logger (BY-NAME extras access)."""
    sink: list[logging.LogRecord] = []
    handler = _CapturingHandler(sink)
    old_level, old_prop = sc.logger.level, sc.logger.propagate
    sc.logger.setLevel(logging.DEBUG)
    sc.logger.addHandler(handler)
    sc.logger.propagate = False
    try:
        yield sink
    finally:
        sc.logger.removeHandler(handler)
        sc.logger.setLevel(old_level)
        sc.logger.propagate = old_prop


# ============================================================================
# apply_hysteresis  (survivors h6,h8,h9,h10,h11,h12,h13,h15,h17,h18,h22)
# ============================================================================


def test_k47_hysteresis_clamps_down_below_boundary() -> None:
    """h15 (debug msg -> None): prev 58 (below), new 61 -> clamp to 59 + the
    exact staying-below DEBUG as the ONLY record."""
    with logs() as recs:
        assert apply_hysteresis(61, 58) == 59
    assert [r.levelno for r in recs] == [logging.DEBUG]
    assert recs[0].getMessage() == (
        "Hysteresis applied: 61 -> 59 (staying below 59 boundary, previous=58)"
    )


def test_k47_hysteresis_clamps_up_above_boundary() -> None:
    """h18 (elif new<b strict), h22 (debug msg -> None): prev 31, new EXACTLY
    29 (<=b) -> clamp UP to 30 + exact staying-above DEBUG."""
    with logs() as recs:
        assert apply_hysteresis(29, 31) == 30
    assert [r.levelno for r in recs] == [logging.DEBUG]
    assert recs[0].getMessage() == (
        "Hysteresis applied: 29 -> 30 (staying above 29 boundary, previous=31)"
    )


def test_k47_hysteresis_buffer_edges_exact() -> None:
    """Buffer arithmetic (b-3, b+4]: (62,58)->59 [h6 -1 twin: high=62, new 62
    falls out -> 62]; (63,58)->59 [h10 < twin: 63<63 False -> 63];
    (64,58)->64 [h8 +2 twin: high=64 -> clamps to 59]; (56,62)->56 [h9 <=
    twin: 56<=56 True -> clamps to 60]; (61,60)->61 [h11 or twin: enters via
    new>b, first if clamps to 59]."""
    assert apply_hysteresis(62, 58) == 59
    assert apply_hysteresis(63, 58) == 59
    assert apply_hysteresis(64, 58) == 64
    assert apply_hysteresis(56, 62) == 56
    assert apply_hysteresis(61, 60) == 61


def test_k47_hysteresis_prev_on_boundary_still_clamps() -> None:
    """(30,29)->29 WITH the staying-below DEBUG: shipped uses prev <= boundary
    (measured) - the h12 prev<b twin lets 30 through SILENTLY (no clamp, no
    log)."""
    with logs() as recs:
        assert apply_hysteresis(30, 29) == 29
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (
            logging.DEBUG,
            "Hysteresis applied: 30 -> 29 (staying below 29 boundary, previous=29)",
        )
    ]


def test_k47_hysteresis_boundary_silence() -> None:
    """(29,29)->29 SILENT prev>b False [h17 >= twin clamps to 30 + logs];
    (29,28)->29 SILENT new>b False [h13 >= twin clamps AND logs - the empty
    log is the kill]."""
    with logs() as recs:
        assert apply_hysteresis(29, 29) == 29
        assert apply_hysteresis(29, 28) == 29
    assert len(recs) == 0


# ============================================================================
# _has_person_detected  (survivors hp2..hp10,hp12..hp28,hp30..hp40,hp47)
# ============================================================================

NO_PERSON_TEXTS = (
    "no person",
    "no one",
    "no individuals",
    "no people",
    "empty scene",
    "no suspect",
    "no perpetrator",
    "nobody",
    "no humans",
)

PERSON_TEXTS = (
    "person",
    "individual",
    "suspect",
    "perpetrator",
    "man",
    "woman",
    "someone",
    "intruder",
    "vandal",
)


def test_k47_person_object_type_channel() -> None:
    """hp2 (.upper twin), hp3 (str(None) swap), hp4/hp6/hp8/hp9 (key None/""/
    XX/UPPER twins), hp28 (return True->False): object_type "PERSON" matches
    via .lower() with a token-free label. None-VALUE object_type reads
    "none" (no token, no crash). Absent keys read ""."""
    assert sc._has_person_detected([{"object_type": "PERSON", "label": "x"}], "") is True
    assert sc._has_person_detected([{"object_type": None, "label": "x"}], "") is False
    assert sc._has_person_detected([{}], "") is False


def test_k47_person_label_channel() -> None:
    """hp12 (.upper twin), hp13 (str(None) swap), hp14/hp16/hp18/hp19 (key
    twins): label carries the token with a token-free object_type - BOTH
    cases. label None-VALUE reads "none" -> False."""
    assert sc._has_person_detected([{"object_type": "car", "label": "PERSON"}], "") is True
    assert sc._has_person_detected([{"object_type": "car", "label": "person"}], "") is True
    assert sc._has_person_detected([{"object_type": "car", "label": None}], "") is False


def test_k47_person_human_tokens_both_channels() -> None:
    """hp30 (any->and), hp31/hp32 (not-in twins on either side), hp33..hp40
    (token XX/UPPER twins): every token matches via LABEL with a token-free
    object_type AND via OBJECT_TYPE with a token-free label."""
    for token in ("human", "man", "woman", "individual"):
        assert sc._has_person_detected([{"object_type": "car", "label": token}], "") is True
        assert sc._has_person_detected([{"object_type": token, "label": "x"}], "") is True


def test_k47_person_only_one_side_person() -> None:
    """hp21 (or->and), hp22/hp24 (obj-side twins), hp25/hp27 (label-side
    twins): "person" ONLY in object_type, and ONLY in label."""
    assert sc._has_person_detected([{"object_type": "person", "label": "car"}], "") is True
    assert sc._has_person_detected([{"object_type": "car", "label": "person"}], "") is True


def test_k47_person_negative_override_and_indicator_lists() -> None:
    """hp28 (detections return True->False): a person detection answers True
    BEFORE the negative check. hp47 (final any->not any): EVERY negative text
    False, EVERY person text True, neutral text False (twin True)."""
    assert sc._has_person_detected([{"object_type": "person"}], "no person") is True
    for text in NO_PERSON_TEXTS:
        assert sc._has_person_detected(None, text) is False, text
    for text in PERSON_TEXTS:
        assert sc._has_person_detected(None, text) is True, text
    assert sc._has_person_detected(None, "nothing relevant here") is False


# ============================================================================
# classify_scenario  (survivors cs13..cs71)
# ============================================================================


def test_k47_classify_keyword_channel_full_log_sequence() -> None:
    """cs37 (matched-keyword debug None -> record message "None"), cs58/cs59
    (active-vandalism debug swap -> the message is NOT emitted for a
    non-historical keep), cs66/cs67/cs69/cs70/cs71 (INFO None / extra None /
    extra dropped / key twins): "tagging" matches exactly ONE keyword of
    exactly ONE scenario; the GRAFFITI special block co-logs its
    active-vandalism DEBUG (measured has_person=False, is_historical=False)
    even when NOT historical -> deterministic 2-DEBUG + 1-INFO, exact
    messages, BY-NAME extras."""
    with logs() as recs:
        out = classify_scenario(summary="tagging")
    assert out == [ScenarioType.GRAFFITI]
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (logging.DEBUG, "Scenario graffiti matched keyword: tagging"),
        (
            logging.DEBUG,
            "Scenario graffiti classified: active vandalism "
            "(has_person=False, is_historical=False)",
        ),
        (logging.INFO, "Classified scenarios: ['graffiti']"),
    ]
    assert recs[2].scenario_count == 1


def test_k47_classify_action_default_is_wildcard() -> None:
    """cs43 (key None twin -> miss -> wildcard ALL), cs46 (2-arg get -> ABSENT
    key returns None -> .lower() AttributeError), cs44 (default None same),
    cs49 ("XXXX" default -> no pattern contains "xxxx" -> no match at all):
    action_result WITHOUT the key - shipped default "" matches EVERY action
    pattern (substring of all) -> all 15 scenarios (SET compare - list order
    is hash-seed dependent)."""
    out = classify_scenario(action_result={"other": "x"})
    assert set(out) == set(sc.SCENARIO_FLOOR_SCORES)
    assert len(out) == len(sc.SCENARIO_FLOOR_SCORES)


def test_k47_classify_action_none_value_raises() -> None:
    """cs44 (default None), cs46 (2-arg get): EXPLICIT None value and the
    shipped-default path - .lower() on None raises AttributeError."""
    with pytest.raises(AttributeError):
        classify_scenario(action_result={"detected_action": None})


def test_k47_classify_action_case_asymmetry_second_operand() -> None:
    """cs54: the SECOND OR operand lowercases the PATTERN (shipped
    `detected_action in pattern.lower()`); the mutant compares against
    `pattern.upper()`. "limbing over" is a strict lowercase substring of
    "climbing over fence" (half 2 fires, half 1 does not - no pattern is a
    substring of it) -> shipped finds FENCE_CLIMBING; the twin's UPPER form
    matches nothing -> []. The first-operand rows cannot reach this twin:
    `pattern.lower() in X` is identical in both."""
    assert classify_scenario(action_result={"detected_action": "limbing over"}) == [
        ScenarioType.FENCE_CLIMBING
    ]


def test_k47_classify_action_empty_dict_never_consulted() -> None:
    """{} is falsy -> the action fallback is SKIPPED entirely; the wildcard
    does NOT fire (pin: no scenarios)."""
    assert classify_scenario(action_result={}) == []


def test_k47_classify_action_bidirectional_match() -> None:
    """cs47/cs48 (key XX/UPPER twins -> miss -> wildcard ALL != exactly-one),
    cs52/cs53 (both OR-side not-in twins), cs54 (pattern.upper twin), cs57
    (action debug None swap): action "climbing" hits pattern "climbing"
    (half 1) and is IN "climbing over fence" (half 2) -> EXACTLY
    [FENCE_CLIMBING] with its action DEBUG then the INFO line + extras."""
    with logs() as recs:
        out = classify_scenario(action_result={"detected_action": "climbing"})
    assert out == [ScenarioType.FENCE_CLIMBING]
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (logging.DEBUG, "Scenario fence_climbing matched action: climbing"),
        (logging.INFO, "Classified scenarios: ['fence_climbing']"),
    ]
    assert recs[1].scenario_count == 1


def test_k47_classify_label_and_description_channels() -> None:
    """cs13/cs14/cs15 (label key None/XX/UPPER), cs17 (.upper twin), cs18
    (str(None) swap), cs19/cs20/cs21 (description key twins): keyword ONLY in
    label (UPPERCASE - kills the .upper twin) / ONLY in description."""
    assert classify_scenario(detections=[{"label": "SPRAY CAN"}]) == [ScenarioType.GRAFFITI]
    assert classify_scenario(detections=[{"description": "graffiti"}]) == [ScenarioType.GRAFFITI]


def test_k47_classify_object_type_channel() -> None:
    """object_type source line: "spray can" ONLY in object_type."""
    assert classify_scenario(detections=[{"object_type": "spray can"}]) == [ScenarioType.GRAFFITI]


def test_k47_classify_joiner_is_single_space() -> None:
    """cs24 ("XX XX" joiner): the cross-token phrase "stolen package" is
    reachable ONLY when label + description join with exactly ONE space."""
    assert classify_scenario(detections=[{"label": "stolen", "description": "package"}]) == [
        ScenarioType.PACKAGE_THEFT
    ]


def test_k47_classify_person_detection_beats_negative_text() -> None:
    """cs26 (has_person fed detections=None): person evidence ONLY as an
    object_type detection, summary carries the NEGATIVE phrase - shipped
    detections-loop answers True BEFORE the negative text check -> graffiti
    KEPT; the twin sees only the text -> negative wins -> SKIPPED."""
    out = classify_scenario(
        summary="pre-existing graffiti, no person",
        detections=[{"object_type": "person"}],
    )
    assert out == [ScenarioType.GRAFFITI]


def test_k47_classify_keyword_match_skips_action_loop() -> None:
    """Defensive: keyword-matched scenario never consults the action channel;
    empty / negative worlds produce no scenarios (INFO-guard truthiness path).
    cs32 (matched=False->None) is EQUIV by construction - every read of
    `matched` is a truthiness test - see header."""
    assert classify_scenario(summary="climbing over fence") == [ScenarioType.FENCE_CLIMBING]
    assert classify_scenario(summary="no person detected", action_result=None) == []
    assert classify_scenario() == []


def test_k47_classify_historical_skip_full_sequence() -> None:
    """cs62 (NOT-classified debug swap): matched-keyword DEBUG co-logs FIRST,
    then the skip line - exact 2-message sequence, NO INFO (empty result)."""
    with logs() as recs:
        out = classify_scenario(summary="old graffiti, empty scene")
    assert out == []
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (logging.DEBUG, "Scenario graffiti matched keyword: graffiti"),
        (
            logging.DEBUG,
            "Scenario graffiti NOT classified: explicitly historical graffiti "
            "with no person detected",
        ),
    ]


def test_k47_classify_historical_with_person_full_sequence() -> None:
    """cs64 (classified debug swap; flag-swap twins get message != pin):
    historical True + person True keeps the floor - message pins BOTH flags
    in ORDER, then the INFO line."""
    with logs() as recs:
        out = classify_scenario(summary="pre-existing graffiti, person")
    assert out == [ScenarioType.GRAFFITI]
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (logging.DEBUG, "Scenario graffiti matched keyword: graffiti"),
        (
            logging.DEBUG,
            "Scenario graffiti classified: active vandalism (has_person=True, is_historical=True)",
        ),
        (logging.INFO, "Classified scenarios: ['graffiti']"),
    ]


# ============================================================================
# get_scenario_floor_score + apply_scenario_floor (gss6,gss8, af4..af13)
# ============================================================================


def test_k47_floor_score_max_and_empty() -> None:
    """gss6 (or-True -> max([]) ValueError), gss8 (else 1): falsy -> EXACTLY 0;
    UNCLASSIFIED (a scenario NOT in the floor table -> the comprehension is
    empty while the LIST is not - gss8's else branch IS live) -> EXACTLY 0,
    gss6's twin raises, gss8's returns 1; multi-scenario -> the HIGHER
    floor."""
    assert get_scenario_floor_score([]) == 0
    assert get_scenario_floor_score([ScenarioType.UNCLASSIFIED]) == 0
    assert get_scenario_floor_score([ScenarioType.TRESPASSING, ScenarioType.GRAFFITI]) == 65


def test_k47_apply_floor_boundary_silent() -> None:
    """Floor EXACTLY equal -> (65, False) with NO log; empty scenarios
    passthrough (af side of gss8)."""
    with logs() as recs:
        assert apply_scenario_floor(65, [ScenarioType.GRAFFITI]) == (65, False)
    assert len(recs) == 0
    assert apply_scenario_floor(30, []) == (30, False)


def test_k47_apply_floor_log_and_extras_exact() -> None:
    """af4 (message None), af5 (extras None), af7 (extras dropped), af8/af9
    (original_score twins), af10/af11 (floor_score twins), af12/af13
    (scenarios twins): FULL message equality + BY-NAME extras values."""
    with logs() as recs:
        assert apply_scenario_floor(20, [ScenarioType.GRAFFITI]) == (65, True)
    assert len(recs) == 1
    assert recs[0].levelno == logging.INFO
    assert recs[0].getMessage() == "Scenario floor applied: 20 -> 65"
    assert recs[0].original_score == 20
    assert recs[0].floor_score == 65
    assert recs[0].scenarios == ["graffiti"]


# ============================================================================
# detect_tailgating
# ============================================================================


def test_k47_tailgating_below_two_persons() -> None:
    """EMPTY indicator FULL observation: 0 persons, 1 person, 2 non-persons."""
    assert detect_tailgating([]) == EMPTY_IND
    assert detect_tailgating(persons(0.0)) == EMPTY_IND
    assert detect_tailgating([{"object_type": "car", "detected_at": T0}] * 2) == EMPTY_IND


def test_k47_tailgating_zone_members_boost_exact() -> None:
    """dt17..dt22 (door/gate/entrance XX+UPPER twins turn a member into a
    NON-member): the +0.2 boost is applied BEFORE the *0.9 gap penalty
    (measured), so gap 2.5 e1 is 0.5850000000000001 unboosted vs
    0.7650000000000001 boosted for EACH of the four zone names; no-arg and a
    NON-member zone stay unboosted."""
    d = persons(0.0, 2.5)
    assert detect_tailgating(d).confidence == 0.5850000000000001
    assert detect_tailgating(d, "hallway").confidence == 0.5850000000000001
    for zone in ("entry_point", "door", "gate", "entrance"):
        assert detect_tailgating(d, zone).confidence == 0.7650000000000001, zone


def test_k47_tailgating_no_time_keys_sort_defaults_zero() -> None:
    """dt30/dt32/dt36/dt37/dt38 (sort-key None fallbacks -> sorted() compares
    None -> TypeError): two persons WITHOUT any time key sort by the 0/0
    default and report gap EXACTLY 0.0."""
    assert detect_tailgating([{"object_type": "person"}] * 2) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.65,
        description="2 persons detected entering in quick succession",
        persons_involved=2,
        time_gap_seconds=0.0,
    )


def test_k47_tailgating_loop_default_missing_detected_at() -> None:
    """dt57/dt59/dt67/dt69 (loop default None -> float(None) TypeError),
    dt64/dt72 (default 1 -> gap |2-1|=1.0 != 2.0): first person has NO
    detected_at (loop default 0), second at epoch 2.0 -> gap EXACTLY 2.0."""
    assert detect_tailgating(
        [{"object_type": "person"}, {"object_type": "person", "detected_at": 2.0}]
    ) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.65,
        description="2 persons detected entering in quick succession",
        persons_involved=2,
        time_gap_seconds=2.0,
    )


def test_k47_tailgating_sort_key_prefers_detected_at_over_timestamp() -> None:
    """dt29/dt33/dt34/dt39/dt40 (sort reads the WRONG key -> falls to the
    timestamp fallback): A carries detected_at 5.0 AND timestamp 30.0; B/C at
    28.0/31.0. Shipped order A,B,C -> gaps 23 (out) and 3 (in) -> e1 gap 3.0
    -> 0.5850000000000001. Key-twins order B,A,C -> gaps 23 and 26 -> EMPTY."""
    dets = [
        {"object_type": "person", "detected_at": 5.0, "timestamp": 30.0},
        {"object_type": "person", "detected_at": 28.0},
        {"object_type": "person", "detected_at": 31.0},
    ]
    assert detect_tailgating(dets) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.5850000000000001,
        description="2 persons detected entering in quick succession",
        persons_involved=2,
        time_gap_seconds=3.0,
    )


def test_k47_tailgating_sort_key_ignoring_detected_at_empty() -> None:
    """dt29 (outer get(None,...)), dt33/dt34 (outer key XXdetected_atXX/
    DETECTED_AT): ALL THREE twins read the inner timestamp-else-0 for every
    detection, ignoring detected_at. World A{da:2}, B{da:8}, C{ts:3}: shipped
    sorts A,C,B -> gap |0-2|=2 counts (loop reads da: C is 0), then 8 out ->
    e1 min 2.0 -> 0.65. Twins sort A,B,C (2,8 fall to 0; C keeps 3) -> gaps 6
    and 8 -> EMPTY."""
    dets = [
        {"object_type": "person", "detected_at": 2.0},
        {"object_type": "person", "detected_at": 8.0},
        {"object_type": "person", "timestamp": 3.0},
    ]
    assert detect_tailgating(dets) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.65,
        description="2 persons detected entering in quick succession",
        persons_involved=2,
        time_gap_seconds=2.0,
    )


def test_k47_tailgating_sort_inner_fallback_reorders() -> None:
    """dt35 (inner d.get(None, 0)), dt39/dt40 (inner key XXtimestampXX/
    TIMESTAMP): twins sort a timestamp-only person at 0 instead of its
    timestamp. World P{ts:5}, A{da:4}, B{da:6}: shipped order A,P,B -> gaps 4
    (in), 6 (out) -> e1 min 4.0 -> *0.8 -> 0.52 gap 4.0. Twins order P,A,B ->
    gaps 4 and 2 both in -> e2 min 2.0 -> 0.8 gap 2.0."""
    dets = [
        {"object_type": "person", "timestamp": 5.0},
        {"object_type": "person", "detected_at": 4.0},
        {"object_type": "person", "detected_at": 6.0},
    ]
    assert detect_tailgating(dets) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.52,
        description="2 persons detected entering in quick succession",
        persons_involved=2,
        time_gap_seconds=4.0,
    )


def test_k47_tailgating_sort_fallback_one_reorders() -> None:
    """dt41 (inner fallback default 1): a NO-TIME person sorts at 0 shipped,
    1 mutant. World X{no keys}, A{da:0.5}, B{da:5.5}: shipped X,A,B -> gaps
    0.5 and 5.0 both <= 5 -> e2 min 0.5 -> 0.8. Mutant A,X,B -> gaps 0.5 (in),
    5.5 (out) -> e1 -> 0.65."""
    dets = [
        {"object_type": "person"},
        {"object_type": "person", "detected_at": 0.5},
        {"object_type": "person", "detected_at": 5.5},
    ]
    assert detect_tailgating(dets) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.8,
        description="3 persons detected entering in quick succession",
        persons_involved=3,
        time_gap_seconds=0.5,
    )


def test_k47_tailgating_window_boundary_inclusive() -> None:
    """dt92 (<= -> <): gap EXACTLY 5.0 counts -> e1 min-gap 5.0 > 3.0 -> *0.8
    -> 0.52, time_gap 5.0. dt43 (window 6.0): gap 5.5 stays EMPTY."""
    assert detect_tailgating(persons(0.0, 5.0)) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.52,
        description="2 persons detected entering in quick succession",
        persons_involved=2,
        time_gap_seconds=5.0,
    )
    assert detect_tailgating(persons(0.0, 5.5)) == EMPTY_IND


def test_k47_tailgating_base_formula_exact() -> None:
    """dt109 (1.5 base -> cap 0.9), dt110 (/0.15 -> 0.9), dt111 (1.15 step ->
    0.9): e1 no-penalty 0.65 on both no-penalty gaps; dt112 (cap 1.9): e3
    0.5+0.45=0.95 unclamped vs 0.9."""
    assert detect_tailgating(persons(0.0, 2.0)).confidence == 0.65
    assert detect_tailgating(persons(0.0, 1.5)).confidence == 0.65
    assert detect_tailgating(persons(0.0, 1.5, 3.0, 4.5)).confidence == 0.9


def test_k47_tailgating_boost_and_cap_exact() -> None:
    """dt119 (+1.2 boost -> min(1.85, 0.95) = 0.95 != 0.85), dt120 (cap 1.95:
    e4 boosted 1.1 != 0.95)."""
    assert detect_tailgating(persons(0.0, 1.5), "gate").confidence == 0.8500000000000001
    assert detect_tailgating(persons(0.0, 1.5, 3.0, 4.5, 6.0), "gate").confidence == 0.95


def test_k47_tailgating_gap_slab_boundaries() -> None:
    """dt121 (if >= 3.0): gap EXACTLY 3.0 -> shipped stays *0.9 0.585...,
    twin *0.8 0.52. dt123 (elif >= 2.0): gap EXACTLY 2.0 -> 0.65, twin 0.585.
    dt122 (>4.0): gap 3.5 e2 -> shipped *0.8 0.6400000000000001, twin *0.9
    0.72... dt124 (elif >3.0): gap 2.5 -> shipped *0.9 0.585..., twin none
    0.5. dt126/dt127 (/0.9, *1.9) read on the 2.5 world."""
    assert detect_tailgating(persons(0.0, 3.0)).confidence == 0.5850000000000001
    assert detect_tailgating(persons(0.0, 2.0)).confidence == 0.65
    assert detect_tailgating(persons(0.0, 3.5, 7.0)).confidence == 0.6400000000000001
    assert detect_tailgating(persons(0.0, 2.5)).confidence == 0.5850000000000001


def test_k47_tailgating_indicator_full_observation() -> None:
    """dt130 (description None), dt132/dt143/dt145 (time_gap -> None twins),
    dt135 (description kwarg dropped -> "" default), dt137 (time_gap kwarg
    dropped -> None), dt139/dt140 (count -1 / +2), dt148 ("INF" - behaviorally
    EQUIV, still pinned by the EXACT 1.5 value): FULL indicator equality."""
    assert detect_tailgating(persons(0.0, 1.5)) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.65,
        description="2 persons detected entering in quick succession",
        persons_involved=2,
        time_gap_seconds=1.5,
    )


def test_k47_tailgating_five_person_cap_full() -> None:
    """Capped world FULL indicator (dt112/dt139/dt140 second read)."""
    assert detect_tailgating(persons(0.0, 1.5, 3.0, 4.5, 6.0)) == sc.TailgatingIndicator(
        detected=True,
        confidence=0.9,
        description="5 persons detected entering in quick succession",
        persons_involved=5,
        time_gap_seconds=1.5,
    )


def test_k47_tailgating_object_type_normalization() -> None:
    """dt7 (or-"XXXX" EQUIV candidate - still pinned defensively): falsy
    object_type (absent/None) is NOT a person -> EMPTY. Positive: "PERSON"
    UPPERCASE counts -> 2 persons."""
    assert (
        detect_tailgating([{"detected_at": T0}, {"detected_at": T0 + 1.5, "object_type": None}])
        == EMPTY_IND
    )
    assert detect_tailgating([{"object_type": "PERSON", "detected_at": T0}, *persons(1.5)]) == (
        sc.TailgatingIndicator(
            detected=True,
            confidence=0.65,
            description="2 persons detected entering in quick succession",
            persons_involved=2,
            time_gap_seconds=1.5,
        )
    )


# ============================================================================
# adjust_risk_score
# ============================================================================


def test_k47_adjust_forwarding_full_metadata() -> None:
    """ar19/ar23 (detections kwarg dropped -> classify never sees the person
    detection -> historical skip -> scenarios [] -> escalation 35 carries the
    result instead of floor 65), ar4/ar5 (scenarios key twins), ar12/ar13
    (tailgating key twins), ar48..ar59 + ar71/ar72 (subdict key twins), ar6/
    ar7/ar8/ar9/ar10/ar11 (initial-value twins): FULL metadata equality in a
    world where every channel is independently load-bearing."""
    score, meta = adjust_risk_score(
        raw_score=10,
        detections=persons(0.0, 1.5),
        summary="graffiti",
        reasoning="pre-existing",
    )
    assert score == 65
    assert meta == {
        "original_score": 10,
        "scenarios": ["graffiti"],
        "floor_applied": True,
        "floor_score": 65,
        "tailgating": {
            "detected": True,
            "confidence": 0.65,
            "description": "2 persons detected entering in quick succession",
            "persons_involved": 2,
            "time_gap_seconds": 1.5,
        },
        "hysteresis_applied": False,
    }


def test_k47_adjust_reasoning_channel_only() -> None:
    """ar22/ar26 (reasoning dropped): the historical+graffiti keywords ride
    ONLY in reasoning, person evidence in the detection - shipped classifies
    GRAFFITI (65); the twin sees no keywords -> scenarios [] -> 20."""
    score, meta = adjust_risk_score(
        raw_score=20,
        detections=[{"object_type": "person"}],
        reasoning="pre-existing graffiti",
    )
    assert score == 65
    assert meta["floor_applied"] is True
    assert meta["floor_score"] == 65
    assert meta["scenarios"] == ["graffiti"]


def test_k47_adjust_floor_score_authority() -> None:
    """ar38 (assigned None), ar39/ar40 (key twins -> KeyError), ar41
    (get_scenario_floor_score(None) -> 0 via the falsy guard): when applied,
    floor_score == get_scenario_floor_score(scenarios) == 65."""
    _, meta = adjust_risk_score(raw_score=20, summary="graffiti")
    assert meta["floor_score"] == sc.get_scenario_floor_score([ScenarioType.GRAFFITI]) == 65


def test_k47_adjust_no_scenario_passthrough_full_meta() -> None:
    """Initial-dict twins (ar4..ar13) second read + the passthrough world."""
    score, meta = adjust_risk_score(raw_score=20, summary="a quiet street")
    assert score == 20
    assert meta == {
        "original_score": 20,
        "scenarios": [],
        "floor_applied": False,
        "floor_score": 0,
        "tailgating": None,
        "hysteresis_applied": False,
    }


def test_k47_adjust_escalation_log_exact() -> None:
    """ar65 (message None), ar66 (extras None), ar68 (extras dropped), ar69/
    ar70 (extras key twins), ar63 (div twin -> score 94, message "20 -> 94"),
    ar47/ar48 (tailgating dict -> None): raw 20 + 2 persons gap 2.5 ->
    confidence 0.5850000000000001 -> effective 32 -> score 32 + exact INFO +
    BY-NAME extras."""
    with logs() as recs:
        score, meta = adjust_risk_score(raw_score=20, detections=persons(0.0, 2.5))
    assert score == 32
    assert meta["floor_applied"] is True
    infos = [r for r in recs if r.levelno == logging.INFO]
    assert len(infos) == 1
    assert infos[0].getMessage() == "Tailgating escalation: 20 -> 32"
    assert infos[0].tailgating_confidence == 0.5850000000000001
    assert infos[0].persons_involved == 2


def test_k47_adjust_zone_forwarding_exact() -> None:
    """ar44/ar46 (zone_type dropped -> unboosted 35 != 46): gate boost world
    raw 10 gap 1.5 -> confidence 0.8500000000000001 -> effective 46."""
    score, meta = adjust_risk_score(raw_score=10, detections=persons(0.0, 1.5), zone_type="gate")
    assert score == 46
    assert meta["tailgating"]["confidence"] == 0.8500000000000001


def test_k47_adjust_escalation_assign_authority() -> None:
    """ar74 (=None -> clamp TypeError), ar75/ar76 (key twins -> KeyError),
    ar77 (flip False): the gate world reads back True and score 46."""
    score, meta = adjust_risk_score(raw_score=10, detections=persons(0.0, 1.5), zone_type="gate")
    assert meta["floor_applied"] is True
    assert score == 46


def test_k47_adjust_escalation_boundary_strict() -> None:
    """ar63 (div twin: int(55/0.72..) = 76 != 39), ar64 (> vs >=): e2 gap-3.0
    world effective EXACTLY 39 - raw 25 escalates to 39; raw EXACTLY 39 keeps
    floor_applied False (the >= twin would flip it True + log)."""
    score, meta = adjust_risk_score(raw_score=25, detections=persons(0.0, 3.0, 6.0))
    assert meta["tailgating"]["confidence"] == 0.7200000000000001
    assert score == 39
    with logs() as recs2:
        score2, meta2 = adjust_risk_score(raw_score=39, detections=persons(0.0, 3.0, 6.0))
    assert score2 == 39
    assert meta2["floor_applied"] is False
    assert [r for r in recs2 if r.levelno == logging.INFO] == []


def test_k47_adjust_floor_and_escalation_interact() -> None:
    """ar8 (init True second read): floor == score 65 with a 32 escalation
    candidate -> no assign: floor_applied False, floor_score 0, score 65."""
    score, meta = adjust_risk_score(raw_score=65, summary="graffiti", detections=persons(0.0, 2.5))
    assert score == 65
    assert meta["floor_applied"] is False
    assert meta["floor_score"] == 0


def test_k47_adjust_hysteresis_flag_and_debug_exact() -> None:
    """ar80 (pre_hysteresis None -> DEBUG "None -> 59" != pin), ar79 (is-None
    polarity -> hysteresis skipped -> 61 + flag False), ar83 (previous
    dropped -> passthrough -> flag False), ar86 (!= -> == -> flag False +
    NO DEBUG): raw 61 prev 58 -> 59, flag True, BOTH DEBUGs (the internal
    apply_hysteresis "staying below" line, then the wrapper line) pinned in
    ORDER. Control: raw 70 prev 27 -> 70, flag False, SILENT."""
    with logs() as recs:
        score, meta = adjust_risk_score(raw_score=61, previous_score=58)
    assert score == 59
    assert meta["hysteresis_applied"] is True
    assert [(r.levelno, r.getMessage()) for r in recs] == [
        (
            logging.DEBUG,
            "Hysteresis applied: 61 -> 59 (staying below 59 boundary, previous=58)",
        ),
        (logging.DEBUG, "Hysteresis adjustment: 61 -> 59 (previous=58)"),
    ]

    with logs() as recs2:
        score2, meta2 = adjust_risk_score(raw_score=70, previous_score=27)
    assert score2 == 70
    assert meta2["hysteresis_applied"] is False
    assert len(recs2) == 0


def test_k47_adjust_hysteresis_flag_respected() -> None:
    """ar79 both sides + ar86: disable flag passes 31 through (flag False);
    enabled clamps 31 (prev 27; buffer 27..32) -> 29 + flag True."""
    score, meta = adjust_risk_score(
        raw_score=31, previous_score=27, apply_hysteresis_adjustment=False
    )
    assert score == 31
    assert meta["hysteresis_applied"] is False

    score2, meta2 = adjust_risk_score(raw_score=31, previous_score=27)
    assert score2 == 29
    assert meta2["hysteresis_applied"] is True


def test_k47_adjust_clamp_bounds_exact() -> None:
    """ar92 (lower clamp 1): raw -20 -> EXACTLY 0; upper clamp raw 120 -> 100."""
    assert adjust_risk_score(raw_score=-20)[0] == 0
    assert adjust_risk_score(raw_score=120)[0] == 100
