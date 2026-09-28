"""Unit tests for the FileWatcher's inotify watch self-check.

watchdog's inotify backend swallows EACCES from inotify_add_watch, so a native
Observer on a camera root the kernel refuses to watch (A5500 box, 2026-09-28:
SELinux enforcing, container_t vs a usr_t /cameras) starts "successfully",
reports a live emitter, and never delivers an event. The probe asks the kernel
directly. These tests run the REAL syscalls on Linux (CI is Linux) - the
behaviour under test is the kernel's answer, not a mock of it.
"""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path

import pytest

from backend.services.inotify_probe import (
    InotifyWatchProbe,
    probe_inotify_watch,
    watch_failure_hint,
)

ON_LINUX = sys.platform.startswith("linux")


class TestProbeAgainstTheRealKernel:
    def test_a_normal_directory_can_be_watched(self, tmp_path: Path) -> None:
        probe = probe_inotify_watch(str(tmp_path))
        if ON_LINUX:
            assert probe.supported is True
            assert probe.ok is True
            assert probe.errno_name is None
        else:  # FSEvents/kqueue hosts: the check is a non-event, never a crash
            assert probe.supported is False
            assert probe.ok is True

    def test_an_unreadable_directory_is_refused_with_eacces(self, tmp_path: Path) -> None:
        # The DAC twin of the SELinux denial: inotify_add_watch needs read
        # permission on the inode. Root bypasses DAC, so as root the same call
        # must SUCCEED - asserted, not skipped.
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o000)
        try:
            probe = probe_inotify_watch(str(locked))
        finally:
            locked.chmod(0o755)
        if not ON_LINUX:
            assert probe.supported is False
        elif os.geteuid() != 0:
            assert probe.ok is False
            assert probe.error == errno.EACCES
            assert probe.errno_name == "EACCES"
        else:
            assert probe.ok is True

    def test_a_missing_path_reports_its_errno_instead_of_raising(self, tmp_path: Path) -> None:
        probe = probe_inotify_watch(str(tmp_path / "does-not-exist"))
        if ON_LINUX:
            assert probe.ok is False
            assert probe.errno_name == "ENOENT"
        else:
            assert probe.supported is False

    def test_a_non_linux_host_skips_the_check_without_crashing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # macOS dev: watchdog picks FSEvents there, there is no inotify to ask.
        monkeypatch.setattr(sys, "platform", "darwin")
        probe = probe_inotify_watch(str(tmp_path))
        assert probe.supported is False
        assert probe.ok is True
        assert probe.errno_name is None


class TestErrnoMapping:
    @pytest.mark.parametrize("err", [errno.EACCES, errno.EPERM])
    def test_permission_denials_name_the_selinux_fix(self, err: int) -> None:
        hint = watch_failure_hint(err)
        assert "SELinux" in hint
        assert ":z" in hint
        assert "container_file_t" in hint
        assert "avc: denied { watch }" in hint

    def test_enospc_names_max_user_watches(self) -> None:
        assert "max_user_watches" in watch_failure_hint(errno.ENOSPC)

    def test_emfile_names_max_user_instances(self) -> None:
        assert "max_user_instances" in watch_failure_hint(errno.EMFILE)

    def test_anything_else_is_unknown(self) -> None:
        assert "unknown" in watch_failure_hint(errno.EIO).lower()

    def test_probe_result_names_its_errno(self) -> None:
        assert InotifyWatchProbe(supported=True, error=errno.ENOSPC).errno_name == "ENOSPC"
