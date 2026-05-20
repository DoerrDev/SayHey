from __future__ import annotations

import json
import time
import urllib.request

from PySide6.QtCore import QThread, Signal

from core.machine_id import get_machine_id_hash


class MessagePoller(QThread):
    sig_message = Signal(int, str, str)  # id, content, created_at

    def __init__(self, api_base: str, interval_sec: int = 30, parent=None) -> None:
        super().__init__(parent)
        self._api_base = api_base.rstrip("/")
        self._interval = max(10, int(interval_sec))
        self._stop = False
        self._machine_id = get_machine_id_hash()

    def request_stop(self) -> None:
        self._stop = True

    def _fetch(self) -> list[dict]:
        req = urllib.request.Request(
            f"{self._api_base}/api/messages",
            headers={"X-Machine-Id": self._machine_id},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _ack(self, ids: list[int]) -> None:
        body = json.dumps({"ids": ids}).encode("utf-8")
        req = urllib.request.Request(
            f"{self._api_base}/api/messages/ack",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Machine-Id": self._machine_id,
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:
            pass

    def run(self) -> None:
        while not self._stop:
            try:
                rows = self._fetch()
                ids: list[int] = []
                for r in rows:
                    self.sig_message.emit(int(r["id"]), str(r.get("content", "")), str(r.get("created_at", "")))
                    ids.append(int(r["id"]))
                if ids:
                    self._ack(ids)
            except Exception:
                pass
            # Sleep in small slices so stop is responsive
            slept = 0
            while slept < self._interval and not self._stop:
                time.sleep(1)
                slept += 1
