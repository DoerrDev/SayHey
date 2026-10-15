from __future__ import annotations

import hashlib
import socket
import uuid


def get_machine_id_hash() -> str:
    mac = uuid.getnode()
    host = socket.gethostname()
    return hashlib.sha256(f"{mac}-{host}".encode("utf-8")).hexdigest()
