from __future__ import annotations

import logging
import queue
import threading
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from typing import Optional

RUNTIME_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "runtime.log"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3


class RuntimeLogWriter:
    """Appends lines to a rotating log file from a background thread.

    write() only enqueues, so callers on the GUI thread never touch the disk.
    """

    def __init__(self, path: Path, max_bytes: int = _MAX_BYTES, backup_count: int = _BACKUP_COUNT) -> None:
        self._lock = threading.Lock()
        # Keyed by path (not id(self)) so recreating a writer reuses the logger
        # instead of leaking a new entry in logging's global registry.
        self._logger = logging.getLogger(f"sayhey.runtime.{path.resolve()}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._listener: Optional[QueueListener] = None
        self._queue_handler: Optional[QueueHandler] = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8", delay=True
            )
        except OSError:
            return
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        q: queue.SimpleQueue = queue.SimpleQueue()
        # The newest writer for a file takes over its logger.
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
        self._queue_handler = QueueHandler(q)
        self._logger.addHandler(self._queue_handler)
        self._listener = QueueListener(q, file_handler)
        self._listener.start()

    def write(self, line: str) -> None:
        if self._listener is not None and self._queue_handler in self._logger.handlers:
            self._logger.info(line)

    def close(self) -> None:
        """Flush pending lines and stop the writer thread."""
        with self._lock:
            listener, self._listener = self._listener, None
        if listener is None:
            return
        # Only detach our own handler; a newer writer may share this logger.
        self._logger.removeHandler(self._queue_handler)
        listener.stop()
        for handler in listener.handlers:
            handler.close()


_shared: Optional[RuntimeLogWriter] = None
_shared_lock = threading.Lock()


def runtime_log() -> RuntimeLogWriter:
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = RuntimeLogWriter(RUNTIME_LOG_PATH)
        return _shared


def close_runtime_log() -> None:
    global _shared
    with _shared_lock:
        writer, _shared = _shared, None
    if writer is not None:
        writer.close()
