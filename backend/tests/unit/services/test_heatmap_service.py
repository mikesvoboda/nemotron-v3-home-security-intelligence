"""WP3.1 first tests for backend.services.heatmap_service.

Mutation history listed this module as no_tests (6 mutants, never covered).
Coverage alone wouldn't satisfy the WP3.1 done-when, so every assertion pins
a computed value a mutant could get wrong:

  * accumulator coordinate mapping: frame->grid scaling is x*grid_w/width
    in x and y*grid_h/height in y with distinct values (960,540) -> (32,24)
    so a swapped axis or off-by-one lands on a different, asserted cell
  * clamping: negative and beyond-frame coords land on edge cells (never
    wrap around to the opposite side)
  * weight accumulation, reset(), get_accumulator_data() returning a COPY
  * compress/decompress round trip through zlib AND the (height,width)
    reshape order — transposed dims produce a visibly different array
  * time buckets: hourly/daily floor; weekly lands on MONDAY 00:00 for
    every weekday including Sunday (weekday() == 6)
  * merge_heatmaps: dimension-mismatch rows are skipped, sums and counts
    add; empty list renders the empty heatmap
  * image endpoints: PNG magic bytes, exact metadata dict, alpha=0 render
    fully transparent, and the empty accumulator short-circuits rendering
  * save_snapshot through a fake session: None on empty, new-record fields,
    merge-into-existing (grid + count add), accumulator reset afterwards
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import numpy as np
import pytest

from backend.models.heatmap import HeatmapData, HeatmapResolution
from backend.services.heatmap_service import (
    HeatmapAccumulator,
    HeatmapService,
    get_heatmap_service,
    reset_heatmap_service,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _acc(w=960, h=540, gw=32, gh=24) -> HeatmapAccumulator:
    return HeatmapAccumulator.create(
        "cam", grid_width=gw, grid_height=gh, source_width=w, source_height=h
    )


class TestAccumulatorCreate:
    def test_grid_shape_is_height_by_width(self) -> None:
        acc = _acc()
        assert acc.grid.shape == (24, 32)  # (grid_height, grid_width), transposed mutants die here
        assert acc.grid.dtype == np.float32
        assert acc.total_detections == 0


class TestAddDetectionMapping:
    def test_center_of_frame_scales_per_axis(self) -> None:
        acc = _acc()  # 960x540 -> 32x24
        acc.add_detection(480, 270)
        assert acc.grid[12, 16] == 1.0  # y=12, x=16; x uses gw/width, y uses gh/height
        assert acc.grid.sum() == 1.0

    def test_asymmetric_point_disambiguates_axes(self) -> None:
        acc = _acc()
        acc.add_detection(600, 30)  # x->20, y->1 (both valid either way round)
        assert acc.grid[1, 20] == 1.0
        assert acc.grid[20, 1] == 0.0  # the transposed cell must be empty

    def test_negative_coords_clamp_to_origin_cell(self) -> None:
        acc = _acc()
        acc.add_detection(-50, -10)
        assert acc.grid[0, 0] == 1.0

    def test_beyond_frame_coords_clamp_to_far_edge(self) -> None:
        acc = _acc()
        acc.add_detection(2000, 1200)
        assert acc.grid[23, 31] == 1.0  # clamps, does NOT index past the end

    def test_weight_accumulates_and_counts_each_add(self) -> None:
        acc = _acc()
        acc.add_detection(100, 100, weight=2.5)
        acc.add_detection(100, 100, weight=0.5)
        assert acc.grid.sum() == 3.0
        assert acc.total_detections == 2  # count is adds, not weight

    def test_reset_clears_grid_and_count(self) -> None:
        acc = _acc()
        acc.add_detection(100, 100)
        acc.reset()
        assert acc.grid.sum() == 0.0
        assert acc.total_detections == 0


class TestServiceAccumulators:
    def test_add_creates_accumulator_lazily(self) -> None:
        svc = HeatmapService()
        svc.add_detection("a", 10, 10)
        assert set(svc.accumulators) == {"a"}

    def test_get_accumulator_data_returns_copy(self) -> None:
        svc = HeatmapService()
        svc.add_detection("a", 10, 10)
        data = svc.get_accumulator_data("a")
        data[0, 0] = 999.0
        assert svc.get_accumulator_data("a")[0, 0] == 1.0  # caller mutation must not write through

    def test_unknown_camera_is_none(self) -> None:
        assert HeatmapService().get_accumulator_data("nope") is None

    def test_reset_accumulator_true_then_false(self) -> None:
        svc = HeatmapService()
        svc.add_detection("a", 10, 10)
        assert svc.reset_accumulator("a") is True
        assert svc.get_accumulator_stats("a")["total_detections"] == 0
        assert svc.reset_accumulator("ghost") is False

    def test_stats_fields(self) -> None:
        svc = HeatmapService(grid_width=16, grid_height=8)
        svc.add_detection("a", 5, 5, source_width=640, source_height=480)
        stats = svc.get_accumulator_stats("a")
        assert stats["grid_width"] == 16
        assert stats["grid_height"] == 8
        assert stats["source_width"] == 640
        assert stats["source_height"] == 480
        assert stats["max_intensity"] == 1.0
        assert stats["total_detections"] == 1
        assert datetime.fromisoformat(stats["last_updated"]).tzinfo is not None
        assert svc.get_accumulator_stats("ghost") is None


class TestCompressRoundtrip:
    def test_roundtrip_preserves_values_and_layout(self) -> None:
        svc = HeatmapService()
        grid = np.arange(12, dtype=np.float32).reshape(3, 4)  # 3 rows, 4 cols
        blob = svc.compress_grid(grid)
        out = svc.decompress_grid(blob, width=4, height=3)
        np.testing.assert_array_equal(out, grid)
        assert out.shape == (3, 4)

    def test_compressed_actually_compresses(self) -> None:
        svc = HeatmapService()
        grid = np.zeros((48, 64), dtype=np.float32)
        assert len(svc.compress_grid(grid)) < grid.nbytes

    def test_dtype_parameter_respected(self) -> None:
        svc = HeatmapService()
        grid = np.arange(6, dtype=np.float64).reshape(2, 3)
        out = svc.decompress_grid(svc.compress_grid(grid), 3, 2, dtype=np.float64)
        assert out.dtype == np.float64
        np.testing.assert_array_equal(out, grid)


class TestTimeBuckets:
    def test_hourly_floors_to_hour(self) -> None:
        svc = HeatmapService()
        ts = datetime(2026, 9, 20, 13, 47, 12, 500, tzinfo=UTC)
        assert svc._calculate_time_bucket(ts, HeatmapResolution.HOURLY) == datetime(
            2026, 9, 20, 13, 0, 0, tzinfo=UTC
        )

    def test_daily_floors_to_midnight(self) -> None:
        svc = HeatmapService()
        ts = datetime(2026, 9, 20, 13, 47, 12, tzinfo=UTC)
        assert svc._calculate_time_bucket(ts, HeatmapResolution.DAILY) == datetime(
            2026, 9, 20, 0, 0, 0, tzinfo=UTC
        )

    @pytest.mark.parametrize(
        ("day", "expected_day"),
        [
            (21, 21),  # Monday stays itself
            (22, 21),  # Tuesday -> Monday
            (27, 21),  # Sunday -> previous Monday, not forward
            (20, 14),  # Sunday one week earlier
        ],
    )
    def test_weekly_lands_on_monday(self, day: int, expected_day: int) -> None:
        svc = HeatmapService()
        ts = datetime(2026, 9, day, 15, 30, tzinfo=UTC)
        bucket = svc._calculate_time_bucket(ts, HeatmapResolution.WEEKLY)
        assert bucket.weekday() == 0  # every bucket is a Monday
        assert bucket == datetime(2026, 9, expected_day, 0, 0, 0, tzinfo=UTC)

    def test_unknown_resolution_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown resolution"):
            HeatmapService()._calculate_time_bucket(datetime.now(UTC), "decadal")


def _rec(camera="cam", w=4, h=3, grid=None, total=1) -> HeatmapData:
    svc = HeatmapService()
    if grid is None:
        grid = np.ones((h, w), dtype=np.float32)
    return HeatmapData(
        camera_id=camera,
        time_bucket=datetime(2026, 9, 20, tzinfo=UTC),
        resolution=HeatmapResolution.HOURLY.value,
        width=w,
        height=h,
        data=svc.compress_grid(grid),
        total_detections=total,
    )


class TestMergeHeatmaps:
    def test_empty_list_renders_empty_heatmap(self) -> None:
        out = HeatmapService().merge_heatmaps([])
        assert out["total_detections"] == 0
        assert base64.b64decode(out["image_base64"]).startswith(PNG_MAGIC)

    def test_grids_and_counts_sum(self) -> None:
        svc = HeatmapService()
        g1 = np.ones((3, 4), dtype=np.float32)
        g2 = np.full((3, 4), 2.0, dtype=np.float32)
        out = svc.merge_heatmaps([_rec(grid=g1, total=4), _rec(grid=g2, total=6)])
        assert out["total_detections"] == 10
        # the render is normalized internally, so assert on the merge via a
        # re-merge with ONE record of the same summed grid: images must match
        expected = svc.merge_heatmaps([_rec(grid=g1 + g2, total=10)])
        assert out["image_base64"] == expected["image_base64"]

    def test_dimension_mismatch_record_is_skipped(self) -> None:
        svc = HeatmapService()
        g = np.ones((3, 4), dtype=np.float32)
        odd = _rec(grid=np.ones((5, 5), dtype=np.float32), w=5, h=5, total=100)
        out = svc.merge_heatmaps([_rec(grid=g, total=1), odd])
        assert out["total_detections"] == 1  # the mismatched record contributes nothing

    def test_single_zero_record(self) -> None:
        out = HeatmapService().merge_heatmaps([_rec(grid=np.zeros((3, 4), dtype=np.float32))])
        assert out["total_detections"] == 1


class TestHeatmapImages:
    def test_no_accumulator_is_empty_transparent(self) -> None:
        svc = HeatmapService()
        out = svc.get_heatmap_image("ghost", output_width=80, output_height=60)
        assert out["width"] == 80 and out["height"] == 60
        assert out["total_detections"] == 0 and out["colormap"] == "jet"
        png = base64.b64decode(out["image_base64"])
        assert png.startswith(PNG_MAGIC)
        import io as _io

        from PIL import Image

        img = Image.open(_io.BytesIO(png))
        assert img.size == (80, 60)
        assert img.getpixel((10, 10))[3] == 0  # fully transparent

    def test_populated_camera_reports_counts(self) -> None:
        svc = HeatmapService()
        svc.add_detection("a", 100, 100)
        out = svc.get_heatmap_image("a")
        assert out["total_detections"] == 1
        assert out["width"] == 640 and out["height"] == 480
        assert base64.b64decode(out["image_base64"]).startswith(PNG_MAGIC)

    def test_alpha_zero_render_is_fully_transparent(self) -> None:
        import io as _io

        from PIL import Image

        svc = HeatmapService()
        svc.add_detection("a", 100, 100)
        out = svc.get_heatmap_image("a", alpha=0.0, output_width=64, output_height=48)
        img = Image.open(_io.BytesIO(base64.b64decode(out["image_base64"])))
        assert np.array(img)[:, :, 3].max() == 0
        # alpha=1 hot cell is opaque where the detection landed
        out2 = svc.get_heatmap_image("a", alpha=1.0, output_width=64, output_height=48)
        img2 = Image.open(_io.BytesIO(base64.b64decode(out2["image_base64"])))
        assert np.array(img2)[:, :, 3].max() > 0


class FakeResult:
    def __init__(self, row=None) -> None:
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class FakeSession:
    """Records execute/add/commit/refresh like AsyncSession's call surface."""

    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.added: list = []
        self.commits = 0
        self.refreshed: list = []

    async def execute(self, query):
        return FakeResult(self.existing)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)


