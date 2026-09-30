from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from structlog.contextvars import bind_contextvars

from .agent import LabAgent
from .audit import record_audit
from .chat_demo import CHAT_DEMO_HTML
from .dashboard import DASHBOARD_HTML, build_dashboard_snapshot
from .diagnostics import render_log_view, render_trace_view
from .incidents import disable, enable, status
from .logging_config import configure_logging, get_logger
from .metrics import record_error, snapshot
from .middleware import CorrelationIdMiddleware
from .pii import hash_user_id, summarize_text
from .schemas import ChatRequest, ChatResponse
from .tracing import tracing_enabled

configure_logging()
log = get_logger()
agent = LabAgent()


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "app_started",
        service=os.getenv("APP_NAME", "day13-monitoring-llmops-lab"),
        env=os.getenv("APP_ENV", "dev"),
        payload={"tracing_enabled": tracing_enabled()},
    )
    yield


app = FastAPI(title="Day 13 Monitoring & LLMOps Lab", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tracing_enabled": tracing_enabled(), "incidents": status()}


@app.get("/metrics")
async def metrics() -> dict:
    return snapshot()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/chat-demo", response_class=HTMLResponse)
async def chat_demo() -> HTMLResponse:
    return HTMLResponse(CHAT_DEMO_HTML)


@app.get("/dashboard/data")
async def dashboard_data() -> dict:
    return build_dashboard_snapshot()


@app.get("/diagnostics/logs/{correlation_id}", response_class=HTMLResponse)
def diagnostic_log(request: Request, correlation_id: str) -> HTMLResponse:
    return render_log_view(request, correlation_id)


@app.get("/diagnostics/trace/{trace_id}", response_class=HTMLResponse)
def diagnostic_trace(request: Request, trace_id: str) -> HTMLResponse:
    return render_trace_view(request, trace_id)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    bind_contextvars(
        user_id_hash=hash_user_id(body.user_id),
        session_id=body.session_id,
        feature=body.feature,
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
    )
    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    try:
        result = agent.run(
            user_id=body.user_id,
            feature=body.feature,
            session_id=body.session_id,
            message=body.message,
            correlation_id=request.state.correlation_id,
        )
        log.info(
            "response_sent",
            service="api",
            latency_ms=result.latency_ms,
            ttft_ms=result.ttft_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            trace_id=result.trace_id,
            tool_name="retrieval",
            tool_success=True,
            payload={"answer_preview": summarize_text(result.answer)},
        )
        return ChatResponse(
            answer=result.answer,
            correlation_id=request.state.correlation_id,
            latency_ms=result.latency_ms,
            ttft_ms=result.ttft_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            trace_id=result.trace_id,
        )
    except Exception as exc:  # pragma: no cover
        error_type = type(exc).__name__
        record_error(error_type)
        log.error(
            "request_failed",
            service="api",
            error_type=error_type,
            tool_name="retrieval" if isinstance(exc, RuntimeError) else None,
            tool_success=False if isinstance(exc, RuntimeError) else None,
            payload={"detail": str(exc), "message_preview": summarize_text(body.message)},
        )
        record_audit(
            "request_failed", request.state.correlation_id, "error",
            {"error_type": error_type},
        )
        raise HTTPException(status_code=500, detail=error_type) from exc


@app.post("/incidents/{name}/enable")
async def enable_incident(name: str, request: Request) -> JSONResponse:
    try:
        enable(name)
        log.warning("incident_enabled", service="control", payload={"name": name})
        record_audit("incident_enabled", request.state.correlation_id, "success", {"scenario": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        record_audit("incident_enabled", request.state.correlation_id, "rejected", {"scenario": name})
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{name}/disable")
async def disable_incident(name: str, request: Request) -> JSONResponse:
    try:
        disable(name)
        log.warning("incident_disabled", service="control", payload={"name": name})
        record_audit("incident_disabled", request.state.correlation_id, "success", {"scenario": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        record_audit("incident_disabled", request.state.correlation_id, "rejected", {"scenario": name})
        raise HTTPException(status_code=404, detail=str(exc)) from exc
