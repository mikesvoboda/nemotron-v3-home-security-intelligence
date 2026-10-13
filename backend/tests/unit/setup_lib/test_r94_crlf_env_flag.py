"""The `--convert-monitoring-key` flag over a CRLF `.env` keeps every other line's bytes.

Ruling 94 Fix 2 sells the flag on one promise: it changes the monitoring key's entry and
nothing else. `docs/operator/admin/security.md` says "every other byte of your `.env` is
left alone" and the flag prints "Nothing else in the file changed." Both are claims about
BYTES, and bytes is exactly where the text-mode I/O around the helper broke them: Python's
`read_text`/`write_text` translate line endings, so a CRLF file loses every `\r` on the
round-trip — 17 `\r` in, 0 out — while the tool reports success. `convert_monitoring_key`
itself preserves each line's own terminator (that is what the r94 CRLF tests pin); the loss
lives only in the two text-mode calls in `setup.py` that wrap it.

These run the CLI wiring (`setup.main()` with `--output-dir`), not the helper: the helper
tier already had CRLF coverage, and it passed. The defect needed the file-on-disk tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.tests.unit.setup_lib.test_r94_env_preserving_reruns import (
    CONVERTED_KEYS,
    LAN_ENV,
    _api_keys,
    _load_setup,
    _run_flag,
)

# LAN_ENV with CRLF terminators: the shape an operator who edits the file on Windows
# (or mounts it from a Windows host) actually has.
LAN_ENV_CRLF = LAN_ENV.replace("\n", "\r\n")
API_KEYS_LINE = 13  # index of the API_KEYS line in LAN_ENV_CRLF (measured, asserted below)


def test_the_crlf_fixture_is_the_shape_the_findings_describe() -> None:
    """Guard the fixture itself: 17 CRs, and the API_KEYS line is where the byte-diff
    assertion says it is. If LAN_ENV is edited under me, the sole-changed-line index
    below would silently compare the wrong line — this fails first."""
    assert LAN_ENV_CRLF.count("\r") == 17
    assert LAN_ENV_CRLF.split("\r\n")[API_KEYS_LINE].startswith("API_KEYS=")


def test_flag_on_a_crlf_env_keeps_every_other_line_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The promise, on the shape that broke it: one line changes, every other byte stands.

    Non-vacuity matters here — a flag that converted nothing would preserve every byte for
    free. So the CR count and the single-changed-line index are asserted only AFTER the
    conversion is confirmed to have happened.
    """
    setup = _load_setup()
    env = tmp_path / ".env"
    env.write_bytes(LAN_ENV_CRLF.encode("utf-8"))
    before = env.read_bytes()

    assert _run_flag(setup, tmp_path, monkeypatch) == 0

    after = env.read_bytes()
    # 1. it really converted (otherwise "nothing else changed" is trivially true)
    assert _api_keys(after.decode("utf-8")) == CONVERTED_KEYS, "the flag did not convert"
    # 2. and it did it without touching the endings of the 16 lines it must not touch
    crs_in, crs_out = before.count(b"\r"), after.count(b"\r")
    assert crs_out == crs_in == 17, (
        f"CRLF file lost its line endings: {crs_in} \\r in, {crs_out} out — "
        "every line's terminator was rewritten, not just the entry"
    )
    ins, outs = before.split(b"\r\n"), after.split(b"\r\n")
    assert len(ins) == len(outs), f"line count changed: {len(ins)} -> {len(outs)}"
    changed = [i for i, (a, b) in enumerate(zip(ins, outs, strict=True)) if a != b]
    assert changed == [API_KEYS_LINE], (
        f"expected only the API_KEYS line ({API_KEYS_LINE}) to change, "
        f"got lines {changed} — a CRLF file must come back CRLF"
    )
    # 3. the message the flag prints is true on this shape, not just on LF
    assert "+ converted" in capsys.readouterr().out.lower()
