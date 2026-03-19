"""Cross-platform daemon management for the scheduler process."""

from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT, Settings
from utils.logger import get_logger

logger = get_logger(__name__)

_PID_FILENAME = "scheduler.pid"
_META_FILENAME = "scheduler.meta.json"
_LOG_FILENAME = "scheduler.console.log"
_WINDOWS_PROCESS_TERMINATE = 0x0001
_WINDOWS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_STILL_ACTIVE = 259


@dataclass(slots=True)
class DaemonStatus:
    """Current daemon status snapshot."""

    running: bool
    pid: int | None
    pid_file: Path
    log_file: Path
    message: str
    started_at: str | None = None
    command: list[str] | None = None
    stale: bool = False


class DaemonService:
    """Manage a single detached scheduler process."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._state_dir = Path(settings.state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._pid_path = self._state_dir / _PID_FILENAME
        self._meta_path = self._state_dir / _META_FILENAME
        self._log_path = self._state_dir / _LOG_FILENAME

    @property
    def log_file(self) -> Path:
        return self._log_path

    def status(self, *, cleanup_stale: bool = True) -> DaemonStatus:
        """Return current daemon status and clean stale pid files by default."""
        pid = self._read_pid()
        meta = self._read_meta()

        if pid is None:
            return DaemonStatus(
                running=False,
                pid=None,
                pid_file=self._pid_path,
                log_file=self._log_path,
                message="守护进程未运行",
                started_at=meta.get("started_at"),
                command=meta.get("command"),
            )

        if self._is_process_alive(pid):
            return DaemonStatus(
                running=True,
                pid=pid,
                pid_file=self._pid_path,
                log_file=self._log_path,
                message=f"守护进程运行中 (PID {pid})",
                started_at=meta.get("started_at"),
                command=meta.get("command"),
            )

        if cleanup_stale:
            self._clear_runtime_files()

        return DaemonStatus(
            running=False,
            pid=pid,
            pid_file=self._pid_path,
            log_file=self._log_path,
            message=f"检测到失效 PID 文件，已清理 (PID {pid})",
            started_at=meta.get("started_at"),
            command=meta.get("command"),
            stale=True,
        )

    def start(self, *, force: bool = False) -> DaemonStatus:
        """Launch the scheduler in a detached background process."""
        current = self.status()
        if current.running:
            if not force:
                return DaemonStatus(
                    running=True,
                    pid=current.pid,
                    pid_file=self._pid_path,
                    log_file=self._log_path,
                    message=f"守护进程已在运行 (PID {current.pid})",
                    started_at=current.started_at,
                    command=current.command,
                )
            self.stop(force=True)

        cmd = self._build_spawn_command()
        logger.info("Starting daemon: %s", cmd)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        log_handle = self._log_path.open("ab")
        try:
            spawn_kwargs: dict[str, Any] = {
                "cwd": str(PROJECT_ROOT),
                "stdin": subprocess.DEVNULL,
                "stdout": log_handle,
                "stderr": log_handle,
            }

            if os.name == "nt":
                spawn_kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )
            else:
                spawn_kwargs["start_new_session"] = True

            proc = subprocess.Popen(cmd, **spawn_kwargs)
        finally:
            log_handle.close()

        time.sleep(1.0)
        if not self._is_process_alive(proc.pid):
            return DaemonStatus(
                running=False,
                pid=proc.pid,
                pid_file=self._pid_path,
                log_file=self._log_path,
                message="守护进程启动失败，请检查日志文件",
                command=cmd,
            )

        self._write_runtime_files(proc.pid, cmd)
        return DaemonStatus(
            running=True,
            pid=proc.pid,
            pid_file=self._pid_path,
            log_file=self._log_path,
            message=f"守护进程已启动 (PID {proc.pid})",
            started_at=self._read_meta().get("started_at"),
            command=cmd,
        )

    def stop(self, *, force: bool = False, timeout: float = 10.0) -> DaemonStatus:
        """Stop the detached scheduler process."""
        current = self.status(cleanup_stale=False)
        if not current.running or current.pid is None:
            self._clear_runtime_files()
            return DaemonStatus(
                running=False,
                pid=None,
                pid_file=self._pid_path,
                log_file=self._log_path,
                message="守护进程未运行",
            )

        pid = current.pid
        logger.info("Stopping daemon pid=%s", pid)
        self._terminate_process(pid, force=False)

        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._is_process_alive(pid):
                self._clear_runtime_files()
                return DaemonStatus(
                    running=False,
                    pid=None,
                    pid_file=self._pid_path,
                    log_file=self._log_path,
                    message=f"守护进程已停止 (PID {pid})",
                )
            time.sleep(0.25)

        if force or os.name == "nt":
            self._terminate_process(pid, force=True)
            time.sleep(0.5)

        if self._is_process_alive(pid):
            return DaemonStatus(
                running=True,
                pid=pid,
                pid_file=self._pid_path,
                log_file=self._log_path,
                message=f"守护进程停止超时 (PID {pid})，请检查日志",
                started_at=current.started_at,
                command=current.command,
            )

        self._clear_runtime_files()
        return DaemonStatus(
            running=False,
            pid=None,
            pid_file=self._pid_path,
            log_file=self._log_path,
            message=f"守护进程已强制停止 (PID {pid})",
        )

    def restart(self, *, force: bool = True) -> DaemonStatus:
        """Restart the daemon process."""
        self.stop(force=force)
        return self.start(force=False)

    def read_log_tail(self, lines: int = 40) -> str:
        """Return the last N lines of daemon console output."""
        if not self._log_path.exists():
            return ""
        with self._log_path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(deque(handle, maxlen=max(1, lines)))

    def _build_spawn_command(self) -> list[str]:
        if getattr(sys, "frozen", False):
            return [str(Path(sys.executable).resolve()), "schedule"]
        return [sys.executable, str(PROJECT_ROOT / "main.py"), "schedule"]

    def _read_pid(self) -> int | None:
        if not self._pid_path.exists():
            return None
        try:
            return int(self._pid_path.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def _read_meta(self) -> dict[str, Any]:
        if not self._meta_path.exists():
            return {}
        try:
            return json.loads(self._meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_runtime_files(self, pid: int, cmd: list[str]) -> None:
        self._pid_path.write_text(str(pid), encoding="utf-8")
        payload = {
            "pid": pid,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "command": cmd,
            "log_file": str(self._log_path),
        }
        self._meta_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _clear_runtime_files(self) -> None:
        for path in (self._pid_path, self._meta_path):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to remove runtime file: %s", path, exc_info=True)

    def _is_process_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            return self._is_process_alive_windows(pid)
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _terminate_process(self, pid: int, *, force: bool) -> None:
        if pid <= 0:
            return
        if os.name == "nt":
            self._terminate_process_windows(pid)
            return

        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return

    @staticmethod
    def _is_process_alive_windows(pid: int) -> bool:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(_WINDOWS_QUERY_LIMITED_INFORMATION, 0, pid)
        if not handle:
            return False

        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == _WINDOWS_STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    @staticmethod
    def _terminate_process_windows(pid: int) -> None:
        kernel32 = ctypes.windll.kernel32
        access = _WINDOWS_PROCESS_TERMINATE | _WINDOWS_QUERY_LIMITED_INFORMATION
        handle = kernel32.OpenProcess(access, 0, pid)
        if not handle:
            return

        try:
            kernel32.TerminateProcess(handle, 1)
        finally:
            kernel32.CloseHandle(handle)
