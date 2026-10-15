from __future__ import annotations

import json
import platform
import time
import urllib.request

from PySide6.QtCore import QThread, Signal

from core.machine_id import get_machine_id_hash
from core.version import __version__


class MessagePoller(QThread):
    sig_unread_count = Signal(int)

    def __init__(self, api_base: str, interval_sec: int = 10, parent=None) -> None:
        super().__init__(parent)
        self._api_base = api_base.rstrip("/")
        self._interval = max(5, int(interval_sec))
        self._stop = False
        self._machine_id = get_machine_id_hash()
        self._last_count = -1

    def request_stop(self) -> None:
        self._stop = True

    def trigger_now(self) -> None:
        self._last_count = -1  # force re-emit even if value unchanged

    def _fetch_count(self) -> int:
        req = urllib.request.Request(
            f"{self._api_base}/api/messages/unread-count",
            headers={
                "X-Machine-Id": self._machine_id,
                "X-Client-Version": __version__,
                "X-Client-Os": f"{platform.system()} {platform.release()}",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(data.get("count", 0))

    def run(self) -> None:
        while not self._stop:
            try:
                n = self._fetch_count()
                if n != self._last_count:
                    self._last_count = n
                    self.sig_unread_count.emit(n)
            except Exception:
                pass
            slept = 0
            while slept < self._interval and not self._stop:
                time.sleep(1)
                slept += 1
