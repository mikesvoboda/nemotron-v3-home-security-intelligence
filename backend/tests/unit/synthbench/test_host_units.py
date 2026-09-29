"""The host's systemd user units (agent-driven design §1; plan ruling P3-R8)."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from synthbench.host.units import (
    GUARD,
    RENDERER,
    SNAPSHOT,
    SNAPSHOT_TIMER,
    UnitContext,
    install,
    render_units,
)

CHECKOUT = Path("/export/synthbench/host-checkout")
PYTHON = CHECKOUT / ".venv" / "bin" / "python"
CTX = UnitContext(
    checkout=CHECKOUT,
    python=PYTHON,
    podman=Path("/usr/bin/podman"),
    root=Path("/export/synthbench"),
    hf_home=Path("/export/models"),
    podman_root=Path("/export/models/containers"),
)


def test_the_renderer_runs_comfyui_in_the_foreground_bound_to_the_guard() -> None:
    text = render_units(CTX)[RENDERER]
    assert "BindsTo=synthbench-guard.service" in text
    assert f"ExecStartPre={PYTHON} -m synthbench.host.renderer precheck" in text
    assert f"ExecStartPost={PYTHON} -m synthbench.host.renderer warmup" in text
    exec_start = next(line for line in text.splitlines() if line.startswith("ExecStart="))
    argv = shlex.split(exec_start.removeprefix("ExecStart="))
    assert argv[0] == "/usr/bin/podman"
    assert "-d" not in argv
    assert argv[-2:] == ["--reserve-vram", "4"]
    assert "127.0.0.1:8188:8188" in argv
    assert "[Install]" not in text  # started by hand, never at boot


def test_the_guard_always_runs_from_the_checkout() -> None:
    text = render_units(CTX)[GUARD]
    assert f"WorkingDirectory={CHECKOUT}" in text
    assert f"ExecStart={PYTHON} -m synthbench.host.guard" in text
    assert "Restart=always" in text
    assert "WantedBy=default.target" in text
    # pragma: allowlist nextline secret
    assert "Environment=SYNTHBENCH_ROOT=/export/synthbench" in text


def test_the_timer_snapshots_every_six_hours_utc() -> None:
    units = render_units(CTX)
    assert "OnCalendar=*-*-* 00/6:00:00 UTC" in units[SNAPSHOT_TIMER]
    assert "Persistent=true" in units[SNAPSHOT_TIMER]
    assert f"ExecStart={PYTHON} -m synthbench corpus snapshot" in units[SNAPSHOT]


def test_install_writes_changed_units_and_reloads_once(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    assert sorted(install(CTX, tmp_path, run)) == sorted(render_units(CTX))
    assert calls == [["systemctl", "--user", "daemon-reload"]]
    assert install(CTX, tmp_path, run) == []
    assert len(calls) == 1
