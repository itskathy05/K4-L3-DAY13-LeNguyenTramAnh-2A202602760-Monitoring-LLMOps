from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import logging_config
from app.audit import record_audit
from app.dashboard import build_dashboard_snapshot
from app.diagnostics import render_log_view, render_trace_view
from app.incidents import STATE
from app.main import app
from app.mock_llm import FakeLLM
from app.pii import scrub_text, scrub_value


def _request(message: str, session: str) -> dict:
    return {"user_id": session, "session_id": session, "feature": "qa", "message": message}


def test_chat_demo_serves_same_origin_safe_ui() -> None:
    async def fetch():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get("/chat-demo")

    response = asyncio.run(fetch())
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for marker in ("/chat", "/dashboard", "/diagnostics/logs/", "/diagnostics/trace/", "Browser round trip"):
        assert marker in response.text
    assert "bubble.textContent=text" in response.text
    assert "innerHTML" not in response.text


def test_correlation_context_and_pii_under_concurrent_requests(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "requests.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await asyncio.gather(
                client.post("/chat", json=_request("Email student@vinuni.edu.vn about refund", "session-a"), headers={"x-request-id": "req-ABCDEF12"}),
                client.post("/chat", json=_request("Phone 090 123 4567 and card 4111 1111 1111 1111", "session-b"), headers={"x-request-id": "invalid"}),
                client.post("/chat", json=_request("CCCD 012345678901 and monitoring", "session-c")),
            )

    responses = asyncio.run(send())
    assert all(response.status_code == 200 for response in responses)
    ids = [response.headers["x-request-id"] for response in responses]
    assert ids[0] == "req-abcdef12"
    assert len(set(ids)) == 3
    assert all(re.fullmatch(r"req-[0-9a-f]{8}", cid) for cid in ids)
    assert all(float(response.headers["x-response-time-ms"]) >= 0 for response in responses)
    assert all(response.json()["correlation_id"] == cid for response, cid in zip(responses, ids))

    text = log_path.read_text(encoding="utf-8")
    for raw in ("student@vinuni.edu.vn", "090 123 4567", "4111 1111 1111 1111", "012345678901"):
        assert raw not in text
    events = [json.loads(line) for line in text.splitlines()]
    requests = [event for event in events if event["event"] == "request_received"]
    assert {event["correlation_id"] for event in requests} == set(ids)
    assert {(event["session_id"], event["correlation_id"]) for event in requests} == set(zip(("session-a", "session-b", "session-c"), ids))
    assert all(event["model"] and event["env"] and event["user_id_hash"] for event in requests)


def test_scrub_value_handles_nested_metadata_and_errors() -> None:
    redacted = scrub_value({
        "nested": ["student@vinuni.edu.vn", {"phone": "0901234567"}],
        "error": ("CCCD 012345678901", "card 4111-1111-1111-1111"),
    })
    serialized = json.dumps(redacted)
    for raw in ("student@vinuni.edu.vn", "0901234567", "012345678901", "4111-1111-1111-1111"):
        assert raw not in serialized
    assert "REDACTED_EMAIL" in serialized
    assert "REDACTED_CREDIT_CARD" in serialized


def test_phone_redaction_preserves_hex_trace_ids() -> None:
    trace_id = "72ab0912345678d0dfa14b67d4c76c9a"
    assert scrub_text(trace_id) == trace_id
    assert scrub_text("phone=0912345678") == "phone=[REDACTED_PHONE_VN]"


def _local_request(host: str = "127.0.0.1") -> Request:
    return Request({"type": "http", "client": (host, 12345), "headers": []})


