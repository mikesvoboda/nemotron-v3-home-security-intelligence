"""r228 MEASURE harness: for each cached route key, which invalidator (if any) deletes it?

Keys come from the repo's OWN generators (CacheKeys.* and the route-level f-string
shape), never typed from memory -- a hand-typed key measures my transcription, not
the code. Read back through a RAW redis client so nothing is prefixed by the
probe itself. Run from the repo root against a Redis this lane owns:

  docker run -d --name r228-measure-redis -p 127.0.0.1:26379:6379 redis:7-alpine
  REDIS_URL=redis://127.0.0.1:26379/0 .venv/bin/python -I \
      backend/tests/evidence/r228_keyshape_census.py after

BEFORE was run at ddb4574cf (0/8 route-stored keys reachable), AFTER at
bfa6bd96c (7/8; the survivor timeline_summary:* has no invalidator at all).
Two of the eight rows (camera-by-id, system-status, summaries-latest) probe
CacheKeys generators no production route calls -- the table is a generator/
invalidator-shape census, not the production blast radius; see the PR body's
scope correction (#issuecomment-6217358643). The durable per-claim pins are the
redis-only tests in backend/tests/integration/test_cache_invalidation_comprehensive.py.

NOT a test tier: plain script, runs only when you invoke it.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import redis.asyncio as aioredis

from backend.services import cache_service as cs
from backend.services.cache_service import CACHE_PREFIX, CacheKeys, RedisClient

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:26379/0")

INVALIDATORS = [
    "invalidate_cameras",
    "invalidate_events",
    "invalidate_event_stats",
    "invalidate_system_status",
    "invalidate_alerts",
    "invalidate_detections",
    "invalidate_summaries",
]


def route_keys():
    """Each key built the way its route builds it.

    timeline_summary has no CacheKeys generator -- the shape is the route's own
    f-string (backend/api/routes/events.py:804), which is itself a finding.
    """
    return {
        "cameras list (all)": CacheKeys.cameras_list_by_status(None),
        "cameras list (online)": CacheKeys.cameras_list_by_status("online"),
        "camera by id": CacheKeys.camera("cam-1"),
        "event stats (all)": CacheKeys.event_stats(None, None, "all"),
        "event stats (camera)": CacheKeys.event_stats(None, None, "cam-1"),
        "system status": CacheKeys.system_status(),
        "summaries latest": CacheKeys.summaries_latest(),
        "timeline summary 1h": "timeline_summary:1h:2026-10-16T00:00:00Z:2026-10-16T12:00:00Z:all",
    }


async def main():
    label_cli = sys.argv[1] if len(sys.argv) > 1 else "unlabeled"
    rc = RedisClient(redis_url=REDIS_URL, password="", ssl_enabled=False, dedicated_pools=False)
    await rc.connect()
    svc = cs.CacheService(redis_client=rc)
    raw = aioredis.from_url(REDIS_URL, decode_responses=True)
    await raw.flushdb()

    settings = cs.get_settings()
    print(f"{label_cli} census")
    print(f"  CACHE_PREFIX={CACHE_PREFIX!r} redis_key_prefix={settings.redis_key_prefix!r}")
    print(f"  _get_cache_prefix() -> {cs._get_cache_prefix()!r}\n")

    keys = route_keys()
    stored = {}
    for label, key in keys.items():
        await svc.set(key, {"probe": 1}, ttl=120)
        hit = await svc.get(key)
        present = sorted(k for k in await raw.keys("*") if k.endswith(f":{key}") or k == key)
        stored[label] = (key, present, hit is not None)

    print(f"{'route key':24} {'stored in Redis':64} get-works")
    for label, (key, present, works) in stored.items():
        print(f"{label:24} {', '.join(present) or '(none)':64} {works}")

    print("\nwhat survives ONE invalidator call against a fully populated instance")
    print(f"{'invalidator':24}" + "".join(f"{k[:15]:>17}" for k in stored))
    for inv in INVALIDATORS:
        for label, (key, _, _) in stored.items():
            await svc.set(key, {"probe": 1}, ttl=120)
        n = await getattr(svc, inv)()
        cells = []
        for label, (key, present, _) in stored.items():
            if not present:
                cells.append(f"{'n/a':>17}")
                continue
            alive = [p for p in present if await raw.exists(p)]
            cells.append(f"{('ALIVE' if alive else 'gone'):>17}")
        print(f"{inv:24}" + "".join(cells) + f"   deleted={n}")

    print("\nVERDICT -- does ANY listed invalidator delete each route-stored key?")
    reached = 0
    for label, (key, present, _) in stored.items():
        who = None
        for inv in INVALIDATORS:
            await svc.set(key, {"probe": 1}, ttl=120)
            await getattr(svc, inv)()
            alive = [p for p in present if await raw.exists(p)]
            if present and not alive:
                who = inv
                break
        if who:
            reached += 1
            print(f"  REACHED {label:24} by {who}")
        else:
            print(f"  MISSED  {label:24} survives all {len(INVALIDATORS)} invalidators")
    print(f"\n{reached}/{len(stored)} route-stored keys reachable by some invalidator")

    await raw.flushdb()
    await raw.aclose()
    await rc.disconnect()


asyncio.run(main())
