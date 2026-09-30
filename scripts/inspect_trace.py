"""Read only safe trace fields through Langfuse Observations API v2."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
from langfuse import get_client

from app.cli import configure_utf8_stdio
from app.pii import scrub_text

SAFE_METADATA = (
    "correlation_id", "feature", "model", "doc_count", "query_preview",
    "prompt_name", "prompt_label", "prompt_version", "prompt_source",
    "prompt_fetch_error", "success",
)
FIELDS = "core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context"


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_id", nargs="?", help="Trace ID returned by /chat or stored in response_sent log")
    parser.add_argument("--correlation-id", help="Find trace IDs matching this log correlation ID")
    parser.add_argument("--recent-hours", type=int, default=24)
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    client = get_client()
    end = datetime.now(timezone.utc) + timedelta(minutes=1)
    start = end - timedelta(hours=args.recent_hours)
    if args.correlation_id:
        condition = [{
            "type": "stringObject", "column": "metadata", "key": "correlation_id",
            "operator": "=", "value": args.correlation_id,
        }]
        rows = client.api.observations.get_many(
            filter=json.dumps(condition), from_start_time=start, to_start_time=end,
            fields="core,basic,metadata", limit=100,
        ).data
        print(json.dumps({
            "correlation_id": args.correlation_id,
            "trace_ids": sorted({row.trace_id for row in rows}),
            "matching_observations": len(rows),
        }, indent=2))
        return 0 if rows else 1
    if args.trace_id:
        rows = client.api.observations.get_many(
            trace_id=args.trace_id, from_start_time=start, to_start_time=end,
            fields=FIELDS, limit=100,
        ).data
        summary = []
        for row in rows:
            metadata = row.metadata if isinstance(row.metadata, dict) else {}
            summary.append({
                "name": row.name,
                "type": row.type,
                "level": row.level,
                "status_message": scrub_text(row.status_message or ""),
                "latency": row.latency,
                "observation_id": row.id,
                "parent_observation_id": row.parent_observation_id,
                "correlation_id": metadata.get("correlation_id"),
                "prompt_name": row.prompt_name or metadata.get("prompt_name"),
                "prompt_label": metadata.get("prompt_label"),
                "prompt_version": row.prompt_version or metadata.get("prompt_version"),
                "prompt_source": metadata.get("prompt_source"),
                "model": row.model,
                "usage_details": row.usage_details,
                "cost_details": row.cost_details,
                "raw_io_present": row.input is not None or row.output is not None,
            })
        print(json.dumps({"trace_id": args.trace_id, "observations": summary}, indent=2, default=str))
        return 0 if rows else 1

    roots = client.api.observations.get_many(
        name="lab-agent-run", is_root_observation=True,
        from_start_time=start, to_start_time=end,
        fields="core,basic,trace_context", limit=100,
    ).data
    projects = client.api.projects.get().data
    print(json.dumps({
        "project": projects[0].name if len(projects) == 1 else "multiple-projects",
        "hours": args.recent_hours,
        "root_trace_count": len(roots),
        "trace_ids": [row.trace_id for row in roots],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
