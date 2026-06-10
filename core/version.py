from __future__ import annotations

# CI on tag push (v*) overwrites this constant via scripts/stamp_version.py
# before Nuitka build. Dev runs fall back to `git describe` for live tag info.
__version__ = "0.2.5.2"


def _git_describe() -> str:
    try:
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--dirty", "--always"],
            cwd=root, stderr=subprocess.DEVNULL, timeout=2,
        ).decode().strip()
        return out.lstrip("v") or __version__
    except Exception:
        return __version__


if __version__ == "v0.2.0":
    __version__ = _git_describe()
