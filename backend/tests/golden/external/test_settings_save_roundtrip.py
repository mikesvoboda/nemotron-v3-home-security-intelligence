"""F-190 / F-191 — the settings SAVE leg: a `PATCH /api/v1/settings` value
written to ``runtime.env`` comes back on the next ``GET`` over real HTTP.

Inventory rows: ``docs/reference/feature-inventory.md`` §Admin, grep anchors
``Feature toggles`` (F-190) and ``System config`` (F-191). Both rows list the
same two-endpoint contract — ``PATCH /api/v1/settings`` then
``GET /api/v1/settings`` — and both are ``half-built`` because only the read leg
was ever witnessed. This spec is the save leg. Ruling 130 flipped these rows on
the read leg alone until ruling 127's writable ``runtime.env`` reached the CI
compose; #7074 landed that as ``HSI_RUNTIME_ENV_PATH=/tmp/runtime.env``
(``docker-compose.ci.yml:157``), which is what makes the write leg observable
here and is why this is new authoring rather than a flip of a broken pin.

Three things make these assertions witnesses and not a tautology:

* ``update_settings`` (``backend/api/routes/settings_api.py:294``) writes the
  env file, then ``get_settings.cache_clear()`` (:350), then returns
  ``get_user_settings()`` which re-inits ``Settings(_env_file=...)``
  (``backend/core/config.py:3497-3500``). A follow-up ``GET`` is therefore a
  *fresh* re-read from the files, so it reports the new value only if the value
  is on disk — an in-memory-only mutation would be undone by the ``cache_clear``.
  The persistence leg (the ``GET`` after the ``PATCH``) is the load-bearing one.
* ``status_code == 200`` is itself the original-bug witness. Before #7074 the
  path defaulted to ``./data/runtime.env``; ``/app/data`` is mounted
  ``read_only: true``, so ``_write_runtime_env`` raised ``OSError`` and the route
  answered 500 (``[Errno 30]``). That 500 is exactly what the assertion below
  would have caught; it is green now only because the write targets tmpfs.
* Neither key is exported as a real container env var in
  ``docker-compose.ci.yml`` (nor in the tracked ``.env.example`` / ``.env.bench``).
  pydantic-settings ranks a real OS env var ABOVE ``_env_file``, so had one been
  set the write could never be read back and this spec would red on a *correct*
  save. It is a genuine round trip precisely because ``_env_file`` is the sole
  source of these two values.

Each test drives one env key the ``SETTINGS_ENV_MAP`` maps
(``settings_api.py:40-79``), and the three tests use three DISJOINT keys so the
tier's ``-n 8 --dist=worksteal`` cannot interleave a write one test is checking.
Every test restores its key and confirms the restore, so a passing run leaves
the stack exactly as it found it.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]

SETTINGS_PATH = "/api/v1/settings"

# A value in band (max_size: ge=100, le=100000) that is neither the default
# (10000) nor a round config number, so it cannot be confused with a value some
# other component happens to set.
QUEUE_NON_DEFAULT = 4242


@pytest.fixture(scope="session", autouse=True)
def save_leg_login_preflight(api_url: str, admin_credentials: dict[str, str]) -> None:
    """Fail — never skip — when the harness is up but this spec cannot log in.

    ``logged_in_api`` answers a non-200 login with ``pytest.skip``
    (``conftest.py:131``), which is the right call for a spec that merely prefers
    a principal. Here it would be an evidential hole: the golden gate reddens only
    when *every* spec in the leg skipped (``scripts/feature_check.py:1169``), and
    the leg's metrics specs run on the *unauthenticated* ``api`` fixture
    (``test_metrics_scrape.py:101``), so a dead login leaves 5 rows executed and
    prints a green tier with all three of these tests absent. That is a pass that
    proves nothing, which is the failure ruling 114 was written against.

    So the precondition is asserted, not skipped, and the assertion is scoped to
    this module: a module that never requests these fixtures is untouched.
    ``api_url`` and ``admin_credentials`` still ``pytest.skip`` when the harness
    env is absent, which is the honest skip ruling 86 asks for — collection and a
    stack-less machine stay green. Only the "env present AND login refused"
    combination is red, and it is recorded ``failed`` because the harness maps
    ``<failure|error>`` to ``failed`` (``junit_results``, ``feature_check.py:1140``).

    Scope is ``session`` deliberately. A module-scoped autouse fixture runs *after*
    the session-scoped ``logged_in_api`` it is meant to outrank, so its skip wins
    and the preflight never executes — measured, not reasoned: a module-scoped
    version of this fixture is reported ``skipped`` while a session-scoped one is
    reported ``failed`` for the same simulated login failure.
    """
    with httpx.Client(base_url=api_url, timeout=30.0) as client:
        response = client.post("/api/auth/login", json=admin_credentials)
    if response.status_code != 200:
        raise AssertionError(
            f"the save-leg witness cannot run: POST /api/auth/login answered "
            f"{response.status_code}, not 200, on a stack whose harness env is fully "
            f"present. These three tests would be SKIPPED and the backend golden tier "
            f"would still read green, because its metrics specs need no login — a "
            f"green that never executed F-190/F-191's save leg. Body: {response.text[:200]}"
        )


def _read(client: httpx.Client) -> dict:
    """``GET /api/v1/settings`` as a dict, asserting the read leg is healthy.

    A 500 here is the F-187 family's own signature (the response schema rejecting
    a value the config emitted); this spec is about the *save* leg, so an
    unhealthy read is reported as such rather than masking a save failure.
    """
    response = client.get(SETTINGS_PATH)
    assert response.status_code == 200, response.text[:500]
    return response.json()


def _patch(client: httpx.Client, payload: dict) -> dict:
    """``PATCH /api/v1/settings`` and return its response body.

    Asserts 200, not 500: 500 is ``[Errno 30] Read-only file system`` on the
    pre-#7074 compose, which is the very defect F-190/F-191's save leg pins.
    """
    response = client.patch(SETTINGS_PATH, json=payload)
    assert response.status_code == 200, response.text[:500]
    return response.json()


def _set_and_confirm(client: httpx.Client, section: str, field: str, value: object) -> None:
    """Save one field and prove it persisted across a settings re-init.

    Two witnesses, in the order the inventory contract lists them: the ``PATCH``
    response echoes the new value, then a separate ``GET`` — served from a fresh
    ``get_settings()`` after ``cache_clear()`` — still reports it. The second is
    the one that cannot pass on an in-memory-only write.
    """
    patched = _patch(client, {section: {field: value}})
    assert patched[section][field] == value, (
        f"PATCH response did not echo {section}.{field}={value!r}: {patched[section]!r}"
    )
    after = _read(client)
    assert after[section][field] == value, (
        f"GET after PATCH did not observe {section}.{field}={value!r}; the write did "
        f"not persist to runtime.env across the settings re-init. GET {section}: "
        f"{after[section]!r}"
    )


def test_f190_feature_toggle_save_roundtrip(logged_in_api: httpx.Client) -> None:
    """F-190: a feature toggle flips on the save leg and comes back on ``GET``.

    ``clip_generation_enabled`` defaults ``True`` (``backend/core/config.py:2703``)
    and maps to ``CLIP_GENERATION_ENABLED`` (``settings_api.py:59``). Saving it
    ``False`` and reading it back ``False`` is the half the read-leg spec never
    covered: that the toggle survives a write to ``runtime.env`` and a reload.
    This is a **persistence** witness only. ``clip_generation_enabled`` is read
    once at construction (``backend/services/clip_generator.py:175-176``), so a
    save changes what a *fresh* process sees, not a live one — the restart-required
    behaviour F-190 itself records. It is not evidence a live toggle flipped.
    """
    baseline = _read(logged_in_api)
    default_value = baseline["features"]["clip_generation_enabled"]
    # The witness only means something if we actually move the value off its
    # current value; assert the default is the documented True so the flip below
    # is real rather than a no-op PATCH-identical.
    assert default_value is True, baseline["features"]

    try:
        _set_and_confirm(logged_in_api, "features", "clip_generation_enabled", False)
    finally:
        _patch(logged_in_api, {"features": {"clip_generation_enabled": True}})

    restored = _read(logged_in_api)
    assert restored["features"]["clip_generation_enabled"] is True, restored["features"]


def test_f191_queue_value_save_roundtrip(logged_in_api: httpx.Client) -> None:
    """F-191: a queue value set on the save leg is what the next ``GET`` reports.

    ``queue.max_size`` defaults 10000, band ``ge=100 le=100000``
    (``backend/core/config.py:2370``), mapped to ``QUEUE_MAX_SIZE``
    (``settings_api.py:69``). Writing 4242 and reading 4242 back — through the
    post-write ``cache_clear`` — is the write leg for the System-config row.
    """
    baseline = _read(logged_in_api)
    default_value = baseline["queue"]["max_size"]
    assert default_value != QUEUE_NON_DEFAULT, (
        f"stack already reports queue.max_size={QUEUE_NON_DEFAULT}; the save witness "
        "would be a PATCH-identical no-op"
    )

    try:
        _set_and_confirm(logged_in_api, "queue", "max_size", QUEUE_NON_DEFAULT)
    finally:
        _patch(logged_in_api, {"queue": {"max_size": default_value}})

    restored = _read(logged_in_api)
    assert restored["queue"]["max_size"] == default_value, restored["queue"]


def test_empty_patch_does_not_clobber_a_saved_value(logged_in_api: httpx.Client) -> None:
    """A no-field ``PATCH {}`` writes nothing and must not revert a saved value.

    ``update_settings`` short-circuits when ``_extract_env_updates`` is empty
    (``settings_api.py:321``) — an empty body returns current settings without
    touching ``runtime.env``. The negative control earns its keep by pinning that
    short-circuit: it first saves a non-default ``rate_limiting.burst_size`` (its
    own key, disjoint from the two tests above), then sends ``PATCH {}``, and the
    value must still be the non-default. If the endpoint ever treated an empty
    PATCH as "write the schema defaults", this read would drop back and go red.
    """
    baseline = _read(logged_in_api)
    original = baseline["rate_limiting"]["burst_size"]
    moved = original + 1
    # ``RateLimitingSettingsUpdate.burst_size`` is banded BOTH ways — ``ge=1,
    # le=100`` (``backend/api/schemas/settings_api.py:586-590``) — so this +1 is
    # only in band while the deployed default sits below the ceiling. Assert it
    # rather than discover it: an out-of-band PATCH answers 422 and would surface
    # as a confusing 200-assertion failure several lines down.
    assert 1 <= moved <= 100, (
        f"burst_size default {original} leaves no in-band headroom for the +1 this "
        "witness needs (schema band is ge=1, le=100); pick a different key"
    )

    try:
        _set_and_confirm(logged_in_api, "rate_limiting", "burst_size", moved)

        empty = _patch(logged_in_api, {})
        assert empty["rate_limiting"]["burst_size"] == moved, (
            f"empty PATCH changed a saved value: burst_size was {moved}, PATCH "
            f"response says {empty['rate_limiting']['burst_size']!r}"
        )
        after = _read(logged_in_api)
        assert after["rate_limiting"]["burst_size"] == moved, (
            f"empty PATCH reverted a saved value on the follow-up GET: {after['rate_limiting']!r}"
        )
    finally:
        _patch(logged_in_api, {"rate_limiting": {"burst_size": original}})

    restored = _read(logged_in_api)
    assert restored["rate_limiting"]["burst_size"] == original, restored["rate_limiting"]
