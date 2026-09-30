"""Query the separate audit log or enforce its 30-day retention policy."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.audit import audit_path
from app.cli import configure_utf8_stdio


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _time(record: dict) -> datetime:
    return datetime.fromisoformat(record["ts"].replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> int:
    configure_utf8_stdio()
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["query", "prune"])
    parser.add_argument("--correlation-id")
    parser.add_argument("--since", help="UTC ISO 8601 timestamp")
    parser.add_argument("--apply", action="store_true", help="Actually prune old records; default is dry-run")
    parser.add_argument("--path", type=Path, default=audit_path())
    args = parser.parse_args()
    records = _read(args.path)
    if args.action == "query":
        since = datetime.fromisoformat(args.since.replace("Z", "+00:00")).astimezone(timezone.utc) if args.since else None
        for record in records:
            if args.correlation_id and record.get("correlation_id") != args.correlation_id:
                continue
            if since and _time(record) < since:
                continue
            print(json.dumps(record, ensure_ascii=False))
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    retained = [record for record in records if _time(record) >= cutoff]
    print(f"retention_days=30 total={len(records)} remove={len(records) - len(retained)} apply={args.apply}")
    if args.apply and args.path.exists():
        args.path.write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in retained),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
