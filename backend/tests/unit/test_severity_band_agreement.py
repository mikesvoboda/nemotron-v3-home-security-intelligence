"""ISS-018's acceptance test: one severity function, every consumer, 0..100.

ISS-018 (docs/vss-integration/17-action-plan.md, "ISS-018 - notification_filter
maps score to level with 40/60/80 bands; shipped bands are 30/60/85") records
that the code spelled the severity bands several different ways at once: the
filter's 40/60/80, the summary parser's 80/60/40, the ack rule's raw 80, and
the bands of record 29/59/84 (``backend/core/config.py``
``Settings.severity_low_max``/``severity_medium_max``/``severity_high_max``).
The fix - shipped in ffb2d17d - is DELEGATION:
``NotificationFilterService._risk_score_to_level`` and
``summary_parser._severity_from_score`` now both call
``SeverityService.risk_score_to_severity``, the one severity function of
record.

This file is the contract test that acceptance asks for - "a parametrised test
over scores 0..100 [asserting] agreement under the defaults and under a
non-default SEVERITY_* configuration". It is deliberately a CENSUS, not a
boundary sample: three separate hard-coded ladders died to produce those
boundaries, and a boundary test only proves the author thought of the edges
they remembered. Every score in the domain gets checked against an independent
oracle (``_expected_level`` below, derived from the settings values themselves),
so five copies agreeing with EACH OTHER is not enough to pass - they must each
agree with the bands.

The copies under test
---------------------
The census's five arms, per the acceptance's named list plus the two extra
copies ISS-018's 2026-10-05 "full band census for the fix" update found:

  1. ``NotificationFilterService._risk_score_to_level`` - the filter seam
     (delegates; the seam itself is AST-pinned by
     ``test_p04_verification_field.py``, which is why ISS-018 had to delegate
     rather than delete);
  2. ``SeverityService.risk_score_to_severity`` - the function of record;
  3. ``summary_parser._severity_from_score`` (delegates);
  4. ``analytics._get_risk_level`` - a STATIC copy in the route module;
  5. ``Event.computed_risk_level`` - a hybrid_property that reads settings at
     call time, so it tracks a non-default configuration the same way the
     delegates do.

``Event.computed_risk_level``'s Python-side arm is read off a transient
``Event(risk_score=n)`` instance: the hybrid_property's Python half is a plain
attribute read plus a settings lookup, so it needs no database, no session and
no flush. (Its ``.expression`` half - the SQL CASE - hard-codes the defaults
too; that arm is covered by the SQL-side pins in
``backend/tests/integration/test_models.py`` and is out of scope for a unit
tier, so this file stays in the fast lane.)

Copies EXEMPT on the record (deliberately NOT in the census - listed here so
nobody re-adds them and a future reader knows the omission is a ruling):

  * ``frontend/src/utils/severityColors.ts`` - the visual color ladders. Its
    docstring states the critical-at-80 early-warn is "deliberately NOT" the
    backend bands and tells future readers not to "unify" them. ISS-018's
    "full band census for the fix" update records it as exempt for exactly
    that reason. A unit test here cannot reach TypeScript anyway.
  * ``frontend/src/utils/risk.ts`` ``RISK_THRESHOLDS`` (29/59/84) - already
    agrees with the bands of record; it is the ladder the backend defaults are
    mirrored from, and it is pinned by its own vitest suite.
  * ``frontend/src/components/settings/NotificationSettings.tsx``
    ``RISK_LEVEL_RANGES`` - the settings-screen ladder that ISS-018's census
    update found still spelling 40/60/80. It has since MOVED to 29/59/84, so
    it no longer needs an exception; it is a frontend constant with its own
    test surface, and restating it here would put a backend test in charge of
    a React file.
  * ``event_broadcaster.requires_ack``'s raw ``risk_score >= 80`` - the ONE
    backend exception, ruled, and carved out by name. See
    ``test_od32_exception_requires_ack_acks_at_raw_80`` below.
  * ``backend/evaluation/harness.py`` - named by the acceptance, deleted in
    d8482861 (R8 S2b retired the Nemotron harness), so there is nothing left
    to agree with. ISS-018's 2026-10-03 update records the deletion.

Voice note for the tests below: the shipped boundary pins stay where they are
(``test_notification_filter.py`` restates the edges at the filter seam,
``test_message_buffer.py`` owns the ack behavior). This file owns the CENSUS -
the "for every score, for every configured band set" half - which is why its
docstrings point at the ruling instead of re-listing numbers.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from backend.api.routes.analytics import _get_risk_level
from backend.core.config import get_settings
from backend.models.event import Event
from backend.models.notification_preferences import (
    CameraNotificationSetting,
    NotificationPreferences,
)
from backend.services.event_broadcaster import requires_ack
from backend.services.notification_filter import NotificationFilterService
from backend.services.severity import get_severity_service, reset_severity_service
from backend.services.summary_parser import _severity_from_score

pytestmark = pytest.mark.unit

# The bands of record, restated as literals ONLY so a test can assert that the
# settings really still say them (a silent .env / runtime.env override in some
# future CI image would otherwise turn the "defaults" census into a census of
# something else, silently).
DEFAULT_BANDS: tuple[int, int, int] = (29, 59, 84)

# ISS-018's acceptance demands a non-default configuration. These are the
# values backend/tests/unit/core/test_config.py's own SEVERITY_* pins use for
# the low bound (19), extended to a strictly-ordered triple.
NON_DEFAULT_BANDS: tuple[int, int, int] = (19, 49, 79)

_ENV_BY_FIELD: tuple[tuple[str, str], ...] = (
    ("SEVERITY_LOW_MAX", "severity_low_max"),
    ("SEVERITY_MEDIUM_MAX", "severity_medium_max"),
    ("SEVERITY_HIGH_MAX", "severity_high_max"),
)

# The scored path needs a timestamp; quiet periods are not part of this file
# (is_quiet_period has its own pins), so it is a fixed value that no period
# could match against an empty period list.
_ARBITRARY_TS = datetime(2026, 10, 5, 14, 30, tzinfo=UTC)

_ALL_LEVELS = ["low", "medium", "high", "critical"]


def _expected_level(score: int, low_max: int, medium_max: int, high_max: int) -> str:
    """The oracle: derive the level from the band maxima themselves.

    This is the fifth statement of the rule, and the only one in this file
    that takes its edges as ARGUMENTS. That is the point - a census that only
    asserts "the copies equal each other" would pass unchanged if all five
    drifted to the same wrong ladder (which is precisely the failure ISS-018
    is about). Every arm here must equal this instead.
    """
    if score <= low_max:
        return "low"
    if score <= medium_max:
        return "medium"
    if score <= high_max:
        return "high"
    return "critical"


def _census(score: int) -> dict[str, str]:
    """Every settings-driven copy's answer for one score, keyed by symbol name.

    ``None`` (the un-scored arm) is not censused: three of these functions
    return None for None and two would crash, and the NULL-score path is
    spec section 6 / ISS-019 territory with its own pins.
    """
    return {
        "NotificationFilterService._risk_score_to_level": NotificationFilterService()
        ._risk_score_to_level(score)
        .value,
        "SeverityService.risk_score_to_severity": get_severity_service()
        .risk_score_to_severity(score)
        .value,
        "summary_parser._severity_from_score": str(_severity_from_score(score)),
        "analytics._get_risk_level": str(_get_risk_level(score)),
        "Event.computed_risk_level": str(Event(risk_score=score).computed_risk_level),
    }


def _delegating_census(score: int) -> dict[str, str]:
    """The census MINUS the one static copy, for the non-default band run.

    ``analytics._get_risk_level`` is excluded here and pinned on its own in
    ``test_analytics_static_ladder_is_a_hardcoded_copy_of_the_default_bands``,
    because it hard-codes 29/59/84 (its comment says "Thresholds match
    backend/core/config.py and frontend/src/utils/risk.ts") and therefore
    cannot follow a configuration it does not read. Listing it, with its own
    named pin, is the path ISS-018's acceptance allows ("are listed in the
    test or fixed with it"); fixing it is product work.
    """
    census = _census(score)
    del census["analytics._get_risk_level"]
    return census


@contextmanager
def configured_bands(bands: tuple[int, int, int]) -> Iterator[tuple[int, int, int]]:
    """Set the SEVERITY_* bands, prove the process really picked them up, and
    always put them back.

    The house settings-override pattern (``backend/tests/unit/conftest.py``
    ``enable_api_key_auth_for_unit_tests`` shows the cache-clear half): mutate
    ``os.environ``, ``get_settings.cache_clear()``,
    ``reset_severity_service()`` (``get_severity_service`` is an
    ``lru_cache(maxsize=1)``, so clearing settings alone would leave the OLD
    ``SeverityService`` instance - and therefore the OLD bands - live behind
    every delegate), then restore in a ``finally``.

    The non-vacuity assertions run INSIDE the context, before the caller's
    assertions: a settings-cache miss, an ignored env var, or a forgotten
    severity-service reset would otherwise make the non-default census a
    re-run of the default one, silently green. Restoring is unconditional
    because pytest-randomly (repo addopts) randomizes test order, so a leaked
    band set would contaminate an arbitrary later test rather than this one.
    """
    low_max, medium_max, high_max = bands
    saved = {env_key: os.environ.get(env_key) for env_key, _ in _ENV_BY_FIELD}
    for (env_key, _field), value in zip(_ENV_BY_FIELD, bands, strict=True):
        os.environ[env_key] = str(value)
    try:
        get_settings.cache_clear()
        reset_severity_service()

        settings = get_settings()
        observed = (
            settings.severity_low_max,
            settings.severity_medium_max,
            settings.severity_high_max,
        )
        assert observed == bands, (
            f"SEVERITY_* env override did not reach Settings: wanted {bands}, "
            f"got {observed} - the census below would be measuring the wrong ladder"
        )
        # And the service every delegate calls has to be the one built from
        # those settings, not the previously cached instance.
        thresholds = get_severity_service().get_thresholds()
        assert thresholds == {
            "low_max": low_max,
            "medium_max": medium_max,
            "high_max": high_max,
        }, f"get_severity_service() still serves the cached bands {thresholds}, not {bands}"

        yield observed
    finally:
        for env_key, value in saved.items():
            if value is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = value
        get_settings.cache_clear()
        reset_severity_service()


@pytest.fixture
def default_bands() -> tuple[int, int, int]:
    """The shipped ladder, verified to be the shipped ladder.

    The default-arm census runs UNSET (no fixture mutates the env for it), so
    a machine or CI image that set SEVERITY_* in the environment would silently
    turn this file's default half into a second non-default run. The assert
    makes that a failure at the first test instead.
    """
    settings = get_settings()
    observed = (
        settings.severity_low_max,
        settings.severity_medium_max,
        settings.severity_high_max,
    )
    assert observed == DEFAULT_BANDS, (
        f"SEVERITY_* is not at its shipped default here ({observed} != "
        f"{DEFAULT_BANDS}) - the 'defaults' census would be measuring something else"
    )
    return observed


# ---------------------------------------------------------------------------
# The census, defaults: all five copies, every score.
# ---------------------------------------------------------------------------


class TestBandAgreementAtDefaults:
    """ISS-018's acceptance, default arm: at every score 0..100 all five
    copies answer the same level, and that level is what the settings derive."""

    @pytest.mark.parametrize("score", range(0, 101))
    def test_every_copy_agrees_with_the_bands_of_record(self, score: int, default_bands):
        census = _census(score)
        expected = _expected_level(score, *default_bands)

        # One assert per copy, so a failure names WHICH copy drifted rather
        # than dumping a dict of five and leaving the reader to diff it.
        for symbol, level in census.items():
            assert level == expected, (
                f"score {score}: {symbol} said {level!r}, the bands of record "
                f"{default_bands} say {expected!r}"
            )

    @pytest.mark.parametrize("score", range(0, 101))
    def test_every_copy_agrees_with_the_others(self, score: int, default_bands):
        """The pairwise half, stated separately from the oracle.

        Redundant with the test above in isolation - and deliberately kept:
        the two fail for different reasons. A drifted oracle would break only
        the first; a copy that returns a non-string (an enum leaking through
        where a value was expected) breaks the equality of the second on shape
        rather than on band. Keeping both means the census cannot go green by
        two mistakes cancelling out.
        """
        census = _census(score)
        assert set(census.values()) == {_expected_level(score, *default_bands)}, census

    def test_the_census_actually_covers_the_named_copies(self, default_bands):
        """Non-vacuity guard for the parametrized pair above.

        A census over an empty or accidental dict passes at every score (the
        repo's recurring vacuity lesson - see
        ``test_r8_s3_florence_provider_retirement.py``'s "every scan pins its
        own non-vacuity"). This pins the arm COUNT and the four distinct
        levels the 0..100 sweep is supposed to traverse.
        """
        assert len(_census(50)) == 5, "ISS-018 named five copies; the census must carry five"
        levels = {level for score in range(101) for level in _census(score).values()}
        assert levels == {"low", "medium", "high", "critical"}, (
            "the sweep over 0..100 must exercise all four bands, or it is not a census"
        )

    @pytest.mark.parametrize("score", [29, 30, 59, 60, 84, 85])
    def test_the_moved_edges_are_where_the_ruling_says_they_are(self, score: int, default_bands):
        """The four edges, spelled out, because their MOVEMENT is the fix.

        ISS-018 shipped with the filter's edges at 40/60/80 and the bands of
        record at 29/59/84, so 30-39 used to be 'low' to the filter while the
        UI called them medium, and 80-84 used to be 'critical' to the filter
        while the UI called them high. These six scores are exactly the
        reclassified territory; a test that only checked mid-band values would
        have passed before the fix.
        """
        expected = _expected_level(score, *default_bands)
        for symbol, level in _census(score).items():
            assert level == expected, f"score {score}: {symbol} said {level!r}, want {expected!r}"


# ---------------------------------------------------------------------------
# The census, non-default SEVERITY_*: the acceptance's second arm.
# ---------------------------------------------------------------------------


class TestBandAgreementUnderNonDefaultBands:
    """ISS-018's acceptance, configured arm: "and under a non-default
    SEVERITY_* configuration". Bands move to 19/49/79 and the settings-driven
    copies must move with them, together.

    ``analytics._get_risk_level`` is not in this census - see
    ``_delegating_census`` and ``TestAnalyticsStaticLadder`` for the listing
    ISS-018's acceptance allows.
    """

    @pytest.mark.parametrize("score", range(0, 101))
    def test_every_settings_driven_copy_follows_the_configured_bands(self, score: int):
        with configured_bands(NON_DEFAULT_BANDS) as bands:
            # Belt over braces: the context manager already proved the bands
            # landed, and "non-default" is the property that makes this arm
            # distinct from the one above.
            assert bands != DEFAULT_BANDS, (
                "a non-default run that equals the defaults is not a second arm"
            )
            census = _delegating_census(score)
            expected = _expected_level(score, *bands)
            for symbol, level in census.items():
                assert level == expected, (
                    f"score {score} under bands {bands}: {symbol} said {level!r}, want {expected!r}"
                )

    def test_the_reclassified_scores_are_reclassified(self):
        """The proof that moving the settings moved the ANSWER, not just the
        numbers on a settings object.

        Scores 20-29 are 'low' at the shipped defaults and 'medium' here; 50-59
        are medium -> high; 80-84 are high -> critical. If a delegate captured
        its bands at import time (the bug class ``reset_severity_service``
        exists for), every row of the parametrized test above would still pass
        at the DEFAULT answer while this one failed.
        """
        with configured_bands(NON_DEFAULT_BANDS):
            assert NotificationFilterService()._risk_score_to_level(20).value == "medium"
            assert NotificationFilterService()._risk_score_to_level(29).value == "medium"
            assert NotificationFilterService()._risk_score_to_level(50).value == "high"
            assert NotificationFilterService()._risk_score_to_level(59).value == "high"
            assert NotificationFilterService()._risk_score_to_level(80).value == "critical"
            assert _severity_from_score(80) == "critical"
            assert Event(risk_score=80).computed_risk_level == "critical"

    @pytest.mark.parametrize("score", [19, 20, 29, 30, 49, 50, 59, 60, 79, 80, 84, 85])
    def test_the_default_census_is_restored_after_the_context_exits(self, score: int):
        """Restoration pin, run at the edges so it cannot pass vacuously.

        Same score set as the drift pin below, for the same reason: a band set
        that leaked past the ``finally`` would disagree with the shipped ladder
        at exactly these scores - and under pytest-randomly the victim would be
        some unrelated later test, which is the worst possible failure site."""
        expected = _expected_level(score, *DEFAULT_BANDS)
        for symbol, level in _census(score).items():
            assert level == expected, (
                f"score {score}: {symbol} said {level!r} after the override was "
                f"supposed to be restored (want {expected!r})"
            )


class TestAnalyticsStaticLadder:
    """The LISTING half of ISS-018's "listed in the test or fixed with it".

    ``backend/api/routes/analytics.py::_get_risk_level`` is a hard-coded copy.
    It agrees with the bands of record - that is what the default-arm census
    above pins, at every one of the 101 scores - but it cannot follow a
    SEVERITY_* configuration, because it does not read one. So it is the one
    census arm that gets an explicit, named, and narrow pin instead of a pass:
    under a non-default band set it keeps answering with the DEFAULT ladder.

    That is a real, measured divergence, not a hypothetical: the camera-activity
    endpoint's ``risk_level`` would describe a score 50 as medium while the
    filter and the stored level call it high, on an install that moved its
    bands. The reason it is not fixed here: this test wave does not touch
    product code. Fixing it is a one-line delegation to ``get_severity_service``
    (the same move ffb2d17d made at the filter and the parser), and the day
    someone makes it they should DELETE this class rather than edit it - the
    pin's whole content is "this copy is static".
    """

    @pytest.mark.parametrize("score", [19, 20, 29, 30, 49, 50, 59, 60, 79, 80, 84, 85])
    def test_static_ladder_is_pinned_to_the_default_bands(self, score: int):
        with configured_bands(NON_DEFAULT_BANDS):
            static_answer = _get_risk_level(score)
        assert static_answer == _expected_level(score, *DEFAULT_BANDS), (
            f"score {score}: analytics._get_risk_level said {static_answer!r} under "
            f"bands {NON_DEFAULT_BANDS}. It answers with the DEFAULT ladder by "
            f"design; if you just delegated it to SeverityService, delete this "
            f"class - a static copy is no longer being listed if it is gone."
        )

    @pytest.mark.parametrize("score", range(0, 101))
    def test_static_ladder_agrees_with_the_function_of_record_at_defaults(
        self, score: int, default_bands
    ):
        """The listing's other half: at the configuration every real install
        runs (ISS-018's own Severity note: "a non-default SEVERITY_* is
        hypothetical (no compose or env file overrides it)") the static copy is
        not a divergence at all."""
        assert _get_risk_level(score) == get_severity_service().risk_score_to_severity(score).value


# ---------------------------------------------------------------------------
# should_notify agrees with the bands, through its own filter.
# ---------------------------------------------------------------------------


class TestShouldNotifyAgreesWithTheBands:
    """ISS-018's acceptance names ``should_notify``'s LEVEL as a consumer under
    test, and the point of running the census through it rather than stopping
    at ``_risk_score_to_level`` is that the level is only half a decision: the
    mapping can be right and the filter still wrong.

    Two settings make the level filter the ONLY thing the answer can turn on:

      * ``risk_filters`` carries the levels under test, and
      * a ``camera_setting`` with ``risk_threshold=0``.

    The second is not cosmetic. OD-29 (owner ruling 2026-10-05,
    docs/vss-integration/17-action-plan.md Intake log) raised
    ``DEFAULT_CAMERA_RISK_THRESHOLD`` to 60 and ruled that "no row" means the
    shipped default setting, not "no floor" - so a test that passed
    ``camera_setting=None`` would get a numeric floor of 60 in the way, and
    every score below 60 would answer False for a reason that has nothing to
    do with bands. A saved value wins over that default (OD-29's
    saved-value-wins clause), so threshold 0 steps the floor out of the path
    and leaves the level filter alone.

    ``verification_verdict`` stays None throughout: the ``rejected`` skip is
    spec section 6's absolute rule and is pinned in
    ``test_notification_filter.py`` and ``test_vlm_analyzer.py``; a rejected
    verdict would make every row False for the wrong reason.
    """

    # The filter subsets are the discriminating part. With all four levels
    # allowed the answer is True everywhere (that row is the "does the level
    # filter pass anything it should" sanity check); the smaller subsets are
    # what turn the census into a test of the EDGES - a band that is one point
    # off puts a score in the wrong answer exactly at the boundary.
    @pytest.mark.parametrize(
        "risk_filters",
        [
            _ALL_LEVELS,
            ["critical"],
            ["high", "critical"],
            ["medium", "high"],
            ["low"],
            [],
        ],
        ids=["all", "critical-only", "high-and-critical", "medium-and-high", "low-only", "none"],
    )
    @pytest.mark.parametrize("score", range(0, 101))
    def test_answer_is_exactly_whether_the_level_passes_the_filter(
        self, score: int, risk_filters: list[str], default_bands
    ):
        prefs = NotificationPreferences(enabled=True, risk_filters=list(risk_filters))
        camera_setting = CameraNotificationSetting(
            camera_id="band-census-cam", enabled=True, risk_threshold=0
        )
        level = _expected_level(score, *default_bands)

        answer = NotificationFilterService().should_notify(
            risk_score=score,
            camera_id="band-census-cam",
            timestamp=_ARBITRARY_TS,
            global_prefs=prefs,
            camera_setting=camera_setting,
            quiet_periods=None,
        )
        assert answer is (level in risk_filters), (
            f"score {score} is {level!r} under bands {default_bands}; with "
            f"risk_filters={risk_filters} should_notify answered {answer}"
        )

    @pytest.mark.parametrize("score", range(0, 101))
    def test_the_filter_follows_a_configured_ladder(self, score: int):
        """...and under a moved ladder, the filter moves with it.

        Same construction as above under bands 19/49/79. The concrete
        expectation this pins: a score 50 with filters {high, critical} must
        notify, because 50 is high at 19/49/79, while at the shipped defaults
        the same score and the same filters answer False (50 is medium). That
        flip is ISS-018's world-class gap in one row - the acceptance's
        "a user whose risk_filters include medium is not notified for a
        score-35 event the UI calls medium", with the bands as the variable.
        """
        with configured_bands(NON_DEFAULT_BANDS) as bands:
            prefs = NotificationPreferences(enabled=True, risk_filters=["high", "critical"])
            camera_setting = CameraNotificationSetting(
                camera_id="band-census-cam", enabled=True, risk_threshold=0
            )
            answer = NotificationFilterService().should_notify(
                risk_score=score,
                camera_id="band-census-cam",
                timestamp=_ARBITRARY_TS,
                global_prefs=prefs,
                camera_setting=camera_setting,
                quiet_periods=None,
            )
            assert answer is (_expected_level(score, *bands) in {"high", "critical"})

    def test_the_configured_and_default_arms_disagree_on_purpose(self):
        """The flip, named, so the parametrized test above cannot be read as
        a tautology: identical inputs, two band settings, opposite answers.

        The three scores are each band's upper neighbour: 20 is low-at-defaults
        / medium-at-19, 50 is medium / high, 80 is high / critical. Under
        filters {high, critical} all three flip True only under the moved
        ladder. If both arms answered alike the test above would be measuring
        one ladder twice.
        """
        prefs = NotificationPreferences(enabled=True, risk_filters=["high", "critical"])
        camera_setting = CameraNotificationSetting(
            camera_id="band-census-cam", enabled=True, risk_threshold=0
        )
        service = NotificationFilterService()

        def decide(score: int) -> bool:
            return service.should_notify(
                risk_score=score,
                camera_id="band-census-cam",
                timestamp=_ARBITRARY_TS,
                global_prefs=prefs,
                camera_setting=camera_setting,
                quiet_periods=None,
            )

        at_defaults = {score: decide(score) for score in (20, 50, 80)}
        with configured_bands(NON_DEFAULT_BANDS):
            at_configured = {score: decide(score) for score in (20, 50, 80)}

        assert at_defaults == {20: False, 50: False, 80: True}, at_defaults
        assert at_configured == {20: False, 50: True, 80: True}, at_configured
        assert at_defaults[50] is not at_configured[50], (
            "score 50 must flip between the two ladders under {high, critical} - "
            "if it does not, the non-default arm is not measuring a different band set"
        )


# ---------------------------------------------------------------------------
# The one named exception: OD-32's ack edge.
# ---------------------------------------------------------------------------


def test_od32_exception_requires_ack_acks_at_raw_80() -> None:
    """The OD-32 carve-out, carved out BY NAME.

    ISS-018's acceptance lists ``requires_ack``'s critical test as a consumer
    that must agree with the bands. Aligning it would move its boundary off the
    raw 80 onto 85, which silently changes what a user is prompted to
    acknowledge at 80-84 - a user-visible behavior change dressed up as a bug
    fix. That is exactly the question raised as **OD-32** and ruled 2026-10-05
    as "(a) keep the popup" (docs/vss-integration/17-action-plan.md Intake log,
    and the OD table's OD-32 row): the raw 80 edge stands as a DELIBERATE
    EARLY-ACK, carved out of ISS-018's agreement test by name, and
    ``backend/tests/unit/services/test_message_buffer.py::
    test_high_risk_score_requires_ack`` stays untouched as the shipped pin of
    that intent.

    So this function does NOT run ``requires_ack`` through the census. It
    records the drift instead: at 80-84 the bands say ``high`` and the ack
    rule says ack. The comment in ``event_broadcaster.requires_ack`` says the
    same thing from the other side ("Do not 'align' this to the bands"), so
    this test and that comment are the two halves of one ruling - the code
    says it is deliberate, this test says it is measured and expected.

    The shipped pin is not touched, re-parametrized or imported here. This is
    a second, SEPARATE witness: it names the four scores the drift covers
    (79/80/84/85 - the two edges of the early-ack window and one score each
    side) and states what each copy answers for them.
    """
    settings = get_settings()
    bands = (
        settings.severity_low_max,
        settings.severity_medium_max,
        settings.severity_high_max,
    )

    def ack(score: int) -> bool:
        # risk_level rides "high" deliberately: the frame's own level string is
        # what the stored event carries for an 80-84 score, so an ack at those
        # scores can only be coming from the raw-score arm. A "critical" level
        # would let requires_ack's second arm answer instead and hide the edge.
        return requires_ack({"type": "event", "data": {"risk_score": score, "risk_level": "high"}})

    # Below the window: no ack, and the bands agree it is not critical.
    assert ack(79) is False
    assert _expected_level(79, *bands) == "high"

    # Inside the window: ack, though the bands still say "high". This is the
    # whole of OD-32 - four points of score where the two rules disagree and
    # the owner chose the popup.
    for score in (80, 82, 84):
        assert ack(score) is True, f"score {score} must keep prompting (OD-32 'keep the popup')"
        assert get_severity_service().risk_score_to_severity(score).value == "high", (
            f"score {score} is high per the bands of record {bands} - if this "
            f"stops being true, the early-ack window has moved and this test, "
            f"not just the ack rule, needs re-reading"
        )

    # Above the window: the two rules agree again, which is what bounds the
    # exception to 80..high_max and keeps it from being a general waiver.
    for score in (85, 100):
        assert ack(score) is True
        assert _expected_level(score, *bands) == "critical"

    # A NULL score never acks on the numeric arm (P0.25: verification_failed
    # carries a PRESENT-None score). Not part of OD-32, but it shares the line
    # of code, so a reader changing that line gets warned here too.
    assert (
        requires_ack({"type": "event", "data": {"risk_score": None, "risk_level": None}}) is False
    )
