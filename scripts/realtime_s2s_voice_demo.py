from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from app_core.controller import VoiceTranslatorController, build_app_config


CURRENT_DIR = _ROOT


async def main() -> None:
    config = build_app_config(CURRENT_DIR / ".env")
    client = VoiceTranslatorController(
        config,
        on_status=lambda message: print(message, flush=True),
        on_source=lambda text: print(f"[src] {text}", flush=True),
        on_translation=lambda text: print(f"[dst] {text}", flush=True),
    )
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
