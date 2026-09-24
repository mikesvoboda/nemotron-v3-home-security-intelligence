#!/usr/bin/env python3
"""F5 stock-imagery fetcher: real photography for the 13 synthetic scenarios.

WHY THIS SHAPE (owner ruling 2026-09-24: "download stock images", no API
keys). The obvious host - Google Images - is declined deliberately: scraping
it breaks its ToS and an unidentified image's license is unknowable, so a
frame whose license you cannot name can never ship, even off-repo. Wikimedia
Commons serves the same need keyless AND license-clean: every file carries
machine-readable license metadata, and only CC/public-domain bits are on it.
`images.pexels.com`/`images.unsplash.com` are reachable too but Unsplash's
keyless search API is gone; Commons needs no key at all.

WHAT IT DOES: per scenario, searches Commons (bitmap-only), keeps files whose
LicenseShortName matches the permissive allow-list, downloads the <=1024px
thumb (bounded bytes), and writes the frame PLUS an attribution record beside
it. Everything lands under the off-repo media root (default
`$AGENT_GPU_DIR/out/media/stock/`) - never the checkout (D10), and a
frame staged inside the repo is refused by target_path() by construction.

Usage:
    uv run python scripts/synthetic_media.py queries
    uv run python scripts/synthetic_media.py fetch --per 6
    uv run python scripts/synthetic_media.py fetch --scenarios casing loitering
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

_LOG = logging.getLogger("vss-eval-media")
# Transient upstream failures (throttling, blips) are the norm on a run that
# makes ~400 requests; each gets this many attempts with backoff. 2026-09-24
# evidence: one fetch run came back 7/13 scenarios EMPTY, the identical search
# terms minutes later returned 40+ clean candidates - pure throttling, silently
# swallowed by a bare `continue`.
RETRIES = 3
# 0.5s/request, not 0.15: the re-fetch run on 2026-09-24 caught Commons
# answering HTTP 429 in bursts (pet_activity lost all three searches to it),
# and the retry backoff alone doesn't outlast that window. Keyless courtesy
# costs a few minutes per full corpus run.
PACE_SECONDS = 0.5

# NOTE transport: stdlib urllib, not httpx. Commons' WAF 403s httpx's TLS
# fingerprint on identical requests (verified 2026-09-24: curl/urllib/requests
# all 200, httpx 403 with any UA); requests is only a transitive dep here, so
# urllib is the zero-new-dependency choice.
import urllib.error
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
# Case-folded fragments; Commons hosts only free-culture/PD files, so this
# allow-list is belt-and-braces against a future surprise (a "Fair use" or
# nonFree tag never carries a CC/PD LicenseShortName).
PERMISSIVE_MARKS = ("cc", "public domain", "pd", "pdm")
UA = "vss-eval-media/1.0 (synthetic eval corpus; contact: repo owner)"

# One or more Commons searches per scenario (spec 5's 13). Queries name the
# SCENE, not a gore wish-list: what a doorbell camera plausibly frames.
SCENARIO_QUERIES: dict[str, list[str]] = {
    "delivery_driver": ["delivery driver package porch", "courier handing package", "delivery van driveway"],
    "pet_activity": ["dog in backyard", "cat on porch", "dog running lawn"],
    "resident_arrival": ["person unlocking front door", "person walking to house entrance", "car arriving driveway garage"],
    "vehicle_parking": ["car parked driveway house", "vehicle parked residential street", "minivan driveway"],
    "yard_maintenance": ["lawn mowing residential", "gardening backyard", "person raking leaves yard", "pressure washing driveway"],
    "casing": ["person photographing house", "person looking at house from street", "suspicious person notebook neighborhood"],
    "loitering": ["person standing street night", "person sitting porch alone", "loiterer"],
    "prowling": ["person walking yard night", "flashlight backyard night", "person between houses fence"],
    "tailgating": ["car following car gate", "vehicle behind vehicle driveway gate", "tailgating"],
    "break_in_attempt": ["crowbar door", "broken window glass door", "forced entry door", "person climbing window"],
    "package_theft": ["person carrying away package porch", "stolen delivery box street", "person taking parcel"],
    "vandalism": ["graffiti house wall", "broken window vandalism", "spray paint wall", "damaged car residential"],
    "weapon_visible": ["knife on table", "handgun case", "baseball bat grip", "crowbar held hand"],
}


def search_params(term: str) -> dict[str, str]:
    """Keyless Commons search: File: namespace, bitmaps only, with the
    license metadata we filter on."""
    return {
        "action": "query",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": term,
        "gsrfiletype": "bitmap",
        "gsrlimit": "20",
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "1024",
        "iiextmetadatafilter": "LicenseShortName|Artist|LicenseURL",
        "format": "json",
    }


def _clean(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


# Commons calls .djvu/.tif scans "bitmaps" in its search filter, and their
# mimes start with `image/` - a magazine scan is not a photograph (a
# Popular Science volume entered the prowling scenario, 2026-09-24 audit).
PHOTO_MIMES = ("image/jpeg", "image/png", "image/webp")


def license_of(page: dict) -> str | None:
    """The permissive license string of a Commons page dict, or None (not a
    photo-mime / metadata missing / license outside the allow-list)."""
    info = (page.get("imageinfo") or [{}])[0]
    if str(info.get("mime", "")) not in PHOTO_MIMES:
        return None
    meta = info.get("extmetadata") or {}
    raw = meta.get("LicenseShortName", {}).get("value")
    if not raw:
        return None
    lic = _clean(raw)
    low = lic.casefold()
    if any(mark in low for mark in PERMISSIVE_MARKS):
        return lic
    return None


def attribution_record(page: dict, scenario: str) -> dict:
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    return {
        "title": page.get("title"),
        "scenario": scenario,
        "license": license_of(page),
        "artist": _clean(meta.get("Artist", {}).get("value", "")),
        "license_url": (meta.get("LicenseURL", {}).get("value") or "").strip(),
        "source": info.get("thumburl") or info.get("url"),
    }


def target_path(root: Path, scenario: str, name: str) -> Path:
    """Where a fetched frame lands; refuses to escape the media root (a frame
    staged toward the checkout is the D10 leak class)."""
    root = root.resolve()
    out = (root / scenario / name).resolve()
    if root not in out.parents:
        raise ValueError(f"path escapes the media root: {scenario!r}/{name!r}")
    return out


_ALLOWED_HOSTS = ("commons.wikimedia.org", "upload.wikimedia.org", "thumb.wikimedia.org")


def _assert_allowed(url: str) -> str:
    """Fetch allow-list. Search results carry URLs from an external API, so
    every fetch is pinned to Wikimedia https hosts (the SSRF class the repo's
    semgrep rule guards)."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError(f"media fetch refused (allow-list): {url[:120]!r}")
    return url


