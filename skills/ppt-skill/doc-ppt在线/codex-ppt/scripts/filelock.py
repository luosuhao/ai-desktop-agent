"""Small local fallback for the subset of filelock used by codex-ppt scripts."""

from __future__ import annotations

import os
import time
from pathlib import Path


class FileLock:
    def __init__(self, lock_file: str, timeout: float = -1, poll_interval: float = 0.05):
        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._fd: int | None = None

    def acquire(self) -> "FileLock":
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR)
        os.write(self._fd, str(os.getpid()).encode("ascii", errors="ignore"))
        return self

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.lock_file.unlink()
        except (FileNotFoundError, PermissionError):
            pass

    def __enter__(self) -> "FileLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