class TestSaveSnapshot:
    @pytest.mark.asyncio
    async def test_empty_camera_returns_none_without_touching_db(self) -> None:
        svc = HeatmapService()
        session = FakeSession()
        assert await svc.save_snapshot(session, "cam", HeatmapResolution.HOURLY) is None
        assert session.commits == 0 and session.added == []

    @pytest.mark.asyncio
    async def test_new_record_fields_and_accumulator_reset(self) -> None:
        svc = HeatmapService(grid_width=8, grid_height=4)
        svc.add_detection("cam", 10, 10, source_width=640, source_height=320)
        session = FakeSession()
        bucket = datetime(2026, 9, 20, 13, 0, tzinfo=UTC)
        rec = await svc.save_snapshot(session, "cam", HeatmapResolution.HOURLY, time_bucket=bucket)
        assert session.added == [rec] and session.commits == 1
        assert rec.camera_id == "cam"
        assert rec.time_bucket == bucket
        assert rec.resolution == "hourly"
        assert (rec.width, rec.height) == (8, 4)
        assert rec.total_detections == 1
        saved = svc.decompress_grid(rec.data, rec.width, rec.height)
        assert saved[0, 0] == 1.0 and saved.sum() == 1.0  # compressed BEFORE reset
        assert svc.accumulators["cam"].grid.sum() == 0.0  # accumulator reset after save
        assert svc.accumulators["cam"].total_detections == 0

    @pytest.mark.asyncio
    async def test_existing_record_merges_grid_and_counts(self) -> None:
        svc = HeatmapService(grid_width=8, grid_height=4)
        svc.add_detection("cam", 10, 10, source_width=640, source_height=320)
        prior = np.zeros((4, 8), dtype=np.float32)
        prior[3, 7] = 5.0
        existing = HeatmapData(
            camera_id="cam",
            time_bucket=datetime(2026, 9, 20, 13, 0, tzinfo=UTC),
            resolution="hourly",
            width=8,
            height=4,
            data=svc.compress_grid(prior),
            total_detections=10,
        )
        session = FakeSession(existing=existing)
        rec = await svc.save_snapshot(
            session,
            "cam",
            HeatmapResolution.HOURLY,
            time_bucket=datetime(2026, 9, 20, 13, 0, tzinfo=UTC),
        )
        assert rec is existing and session.added == [] and session.commits == 1
        assert rec.total_detections == 11
        merged = svc.decompress_grid(rec.data, 8, 4)
        assert merged[3, 7] == 5.0  # prior cell preserved by merge
        assert merged[0, 0] == 1.0  # (10,10) on 640x320 -> grid cell (0,0)

    @pytest.mark.asyncio
    async def test_bucket_derived_when_not_provided(self) -> None:
        svc = HeatmapService()
        svc.add_detection("cam", 10, 10)
        rec = await svc.save_snapshot(FakeSession(), "cam", HeatmapResolution.DAILY)
        assert rec.time_bucket.hour == 0 and rec.time_bucket.minute == 0


class TestSingleton:
    def test_get_is_stable_and_reset_rebuilds(self) -> None:
        reset_heatmap_service()
        svc = get_heatmap_service()
        assert get_heatmap_service() is svc
        reset_heatmap_service()
        assert get_heatmap_service() is not svc
        reset_heatmap_service()
