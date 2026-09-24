"""Unit tests for scripts/synthetic_media.py (F5 stock-imagery fetcher).

Licensing discipline is the point of these tests, not the HTTP: only
Wikimedia Commons is used (its every-file license is free-culture or PD and
machine-readable), a permissive-license allow-list is enforced, and every
download is recorded with attribution beside the bytes - off-repo.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

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