def test_log_diagnostic_is_loopback_only_and_hides_payload(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "logs.jsonl"
    trace_id = "72ab0912345678d0dfa14b67d4c76c9a"
    path.write_text(json.dumps({
        "event": "response_sent", "correlation_id": "req-12345678", "trace_id": trace_id,
        "latency_ms": 2653, "payload": {"answer_preview": "<script>unsafe</script>"},
    }) + "\n", encoding="utf-8")
    monkeypatch.setenv("LOG_PATH", str(path))
    content = render_log_view(_local_request(), "req-12345678").body.decode()
    assert "2653" in content and trace_id in content
    assert "<script>" not in content and "answer_preview" not in content
    with pytest.raises(HTTPException) as error:
        render_log_view(_local_request("8.8.8.8"), "req-12345678")
    assert error.value.status_code == 403


def test_trace_diagnostic_uses_live_safe_observation_fields(monkeypatch) -> None:
    from app import diagnostics

    started = datetime(2026, 9, 29, tzinfo=timezone.utc)
    root = SimpleNamespace(
        id="root", name="lab-agent-run", type="AGENT", parent_observation_id=None,
        start_time=started, latency=2.653, metadata={"correlation_id": "req-12345678"},
        model="", prompt_name="day13-chat", prompt_version=1, usage_details={},
        cost_details={}, status_message="", input="private input", output="private output",
    )
    child = SimpleNamespace(
        id="retriever", name="retrieval", type="RETRIEVER", parent_observation_id="root",
        start_time=started, latency=2.501, metadata={"correlation_id": "req-12345678"},
        model="", prompt_name="", prompt_version=None, usage_details={},
        cost_details={}, status_message="", input="private input", output="private output",
    )
    fake = SimpleNamespace(api=SimpleNamespace(observations=SimpleNamespace(
        get_many=lambda **_: SimpleNamespace(data=[child, root])
    )))
    monkeypatch.setattr(diagnostics, "get_langfuse_client", lambda: fake)
    content = render_trace_view(_local_request(), "a" * 32).body.decode()
    assert "retrieval" in content and "2501" in content and "req-12345678" in content
    assert "private input" not in content and "private output" not in content


def test_dashboard_calculates_all_six_panels_from_log(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    common = {"ts": "2026-09-29T12:00:00Z", "service": "api", "level": "info"}
    events = [
        {**common, "event": "request_received", "correlation_id": "req-00000001"},
        {**common, "event": "request_received", "correlation_id": "req-00000002"},
        {**common, "event": "request_received", "correlation_id": "req-00000003"},
        {**common, "event": "response_sent", "correlation_id": "req-00000001", "latency_ms": 100, "ttft_ms": 20, "cost_usd": 0.01, "tokens_in": 10, "tokens_out": 20, "quality_score": 0.8, "tool_success": True},
        {**common, "event": "response_sent", "correlation_id": "req-00000002", "latency_ms": 300, "ttft_ms": 40, "cost_usd": 0.02, "tokens_in": 30, "tokens_out": 40, "quality_score": 0.6, "tool_success": True},
        {**common, "event": "request_failed", "correlation_id": "req-00000003", "error_type": "RuntimeError", "tool_success": False},
    ]
    log_path.write_text("\n".join(json.dumps(event) for event in events) + "\nnot-json\n", encoding="utf-8")
    snapshot = build_dashboard_snapshot(now=__import__("datetime").datetime.fromisoformat("2026-09-29T12:01:00+00:00"), log_path=log_path)
    panels = {panel["id"]: panel for panel in snapshot["panels"]}
    assert len(panels) == 6
    assert snapshot["event_count"] == 6
    assert panels["latency"]["summary"]["P95"] == 300
    assert panels["latency"]["summary"]["TTFT P95"] == 40
    assert panels["traffic"]["summary"]["Requests"] == 3
    assert panels["errors"]["summary"]["Error rate"] == 33.33
    assert panels["errors"]["summary"]["Retrieval success"] == 66.67
    assert panels["errors"]["summary"]["Breakdown"] == {"RuntimeError": 1}
    assert panels["cost"]["summary"]["Total"] == 0.03
    assert panels["tokens"]["summary"] == {"Input": 40, "Output": 60}
    assert panels["quality"]["summary"]["Mean"] == 0.7
    assert panels["latency"]["line_threshold"] == 3000


def test_incident_error_writes_separate_scrubbed_audit_record(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "errors.jsonl"
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_path))
    monkeypatch.setitem(STATE, "tool_fail", True)

    async def send():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.post("/chat", json=_request("contact student@vinuni.edu.vn", "session-error"))

    response = asyncio.run(send())
    assert response.status_code == 500
    event = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["action"] == "request_failed"
    assert event["correlation_id"] == response.headers["x-request-id"]
    assert "student@vinuni.edu.vn" not in audit_path.read_text(encoding="utf-8")
    assert "student@vinuni.edu.vn" not in log_path.read_text(encoding="utf-8")


def test_audit_writer_scrubs_details(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(path))
    record_audit("incident_enabled", "req-12345678", "success", {"note": "student@vinuni.edu.vn"})
    item = json.loads(path.read_text(encoding="utf-8"))
    assert item["details"]["note"] == "[REDACTED_EMAIL]"


def test_fake_llm_cost_mode_uses_real_answer_length(monkeypatch) -> None:
    prompt = "Feature=qa\nDocs=Refunds are available within 7 days with proof of purchase.\nQuestion=refund?"
    standard = FakeLLM(style="standard").generate(prompt)
    concise = FakeLLM(style="concise").generate(prompt)
    assert concise.usage.output_tokens < standard.usage.output_tokens
    assert "7 days" in concise.text and "proof of purchase" in concise.text
    assert concise.usage.output_tokens == (len(concise.text) + 3) // 4
    monkeypatch.setitem(STATE, "cost_spike", True)
    spike = FakeLLM(style="standard").generate(prompt)
    assert spike.usage.output_tokens > standard.usage.output_tokens * 3


def test_audit_retention_is_dry_run_until_apply(monkeypatch, tmp_path: Path, capsys) -> None:
    from scripts import audit_log

    path = tmp_path / "audit.jsonl"
    old = {"ts": "2020-01-01T00:00:00Z", "correlation_id": "req-00000001"}
    fresh = {"ts": "2099-01-01T00:00:00Z", "correlation_id": "req-00000002"}
    original = "\n".join(json.dumps(record) for record in (old, fresh)) + "\n"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["audit_log.py", "prune", "--path", str(path)])
    assert audit_log.main() == 0
    assert "remove=1 apply=False" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == original
    monkeypatch.setattr("sys.argv", ["audit_log.py", "prune", "--path", str(path), "--apply"])
    assert audit_log.main() == 0
    assert [json.loads(line)["correlation_id"] for line in path.read_text(encoding="utf-8").splitlines()] == ["req-00000002"]


