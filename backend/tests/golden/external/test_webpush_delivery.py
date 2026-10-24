"""B4.3 golden path — one Web Push delivery through the live stack (4n-alerting.md).

The box's row is "Golden path (pytest) against [r308a]'s push-service fake":
a MEDIUM-tier fixture image dropped into the run's camera root flows through
the real pipeline (watcher → detector → fake VLM → policy → planner →
delivery row → worker → ``WebPushChannel``), and the push service fake
records what actually arrived on the wire — read back here, decrypted here.

Why every layer is the product's own and none is patched:

* the **fixture** is ``f4.4-gold-high.jpg`` plus the suffix ``webpush-golden-9``
  appended past the JPEG EOI (PIL tolerates trailing bytes, so verify and load
  pass and the watcher's 10 KB minimum clears). The suffix picks the digest:
  sha256 ``dbc76388…059785`` draws ``confirmed`` / risk **43** from the fake
  VLM's ``vlm_assess`` generator — the ``gateway`` profile, since the
  production client sets no ``x-fake-profile`` header — and 43 is MEDIUM tier
  (severity_low_max=29 < 43 <= severity_medium_max=59, ``severity.py``), so
  the **default** rule (risk_threshold 60) stays silent and the frontend's
  ``assertSoleAlertIsSmoke`` pin (exactly one high/critical event on the
  shared stack, shard 4) keeps holding.
* the **rule** is a custom rule created over the API, threshold 30 scoped to
  this leg's own camera: a custom rule's tier filter is the default rule's
  privilege (``policy.py``'s ``_check_verdict_and_severity`` skips
  ``risk_filters`` for non-default rules), so threshold 30 matches the
  MEDIUM event while the default rule never fires, and the alert carries the
  rule's name, which ``payload.py`` puts in the push title.
* the **subscription** is registered through the API the settings page uses
  (``PUT /api/notification-preferences/push-subscription``), with a real P-256
  p256dh key so ``pywebpush`` can encrypt to it and a random auth secret. The
  endpoint is the sink's in-network address (``FEATURE_CHECK_SINK_PUSH_HOST``,
  read off the same rendered compose.json the backend boots with), because the
  backend container dials it; the read-back uses the host-side loopback URL
  the harness exports separately (``FEATURE_CHECK_SINK_PUSH_URL``). Both
  spellings exist because inside the backend container the host-side loopback
  URL points at the backend, not the sink.
* the **encryption** is proven end to end: the sink records the raw request
  bytes (``body_b64``, added for this leg), and the leg decrypts the
  ciphertext with ``http_ece`` using only the receiver's private key and auth
  secret — RFC 8291's contract — and gets back exactly the title JSON the
  adapter builds (``{"title": <rule name>}``). That single assertion covers
  the privacy row ("push carries the title only") on the wire: anything more
  than the title in the payload reds here.

The camera folder is the leg's own (``golden-b43-webpush`` → camera id
``golden_b43_webpush`` after the watcher's normalization), so the watcher
auto-creates a camera scoped to this run and the teardown (permanent event
purge — which cascades the alert and its delivery rows — rule delete,
subscription delete) removes everything the leg created. The dedupe window
is 300 s; the fixture bytes are unique to this module and the module drops
once.

Per-worker isolation (the CI red of 2026-10-23): the repo's default addopts
run ``-n 8 --dist=worksteal``, which schedules at FUNCTION granularity — a
module whose tests land on two workers builds TWO full fixture chains, one
per worker. Two chains over the same constants collide three ways, each
observed in run 39906556327: (1) dedupe keys on file CONTENT only
(``dedupe:{sha256}``, camera-independent), so both chains' drops collapse
onto one event and one chain's teardown deletes the other's fixture;
(2) the subscription upsert keys the channel row on ``device_id`` — a second
PUT with the same id ROTATES the row's endpoint and keys in place
(``_push_channel_of``), leaving the first worker's receiver keys pointing at
a subscription that no longer matches the row the worker sends to;
(3) one teardown purges the shared event while the other chain is still
reading it. So every identity the chain touches is keyed per xdist worker
(``PYTEST_XDIST_WORKER``, 'master' when serial): folder, camera, device,
rule, and the fixture SUFFIX — because dedupe and the fake VLM's verdict
draw both key on bytes, camera folders alone would not separate the chains
(``app.py:_images_of`` hashes the decoded data-URI bytes). Each worker's
suffix is measured to draw confirmed / MEDIUM (above this leg's rule
threshold 30, below the default rule's 60) from
``_rng_for("vlm_assess", digest, "gateway", "verdict")`` and pinned by
digest so a moved fixture re-measures instead of silently redrawing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import http_ece
import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]

# Per-worker fixture suffixes: ``webpush-golden-<worker ordinal>-9-<draw>``,
# each measured (backend/ai_contract/fake/generators.py:456's draw, gateway
# profile, on f4.4-gold-high.jpg's bytes) to land verdict=confirmed with a
# risk_score in 31..59 — MEDIUM tier: above this leg's custom-rule threshold
# 30 (policy.py: `score < threshold` refuses), below the default rule's 60 so
# the frontend's sole-high-event pin on the shared stack keeps holding.
# Digests pinned per worker so a moved fixture re-measures instead of
# silently drawing a different tier. sha256 of public fixture bytes — the
# digests the fake VLM draws from, not secrets.
_WORKER_DIGESTS: dict[str, str] = {
    "gw0": "2d47fa5c34788a627f33b613441dc463536efea43c6306839def418047d55928",  # pragma: allowlist secret
    "gw1": "da2c2038bd7a0c8ab85a61c41e3ecb1e4df78804ab60b4daf152185719daebeb",  # pragma: allowlist secret
    "gw2": "2055e78d0fab83d7c1bd5d8d44f353ab72aa37daa030f4c0ae651224285ed467",  # pragma: allowlist secret
    "gw3": "5b634dd96b3ecf3b2639ea8456a107613750d556d31ab56f703e8c858ce63c65",  # pragma: allowlist secret
    "gw4": "67ae9e1d7287251da35a594c664258b7c6a09e3dab68a52bc95a4fb614c70400",  # pragma: allowlist secret
    "gw5": "7e4384e3de5de23a6b18ba05453124ee10d8d079b7633c510118025ada51bdd3",  # pragma: allowlist secret
    "gw6": "db7f860dd479609875fb4960d3c285c0cf2a9dc9f03ad9e5edf0c74cd7286e69",  # pragma: allowlist secret
    "gw7": "12d622b15e2e706b2940ea0f98abcdb0f2dea358922d51a5953a539cf846b061",  # pragma: allowlist secret
}
_WORKER_SUFFIXES: dict[str, str] = {
    "gw0": "webpush-golden-0-9-5",
    "gw1": "webpush-golden-1-9-2",
    "gw2": "webpush-golden-2-9-2",
    "gw3": "webpush-golden-3-9-8",
    "gw4": "webpush-golden-4-9-6",
    "gw5": "webpush-golden-5-9-0",
    "gw6": "webpush-golden-6-9-24",
    "gw7": "webpush-golden-7-9-7",
}
# The serial run's identity (no xdist): the original single suffix/digest.
_MAIN_SUFFIX = "webpush-golden-9"
_MAIN_DIGEST = (
    "dbc7638825570c937bb74c491150293d3ab805a015783741279b807ec0059785"  # pragma: allowlist secret
)


# WebPushChannel._TTL_SECONDS (adapter): one hour per RFC 8030's offline hold.
_TTL = "3600"


def _leg() -> dict[str, str]:
    """This chain's identity: worker-keyed camera, device, rule and fixture.

    One dict because the identity is used together everywhere; a worker id
    outside the measured tables (a -n value above 8, a future renames) fails
    LOUDLY here rather than silently sharing another worker's identity —
    the red the per-worker split exists to prevent.
    """
    wid = os.environ.get("PYTEST_XDIST_WORKER", "master")
    if wid == "master":
        suffix, digest = _MAIN_SUFFIX, _MAIN_DIGEST
    elif wid in _WORKER_SUFFIXES:
        suffix, digest = _WORKER_SUFFIXES[wid], _WORKER_DIGESTS[wid]
    else:
        pytest.fail(
            f"no measured fixture suffix for xdist worker {wid!r}: the fake VLM's "
            f"verdict draw is keyed on the fixture bytes, so every worker needs a "
            f"suffix measured to confirmed/MEDIUM (see the module docstring)"
        )
    n = wid.removeprefix("gw") if wid.startswith("gw") else "main"
    return {
        "suffix": suffix,
        "digest": digest,
        "camera_folder": f"golden-b43-webpush-{n}",
        "camera": f"golden_b43_webpush_{n}",  # Camera.from_folder_name normalizes [-\s] to _
        "device": f"golden-webpush-{n}",
        "rule": f"golden-b43-webpush-rule-{n}",
    }


SINK_ENV = (
    "FEATURE_CHECK_SINK_PUSH_URL",
    "FEATURE_CHECK_SINK_PUSH_HOST",
    "FEATURE_CHECK_MODE",
)


def _sinks() -> dict[str, str]:
    """The push sink's two spellings, or a skip when the harness env is absent.

    Collection must never crash (the conftest's rule); a spec that runs
    outside the harness skips rather than erroring — same contract as the
    sibling modules' ``_sinks()``.
    """
    missing = [
        name
        for name in (*SINK_ENV, "FEATURE_CHECK_CAMERA_ROOT", "FEATURE_CHECK_SCENARIOS")
        if not os.environ.get(name)
    ]
    if missing:
        pytest.skip(f"feature-check env absent: {', '.join(missing)}")
    return {name: os.environ[name].rstrip("/") for name in SINK_ENV}


@pytest.fixture(scope="module")
def sinks() -> dict[str, str]:
    return _sinks()


@pytest.fixture(scope="module")
def subscription(logged_in_api: httpx.Client, sinks: dict[str, str]) -> Iterator[dict[str, Any]]:
    """A registered webpush channel on the Household recipient.

    Generates a real P-256 subscription keypair (what a browser's
    ``pushManager.subscribe()`` produces), registers it against the sink's
    in-network endpoint, and deletes the channel row at module end — the row
    is what the worker sends to, so leaving it behind would let a later
    alert on this stack push to a dead endpoint.
    """
    receiver = ec.generate_private_key(ec.SECP256R1())
    p256dh = base64.urlsafe_b64encode(
        receiver.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    ).rstrip(b"=")
    auth_secret = os.urandom(16)
    auth = base64.urlsafe_b64encode(auth_secret).rstrip(b"=")

    leg = _leg()
    endpoint = f"http://{sinks['FEATURE_CHECK_SINK_PUSH_HOST']}/push/{uuid.uuid4().hex[:12]}"
    # The endpoint's path is this leg's own filter key at the sink: records
    # carry the request path, and only a record addressed to THIS
    # subscription's endpoint can stand in for this leg's delivery.
    push_path = "/" + endpoint.split("/", 3)[3]
    created = logged_in_api.put(
        "/api/notification-preferences/push-subscription",
        json={
            "device_id": leg["device"],
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh.decode(), "auth": auth.decode()},
        },
    )
    assert created.status_code == 200, created.text[:500]
    body = created.json()
    assert body["status"] == "registered", body
    # The masked echo never carries the secrets (privacy row).
    assert auth.decode() not in created.text
    state = {
        "endpoint": endpoint,
        "push_path": push_path,
        "receiver": receiver,
        "auth_secret": auth_secret,
        "device": leg["device"],
        # The payload's title is the rule's name and the rule is this chain's
        # own (_leg is worker-deterministic), so the decrypt test can pin it
        # without a dependency on the rule fixture.
        "rule_name": _leg()["rule"],
    }
    try:
        yield state
    finally:
        removed = logged_in_api.delete(
            "/api/notification-preferences/push-subscription",
            params={"device_id": leg["device"]},
        )
        assert removed.status_code == 200, (
            f"cleanup DELETE push-subscription answered {removed.status_code}: {removed.text[:300]}"
        )


def _drop_fixture() -> None:
    """Write the fixture bytes into the leg's own camera folder.

    The watcher picks the file up on create (size settles, 10 KB minimum
    clears), auto-creates the camera from the folder name, runs the
    detector + fake VLM, and the pipeline then evaluates the rules —
    including this leg's custom rule, so the drop is deliberately AFTER the
    subscription and rule fixtures, not before.

    The suffix is this WORKER's (``_leg``): dedupe keys on content, so two
    chains dropping identical bytes would collapse onto one event even in
    different camera folders. The folder and file are chmod'd 0o777/0o666
    after the write: CI binds the run's camera dir into the backend
    container, whose appuser (uid 1000) must UNLINK files a runner user
    (uid 1001) created — the directory needs group/other write for the
    unlink itself, the file needs it for the delete to clear the file
    (event_purger's ``_unlink_path`` raises PermissionError otherwise and
    the API answers 500).
    """
    leg = _leg()
    scenario_dir = Path(os.environ["FEATURE_CHECK_SCENARIOS"]).parent
    base = (scenario_dir / "f4.4-gold-high.jpg").read_bytes()
    data = base + leg["suffix"].encode()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == leg["digest"], (
        "the fixture bytes moved; the fake VLM's verdict draw is keyed on this "
        "digest — re-measure the suffix before trusting the leg's tiers"
    )

    folder = Path(os.environ["FEATURE_CHECK_CAMERA_ROOT"]) / leg["camera_folder"]
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o777)
    file = folder / f"webpush-golden-{uuid.uuid4().hex[:8]}.jpg"
    file.write_bytes(data)
    file.chmod(0o666)


def _wait_for_the_event(logged_in_api: httpx.Client, leg: dict[str, str]) -> dict[str, Any]:
    """Poll the camera's confirmed events until this leg's MEDIUM one lands.

    The list endpoint's ``verdict`` filter (422 on a typo, never an empty
    false-all-clear) scopes the poll; the camera is this WORKER's own folder,
    so the sole confirmed event on it is this chain's — the per-worker split
    moved the uniqueness contract from the event's content (a pinned risk
    score) to its container (a per-worker camera), which is what lets the
    suffix table vary the draw.
    """
    deadline = time.monotonic() + 240.0
    while time.monotonic() < deadline:
        listed = logged_in_api.get(
            "/api/events",
            params={"camera_id": leg["camera"], "verdict": "confirmed", "limit": 10},
        )
        assert listed.status_code == 200, listed.text[:300]
        items = listed.json().get("items", [])
        for item in items:
            if item.get("risk_score") in range(31, 60):
                return item
        time.sleep(5.0)  # real - the poll loop IS the VLM+pipeline wait
    pytest.fail(f"no confirmed/MEDIUM event for camera {leg['camera']} within 240 s")


@pytest.fixture(scope="module")
def b43_event(
    logged_in_api: httpx.Client,
    subscription: dict[str, Any],
    b43_rule: str,
) -> Iterator[dict[str, Any]]:
    """Drop the fixture image and poll the event to its verdict.

    Fixture order is load-bearing: subscription and rule exist BEFORE the
    drop (the pipeline evaluates rules when the verdict lands; the planner
    needs the channel row), and the permanent purge in teardown — which
    cascades the alert and its delivery rows — runs after every test read
    the wire.
    """
    leg = _leg()
    _drop_fixture()
    event = _wait_for_the_event(logged_in_api, leg)
    try:
        yield event
    finally:
        # Soft delete first (trash), then permanent purge — the purger refuses
        # a live event. The FK chain (alerts → events CASCADE; deliveries →
        # alerts CASCADE) means the permanent delete clears the alert and the
        # delivery rows this leg created.
        soft = logged_in_api.delete(f"/api/events/{event['id']}")
        assert soft.status_code == 204, f"soft delete: {soft.status_code} {soft.text[:300]}"
        purged = logged_in_api.delete(f"/api/events/{event['id']}", params={"permanent": "true"})
        assert purged.status_code == 204, (
            f"permanent delete: {purged.status_code} {purged.text[:300]}"
        )


@pytest.fixture(scope="module")
def b43_rule(logged_in_api: httpx.Client) -> Iterator[str]:
    """A custom rule scoped to this leg's camera, threshold under the event.

    The rule fires on the MEDIUM event (custom rules skip the default rule's
    tier filter), and its name is the push payload's title. Deleted at module
    end so no later alert on this stack plans a webpush delivery from it.
    Rule creation validates no camera ids, so creating it before the camera
    exists is the product's own behavior, not a test crutch.
    """
    leg = _leg()
    created = logged_in_api.post(
        "/api/alerts/rules",
        json={
            "name": leg["rule"],
            "enabled": True,
            "severity": "medium",
            "risk_threshold": 30,
            "camera_ids": [leg["camera"]],
            "cooldown_seconds": 3600,
        },
    )
    assert created.status_code == 201, created.text[:500]
    rule_id = created.json()["id"]
    try:
        yield rule_id
    finally:
        deleted = logged_in_api.delete(f"/api/alerts/rules/{rule_id}")
        assert deleted.status_code in (204, 404), (
            f"cleanup rule delete answered {deleted.status_code}"
        )


@pytest.fixture(scope="module")
def delivered(
    sinks: dict[str, str],
    subscription: dict[str, Any],
    b43_event: dict[str, Any],
    b43_rule: str,
) -> list[dict[str, Any]]:
    """The push-sink records this leg's delivery, once it lands.

    The worker claims webpush rows immediately (the 15 s browser republish
    horizon gates only kind='browser'), and the pipeline wakes it on commit —
    the poll covers both schedules plus the VLM/detection latency the event
    itself already absorbed. Records are filtered to this leg's endpoint path
    so a sibling module's push traffic cannot stand in for ours.
    """
    reader = sinks["FEATURE_CHECK_SINK_PUSH_URL"]
    deadline = time.monotonic() + 120.0
    records: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        # nosemgrep: ssrf-requests - the push fake's harness env URL, the leg's subject
        listed = httpx.get(f"{reader}/requests", timeout=10.0)  # real
        assert listed.status_code == 200, listed.text[:300]
        # The endpoint is RECIPIENT-scoped (planner.py plans every enabled
        # channel of the recipient for every alert), so sibling legs' pushes
        # also land on this path — encrypted to THIS subscription's keys but
        # titled by THEIR rule (run 39968364788 shard 1: gw0's record carried
        # gw6's title). A path-only filter cannot tell the legs apart; the
        # decrypt can: this leg's record is the one whose plaintext names
        # this leg's rule. Wrong-key records raise here — a decrypt failure
        # is a wrong-subscription record, skip it, keep polling.
        ours = [
            r
            for r in listed.json().get("requests", [])
            if r["path"] == subscription["push_path"]
            and _decrypts_to(r, subscription, _leg()["rule"])
        ]
        if ours:
            records = ours
            break
        time.sleep(5.0)  # real - the poll loop IS the delivery wait
    assert records, (
        "no push delivery naming this leg's rule reached the sink within 120 s: "
        "the event, rule and subscription fixtures all exist, so check the "
        "worker and the planner"
    )
    return records


def _decrypts_to(record: dict[str, Any], subscription: dict[str, Any], rule: str) -> bool:
    """Does this record decrypt, with THIS subscription's keys, to our title?

    The recipient-scoped fanout (planner.py plans every enabled channel for
    every alert) puts sibling legs' payloads on this leg's endpoint; this
    leg's record is the one whose plaintext names this leg's rule. A record
    that fails to decrypt here was encrypted to different keys (a rotated or
    sibling row) — it is not ours, and swallowing the error keeps the poll
    loop alive for the real one.
    """
    try:
        payload = json.loads(_decrypt_payload(record, subscription))
    except Exception:  # any decrypt failure means "not our record"
        return False
    return payload == {"title": rule}


def _decrypt_payload(record: dict[str, Any], subscription: dict[str, Any]) -> bytes:
    """RFC 8291 decrypt of a recorded push body with the receiver's keys.

    The recorded ciphertext is the sink's ``body_b64``; the receiver's
    private key and auth secret are the subscription fixture's. The request
    headers carry the salt (``encryption``) and the sender's public key (the
    ``crypto-key``'s ``dh=``), but ``aes128gcm`` embeds both in the body's
    content header, so the decrypt needs no header parsing.
    """
    ciphertext = base64.b64decode(record["body_b64"])
    return http_ece.decrypt(
        ciphertext,
        private_key=subscription["receiver"],
        auth_secret=subscription["auth_secret"],
        version="aes128gcm",
    )


class TestThePushDelivery:
    def test_the_record_is_a_vapid_webpush_request(
        self,
        sinks: dict[str, str],
        delivered: list[dict[str, Any]],
        subscription: dict[str, Any],
    ) -> None:
        """The wire shape: this leg's endpoint, TTL 3600, the vapid header.

        The adapter sets ``ttl=3600`` (RFC 8030: how long the service holds
        the message for an offline browser) and pywebpush signs with the
        ``vapid t=<jwt>,k=<key>`` scheme (RFC 8292). The endpoint is this
        module's own (the subscription fixture minted it from the device id),
        so a record from another leg cannot stand in for ours.
        """
        record = delivered[-1]
        assert record["path"] == subscription["push_path"], record
        assert sinks["FEATURE_CHECK_SINK_PUSH_HOST"] in subscription["endpoint"], subscription[
            "endpoint"
        ]
        assert record["headers"]["ttl"] == _TTL, record
        assert record["headers"]["content-encoding"] == "aes128gcm", record
        authorization = record["headers"]["authorization"]
        assert authorization.startswith("vapid t="), authorization
        assert ",k=" in authorization, authorization

    def test_the_payload_decrypts_to_the_title_only(
        self, delivered: list[dict[str, Any]], subscription: dict[str, Any]
    ) -> None:
        """RFC 8291 round-trip: the plaintext is exactly the title JSON.

        The decrypt uses only the receiver's private key + auth secret — the
        keys a browser holds — so a correct decrypt is full proof the product
        encrypted to THIS subscription: wrong p256dh, wrong auth, a plaintext
        payload, or a different content encoding all red here. The plaintext
        itself pins the privacy row ("push carries the title only") on the
        wire: the JSON carries the rule name and nothing else.
        """
        record = delivered[-1]
        plaintext = _decrypt_payload(record, subscription)
        payload = json.loads(plaintext)
        assert payload == {"title": subscription["rule_name"]}, payload

    def test_the_alert_the_rule_raised_exists(
        self, logged_in_api: httpx.Client, b43_event: dict[str, Any]
    ) -> None:
        """The alert row behind the delivery exists with the rule's name.

        The delivery row itself has no read-back surface yet (the history API
        is a stub, ``notification.py`` returns an empty list), so the wire
        record is the delivery proof (the tests above) and this test pins the
        alert that drove it: matched by the custom rule, carrying its name in
        ``alert_metadata`` (exposed as ``metadata``). When the history API
        lands, its assertion moves here.
        """
        alerts = logged_in_api.get("/api/alert-service/alerts", params={"limit": 50})
        assert alerts.status_code == 200, alerts.text[:300]
        # The event carries other legs' alerts too: the webhook-deliveries leg
        # files its own rule-less alert (rule_id None) on the stack's freshest
        # event and acknowledges it by design (test_webhook_deliveries.py:169),
        # and rule-less alerts on THIS event match an event_id-only filter —
        # run 39968364788 shard 1: gw0's mine[0] was the webhook leg's acked
        # row. Match the custom rule's OWN row by its metadata name; the
        # default rule's row for this event (if any) is not this leg's.
        mine = [
            a
            for a in alerts.json().get("items", [])
            if a.get("event_id") == b43_event["id"]
            and (a.get("metadata") or {}).get("rule_name") == _leg()["rule"]
        ]
        assert mine, (
            f"no alert row naming {_leg()['rule']} for the b43 event "
            f"{b43_event['id']}: the custom rule (threshold 30) should have "
            "raised one"
        )
        alert = mine[0]
        assert alert["status"] == "open", alert
        metadata = alert.get("metadata") or {}
        assert metadata.get("rule_name") == _leg()["rule"], alert
