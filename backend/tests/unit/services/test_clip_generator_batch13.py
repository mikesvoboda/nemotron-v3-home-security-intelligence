"""Batch-13 battery: clip_generator TEST-GAP clusters C5-C16 (wp44-triage
dossier) + validator error-message contracts. Every asserted string/value
was MEASURED against the shipped module before the assert was written
(source read 2026-09-22; settings-vs-fallback probe: all four settings
attrs equal their fallback literals under the test env, so fallback
adoption is pinned with a patched get_settings instead).

Dossier clusters killed here: C5 (concat suffix), C6 (subprocess PIPE
kwargs), C7+C9 (video-extract argv + roll arithmetic), C8 (image-sequence
argv), C10 (duration guard boundaries 0.0/3600/3601), C11 (stderr-fallback
ternary), C12 (image-path error message), C13 (roll boundary 301), C14
(concat quote-escaping; existing L1276 assert is a tautology), C15
(validate-image-paths continue-vs-break order), C16 (gif -vf fps value).
C1/C2 logger diagnostics + C3 unreachable dash guard + C4 value-equal
tweaks follow the WP4.4 EQUIVALENT ruling (per-shape in the ledger row).
"""

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import clip_generator as cg
from backend.services.clip_generator import (
    ClipGenerationError,
    ClipGenerator,
    _validate_fps,
    _validate_output_format,
    _validate_roll_seconds,
    _validate_video_path,
    get_clip_generator,
    reset_clip_generator,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def clips_dir(tmp_path):
    d = tmp_path / "clips"
    d.mkdir()
    return d


@pytest.fixture
def gen(clips_dir):
    return ClipGenerator(
        clips_directory=str(clips_dir),
        pre_roll_seconds=5,
        post_roll_seconds=5,
        enabled=True,
    )


@pytest.fixture
def event30s():
    e = MagicMock()
    e.id = 123
    e.started_at = datetime(2024, 1, 15, 10, 30, 0)
    e.ended_at = datetime(2024, 1, 15, 10, 30, 30)  # 30s span -> duration 40.0 with 5/5 rolls
    return e


def _proc(returncode=0, stderr=b""):
    p = AsyncMock()
    p.returncode = returncode
    p.communicate = AsyncMock(return_value=(b"", stderr))
    return p


class TestInitAdoption:
    """C1-adjacent: __init__ getattr-name/kwarg mutants. The real settings
    equal the fallbacks (probe 2026-09-22), so adoption is pinned with
    DISTINCT patched values — name swaps change observable state."""

    def test_explicit_overrides_win(self, clips_dir):
        g = ClipGenerator(
            clips_directory=str(clips_dir),
            pre_roll_seconds=7,
            post_roll_seconds=9,
            enabled=False,
        )
        assert g.clips_directory == clips_dir
        assert g._pre_roll_seconds == 7
        assert g._post_roll_seconds == 9
        assert g.enabled is False

    def test_distinct_settings_adopted_per_attr(self, tmp_path):
        fake = SimpleNamespace(
            clips_directory=str(tmp_path / "sdir"),
            clip_pre_roll_seconds=11,
            clip_post_roll_seconds=13,
            clip_generation_enabled=False,
        )
        with patch(
            "backend.services.clip_generator.get_settings", return_value=fake, autospec=True
        ):
            g = ClipGenerator()
        assert g.clips_directory == Path(str(tmp_path / "sdir"))
        assert g._pre_roll_seconds == 11
        assert g._post_roll_seconds == 13
        assert g.enabled is False

    def test_missing_attrs_fall_back_to_literals(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # fallback "data/clips" must not mkdir in repo
        with patch(
            "backend.services.clip_generator.get_settings",
            return_value=SimpleNamespace(),
            autospec=True,
        ):
            g = ClipGenerator()
        assert g.clips_directory == Path("data/clips")
        assert (g._pre_roll_seconds, g._post_roll_seconds) == (5, 5)
        assert g.enabled is True

    def test_ensure_directory_creates_missing(self, tmp_path):
        target = tmp_path / "deep" / "nested"
        with patch(
            "backend.services.clip_generator.get_settings",
            return_value=SimpleNamespace(
                clips_directory=str(target),
                clip_pre_roll_seconds=5,
                clip_post_roll_seconds=5,
                clip_generation_enabled=True,
            ),
            autospec=True,
        ):
            ClipGenerator()
        assert target.is_dir()

    def test_ensure_directory_raises_on_failure(self, tmp_path):
        with patch(
            "backend.services.clip_generator.get_settings",
            return_value=SimpleNamespace(
                clips_directory=str(tmp_path / "x"),
                clip_pre_roll_seconds=5,
                clip_post_roll_seconds=5,
                clip_generation_enabled=True,
            ),
            autospec=True,
        ):
            with patch.object(Path, "mkdir", side_effect=OSError("nope"), autospec=True):
                with pytest.raises(OSError, match="nope"):
                    ClipGenerator()


class TestValidators:
    """C2-in-contract subset: ValueError messages are asserted by the
    shipped test file, so exact-message pins are the shipped contract."""

    def test_roll_seconds_accepts_boundaries(self):
        assert _validate_roll_seconds(0, "pre_seconds") == 0
        assert _validate_roll_seconds(300, "pre_seconds") == 300

    def test_roll_seconds_rejects_301_and_negatives_exact_message(self):
        # C13: mutant `> 300` -> `> 301` passes 301 through.
        with pytest.raises(ValueError) as ei:
            _validate_roll_seconds(301, "pre_seconds")
        assert str(ei.value) == "pre_seconds must be between 0 and 300 seconds, got 301"
        with pytest.raises(ValueError) as ei:
            _validate_roll_seconds(-1, "post_seconds")
        assert str(ei.value) == "post_seconds must be between 0 and 300 seconds, got -1"

    def test_roll_seconds_type_message_names_actual_type(self):
        with pytest.raises(ValueError) as ei:
            _validate_roll_seconds("x", "pre_seconds")
        assert str(ei.value) == "pre_seconds must be an integer, got str"

    def test_fps_boundaries_and_messages(self):
        assert _validate_fps(1) == 1
        assert _validate_fps(60) == 60
        with pytest.raises(ValueError) as ei:
            _validate_fps(61)
        assert str(ei.value) == "fps must be between 1 and 60, got 61"
        with pytest.raises(ValueError) as ei:
            _validate_fps(0)
        assert str(ei.value) == "fps must be between 1 and 60, got 0"
        with pytest.raises(ValueError) as ei:
            _validate_fps(2.0)
        assert str(ei.value) == "fps must be an integer, got float"

    def test_output_format_normalizes_and_rejects(self):
        assert _validate_output_format(" MP4 ") == "mp4"
        assert _validate_output_format("Gif") == "gif"
        with pytest.raises(ValueError) as ei:
            _validate_output_format("AVI")
        assert str(ei.value) == "Output format must be one of ['gif', 'mp4'], got 'AVI'"

    def test_video_path_messages(self, tmp_path):
        missing = tmp_path / "nope.mp4"
        with pytest.raises(ValueError) as ei:
            _validate_video_path(missing)
        assert str(ei.value) == f"Video file not found: {missing}"
        with pytest.raises(ValueError) as ei:  # directory is not a file
            _validate_video_path(tmp_path)
        assert str(ei.value) == f"Path is not a file: {tmp_path}"
        good = tmp_path / "v.mp4"
        good.touch()
        assert _validate_video_path(good) == good.resolve()


class TestVideoExtractArgv:
    """C7 (24) + C9 (2): the shipped tests spot-assert 4 tokens; pin the
    COMPLETE argv instead."""

    async def test_exact_full_argv(self, gen, event30s, tmp_path, clips_dir):
        video = (tmp_path / "src.mp4").resolve()
        video.touch()
        out = clips_dir / "123_clip.mp4"
        with patch("asyncio.create_subprocess_exec", return_value=_proc(), autospec=True) as ex:
            out.touch()  # ffmpeg "created" the clip
            result = await gen.generate_clip_from_video(event30s, video)
        assert result == out
        # duration = 30.0 + pre 5 + post 5 = 40.0 ; -ss = validated_pre
        assert ex.call_args[0] == (
            "ffmpeg",
            "-y",
            "-ss",
            "5",
            "-i",
            str(video),
            "-t",
            "40.0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(out),
        )
        # C6: stdout/stderr captured via PIPE (kwargs), not omitted/None
        assert ex.call_args.kwargs == {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }

    async def test_custom_rolls_shift_ss_and_t(self, gen, event30s, tmp_path, clips_dir):
        video = (tmp_path / "src.mp4").resolve()
        video.touch()
        out = clips_dir / "123_clip.mp4"
        with patch("asyncio.create_subprocess_exec", return_value=_proc(), autospec=True) as ex:
            out.touch()
            await gen.generate_clip_from_video(event30s, video, pre_seconds=10, post_seconds=2)
        args = ex.call_args[0]
        assert args[args.index("-ss") + 1] == "10"
        assert args[args.index("-t") + 1] == "42.0"  # 30 + 10 + 2 ; C9 flips die

    async def test_duration_zero_allowed_and_3600_allowed_3601_none(self, gen, tmp_path, clips_dir):
        # C10 boundaries: shipped rejects only duration < 0 or > 3600.
        zero = MagicMock()
        zero.id = 1
        zero.started_at = zero.ended_at = datetime(2024, 1, 15, 10, 0, 0)
        h1 = MagicMock()
        h1.id = 2
        h1.started_at = datetime(2024, 1, 15, 10, 0, 0)
        h1.ended_at = datetime(2024, 1, 15, 11, 0, 0)  # exactly 3600s with 0/0 rolls
        h1p1 = MagicMock()
        h1p1.id = 3
        h1p1.started_at = datetime(2024, 1, 15, 10, 0, 0)
        h1p1.ended_at = datetime(2024, 1, 15, 11, 0, 1)  # 3601s
        video = (tmp_path / "src.mp4").resolve()
        video.touch()
        for ev, rolls, expect_ok in (
            (zero, (0, 0), True),  # duration 0.0: kills `< 0`->`<= 0` and `> 3600`->`< 1`
            (h1, (0, 0), True),  # duration 3600.0: kills `>= 3600`
            (h1p1, (0, 0), False),  # duration 3601.0: kills `> 3601`
        ):
            pre, post = rolls
            with patch("asyncio.create_subprocess_exec", return_value=_proc(), autospec=True):
                (clips_dir / f"{ev.id}_clip.mp4").touch()
                result = await gen.generate_clip_from_video(
                    ev, video, pre_seconds=pre, post_seconds=post
                )
            assert (result is not None) is expect_ok, f"duration boundary failed for id={ev.id}"

    async def test_failure_paths(self, gen, event30s, tmp_path, clips_dir):
        video = tmp_path / "src.mp4"
        # disabled -> None, no subprocess
        with patch("asyncio.create_subprocess_exec", autospec=True) as ex:
            assert (
                await gen.__class__(
                    clips_directory=str(clips_dir), enabled=False
                ).generate_clip_from_video(event30s, video)
                is None
            )
            assert await gen.generate_clip_from_video(event30s, tmp_path / "missing.mp4") is None
            assert (
                await gen.generate_clip_from_video(event30s, video.resolve(), pre_seconds=301)
                is None
            )
            ex.assert_not_called()
        # rc=1 with stderr -> exact message text (C11)
        video.touch()
        with patch("asyncio.create_subprocess_exec", return_value=_proc(1, b"boom"), autospec=True):
            with pytest.raises(ClipGenerationError) as ei:
                await gen.generate_clip_from_video(event30s, video.resolve())
        assert str(ei.value) == "FFmpeg exited with code 1: boom"
        # rc=1 stderr None -> "Unknown error" (kills `stderr or True` -> None.decode crash)
        with patch("asyncio.create_subprocess_exec", return_value=_proc(1, None), autospec=True):
            with pytest.raises(ClipGenerationError) as ei:
                await gen.generate_clip_from_video(event30s, video.resolve())
        assert str(ei.value) == "FFmpeg exited with code 1: Unknown error"
        # ffmpeg binary missing -> None ; other exceptions -> None ; no output file -> None
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError, autospec=True):
            assert await gen.generate_clip_from_video(event30s, video.resolve()) is None
        with patch("asyncio.create_subprocess_exec", side_effect=RuntimeError("x"), autospec=True):
            assert await gen.generate_clip_from_video(event30s, video.resolve()) is None
        with patch("asyncio.create_subprocess_exec", return_value=_proc(), autospec=True):
            assert (
                await gen.generate_clip_from_video(event30s, video.resolve()) is None
            )  # no output created


class TestImagesArgv:
    """C8 (44) + C6 + C11/C12 on the image branch. Calls the shipped
    _run_ffmpeg_for_images directly so argv is isolated from flow."""

    async def _run(self, tmp_path, fmt, fps=2):
        # The shipped success path stats the output file, so it must be a
        # REAL file (exists()-patch alone still fails on .stat()).
        list_file = tmp_path / "concat.txt"
        out = tmp_path / "out-clip"
        out.touch()
        list_file.touch()
        proc = _proc()
        with patch("asyncio.create_subprocess_exec", return_value=proc, autospec=True) as ex:
            with patch.object(ClipGenerator, "_ensure_clips_directory", autospec=True):
                g = ClipGenerator(clips_directory=str(tmp_path), enabled=True)
            result = await g._run_ffmpeg_for_images(7, list_file, out, fmt, fps)
        return ex, result, out

    async def test_exact_gif_argv(self, tmp_path):
        ex, result, out = await self._run(tmp_path, "gif", fps=3)
        assert result == out
        assert ex.call_args[0] == (
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(tmp_path / "concat.txt"),
            "-vf",
            "fps=3,scale=320:-1:flags=lanczos",
            "-loop",
            "0",
            str(out),
        )

    async def test_exact_mp4_argv_and_pipe_kwargs(self, tmp_path):
        ex, _, out = await self._run(tmp_path, "mp4")
        assert ex.call_args[0] == (
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(tmp_path / "concat.txt"),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        )
        assert ex.call_args.kwargs == {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }

    async def test_rc1_message_and_temp_cleanup(self, tmp_path):
        list_file = tmp_path / "cleanup-check.txt"
        list_file.write_text("x")
        proc = _proc(3, b"kaput")
        with patch("asyncio.create_subprocess_exec", return_value=proc, autospec=True):
            with patch.object(ClipGenerator, "_ensure_clips_directory", autospec=True):
                g = ClipGenerator(clips_directory=str(tmp_path), enabled=True)
            with pytest.raises(ClipGenerationError) as ei:  # C12: message, not just type
                await g._run_ffmpeg_for_images(9, list_file, tmp_path / "o", "mp4", 2)
        assert str(ei.value) == "FFmpeg exited with code 3: kaput"
        assert not list_file.exists()  # finally: unlink ran even on raise


class TestFromImagesFlow:
    async def test_output_naming_and_args_forwarded(self, gen, event30s, tmp_path):
        img = tmp_path / "a.png"
        img.touch()
        with patch.object(
            gen, "_run_ffmpeg_for_images", new=AsyncMock(return_value=Path("ok"))
        ) as run:
            result = await gen.generate_clip_from_images(
                event30s, [img], fps=4, output_format="gif"
            )
        assert result == Path("ok")
        eid, list_file, out_path, fmt, fps = run.call_args[0]
        assert (eid, out_path.name, fmt, fps) == (123, "123_clip.gif", "gif", 4)
        assert list_file.suffix == ".txt"  # C5: suffix mutants change this
        # nosemgrep: path-traversal-open - list_file is generator-internal tmp_path
        content = Path(list_file).read_text()
        assert content == f"file '{img.resolve()}'\nduration 0.25\nfile '{img.resolve()}'\n"
        Path(list_file).unlink()

    async def test_format_normalization_reaches_path(self, gen, event30s, tmp_path):
        img = tmp_path / "a.png"
        img.touch()
        with patch.object(
            gen, "_run_ffmpeg_for_images", new=AsyncMock(return_value=Path("ok"))
        ) as run:
            await gen.generate_clip_from_images(event30s, [img], output_format=" MP4 ")
        out_path = run.call_args[0][2]
        assert out_path.name == "123_clip.mp4"  # normalized + stripped -> .mp4
        assert out_path.parent == gen.clips_directory

    async def test_guards(self, gen, event30s, tmp_path):
        # disabled -> None; fps validated before anything (raises, not None);
        # empty images -> None; all-invalid images -> None
        disabled = ClipGenerator(clips_directory=str(gen.clips_directory), enabled=False)
        assert await disabled.generate_clip_from_images(event30s, [tmp_path]) is None
        with pytest.raises(ValueError):
            await gen.generate_clip_from_images(event30s, [tmp_path / "x"], fps=0)
        assert await gen.generate_clip_from_images(event30s, []) is None
        assert await gen.generate_clip_from_images(event30s, [tmp_path / "ghost.png"]) is None

    async def test_concat_quote_escaping_exact(self, gen, tmp_path):
        # C14: the shipped test's L1276 disjunct is a tautology; pin content.
        weird = tmp_path / "it's.png"
        weird.touch()
        other = tmp_path / "b.png"
        other.touch()
        paths = gen._validate_image_paths([weird, other])
        list_file = gen._create_concat_file(paths, fps=2)
        try:
            # nosemgrep: path-traversal-open - list_file is generator-internal tmp_path
            content = Path(list_file).read_text()
        finally:
            Path(list_file).unlink()
        esc = f"{weird.resolve()}".replace("'", "'\\''")
        assert content == (
            f"file '{esc}'\nduration 0.5\n"
            f"file '{other.resolve()}'\nduration 0.5\n"
            f"file '{other.resolve()}'\n"
        )

    async def test_image_path_ordering_skips_invalid(self, gen, tmp_path):
        # C15: continue-vs-break is invisible when invalid is LAST; put it first.
        first = tmp_path / "missing.png"
        good = tmp_path / "good.png"
        good.touch()
        assert gen._validate_image_paths([first, good]) == [good.resolve()]
        assert gen._validate_image_paths([tmp_path, good]) == [good.resolve()]  # dir skipped

    async def test_file_not_found_maps_to_none(self, gen, event30s, tmp_path):
        img = tmp_path / "a.png"
        img.touch()
        with patch.object(gen, "_create_concat_file", side_effect=FileNotFoundError, autospec=True):
            assert await gen.generate_clip_from_images(event30s, [img]) is None
        with patch.object(gen, "_create_concat_file", side_effect=RuntimeError("z"), autospec=True):
            assert await gen.generate_clip_from_images(event30s, [img]) is None


class TestDispatchAndStorage:
    async def test_for_event_prefers_video_and_validates_fps_first(self, gen, event30s, tmp_path):
        img = tmp_path / "a.png"
        img.touch()
        with patch.object(
            gen, "generate_clip_from_video", new=AsyncMock(return_value=Path("v"))
        ) as vid:
            with patch.object(gen, "generate_clip_from_images", new=AsyncMock()) as imgm:
                out = await gen.generate_clip_for_event(
                    event30s, video_path="/x.mp4", image_paths=[img]
                )
        assert out == Path("v")
        vid.assert_awaited_once_with(event30s, "/x.mp4")
        imgm.assert_not_awaited()
        with pytest.raises(ValueError):  # fps validated before dispatch
            await gen.generate_clip_for_event(event30s, video_path="/x.mp4", fps=99)
        # empty-string video is falsy -> image branch
        with patch.object(gen, "generate_clip_from_video", new=AsyncMock()) as vid:
            with patch.object(
                gen, "generate_clip_from_images", new=AsyncMock(return_value=Path("i"))
            ):
                out = await gen.generate_clip_for_event(
                    event30s, video_path="", image_paths=[img], fps=3
                )
        assert out == Path("i")
        vid.assert_not_awaited()
        assert await gen.generate_clip_for_event(event30s) is None  # no source

    def test_get_clip_path_pref_mp4_then_gif(self, gen, clips_dir):
        assert gen.get_clip_path(99) is None
        (clips_dir / "99_clip.gif").touch()
        assert gen.get_clip_path(99) == clips_dir / "99_clip.gif"
        (clips_dir / "99_clip.mp4").touch()
        assert gen.get_clip_path(99) == clips_dir / "99_clip.mp4"

    def test_delete_clip_paths(self, gen, clips_dir):
        assert gen.delete_clip(1) is False  # nothing there
        (clips_dir / "2_clip.gif").touch()
        assert gen.delete_clip(2) is True
        assert not (clips_dir / "2_clip.gif").exists()
        (clips_dir / "3_clip.mp4").touch()
        (clips_dir / "3_clip.gif").touch()
        assert gen.delete_clip(3) is True  # mp4 first
        assert (clips_dir / "3_clip.gif").exists() and not (clips_dir / "3_clip.mp4").exists()
        with patch.object(Path, "unlink", side_effect=OSError("busy"), autospec=True):
            (clips_dir / "4_clip.mp4").touch()
            assert gen.delete_clip(4) is False  # exception -> False

    def test_singleton_roundtrip(self):
        original = cg._clip_generator
        try:
            reset_clip_generator()
            a = get_clip_generator()
            assert get_clip_generator() is a
            reset_clip_generator()
            assert cg._clip_generator is None
        finally:
            cg._clip_generator = original