def test_challenge_analyzer_uses_latest_baseline_per_session(monkeypatch, tmp_path: Path, capsys) -> None:
    from app.challenge import ChallengeConfig
    from scripts import analyze_challenge

    challenge = ChallengeConfig(
        cohort="K4", challenge_id="test-l3a", incident="rag_slow", seed=1,
        affected_feature="monitoring", latency_threshold_ms=2000,
        queries=({"user_id": "u", "session_id": "s1", "feature": "monitoring", "message": "q"},),
    )
    monkeypatch.setattr(analyze_challenge, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(analyze_challenge, "load_challenge", lambda: challenge)
    (tmp_path / "data").mkdir()
    events = [
        {"ts": "2026-09-29T08:00:00Z", "event": "response_sent", "feature": "monitoring", "session_id": "s1", "latency_ms": 9000},
        {"ts": "2026-09-29T08:01:00Z", "event": "response_sent", "feature": "monitoring", "session_id": "s1", "latency_ms": 100},
        {"ts": "2026-09-29T08:02:00Z", "event": "incident_enabled", "payload": {"name": "rag_slow"}},
        {"ts": "2026-09-29T08:03:00Z", "event": "response_sent", "feature": "monitoring", "session_id": "s1", "latency_ms": 2653, "correlation_id": "req-00000001", "trace_id": "a" * 32},
        {"ts": "2026-09-29T08:04:00Z", "event": "incident_disabled", "payload": {"name": "rag_slow"}},
    ]
    (tmp_path / "data" / "logs.jsonl").write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    assert analyze_challenge.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["baseline"] == {"requests": 1, "p50_ms": 100.0, "p95_ms": 100.0, "over_challenge_threshold": 0}
    assert result["incident_metrics"]["over_challenge_threshold"] == 1


def test_submission_scanner_exempts_only_named_synthetic_fixtures(monkeypatch, tmp_path: Path) -> None:
    from scripts import check_submission

    (tmp_path / "data").mkdir()
    (tmp_path / "docs").mkdir()
    fixture = tmp_path / "data" / "sample_queries.jsonl"
    note = tmp_path / "docs" / "note.md"
    fixture.write_text("synthetic 0901234567", encoding="utf-8")
    note.write_text("accidental 0901234567", encoding="utf-8")
    monkeypatch.setattr(check_submission, "REPO_ROOT", tmp_path)
    findings = check_submission.scan_files([fixture, note])
    assert findings == ["docs/note.md:1: possible PII"]
