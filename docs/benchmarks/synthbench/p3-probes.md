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

## ZFS (host, same day)

A replace shows as `-` and `+` on the same path in `zfs diff -FH`. An in-place write or an
append shows as `M`, `write_new`'s hard link as a single `+`, and directories as `M` with type
`/` (plan rulings P3-R5 and P3-R6).
