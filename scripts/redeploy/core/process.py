"""Subprocess execution wrapper with logging and dry-run support."""

import asyncio
import shlex
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

from scripts.redeploy.core import output
from scripts.redeploy.models import CommandResult


class ProcessRunner:
    """Wrapper for subprocess execution with logging and dry-run support."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def run(
        self,
        cmd: list[str],
        check: bool = True,
        capture: bool = True,
        timeout: int | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run a command synchronously.

        Args:
            cmd: Command and arguments as list
            check: Raise exception on non-zero exit
            capture: Capture stdout/stderr (vs streaming)
            timeout: Timeout in seconds
            cwd: Working directory
            env: Environment variables (merged with current env)

        Returns:
            CommandResult with returncode, stdout, stderr, duration
        """
        cmd_str = shlex.join(cmd)

        if self.dry_run:
            output.dry_run(cmd_str)
            return CommandResult(
                returncode=0,
                stdout="",
                stderr="",
                duration=0.0,
                command=cmd,
            )

        start = time.monotonic()

        try:
            # Merge environment
            run_env = None
            if env:
                import os

                run_env = {**os.environ, **env}

            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=run_env,
                check=False,  # We'll handle checking ourselves
            )

            duration = time.monotonic() - start

            cmd_result = CommandResult(
                returncode=result.returncode,
                stdout=result.stdout if capture else "",
                stderr=result.stderr if capture else "",
                duration=duration,
                command=cmd,
            )

            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    result.stdout,
                    result.stderr,
                )

            return cmd_result

        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start
            return CommandResult(
                returncode=-1,
                stdout=e.stdout or "" if hasattr(e, "stdout") else "",
                stderr=f"Command timed out after {timeout}s",
                duration=duration,
                command=cmd,
            )

    async def run_async(
        self,
        cmd: list[str],
        check: bool = True,
        capture: bool = True,
        timeout: int | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run a command asynchronously.

        Args:
            cmd: Command and arguments as list
            check: Raise exception on non-zero exit
            capture: Capture stdout/stderr
            timeout: Timeout in seconds
            cwd: Working directory
            env: Environment variables

        Returns:
            CommandResult with returncode, stdout, stderr, duration
        """
        cmd_str = shlex.join(cmd)

        if self.dry_run:
            output.dry_run(cmd_str)
            return CommandResult(
                returncode=0,
                stdout="",
                stderr="",
                duration=0.0,
                command=cmd,
            )

        start = time.monotonic()

        # Merge environment
        import os

        run_env = {**os.environ, **(env or {})}

        try:
            if capture:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=run_env,
                )

                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(),
                        timeout=timeout,
                    )
                    stdout = stdout_bytes.decode() if stdout_bytes else ""
                    stderr = stderr_bytes.decode() if stderr_bytes else ""
                except TimeoutError:
                    process.kill()
                    await process.wait()
                    duration = time.monotonic() - start
                    return CommandResult(
                        returncode=-1,
                        stdout="",
                        stderr=f"Command timed out after {timeout}s",
                        duration=duration,
                        command=cmd,
                    )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=cwd,
                    env=run_env,
                )
                try:
                    await asyncio.wait_for(process.wait(), timeout=timeout)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                    duration = time.monotonic() - start
                    return CommandResult(
                        returncode=-1,
                        stdout="",
                        stderr=f"Command timed out after {timeout}s",
                        duration=duration,
                        command=cmd,
                    )
                stdout = ""
                stderr = ""

            duration = time.monotonic() - start
            returncode = process.returncode or 0

            cmd_result = CommandResult(
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                command=cmd,
            )

            if check and returncode != 0:
                raise subprocess.CalledProcessError(
                    returncode,
                    cmd,
                    stdout,
                    stderr,
                )

            return cmd_result

        except Exception as e:
            if isinstance(e, subprocess.CalledProcessError):
                raise
            duration = time.monotonic() - start
            return CommandResult(
                returncode=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                command=cmd,
            )

    def stream(
        self,
        cmd: list[str],
        prefix: str = "",
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> Generator[str, None, int]:
        """Stream command output line by line.

        Args:
            cmd: Command and arguments
            prefix: Prefix to add to each line
            cwd: Working directory
            env: Environment variables

        Yields:
            Lines of output (stdout and stderr combined)

        Returns:
            Exit code
        """
        cmd_str = shlex.join(cmd)

        if self.dry_run:
            output.dry_run(cmd_str)
            return 0

        # Merge environment
        import os

        run_env = {**os.environ, **(env or {})}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=run_env,
            bufsize=1,  # Line buffered
        )

        try:
            if process.stdout:
                for raw_line in process.stdout:
                    stripped = raw_line.rstrip("\n")
                    if prefix:
                        yield f"{prefix}{stripped}"
                    else:
                        yield stripped

            process.wait()
            return process.returncode
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def run_silent(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> bool:
        """Run a command silently, returning success/failure.

        Useful for checking if something exists or simple operations
        where we don't care about output.

        Args:
            cmd: Command and arguments
            cwd: Working directory
            env: Environment variables

        Returns:
            True if command succeeded (exit code 0)
        """
        if self.dry_run:
            return True

        try:
            result = self.run(cmd, check=False, capture=True, cwd=cwd, env=env)
            return result.success
        except Exception:
            return False
