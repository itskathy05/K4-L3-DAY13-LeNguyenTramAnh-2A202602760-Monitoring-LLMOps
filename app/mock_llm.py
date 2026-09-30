from __future__ import annotations

import os
import time
from dataclasses import dataclass

from .incidents import STATE


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str
    ttft_ms: int


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5", style: str | None = None) -> None:
        self.model = model
        self.style = style or os.getenv("FAKE_LLM_STYLE", "standard")
        if self.style not in {"standard", "concise"}:
            raise ValueError("FAKE_LLM_STYLE must be 'standard' or 'concise'")

    def _answer(self, prompt: str) -> str:
        if "Refunds are available within 7 days" in prompt:
            brief = "Refunds are available within 7 days with proof of purchase."
            detail = " Keep your purchase receipt so the request can be checked against the refund policy."
        elif "Metrics detect incidents" in prompt:
            brief = "Metrics show symptoms, logs locate affected requests, and traces reveal the slow step."
            detail = " Match the log correlation ID to the trace before naming a root cause."
        elif "Do not expose PII" in prompt:
            brief = "PII and other sensitive data must not appear in logs or traces."
            detail = " Scrub values before serialization and retain only safe request metadata."
        else:
            brief = "Metrics reveal symptoms, logs locate requests, traces explain failures, and PII or sensitive data stays private."
            detail = " Check the user-visible impact and correlate each signal before changing the system."
        return brief if self.style == "concise" else brief + detail

    def generate(self, prompt: str) -> FakeResponse:
        started = time.perf_counter()
        time.sleep(0.05)  # mô phỏng thời điểm token đầu tiên sẵn sàng
        ttft_ms = int((time.perf_counter() - started) * 1000)
        time.sleep(0.10)
        answer = self._answer(prompt)
        if STATE["cost_spike"]:
            answer = " ".join([answer] * 4)
        input_tokens = max(1, (len(prompt) + 3) // 4)
        output_tokens = max(1, (len(answer) + 3) // 4)
        return FakeResponse(
            text=answer,
            usage=FakeUsage(input_tokens, output_tokens),
            model=self.model,
            ttft_ms=ttft_ms,
        )
