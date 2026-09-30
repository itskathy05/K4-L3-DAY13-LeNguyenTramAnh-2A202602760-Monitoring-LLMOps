"""Summarize the official incident from local JSONL logs without exposing queries."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.challenge import load_challenge
from app.metrics import percentile


def _timestamp(event: dict) -> datetime:
    return datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))


def _summary(events: list[dict], threshold_ms: int) -> dict:
    values = [event["latency_ms"] for event in events]
    return {
        "requests": len(values),
        "p50_ms": percentile(values, 50) if values else None,
        "p95_ms": percentile(values, 95) if values else None,
        "over_challenge_threshold": sum(value > threshold_ms for value in values),
    }


def main() -> int:
    challenge = load_challenge()
    log_path = REPO_ROOT / "data" / "logs.jsonl"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    changes = [
        event for event in events
        if event.get("event") in {"incident_enabled", "incident_disabled"}
        and event.get("payload", {}).get("name") == challenge.incident
    ]
    enables = [event for event in changes if event["event"] == "incident_enabled"]
    if not enables:
        raise SystemExit(f"No enable event for {challenge.incident} in {log_path}")
    enabled_at = _timestamp(enables[-1])
    disables = [
        event for event in changes
        if event["event"] == "incident_disabled" and _timestamp(event) > enabled_at
    ]
    disabled_at = _timestamp(disables[0]) if disables else None
    sessions = {query["session_id"] for query in challenge.queries}
    responses = [
        event for event in events
        if event.get("event") == "response_sent"
        and event.get("feature") == challenge.affected_feature
        and event.get("session_id") in sessions
    ]
    baseline_by_session = {}
    for event in responses:
        if _timestamp(event) < enabled_at:
            baseline_by_session[event["session_id"]] = event
    baseline = list(baseline_by_session.values())
    incident = [
        event for event in responses
        if enabled_at <= _timestamp(event)
        and (disabled_at is None or _timestamp(event) < disabled_at)
    ]
    result = {
        "challenge_id": challenge.challenge_id,
        "cohort": challenge.cohort,
        "seed": challenge.seed,
        "incident": challenge.incident,
        "affected_feature": challenge.affected_feature,
        "threshold_ms": challenge.latency_threshold_ms,
        "enabled_at_utc": enabled_at.isoformat(),
        "disabled_at_utc": disabled_at.isoformat() if disabled_at else None,
        "baseline": _summary(baseline, challenge.latency_threshold_ms),
        "incident_metrics": _summary(incident, challenge.latency_threshold_ms),
        "incident_requests": [
            {
                "correlation_id": event["correlation_id"],
                "trace_id": event.get("trace_id"),
                "latency_ms": event["latency_ms"],
                "at_utc": event["ts"],
            }
            for event in incident
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if len(incident) == len(challenge.queries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
