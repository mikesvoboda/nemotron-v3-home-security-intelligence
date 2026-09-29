# Synthbench P3 probes (2026-09-28)

This is the evidence for the agent-driven design's two **[A]** assumptions and for the corpus
mount. It comes from a fresh `agent-dgx` sandbox (`p3probe`) that mounted
`/synthbench/corpus:rw` and `/synthbench/status:ro`. Plan:
`docs/superpowers/plans/2026-09-28-synthbench-p3-agent-driven-generation.md`, Task 1.

| Question                                            | Result                                                                                                                                                        |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sandbox reaches the host's `:8188` (design R2)      | `http://host.docker.internal:8188/system_stats` answered the stub (`{"stub": true}`). `http://127.0.0.1:8188` refused the connection (errno 111).             |
| Image read reaches Qwen vision through LiteLLM (R1) | The image showed `PCSW-8504`. The agent (Qwen, through LiteLLM) replied `PCSW-8504`.                                                                          |
| `os.link` on the corpus mount                       | ok                                                                                                                                                            |
| `os.replace` on the corpus mount                    | ok                                                                                                                                                            |
| `O_APPEND` write on the corpus mount                | ok                                                                                                                                                            |
| `flock` on the corpus mount                         | ok                                                                                                                                                            |
| uid:gid and mode the host sees for sandbox files    | The sandbox user `agent` (1000:1000) shows as `msvoboda:msvoboda` on the host. Modes are kept: `mkstemp`'s file stays `600`, so the store sets `0644` itself. |

## The sandbox cannot mount paths under `/export`

The first launch, with `--mount /export/synthbench/corpus:rw --mount
/export/synthbench/status:ro`, failed at `sbx create` with `failed to run sandbox container`.
The sbx daemon log (`~/.local/state/sandboxes/sandboxes/sandboxd/daemon.log`) shows the cause:

```text
policybind: bind failed: stat source "/mnt/host/export/synthbench/corpus": no such file or directory
policybind: bind failed: stat source "/mnt/host/export/synthbench/status": no such file or directory
```

The VM sees the host through one virtio-fs share of `/`. Several causes were ruled out:

- the sbx filesystem policy, which allows `**`, and the daemon logged "path allowed";
- permissions;
- the daemon's mount namespace, which is the same as the host's;
- the datasets' creation times;
- mount depth: `/synthbench/corpus` is two ZFS mounts below the root filesystem and binds fine.

What fails is paths under `/export` itself. With the owner's approval, the dataset moved:

```bash
sudo zfs set mountpoint=/synthbench primary/export/synthbench   # corpus inherits /synthbench/corpus
ln -s /synthbench /export/synthbench                            # host paths keep working
```

The dataset names are unchanged (`primary/export/synthbench/corpus`). To revert, remove the
symlink and run `sudo zfs inherit mountpoint primary/export/synthbench`.

## Sandbox image

The sandbox image lacks the X11 and GL libraries that the locked `opencv-python` wheel links.
`import cv2` fails with `libxcb.so.1` missing, and every synthbench command imports OpenCV at
start-up, `sample` included (verified 2026-09-28). The fix, once per sandbox:

```bash
sbx exec agent-<name> sudo apt-get install -y libxcb1 libgl1 libglib2.0-0
```

The operator runbook's "Create the agent's sandbox" runs it, then `uv sync --frozen` and
`uv run python -c "import synthbench.cli"` to confirm.

## ZFS (host, same day)

A replace shows as `-` and `+` on the same path in `zfs diff -FH`. An in-place write or an
append shows as `M`, `write_new`'s hard link as a single `+`, and directories as `M` with type
`/` (plan rulings P3-R5 and P3-R6).

## Stack change (2026-09-28)

The flagship's util gate went from 0.84 to 0.76 (stack repository `main` 6ba507f, MR
`perf/flagship-util-076`), applied with `stack/scripts/swap.sh qwen38-flash-next`. vLLM was
ready in 268 s, and the whole swap took 280 s.

| Check                                                | Result                                    |
| ---------------------------------------------------- | ----------------------------------------- |
| Live `ENGINE_ARGS`                                   | `gpu-memory-utilization 0.76`             |
| `127.0.0.1:8000/health`                              | `200`                                     |
| A request through LiteLLM (`claude-flagship`)        | replied `ready`                           |
| `sbx policy check network host.docker.internal:8188` | `Allowed` (explicit rules for 8188 added) |
| `sbx policy check network localtest.me:8000`         | `Denied` (the flagship stays closed)      |

The guard was already running during the swap. It logged `flagship failed 3 health checks in a
row: stopping the renderer`, then `flagship healthy again; the renderer stays stopped until the
owner starts it`. sbx keeps its policy rules in `~/.cache/sandboxes/sandboxes/policykit/governor.db`
(SQLite). They survive daemon restarts and reboots, but `sbx policy reset` or `sbx reset`
removes them.

## Host install and smoke (2026-09-28)

- **Host checkout.** `/synthbench/host-checkout`, detached at 91cda2d6 (the PR head). Its
  `.venv` synced in 15 s. The four units are installed, and the guard and the snapshot timer
  are enabled. The systemd user `PATH` includes `/usr/sbin`, so the units find `zfs`.
- **Renderer beside the flagship.**
  - The pre-check passed after the stack change; before it, it refused on util alone.
  - The unit was active 44 s after `start`, and the warm-up image took 32.1 s including the
    model load.
  - GPU memory in use went from 190,754 MiB to 242,949 MiB, so the renderer holds 51.0 GiB.
  - The flagship stayed at `200`.
- **Smoke** (3 events on a scratch root):
  - `sample`, `check`, `render`, `camera`, `report` and the final `check` all exited 0. The
    final `check` verified 6 files.
  - Render times were 8.3, 5.0 and 5.0 s per image, with the flagship nearly idle.
  - The stills are 1920x1080 with the overlay top-left, for example `2026-11-09 21:32:13`
    for a 21:32 spec.
  - Triage: 2 `ok` and 1 `reroll` (`text_overlay`). FLUX drew a fake `4:40` because the
    prompt said "at 4:40 in the morning". A 3-event batch may reroll 0 events, so `triage`
    marked it `failed` and exited 2, as designed.
- **Guard stop path.**
  - A second guard pointed at `127.0.0.1:9` stopped the renderer after 3 ticks. The real
    status stayed `healthy`.
  - The guard's `serve.stop` fallback raced the unit's own `ExecStop` (`podman stop` exited
    125, "container state improper"). That left the container stuck in `Removing`, so the next
    pre-check refused to start the renderer.
  - `podman rm -f synthbench-comfyui` cleared it, and the renderer restarted with a 29.1 s
    warm-up. Follow-up: run the fallback only when `systemctl stop` fails or the container
    outlives it.
- **First snapshot.** `corpus snapshot: 1 kept, no hold`, and
  `primary/export/synthbench/corpus@synthbench-20260929T033843Z` exists.
