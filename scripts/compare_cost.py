"""Compare estimated fake-LLM cost on the same fixed workload."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent import LabAgent
from app.mock_llm import FakeLLM
from app.mock_rag import retrieve
from app.prompt_management import resolve_prompt


def compare() -> dict:
    queries = [
        json.loads(line)
        for line in (REPO_ROOT / "data" / "sample_queries.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected = [
        json.loads(line)
        for line in (REPO_ROOT / "data" / "expected_answers.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    agent = LabAgent()
    results: dict[str, dict] = {}
    for style in ("standard", "concise"):
        llm = FakeLLM(style=style)
        output_tokens = 0
        input_tokens = 0
        costs = []
        qualities = []
        for query in queries:
            docs = retrieve(query["message"])
            prompt = resolve_prompt(
                None, feature=query["feature"], docs=docs,
                message=query["message"], enabled=False,
            )
            response = llm.generate(prompt.text)
            output_tokens += response.usage.output_tokens
            input_tokens += response.usage.input_tokens
            costs.append(agent._estimate_cost(response.usage.input_tokens, response.usage.output_tokens))
            qualities.append(agent._heuristic_quality(query["message"], response.text, docs))
        answer_checks = all(
            all(term.lower() in llm.generate(resolve_prompt(
                None, feature="qa", docs=retrieve(case["question"]),
                message=case["question"], enabled=False,
            ).text).text.lower() for term in case["must_include"])
            for case in expected
        )
        results[style] = {
            "requests": len(queries),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": round(sum(costs), 6),
            "quality_mean": round(mean(qualities), 3),
            "expected_answer_checks_passed": answer_checks,
        }
    before = results["standard"]["estimated_cost_usd"]
    after = results["concise"]["estimated_cost_usd"]
    return {
        "workload": "data/sample_queries.jsonl",
        "cost_is_simulated": True,
        "standard": results["standard"],
        "concise": results["concise"],
        "cost_reduction_pct": round((before - after) * 100 / before, 2),
        "guardrails_passed": (
            after < before
            and results["concise"]["quality_mean"] >= 0.75
            and results["concise"]["expected_answer_checks_passed"]
        ),
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