class _AllowListRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-apply the fetch allow-list to EVERY redirect hop. urlopen follows
    30x by default and _assert_allowed only ever saw the first URL, so a
    Wikimedia-listed URL answering 302 -> evil.example would have been fetched
    unchecked. Commons itself redirects (Special:FilePath -> upload.wikimedia),
    so hops are revalidated, not forbidden."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        _assert_allowed(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_AllowListRedirectHandler)


def _get(url: str, params: dict[str, str] | None = None) -> bytes:
    full = f"{_assert_allowed(url)}?{urllib.parse.urlencode(params)}" if params else _assert_allowed(url)
    req = urllib.request.Request(full, headers={"User-Agent": UA})
    # nosemgrep: ssrf-requests - every hop passes _assert_allowed via _OPENER's
    # redirect handler (tests pin off-list + plain-http hops and the opener wiring)
    with _OPENER.open(req, timeout=30) as resp:  # noqa: S310 - allow-listed per hop
        time.sleep(PACE_SECONDS)  # gentle on the keyless API, every request
        return resp.read()


def _get_with_retry(url: str, params: dict[str, str] | None = None) -> bytes:
    """`_get` with bounded retries for transient network/HTTP failures. An
    allow-list refusal (ValueError) is policy, not a blip - it re-raises
    immediately rather than hammering a host we must not call."""
    for attempt in range(1, RETRIES + 1):
        try:
            return _get(url, params)
        except ValueError:
            raise
        except (OSError, urllib.error.URLError):
            if attempt >= RETRIES:
                raise
            time.sleep(0.5 * attempt)
    raise AssertionError("unreachable")  # loop returns or raises


