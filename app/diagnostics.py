"""Loopback-only, read-only views of scrubbed logs and safe trace metadata."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from .pii import scrub_text
from .tracing import get_langfuse_client

STYLE = """<style>body{font:16px Segoe UI,Arial,sans-serif;max-width:1240px;margin:32px auto;color:#152238;background:#f4f7fb}
h1{font-size:26px}p{color:#4d5d75}table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 3px 12px #10253d0d}
th,td{border:1px solid #d9e2ed;padding:12px;text-align:left;vertical-align:top}th{background:#edf3fa}
code{font:14px Consolas,monospace}a{color:#2463d3}small{color:#66758c}</style>"""
LOG_FIELDS = (
    "ts", "event", "correlation_id", "env", "feature", "model",
    "user_id_hash", "message_preview", "latency_ms", "ttft_ms", "tool_success", "trace_id",
)


def _local_only(request: Request) -> None:
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Local diagnostics only")


def _cell(value: object) -> str:
    return f"<code>{html.escape(str(value))}</code>"


def render_log_view(request: Request, correlation_id: str) -> HTMLResponse:
    _local_only(request)
    if not re.fullmatch(r"req-[0-9a-f]{8}", correlation_id):
        raise HTTPException(status_code=400, detail="Invalid correlation ID")
    path = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))
    records: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("correlation_id") == correlation_id:
                records.append(event)
    if not records:
        raise HTTPException(status_code=404, detail="Correlation ID not found in local log")
    rows = []
    for event in records:
        cells = []
        for field in LOG_FIELDS:
            value = event.get("payload", {}).get("message_preview", "") if field == "message_preview" else event.get(field, "")
            if field == "trace_id" and re.fullmatch(r"[0-9a-f]{32}", str(value)):
                value = f'<a href="/diagnostics/trace/{value}">{_cell(value)}</a>'
                cells.append(f"<td>{value}</td>")
            else:
                cells.append(f"<td>{_cell(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    headings = "".join(f"<th>{html.escape(field)}</th>" for field in LOG_FIELDS)
    body = (
        f"<h1>Structured log: {_cell(correlation_id)}</h1>"
        f"<p>Source: local scrubbed JSONL log. {len(records)} matching event(s).</p>"
        f"<table><thead><tr>{headings}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    return HTMLResponse("<!doctype html><meta charset='utf-8'>" + STYLE + body)


def render_trace_view(request: Request, trace_id: str) -> HTMLResponse:
    _local_only(request)
    if not re.fullmatch(r"[0-9a-f]{32}", trace_id):
        raise HTTPException(status_code=400, detail="Invalid trace ID")
    observations = get_langfuse_client().api.observations.get_many(
        trace_id=trace_id,
        fields="core,basic,time,metadata,model,usage,prompt,metrics,trace_context",
        limit=100,
    ).data
    if not observations:
        raise HTTPException(status_code=404, detail="Trace not found in Langfuse")
    by_id = {item.id: item for item in observations}
    ordered = sorted(observations, key=lambda item: (item.parent_observation_id is not None, item.start_time))
    rows = []
    for item in ordered:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        parent = by_id.get(item.parent_observation_id)
        fields = (
            item.name,
            item.type,
            item.id,
            parent.name if parent else "root",
            round((item.latency or 0) * 1000, 1),
            metadata.get("correlation_id", ""),
            item.model or "",
            item.prompt_name or metadata.get("prompt_name", ""),
            item.prompt_version or metadata.get("prompt_version", ""),
            json.dumps(item.usage_details or {}),
            json.dumps(item.cost_details or {}),
            scrub_text(item.status_message or ""),
        )
        rows.append("<tr>" + "".join(f"<td>{_cell(value)}</td>" for value in fields) + "</tr>")
    headings = ("Observation", "Type", "ID", "Parent", "Latency ms", "Correlation ID", "Model", "Prompt", "Version", "Usage", "Cost", "Status")
    body = (
        f"<h1>Trace waterfall: {_cell(trace_id)}</h1>"
        f"<p>Source: live Langfuse Observations API v2. Safe metadata only; raw input/output omitted.</p>"
        f"<table><thead><tr>{''.join(f'<th>{html.escape(field)}</th>' for field in headings)}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return HTMLResponse("<!doctype html><meta charset='utf-8'>" + STYLE + body)
