"""Unit tests for scripts/synthetic_media.py (F5 stock-imagery fetcher).

Licensing discipline is the point of these tests, not the HTTP: only
Wikimedia Commons is used (its every-file license is free-culture or PD and
machine-readable), a permissive-license allow-list is enforced, and every
download is recorded with attribution beside the bytes - off-repo.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import urllib.error
from pathlib import Path

import pytest

JPEG = b"\xff\xd8" + b"z" * 25_000  # in-band size, real JPEG magic

_MOD = Path(__file__).resolve().parent / "synthetic_media.py"
_spec = importlib.util.spec_from_file_location("synthetic_media_uu", _MOD)
assert _spec and _spec.loader
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)


def _img(title: str, license_short: str, mime: str = "image/jpeg") -> dict:
    return {
        "title": title,
        "imageinfo": [
            {
                "mime": mime,
                "thumburl": "https://thumb.example/x.jpg",
                "extmetadata": {
                    "LicenseShortName": {"value": license_short},
                    "Artist": {"value": "A Photographer"},
                    "LicenseURL": {"value": "https://creativecommons.org/licenses/by/4.0/"},
                },
            }
        ],
    }


class TestLicenseFilter:
    def test_permissive_licenses_pass(self) -> None:
        for lic in ("CC0", "CC BY 4.0", "CC BY-SA 3.0", "Public domain", "PD"):
            assert sm.license_of(_img("t", lic)) == lic

    def test_noncommons_mime_rejected(self) -> None:
        assert sm.license_of(_img("t", "CC0", mime="application/pdf")) is None

    def test_missing_metadata_rejected(self) -> None:
        bad = {"title": "x", "imageinfo": [{"mime": "image/jpeg"}]}
        assert sm.license_of(bad) is None

    def test_allowlist_covers_the_real_commons_set(self) -> None:
        # Commons hosts only free-culture/PD; the two families are CC and PD.
        # Casefold first - license_of() compares casefolded, so must this.
        assert any(k in "CC BY-SA 2.0 DEED".casefold() for k in sm.PERMISSIVE_MARKS)
        assert any(k in "Public Domain Mark 1.0".casefold() for k in sm.PERMISSIVE_MARKS)


class TestQueryMap:
    def test_every_scenario_has_queries(self) -> None:
        scenarios = {
            "delivery_driver",
            "pet_activity",
            "resident_arrival",
            "vehicle_parking",
            "yard_maintenance",
            "casing",
            "loitering",
            "prowling",
            "tailgating",
            "break_in_attempt",
            "package_theft",
            "vandalism",
            "weapon_visible",
        }
        assert scenarios <= set(sm.SCENARIO_QUERIES)
        assert all(v for v in sm.SCENARIO_QUERIES.values())


class TestSearchRequest:
    def test_request_is_keyless_and_bitmap_only(self) -> None:
        params = sm.search_params("porch package")
        assert params["gsrfiletype"] == "bitmap"
        assert "apikey" not in json.dumps(params).lower()
        assert params["gsrnamespace"] == "6"  # File:


class TestDownloadSafety:
    def test_url_allowlist_blocks_offsite(self) -> None:
        for bad in (
            "http://commons.wikimedia.org/x.jpg",  # not https
            "https://evil.example/keystore",  # off-site
            "https://169.254.169.254/latest/meta-data/",  # cloud metadata
            "https://localhost:9/x",
        ):
            with pytest.raises(ValueError, match="allow-list"):
                sm._assert_allowed(bad)

    def test_url_allowlist_passes_wikimedia_https(self) -> None:
        sm._assert_allowed("https://thumb.wikimedia.org/wikipedia/commons/thumb/x/1280px-x.jpg")
        sm._assert_allowed("https://upload.wikimedia.org/wikipedia/commons/x.jpg")

    def test_refuses_paths_outside_media_root(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="media root"):
            sm.target_path(tmp_path / "root", scenario="..", name="x.jpg")

    def test_target_path_stays_inside_root(self, tmp_path) -> None:
        p = sm.target_path(tmp_path / "root", scenario="casing", name="001.json")
        assert p.resolve().is_relative_to((tmp_path / "root").resolve())

    def test_attribution_line_shape(self) -> None:
        rec = sm.attribution_record(_img("File:A.jpg", "CC BY 4.0"), "casing")
        assert rec["license"] == "CC BY 4.0"
        assert rec["scenario"] == "casing"
        assert rec["title"] == "File:A.jpg"


class TestRetry:
    """2026-09-24 fetch run: 7 of 13 scenarios came back with 0 frames and
    the code could not say why - every network hiccup was swallowed by a bare
    `continue`. Same search terms minutes later returned 40+ license-clean
    candidates, so the failures were transient HTTP throttling. Transients get
    a bounded retry; anything past it is SKIPPED WITH A LOG LINE."""

    def test_transient_failure_retried_then_succeeds(self, monkeypatch) -> None:
        calls: list[int] = []
        sleeps: list[float] = []
        monkeypatch.setattr(sm.time, "sleep", sleeps.append)

        def flaky(url, params=None):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.URLError("429-ish")
            return b"frame"

        monkeypatch.setattr(sm, "_get", flaky)
        assert sm._get_with_retry("https://upload.wikimedia.org/x.jpg") == b"frame"
        assert len(calls) == 3
        assert len(sleeps) == 2, "backoff between attempts, none after success"

    def test_retry_exhaustion_reraises(self, monkeypatch) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        n = {"i": 0}

        def always_fail(url, params=None):
            n["i"] += 1
            raise OSError("net down")

        monkeypatch.setattr(sm, "_get", always_fail)
        with pytest.raises(OSError):
            sm._get_with_retry("https://upload.wikimedia.org/x.jpg")
        assert n["i"] == sm.RETRIES

    def test_allowlist_violation_is_never_retried(self, monkeypatch) -> None:
        """ValueError from _assert_allowed is a policy refusal, not a
        transient - retrying an off-site URL would be worse than useless."""
        calls: list[int] = []

        def refuse(url, params=None):
            calls.append(1)
            raise ValueError("media fetch refused (allow-list)")

        monkeypatch.setattr(sm, "_get", refuse)
        with pytest.raises(ValueError, match="allow-list"):
            sm._get_with_retry("https://evil.example/x")
        assert len(calls) == 1


class TestLoudSkips:
    """The F5 honesty rule: a missing frame is fine, an UNEXPLAINED missing
    frame makes corpus gaps un-auditable."""

    @staticmethod
    def _fake_get(image_resp, *, fail_image=True):
        body = json.dumps(
            {
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Ok.jpg",
                            "index": 1,
                            "imageinfo": [
                                {
                                    "mime": "image/jpeg",
                                    "thumburl": "https://upload.wikimedia.org/x.jpg",
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "CC BY 4.0"},
                                        "Artist": {"value": "A"},
                                        "LicenseURL": {"value": ""},
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        ).encode()

        def fake(url, params=None):
            if params is not None:
                return body  # the search call
            if fail_image:
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)
            return image_resp

        return fake

    def test_download_failure_is_logged_not_silent(self, tmp_path, monkeypatch, caplog) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        monkeypatch.setattr(sm, "_get", self._fake_get(b""))
        with caplog.at_level(logging.WARNING, logger="vss-eval-media"):
            recs = sm.fetch_scenario("casing", 1, tmp_path)
        assert recs == []
        assert "File:Ok.jpg" in caplog.text, "the log must name WHAT was skipped"

    def test_undersized_frame_logged_as_skipped(self, tmp_path, monkeypatch, caplog) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        monkeypatch.setattr(sm, "_get", self._fake_get(b"z" * 100, fail_image=False))
        with caplog.at_level(logging.WARNING, logger="vss-eval-media"):
            recs = sm.fetch_scenario("casing", 1, tmp_path)
        assert recs == [] and not (tmp_path / "casing" / "001.jpg").exists()
        assert "size" in caplog.text.lower()

    def test_successful_fetch_writes_frame_and_manifest(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        frame = JPEG  # inside the 20 kB..4 MB bound, JPEG magic
        monkeypatch.setattr(sm, "_get", self._fake_get(frame, fail_image=False))
        recs = sm.fetch_scenario("casing", 1, tmp_path)
        assert [r["file"] for r in recs] == [str(tmp_path / "casing" / "001.jpg")]
        assert (tmp_path / "casing" / "001.jpg").read_bytes() == frame
        assert (tmp_path / "casing" / "001.json").exists()
        manifest = json.loads((tmp_path / "casing" / "manifest.json").read_text())
        assert manifest[0]["license"] == "CC BY 4.0"


class TestFrameSanity:
    """2026-09-24 corpus audit: a `Popular Science Monthly Volume 90.djvu`
    scan passed the filter (mime image/vnd.djvu starts with `image/` and
    Commons calls .djvu a bitmap) and a .jpg slot could hold non-JPEG bytes.
    Frames must be photo-mimes with JPEG magic, and the same file must not
    fill two slots of one scenario (two search terms returned identical
    titles in casing/prowling/loitering)."""

    @staticmethod
    def _body(pages: list[dict]) -> bytes:
        return json.dumps(
            {"query": {"pages": {str(i + 1): p for i, p in enumerate(pages)}}}
        ).encode()

    @staticmethod
    def _page(title: str, index: int, mime: str = "image/jpeg") -> dict:
        return _img(title, "CC0") | {"index": index, "imageinfo": [{**_img(title, "CC0")["imageinfo"][0], "mime": mime}]}

    def test_document_mimes_rejected(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        monkeypatch.setattr(sm, "_get", lambda u, p=None: self._body([self._page("File:Mag.djvu", 1, "image/vnd.djvu")]))
        assert sm.fetch_scenario("prowling", 6, tmp_path) == []

    def test_non_jpeg_bytes_skipped_loudly(self, tmp_path, monkeypatch, caplog) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"z" * 25_000
        monkeypatch.setattr(sm, "_get", TestLoudSkips._fake_get(png_bytes, fail_image=False))
        with caplog.at_level(logging.WARNING, logger="vss-eval-media"):
            assert sm.fetch_scenario("casing", 1, tmp_path) == []
        assert "not a JPEG" in caplog.text

    @staticmethod
    def _search_and_frames(pages: list[dict]):
        """Stub `_get`: the search call (params present) gets `pages`; every
        frame download gets a JPEG-magic in-band frame."""

        def fake(url, params=None):
            return TestFrameSanity._body(pages) if params is not None else JPEG

        return fake

    def test_duplicate_titles_fill_one_slot(self, tmp_path, monkeypatch) -> None:
        # [Same, Same, New] per=2: dedup drops the 2nd Same so New reaches the
        # 2nd slot. Without dedup the run would stop at [Same, Same] and never
        # fetch New - which is the exact casing/prowling/loitering defect.
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        dupes = [self._page("File:Same.jpg", 1), self._page("File:Same.jpg", 2), self._page("File:New.jpg", 3)]
        monkeypatch.setattr(sm, "_get", self._search_and_frames(dupes))
        recs = sm.fetch_scenario("casing", 2, tmp_path)
        assert [Path(r["file"]).name for r in recs] == ["001.jpg", "002.jpg"]
        assert [r["title"] for r in recs] == ["File:Same.jpg", "File:New.jpg"]

    def test_resume_remember_existing_titles(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        d = tmp_path / "casing"
        d.mkdir()
        (d / "001.jpg").write_bytes(b"\xff\xd8" + b"z" * 25_000)
        (d / "001.json").write_text(json.dumps({"title": "File:Same.jpg", "file": str(d / "001.jpg")}))
        monkeypatch.setattr(sm, "_get", self._search_and_frames([self._page("File:Same.jpg", 1)]))
        recs = sm.fetch_scenario("casing", 2, tmp_path)
        assert recs == [], "the already-held file must not be refetched into 002"
        assert sorted(d.glob("*.jpg")) == [d / "001.jpg"]


class TestResume:
    """Re-running over a partly-filled scenario must TOP UP, not spin.
    (Found 2026-09-24 re-running the 7 empty scenarios: the slot index was
    len(recs)+1 - fresh-run only - so a directory with 001.jpg already on disk
    made every candidate skip forever.)"""

    def test_topup_appends_after_existing_frames(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(sm.time, "sleep", lambda s: None)
        d = tmp_path / "casing"
        d.mkdir()
        (d / "001.jpg").write_bytes(JPEG)
        (d / "001.json").write_text(json.dumps({"title": "File:Old.jpg", "file": str(d / "001.jpg")}))
        monkeypatch.setattr(
            sm, "_get", TestLoudSkips._fake_get(JPEG, fail_image=False)
        )
        recs = sm.fetch_scenario("casing", 2, tmp_path)
        assert [r["file"] for r in recs] == [str(d / "002.jpg")], "must fill 002, not re-check 001"
        # manifest covers ALL frames in the dir, not just this run's writes
        manifest = json.loads((d / "manifest.json").read_text())
        assert {m["file"] for m in manifest} == {str(d / "001.jpg"), str(d / "002.jpg")}

    def test_full_scenario_short_circuits(self, tmp_path, monkeypatch) -> None:
        d = tmp_path / "casing"
        d.mkdir()
        for i in (1, 2):
            (d / f"00{i}.jpg").write_bytes(JPEG)

        def no_network(*a, **k):
            raise AssertionError("must not touch the network when already full")

        monkeypatch.setattr(sm, "_get", no_network)
        recs = sm.fetch_scenario("casing", 2, tmp_path)
        assert recs == []
