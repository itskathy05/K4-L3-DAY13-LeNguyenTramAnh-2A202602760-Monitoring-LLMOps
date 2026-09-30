"""Minimal separate audit trail for lab control actions and failures."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .pii import scrub_value

AUDIT_LOCK = Lock()


def audit_path() -> Path:
    return Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))


def record_audit(
    action: str,
    correlation_id: str,
    outcome: str,
    details: dict[str, Any] | None = None,
) -> None:
    record = scrub_value({
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": "local-lab-operator",
        "action": action,
        "outcome": outcome,
        "correlation_id": correlation_id,
        "details": details or {},
    })
    path = audit_path()
    with AUDIT_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
