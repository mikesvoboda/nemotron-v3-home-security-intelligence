"""Startup self-check: can this process actually inotify-watch the camera root?

watchdog's inotify backend swallows EACCES from ``inotify_add_watch``
(``Inotify._raise_error`` re-raises every errno except EACCES). On a host whose
kernel refuses the watch, a native ``Observer`` therefore starts normally,
``is_alive()`` is True, its ``InotifyEmitter`` is alive - and no event ever
arrives. There is no public watchdog signal for it. Seen on the A5500 box
(2026-09-28): SELinux enforcing, the backend as ``container_t``, the camera
root labelled ``usr_t`` and mounted without ``:z`` - reading uploads worked,
watching was denied (``avc: denied { watch watch_reads }``), and nothing was
ingested while the watcher logged "started successfully".

So the FileWatcher asks the kernel directly, once, before trusting a native
observer: ``inotify_init1`` + ``inotify_add_watch(root, IN_CREATE |
IN_MOVED_TO | IN_CLOSE_WRITE)``, then close. A watch needs only read access,
so this works on ``:ro`` mounts too.
"""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass

IN_CLOSE_WRITE = 0x00000008
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
PROBE_MASK = IN_CREATE | IN_MOVED_TO | IN_CLOSE_WRITE

_PERMISSION_HINT = (
    "permission denied by the kernel (DAC, SELinux or another LSM). On an "
    "SELinux-enforcing host a container (container_t) may READ a usr_t camera "
    "root but not WATCH it: add :z to the camera mount (e.g. "
    "${FOSCAM_BASE_PATH}:/cameras:z) or relabel the camera root to "
    "container_file_t; the host audit log shows it as `avc: denied { watch }`"
)
_HINTS: dict[int, str] = {
    errno.EACCES: _PERMISSION_HINT,
    errno.EPERM: _PERMISSION_HINT,
    errno.ENOSPC: (
        "the per-user inotify watch limit is exhausted: raise "
        "fs.inotify.max_user_watches on the host (e.g. sysctl -w "
        "fs.inotify.max_user_watches=524288)"
    ),
    errno.EMFILE: (
        "the per-user inotify instance limit (or the process fd limit) is "
        "exhausted: raise fs.inotify.max_user_instances on the host (e.g. "
        "sysctl -w fs.inotify.max_user_instances=1024)"
    ),
}


@dataclass(frozen=True)
class InotifyWatchProbe:
    """One attempt to establish an inotify watch.

    ``supported`` is False where there is no inotify to ask (macOS/Windows:
    watchdog uses FSEvents/kqueue/ReadDirectoryChangesW there) - the check is
    then skipped, never failed. ``error`` is the errno of the refused call.
    """

    supported: bool
    error: int | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def errno_name(self) -> str | None:
        return None if self.error is None else errno_name(self.error)


def errno_name(err: int) -> str:
    """``errno.EACCES`` -> ``"EACCES"`` (the reason health surfaces report)."""
    return errno.errorcode.get(err, f"errno {err}")


def watch_failure_hint(err: int) -> str:
    """Likely cause and fix for an errno from inotify_init1/inotify_add_watch."""
    return _HINTS.get(err, f"unknown inotify failure ({os.strerror(err)})")


def _load_inotify() -> tuple[Callable[[int], int], Callable[[int, bytes, int], int]] | None:
    if not sys.platform.startswith("linux"):
        return None
    try:
        libc = ctypes.CDLL(None)
        init1 = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, use_errno=True)(
            ("inotify_init1", libc)
        )
        add_watch = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32, use_errno=True
        )(("inotify_add_watch", libc))
    except OSError, AttributeError:
        return None  # a libc without inotify: nothing to ask
    return init1, add_watch


def probe_inotify_watch(path: str | os.PathLike[str]) -> InotifyWatchProbe:
    """Ask the kernel whether ``path`` can be inotify-watched by this process."""
    fns = _load_inotify()
    if fns is None:
        return InotifyWatchProbe(supported=False)
    init1, add_watch = fns
    fd = init1(os.O_CLOEXEC)
    if fd < 0:
        return InotifyWatchProbe(supported=True, error=ctypes.get_errno())
    try:
        if add_watch(fd, os.fsencode(path), PROBE_MASK) < 0:
            return InotifyWatchProbe(supported=True, error=ctypes.get_errno())
        return InotifyWatchProbe(supported=True)
    finally:
        os.close(fd)  # closing the instance drops the watch with it
