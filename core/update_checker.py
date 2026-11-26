import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from core.version import __version__

GITHUB_API = "https://api.github.com/repos/DoerrDev/SayHey/releases/latest"
GITEE_API = "https://gitee.com/api/v5/repos/chenjunbin2345/SayHey/releases/latest"
HTTP_TIMEOUT = 8


@dataclass
class UpdateInfo:
    has_update: bool
    latest_tag: str = ""
    name: str = ""
    notes: str = ""
    zip_url: str = ""
    zip_size: int = 0
    source: str = ""  # "github" or "gitee"


def _normalize(tag: str) -> tuple:
    s = tag.lstrip("vV")
    parts = re.split(r"[.\-+]", s)
    out = []
    for p in parts:
        out.append(int(p) if p.isdigit() else p)
    return tuple(out)


def _is_newer(remote: str, local: str) -> bool:
    try:
        return _normalize(remote) > _normalize(local)
    except Exception:
        return remote != local


def _http_get_json(url: str) -> dict | None:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"SayHey/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _pick_zip_asset(release: dict, source: str) -> tuple[str, int]:
    assets = release.get("assets") or []
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".zip"):
            if source == "github":
                return a.get("browser_download_url", ""), int(a.get("size", 0) or 0)
            return a.get("browser_download_url") or a.get("download_url", ""), int(
                a.get("size", 0) or 0
            )
    return "", 0


def _query(url: str, source: str) -> UpdateInfo | None:
    data = _http_get_json(url)
    if not data:
        return None
    tag = data.get("tag_name") or ""
    if not tag:
        return None
    zip_url, size = _pick_zip_asset(data, source)
    if not zip_url:
        return None
    return UpdateInfo(
        has_update=_is_newer(tag, __version__),
        latest_tag=tag,
        name=data.get("name") or tag,
        notes=data.get("body") or "",
        zip_url=zip_url,
        zip_size=size,
        source=source,
    )


def check_for_updates() -> UpdateInfo | None:
    info = _query(GITHUB_API, "github")
    if info is not None:
        return info
    return _query(GITEE_API, "gitee")


class _Checker(QObject):
    finished = Signal(object)

    def run(self):
        self.finished.emit(check_for_updates())


def start_check(on_done) -> QThread:
    thread = QThread()
    checker = _Checker()
    checker.moveToThread(thread)
    thread.started.connect(checker.run)
    checker.finished.connect(on_done)
    checker.finished.connect(thread.quit)
    thread.start()
    thread._checker = checker
    return thread
