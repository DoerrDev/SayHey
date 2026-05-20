"""Standalone updater for SayHey. Compiled to updater.exe via Nuitka.

Args:
  --zip <path>      Full release zip
  --target <dir>    dist/sayhey/ directory
  --restart <exe>   exe to launch after update
  --pid <pid>       wait for this process to exit
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

LOG_NAME = "update.log"


def _log(target: Path, msg: str) -> None:
    try:
        with open(target / LOG_NAME, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def wait_pid(pid: int, timeout: float = 30.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if os.name == "nt":
                import ctypes
                PROCESS_QUERY_LIMITED = 0x1000
                h = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED, False, pid
                )
                if not h:
                    return True
                exit_code = ctypes.c_ulong(0)
                ctypes.windll.kernel32.GetExitCodeProcess(
                    h, ctypes.byref(exit_code)
                )
                ctypes.windll.kernel32.CloseHandle(h)
                if exit_code.value != 259:  # STILL_ACTIVE
                    return True
            else:
                os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.3)
    return False


def apply_zip(zip_path: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        common = None
        for n in names:
            parts = n.split("/", 1)
            if len(parts) == 2 and parts[0]:
                if common is None:
                    common = parts[0]
                elif common != parts[0]:
                    common = ""
                    break
            else:
                common = ""
                break
        prefix = (common + "/") if common else ""

        for name in names:
            if name.endswith("/"):
                continue
            rel = name[len(prefix):] if prefix and name.startswith(prefix) else name
            if not rel:
                continue
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(dst, "wb") as out:
                shutil.copyfileobj(src, out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--restart", required=True)
    ap.add_argument("--pid", type=int, required=True)
    a = ap.parse_args()

    target = Path(a.target)
    _log(target, f"updater start pid={a.pid} zip={a.zip}")

    if not wait_pid(a.pid, 30):
        _log(target, "WARN: main process still alive after 30s, proceeding anyway")
    time.sleep(1.0)

    try:
        apply_zip(Path(a.zip), target)
        _log(target, "apply ok")
    except Exception as e:
        _log(target, f"FAIL: {e}")
        sys.exit(1)

    try:
        os.remove(a.zip)
    except OSError:
        pass

    try:
        if os.name == "nt":
            subprocess.Popen(
                [a.restart], creationflags=0x00000008, close_fds=True
            )
        else:
            subprocess.Popen([a.restart], close_fds=True)
    except Exception as e:
        _log(target, f"restart failed: {e}")


if __name__ == "__main__":
    main()
