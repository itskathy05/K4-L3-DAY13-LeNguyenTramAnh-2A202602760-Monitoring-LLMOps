from __future__ import annotations

from contextlib import contextmanager

import pytest

from app import agent as agent_module


class ManagedPrompt:
    version = 3

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.span_updates: list[dict] = []
        self.observations: list[dict] = []

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        observation = RecordingObservation(kwargs)
        self.observations.append({"start": kwargs, "updates": observation.updates})
        yield observation

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)


class RecordingObservation:
    def __init__(self, start: dict) -> None:
        self.start = start
        self.updates: list[dict] = []

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)


def test_agent_records_prompt_version_with_v4_observation_api(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    propagated: list[dict] = []

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Explain traces",
        correlation_id="req-12345678",
    )

    span_update = client.span_updates[-1]
    assert span_update["metadata"] == {
        "doc_count": 1,
        "query_preview": "Explain traces",
        "prompt_name": "day13-chat",
        "prompt_label": "production",
        "prompt_version": "3",
        "prompt_source": "langfuse",
        "prompt_fetch_error": "",
    }
    assert span_update["version"] == "3"
    assert propagated[0]["metadata"]["correlation_id"] == "req-12345678"
    assert propagated[-1]["prompt"] is client.prompt
    assert [item["start"]["as_type"] for item in client.observations] == [
        "retriever", "generation"
    ]
    generation = client.observations[-1]
    assert generation["start"]["prompt"] is client.prompt
    assert generation["updates"][0]["usage_details"]["input"] > 0
    assert generation["updates"][0]["cost_details"]["total"] > 0


def test_retrieval_failure_marks_its_observation_error(monkeypatch) -> None:
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    @contextmanager
    def no_op_attributes(**kwargs):
        yield

    def fail_retrieval(message: str):
        raise RuntimeError("retrieval failed")

    monkeypatch.setattr(agent_module, "propagate_attributes", no_op_attributes)
    monkeypatch.setattr(agent_module, "retrieve", fail_retrieval)
    with pytest.raises(RuntimeError):
        agent_module.LabAgent.run.__wrapped__(
            agent_module.LabAgent(),
            user_id="u1", feature="qa", session_id="s1",
            message="test", correlation_id="req-12345678",
        )
    assert len(client.observations) == 1
    update = client.observations[0]["updates"][0]
    assert update["level"] == "ERROR"
    assert update["metadata"]["success"] is False
