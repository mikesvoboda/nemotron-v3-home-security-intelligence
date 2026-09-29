"""systemd user units for the host side (agent-driven design §1; plan ruling P3-R8).

    /export/synthbench/host-checkout/.venv/bin/python -m synthbench.host.units install

writes them for the checkout it runs from, with that checkout's python. The guard and the
snapshot timer are enabled at boot; the renderer has no [Install] section, so the owner starts
it by hand.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from synthbench.generate.comfy.serve import ServeConfig, run_args
from synthbench.generate.podman import podman_root
from synthbench.host.renderer import RESERVE_VRAM_ARGS

GUARD = "synthbench-guard.service"
RENDERER = "synthbench-renderer.service"
SNAPSHOT = "synthbench-snapshot.service"
SNAPSHOT_TIMER = "synthbench-snapshot.timer"
DEFAULT_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class UnitContext:
    checkout: Path  # the repository root whose code the units run
    python: Path  # that checkout's .venv python (not resolved: the venv is the point)
    podman: Path
    root: Path  # SYNTHBENCH_ROOT
    hf_home: Path
    podman_root: Path

    @classmethod
    def current(cls, env: Mapping[str, str] | None = None) -> UnitContext:
        e = os.environ if env is None else env
        return cls(
            checkout=Path(__file__).resolve().parents[2],
            python=Path(sys.executable),
            podman=Path(shutil.which("podman") or "/usr/bin/podman"),
            root=Path(e.get("SYNTHBENCH_ROOT", "/export/synthbench")),
            hf_home=Path(e.get("HF_HOME", "/export/models")),
            podman_root=podman_root(e),
        )


def render_units(ctx: UnitContext) -> dict[str, str]:
    env = "".join(
        f"Environment={key}={value}\n"
        for key, value in (
            ("SYNTHBENCH_ROOT", ctx.root),
            ("HF_HOME", ctx.hf_home),
            ("SYNTHBENCH_PODMAN_ROOT", ctx.podman_root),
        )
    )
    cfg = ServeConfig(
        port=8188,
        models_root=ctx.hf_home,
        out_dir=ctx.root / "comfy-out",
        cache_dir=ctx.root / "cache",
    )
    podman = run_args(cfg, detach=False, extra=RESERVE_VRAM_ARGS)
    podman[0] = str(ctx.podman)
    docs = f"Documentation=file://{ctx.checkout}/docs/synthbench/operator-runbook.md\n"
    service = f"WorkingDirectory={ctx.checkout}\n{env}"
    py = f"{ctx.python} -m"
    return {
        GUARD: (
            "[Unit]\n"
            "Description=synthbench guard: flagship status for render; stops the renderer when "
            "the flagship fails\n"
            f"{docs}\n"
            "[Service]\nType=simple\n"
            f"{service}ExecStart={py} synthbench.host.guard\n"
            "Restart=always\nRestartSec=5\n\n"
            "[Install]\nWantedBy=default.target\n"
        ),
        RENDERER: (
            "[Unit]\n"
            "Description=synthbench renderer: ComfyUI with FLUX.2 [dev] beside the flagship\n"
            f"{docs}BindsTo={GUARD}\nAfter={GUARD}\n\n"
            "[Service]\nType=simple\n"
            f"{service}ExecStartPre={py} synthbench.host.renderer precheck\n"
            f"ExecStart={shlex.join(podman)}\n"
            f"ExecStartPost={py} synthbench.host.renderer warmup\n"
            f"ExecStop={py} synthbench.generate.comfy.serve down\n"
            "TimeoutStartSec=1200\nTimeoutStopSec=90\nRestart=no\n"
        ),
        SNAPSHOT: (
            "[Unit]\nDescription=synthbench corpus snapshot and prune (design §6)\n"
            f"{docs}\n"
            "[Service]\nType=oneshot\n"
            f"{service}ExecStart={py} synthbench corpus snapshot\n"
        ),
        SNAPSHOT_TIMER: (
            "[Unit]\nDescription=Every 6 h: snapshot and prune the synthbench corpus\n\n"
            "[Timer]\nOnCalendar=*-*-* 00/6:00:00 UTC\nPersistent=true\n\n"
            "[Install]\nWantedBy=timers.target\n"
        ),
    }


def install(ctx: UnitContext, unit_dir: Path, run: Runner = subprocess.run) -> list[str]:
    """Write the units that differ; reload systemd once if any did. Returns their names."""
    unit_dir.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for name, text in render_units(ctx).items():
        path = unit_dir / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            changed.append(name)
    if changed:
        run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.host.units")
    parser.add_argument("command", choices=["install", "show"])
    parser.add_argument("--unit-dir", type=Path, default=DEFAULT_UNIT_DIR)
    args = parser.parse_args(argv)
    ctx = UnitContext.current()
    if args.command == "show":
        for name, text in render_units(ctx).items():
            sys.stdout.write(f"# {name}\n{text}\n")
        return 0
    changed = install(ctx, args.unit_dir)
    sys.stdout.write(
        f"{len(changed)} unit file(s) changed in {args.unit_dir}: {', '.join(changed) or 'none'}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