def fetch_scenario(scenario: str, per: int, root: Path) -> list[dict]:
    """Up to `per` license-clean frames for one scenario; returns the
    manifest records actually written. A network blip skips the candidate -
    a missing frame is honest, a fabricated or unlicensed one is not - but
    the skip is LOGGED with the title: a 30-frame run that silently produced
    7 empty scenarios was un-auditable (2026-09-24)."""
    dirpath = root / scenario
    dirpath.mkdir(parents=True, exist_ok=True)
    # Resume/top-up: frames already on disk count toward `per` and the next
    # slot is the first free NN.jpg. The old code keyed the slot off
    # len(recs)+1 - correct only on a from-scratch run - so a directory with
    # 001.jpg already present skipped every candidate forever and filled
    # nothing. `written` is what THIS run added (main() totals on it); the
    # manifest covers every frame in the directory.
    existing = sorted(dirpath.glob("[0-9][0-9][0-9].jpg"))
    # Two search terms often surface the same Commons file; without dedupe it
    # fills two slots of one scenario (seen in casing/prowling/loitering).
    have_titles = {t for t in (_manifest_entry(p).get("title") for p in existing) if t}
    written: list[dict] = []
    slot = len(existing)
    for term in SCENARIO_QUERIES[scenario]:
        if slot >= per:
            break
        try:
            body = json.loads(_get_with_retry(API, search_params(term)))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as e:
            _LOG.warning("%s: search %r failed, moved on: %s", scenario, term, e)
            continue
        pages = (body.get("query") or {}).get("pages") or {}
        ranked = sorted(pages.values(), key=lambda p: p.get("index", 999))
        for page in ranked:
            if slot >= per:
                break
            title = page.get("title", "?")
            if not license_of(page):
                continue  # license filter: the norm, not a skip worth noise
            if title in have_titles:
                continue  # same file via another search term: one slot is enough
            info = page["imageinfo"][0]
            url = info.get("thumburl") or info.get("url")
            if not url or not url.startswith("https://"):
                _LOG.warning("%s: %s has no https thumb url", scenario, title)
                continue
            dest = target_path(root, scenario, f"{slot + 1:03d}.jpg")
            if dest.exists():
                slot += 1  # already filled by an earlier run: move past it
                continue
            try:
                frame = _get_with_retry(url)
            except (OSError, urllib.error.URLError) as e:
                _LOG.warning("%s: skip %s after %d tries: %s", scenario, title, RETRIES, e)
                continue
            if not 20_000 <= len(frame) <= 4_000_000:
                # stub thumbs / absurd originals: plumbing stays bounded
                _LOG.warning("%s: skip %s, out-of-band size %d", scenario, title, len(frame))
                continue
            if not frame.startswith(b"\xff\xd8"):
                # slots are NN.jpg; Commons URL extensions lie sometimes
                _LOG.warning("%s: skip %s, not a JPEG (magic bytes)", scenario, title)
                continue
            dest.write_bytes(frame)
            have_titles.add(title)
            rec = attribution_record(page, scenario)
            rec["file"] = str(dest)
            rec["bytes"] = len(frame)
            dest.with_suffix(".json").write_text(json.dumps(rec, indent=2))
            written.append(rec)
            slot += 1
    all_recs = [_manifest_entry(p) for p in sorted(dirpath.glob("[0-9][0-9][0-9].jpg"))]
    if all_recs:
        (dirpath / "manifest.json").write_text(json.dumps(all_recs, indent=2))
    return written


def _manifest_entry(jpg: Path) -> dict:
    """Manifest row for one frame on disk: its attribution JSON when present,
    a path-only row when not (a frame without a sidecar is still reported,
    never hidden)."""
    sidecar = jpg.with_suffix(".json")
    try:
        return json.loads(sidecar.read_text())
    except (OSError, json.JSONDecodeError):
        return {"file": str(jpg), "attribution": "MISSING"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("queries", help="print the scenario->search-query map")
    fp = sub.add_parser("fetch", help="download license-clean stock frames")
    fp.add_argument("--scenarios", nargs="*", default=None, help="default: all 13")
    fp.add_argument("--per", type=int, default=6, help="frames per scenario")
    gpu = os.environ.get("AGENT_GPU_DIR", "/agents/agent-vss1/gpu")
    fp.add_argument("--root", default=str(Path(gpu) / "out" / "media" / "stock"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "queries":
        print(json.dumps(SCENARIO_QUERIES, indent=2))
        return 0

    wanted = args.scenarios or sorted(SCENARIO_QUERIES)
    bad = set(wanted) - set(SCENARIO_QUERIES)
    if bad:
        print(f"unknown scenarios: {sorted(bad)}", file=sys.stderr)
        return 2
    root = Path(args.root)
    total = 0
    for scenario in wanted:
        recs = fetch_scenario(scenario, args.per, root)
        total += len(recs)
        print(f"{scenario}: {len(recs)} frames -> {root / scenario}")
    print(f"TOTAL {total} license-clean frames under {root} (off-repo)")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
