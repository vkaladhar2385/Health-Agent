"""Triage, investigate, then diagnose. One model, no memory."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph

from pipeline_health_agent.data import build_scenario
from pipeline_health_agent.tools import (
    bind_scenario,
    get_pipeline_metrics,
    get_recent_deploys,
    search_logs,
)

DEFAULT_MODEL = "claude-sonnet-5"


class AgentState(TypedDict, total=False):
    pipeline: str
    metrics: dict[str, float | int | str]
    logs: list[str]
    deploys: list[dict[str, str]]
    triage: str
    investigation: str
    diagnosis: str


def run_diagnosis(pipeline: str, fault: str = "consumer_lag_spike") -> AgentState:
    """Inject a fault into one pipeline and run the graph. The model is not told the fault name."""
    load_project_env()
    bind_scenario(build_scenario(pipeline, fault))
    graph = build_graph()
    return graph.invoke({"pipeline": pipeline})


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("triage", triage)
    graph.add_node("investigate", investigate)
    graph.add_node("diagnose", diagnose)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "investigate")
    graph.add_edge("investigate", "diagnose")
    graph.add_edge("diagnose", END)
    return graph.compile()


def triage(state: AgentState) -> AgentState:
    metrics = get_pipeline_metrics(state["pipeline"])
    text = _ask(
        "You triage one data pipeline. Use only the metrics below. "
        "Say whether it looks healthy or degraded, and whether logs, deploys, or both "
        "should be inspected next. Two or three sentences.",
        f"Metrics from get_pipeline_metrics:\n{_dump(metrics)}",
    )
    return {"metrics": metrics, "triage": text}


def investigate(state: AgentState) -> AgentState:
    pipeline = state["pipeline"]
    logs = search_logs(pipeline)
    deploys = get_recent_deploys(pipeline)
    text = _ask(
        "You investigate a data pipeline. Use only the triage note, logs, and deploys. "
        "Summarize the evidence that explains the metrics. Quote the relevant log line "
        "and deploy change. Do not invent events.",
        "\n\n".join(
            [
                f"Triage:\n{state['triage']}",
                f"Logs from search_logs:\n{_dump(logs)}",
                f"Deploys from get_recent_deploys:\n{_dump(deploys)}",
            ]
        ),
    )
    return {"logs": logs, "deploys": deploys, "investigation": text}


def diagnose(state: AgentState) -> AgentState:
    text = _ask(
        "You diagnose a data pipeline. Use only the evidence below. "
        "State the root cause in one sentence, then the evidence you used. "
        "If the evidence shows a consumer lag spike, name that spike and what caused it. "
        "If the pipeline is healthy, say it is healthy.",
        "\n\n".join(
            [
                f"Metrics:\n{_dump(state['metrics'])}",
                f"Triage:\n{state['triage']}",
                f"Investigation:\n{state['investigation']}",
            ]
        ),
    )
    return {"diagnosis": text}


def load_project_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _ask(instructions: str, evidence: str) -> str:
    model = ChatAnthropic(
        model=os.environ.get("PHA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        api_key=_env("ANTHROPIC_API_KEY"),
        max_tokens=1024,
    )
    message = model.invoke(
        [
            {"role": "system", "content": instructions},
            {"role": "user", "content": evidence},
        ]
    )
    return _text(message.content)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is missing. Set it in .env.")
    return value


def _dump(value: object) -> str:
    return json.dumps(value, indent=2)


def _text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
    return "\n".join(part.strip() for part in parts if part.strip())
