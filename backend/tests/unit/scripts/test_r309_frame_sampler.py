"""Tests for scripts/uplevel/r309_frame_sampler.py — the [r309] stratified sampler.

The sampler must:
* walk the Foscam tree deterministically (sorted os.walk) and accept only the
  backend's IMAGE_EXTENSIONS with parseable Foscam names;
* stratify by camera-local capture hour (day window vs night/IR) using the
  backend's own `parse_capture_time`;
* flag distant frames by width below the threshold (the honest proxy);
* select seeded and repeatably: same tree + same seed = same selection;
* write paths and strata only — no image bytes, no crops — and refuse to run
  without a camera timezone or an empty/unreadable tree (exit 2, named).

Fixtures build a real Foscam-shaped tree with tiny real JPEGs (probed SOFn
headers), so the dimension probe is exercised against actual bytes, not
mocked file objects (UR-69 spirit: the test must be able to FAIL).

The module is imported (with the repo root on sys.path, the repo's own
convention from test_a5500_precheck.py) and `main()` is driven in-process:
success = the call returns; refusals raise SystemExit(2), which pytest
asserts on directly.

The camera-timezone fallback is tested at the seam the script actually
consumes — the `camera_timezone` field of the settings object returned by
`backend.core.config.get_settings` (stubbed). The real `get_settings` is
@cache'd, so letting it read the environment here would make these tests
order-dependent against every other test module in the same xdist worker
(and hostage to any ambient CAMERA_TIMEZONE in the container env); whether
env vars reach Settings is pydantic-settings' job, not the sampler's.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

# Add project root to path for imports - must be before script imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.uplevel import r309_frame_sampler as sampler  # noqa: E402

# --- fixture builders -------------------------------------------------------


def make_jpeg_bytes(width: int, height: int) -> bytes:
    """Minimal bytes a real JPEG decoder would reject but our probe reads:
    SOI + a real SOF0 segment carrying the declared dimensions.

    SOF0 wire order: FF C0, 16-bit segment length (= 8 + 3*components),
    8-bit precision, 16-bit HEIGHT, 16-bit WIDTH, then the component table.
    """
    payload = (
        struct.pack(">BHH", 8, height, width)  # precision=8, then H then W
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    )
    seg_len = len(payload) + 2
    return b"\xff\xd8\xff\xc0" + struct.pack(">H", seg_len) + payload + b"\xff\xd9"


def foscam_name(prefix: str, when: str, ext: str = "jpg") -> str:
    """MDAlarm_20260911-123100.jpg shape (backend/services/capture_time.py)."""
    return f"{prefix}_{when}.{ext}"


def build_tree(
    root: Path,
    *,
    day_count: int = 3,
    night_count: int = 2,
    distant_width: int = 640,
    near_width: int = 1280,
) -> None:
    """Camera folder 'Front Yard' with snap/ stills spanning both strata."""
    snap = root / "Front Yard" / "snap"
    snap.mkdir(parents=True, exist_ok=True)
    # Real Foscam names carry HHMMSS (6 digits) - the backend regex requires
    # it, so a 5-digit time field must never appear in a fixture.
    day = [f"MDAlarm_20260911-{10 + i:02d}0000.jpg" for i in range(day_count)]
    night = [f"MDAlarm_20260911-{i:02d}0000.jpg" for i in range(1, night_count + 1)]
    for i, name in enumerate(day):
        width = distant_width if i % 2 else near_width
        (snap / name).write_bytes(make_jpeg_bytes(width, 720))
    for i, name in enumerate(night):
        width = distant_width if i % 2 else near_width
        (snap / name).write_bytes(make_jpeg_bytes(width, 720))


def run_sampler(*argv: str, monkeypatch) -> None:
    """Drive the sampler's main() in-process with the given argv.

    SystemExit(2) from `fail()` propagates - tests assert on it."""
    monkeypatch.setattr(sys, "argv", ["r309_frame_sampler", *argv], raising=False)
    sampler.main()


class _StubSettings:
    """Stand-in for backend.core.config.Settings with one field."""

    def __init__(self, camera_timezone: str | None) -> None:
        self.camera_timezone = camera_timezone


# --- tests ------------------------------------------------------------------


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "foscam"
    build_tree(root)
    return root


def test_samples_seeded_and_repeatable(tree: Path, tmp_path: Path,
                                       monkeypatch) -> None:
    """Same tree + same seed = byte-identical selection list."""
    out1 = tmp_path / "sel1.json"
    out2 = tmp_path / "sel2.json"
    common = ["--root", str(tree), "--seed", "7", "--camera-tz",
              "America/New_York", "--per-stratum", "4"]
    run_sampler(*common, "--out", str(out1), monkeypatch=monkeypatch)
    run_sampler(*common, "--out", str(out2), monkeypatch=monkeypatch)
    assert out1.read_bytes() == out2.read_bytes()


def test_strata_and_distant_flag_written(tree: Path, tmp_path: Path,
                                         monkeypatch) -> None:
    """Selection entries carry (path, stratum, distant) and nothing else."""
    out = tmp_path / "sel.json"
    run_sampler("--root", str(tree), "--seed", "3",
                "--camera-tz", "America/New_York",
                "--per-stratum", "10", "--out", str(out),
                monkeypatch=monkeypatch)
    report = json.loads(out.read_text())
    assert report["counted"]["images_seen"] == 5
    selected = report["selected"]
    assert len(selected) == 5
    for e in selected:
        assert set(e) == {"path", "stratum", "distant"}
        assert e["stratum"] in ("day", "night_ir")
        assert isinstance(e["distant"], bool)
    day = [e for e in selected if e["stratum"] == "day"]
    night = [e for e in selected if e["stratum"] == "night_ir"]
    assert len(day) == 3 and len(night) == 2
    assert any(e["distant"] for e in selected)


def test_night_by_camera_local_time_not_utc(tmp_path: Path,
                                            monkeypatch) -> None:
    """Camera-local night hours must classify as night_ir even when their
    UTC hour falls inside the day window. 02:10 New York (EDT, UTC-4) is
    06:10 UTC - inside [6, 19) - so a sampler that stratifies on the UTC
    hour calls it 'day'. 19:10 New York is 23:10 UTC, outside [6, 19):
    a sampler that stratifies on UTC calls IT 'day' too. Both directions
    are pinned; the local-clock reading is the only one that passes."""
    root = tmp_path / "foscam"
    snap = root / "Back Yard" / "snap"
    snap.mkdir(parents=True)
    (snap / "MDAlarm_20260911-021000.jpg").write_bytes(make_jpeg_bytes(1280, 720))
    (snap / "MDAlarm_20260911-191000.jpg").write_bytes(make_jpeg_bytes(1280, 720))
    out = tmp_path / "sel.json"
    run_sampler("--root", str(root), "--seed", "0",
                "--camera-tz", "America/New_York",
                "--per-stratum", "10", "--out", str(out),
                monkeypatch=monkeypatch)
    report = json.loads(out.read_text())
    assert report["counted"]["night_ir_total"] == 2
    assert report["counted"]["day_total"] == 0


def test_non_foscam_names_are_counted_not_sampled(tmp_path: Path,
                                                  monkeypatch) -> None:
    """A still named like nothing Foscam produces lands in unparsable_names
    and never in a bucket - the sampler does not guess its hour."""
    root = tmp_path / "foscam"
    snap = root / "Front Yard" / "snap"
    snap.mkdir(parents=True)
    (snap / "photo_20260911.jpg").write_bytes(make_jpeg_bytes(1280, 720))
    (snap / "MDAlarm_20260911-120000.jpg").write_bytes(make_jpeg_bytes(1280, 720))
    out = tmp_path / "sel.json"
    run_sampler("--root", str(root), "--seed", "0",
                "--camera-tz", "America/New_York",
                "--per-stratum", "10", "--out", str(out),
                monkeypatch=monkeypatch)
    report = json.loads(out.read_text())
    assert report["counted"]["unparsable_names"] == 1
    assert report["counted"]["images_seen"] == 2
    assert len(report["selected"]) == 1


def test_video_files_are_never_selected(tmp_path: Path, monkeypatch) -> None:
    """The bake-off scores stills; record/ clips must not enter the list."""
    root = tmp_path / "foscam"
    (root / "Front Yard" / "snap").mkdir(parents=True)
    (root / "Front Yard" / "record").mkdir(parents=True)
    (root / "Front Yard" / "record" / "MDalarm_20260728_111148.mkv").write_bytes(
        b"\x00" * 32
    )
    (root / "Front Yard" / "snap" / "MDAlarm_20260911-120000.jpg").write_bytes(
        make_jpeg_bytes(1280, 720)
    )
    out = tmp_path / "sel.json"
    run_sampler("--root", str(root), "--seed", "0",
                "--camera-tz", "America/New_York",
                "--per-stratum", "10", "--out", str(out),
                monkeypatch=monkeypatch)
    report = json.loads(out.read_text())
    assert report["counted"]["images_seen"] == 1
    assert all(e["path"].endswith(".jpg") for e in report["selected"])


def test_requires_camera_timezone(tmp_path: Path, monkeypatch) -> None:
    """No --camera-tz and no configured camera_timezone -> SystemExit(2),
    naming the refusal."""
    root = tmp_path / "foscam"
    build_tree(root)
    monkeypatch.setattr(
        "backend.core.config.get_settings",
        lambda: _StubSettings(camera_timezone=None),
    )
    with pytest.raises(SystemExit) as excinfo:
        run_sampler("--root", str(root), "--seed", "0",
                    "--out", str(tmp_path / "sel.json"), monkeypatch=monkeypatch)
    assert excinfo.value.code == 2


def test_respects_camera_timezone_env(tmp_path: Path, monkeypatch) -> None:
    """The configured camera_timezone (what CAMERA_TIMEZONE populates in a
    real Settings) substitutes for --camera-tz."""
    root = tmp_path / "foscam"
    build_tree(root)
    out = tmp_path / "sel.json"
    monkeypatch.setattr(
        "backend.core.config.get_settings",
        lambda: _StubSettings(camera_timezone="America/New_York"),
    )
    run_sampler("--root", str(root), "--seed", "0", "--out", str(out),
                monkeypatch=monkeypatch)
    assert json.loads(out.read_text())["counted"]["images_seen"] == 5


def test_missing_root_fails_loudly(tmp_path: Path, monkeypatch) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_sampler("--root", str(tmp_path / "nope"), "--seed", "0",
                    "--camera-tz", "America/New_York",
                    "--out", str(tmp_path / "sel.json"), monkeypatch=monkeypatch)
    assert excinfo.value.code == 2


def test_empty_tree_fails_loudly(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "foscam"
    root.mkdir()
    with pytest.raises(SystemExit) as excinfo:
        run_sampler("--root", str(root), "--seed", "0",
                    "--camera-tz", "America/New_York",
                    "--out", str(tmp_path / "sel.json"), monkeypatch=monkeypatch)
    assert excinfo.value.code == 2


def test_png_dimensions_measured(tmp_path: Path, monkeypatch) -> None:
    """A .png still (IMAGE_EXTENSIONS accepts it) measures and stratifies."""
    root = tmp_path / "foscam"
    snap = root / "Front Yard" / "snap"
    snap.mkdir(parents=True)
    ihdr = struct.pack(">II", 1920, 1080) + b"\x08\x02\x00\x00\x00"
    png = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr
           + struct.pack(">I", 0) + b"IEND")
    (snap / "MDAlarm_20260911-120000.png").write_bytes(png)
    out = tmp_path / "sel.json"
    run_sampler("--root", str(root), "--seed", "0",
                "--camera-tz", "America/New_York",
                "--per-stratum", "10", "--out", str(out),
                monkeypatch=monkeypatch)
    report = json.loads(out.read_text())
    assert report["counted"]["images_seen"] == 1
    assert report["selected"][0]["path"].endswith(".png")
    assert report["selected"][0]["stratum"] == "day"


def test_per_stratum_half_split_between_distant_and_near(tree: Path,
                                                         tmp_path: Path,
                                                         monkeypatch) -> None:
    """A stratum's slots split distant-first, near-second, per the docstring."""
    out = tmp_path / "sel.json"
    run_sampler("--root", str(tree), "--seed", "11",
                "--camera-tz", "America/New_York",
                "--per-stratum", "2", "--out", str(out),
                monkeypatch=monkeypatch)
    selected = json.loads(out.read_text())["selected"]
    day = [e for e in selected if e["stratum"] == "day"]
    # day pool holds 3 frames: 2 distant (640), 1 near (1280).
    # take_distant = min(2, 2//2) = 1, take_near = min(1, 2-1) = 1.
    assert len(day) == 2
    assert sum(1 for e in day if e["distant"]) == 1
    assert sum(1 for e in day if not e["distant"]) == 1
