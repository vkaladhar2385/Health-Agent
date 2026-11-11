"""Triage → investigate → diagnose → propose → human approval → remediate → remember."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from pipeline_health_agent.data import build_scenario
from pipeline_health_agent.memory import IncidentStore
from pipeline_health_agent.paths import CHECKPOINT_DB, ensure_data_dir
from pipeline_health_agent.tools import (
    bind_scenario,
    bind_store,
    get_pipeline_metrics,
    get_recent_deploys,
    lookup_incidents,
    open_ticket,
    restart_consumer,
    scale_partitions,
    search_logs,
)

DEFAULT_MODEL = "claude-sonnet-5"
Decision = Literal["approve", "reject"]


class AgentState(TypedDict, total=False):
    pipeline: str
    fault: str
    metrics: dict[str, float | int | str]
    logs: list[str]
    deploys: list[dict[str, str]]
    past_incidents: list[dict[str, str | int]]
    triage: str
    investigation: str
    diagnosis: str
    proposed_action: dict[str, str]
    decision: str
    remediation_result: dict[str, str | int]
    incident_id: int


def new_thread_id() -> str:
    return str(uuid.uuid4())


def build_graph(checkpointer: SqliteSaver | None = None):
    graph = StateGraph(AgentState)
    graph.add_node("triage", triage)
    graph.add_node("investigate", investigate)
    graph.add_node("diagnose", diagnose)
    graph.add_node("propose", propose)
    graph.add_node("await_approval", await_approval)
    graph.add_node("remediate", remediate)
    graph.add_node("remember", remember)

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "investigate")
    graph.add_edge("investigate", "diagnose")
    graph.add_edge("diagnose", "propose")
    graph.add_edge("propose", "await_approval")
    graph.add_conditional_edges(
        "await_approval",
        route_after_approval,
        {"remediate": "remediate", "remember": "remember"},
    )
    graph.add_edge("remediate", "remember")
    graph.add_edge("remember", END)
    return graph.compile(checkpointer=checkpointer or make_checkpointer())


def make_checkpointer() -> SqliteSaver:
    ensure_data_dir()
    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    return SqliteSaver(conn)


def prepare_run(
    pipeline: str,
    fault: str = "consumer_lag_spike",
    *,
    store: IncidentStore | None = None,
) -> IncidentStore:
    """Load env, bind scenario and memory for this process."""
    load_project_env()
    bind_scenario(build_scenario(pipeline, fault))
    incident_store = store or IncidentStore()
    bind_store(incident_store)
    return incident_store


def start_diagnosis(
    pipeline: str,
    fault: str = "consumer_lag_spike",
    *,
    thread_id: str | None = None,
) -> tuple[str, dict]:
    """Run until the approval interrupt. Returns (thread_id, interrupt payload or final state)."""
    prepare_run(pipeline, fault)
    graph = build_graph()
    tid = thread_id or new_thread_id()
    config = {"configurable": {"thread_id": tid}}
    result = graph.invoke({"pipeline": pipeline, "fault": fault}, config=config)
    return tid, _public_result(result, graph, config)


def resume_diagnosis(thread_id: str, decision: Decision) -> dict:
    """Resume a paused run with approve or reject."""
    load_project_env()
    store = IncidentStore()
    bind_store(store)
    graph = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise RuntimeError(f"No paused run found for thread {thread_id}.")
    pipeline = snapshot.values["pipeline"]
    fault = snapshot.values.get("fault", "consumer_lag_spike")
    bind_scenario(build_scenario(pipeline, fault))
    result = graph.invoke(Command(resume=decision), config=config)
    return _public_result(result, graph, config)


def triage(state: AgentState) -> AgentState:
    metrics = get_pipeline_metrics(state["pipeline"])
    past = lookup_incidents(state["pipeline"])
    memory_note = (
        f"Past incidents for this pipeline:\n{_dump(past)}"
        if past
        else "No past incidents in memory for this pipeline."
    )
    text = _ask(
        "You triage one data pipeline. Use only the metrics and past incidents below. "
        "Say whether it looks healthy or degraded, and whether logs, deploys, or both "
        "should be inspected next. If past incidents are relevant, say so briefly. "
        "Two or three sentences.",
        f"Metrics from get_pipeline_metrics:\n{_dump(metrics)}\n\n{memory_note}",
    )
    return {"metrics": metrics, "past_incidents": past, "triage": text}


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


def propose(state: AgentState) -> AgentState:
    action = _choose_action(state)
    return {"proposed_action": action}


def await_approval(state: AgentState) -> AgentState:
    proposal = state["proposed_action"]
    decision = interrupt(
        {
            "message": "Write action requires human approval.",
            "proposed_action": proposal,
            "diagnosis": state.get("diagnosis", ""),
        }
    )
    if decision not in ("approve", "reject"):
        raise ValueError(f"Decision must be 'approve' or 'reject', got {decision!r}.")
    return {"decision": decision}


def remediate(state: AgentState) -> AgentState:
    proposal = state["proposed_action"]
    action = proposal["action"]
    pipeline = state["pipeline"]
    if action == "restart_consumer":
        result = restart_consumer(pipeline)
    elif action == "scale_partitions":
        result = scale_partitions(pipeline)
    elif action == "open_ticket":
        result = open_ticket(pipeline, summary=proposal.get("reason", state["diagnosis"]))
    else:
        raise ValueError(f"Unknown remediation action {action!r}.")
    return {"remediation_result": result}


def remember(state: AgentState) -> AgentState:
    store = IncidentStore()
    decision = state.get("decision", "reject")
    if decision == "approve":
        result_text = json.dumps(state.get("remediation_result", {}))
    else:
        result_text = "not_run: human rejected the proposed write action"
    incident = store.save(
        pipeline=state["pipeline"],
        diagnosis=state.get("diagnosis", ""),
        action=state.get("proposed_action", {}).get("action", "none"),
        decision=decision,
        result=result_text,
    )
    return {"incident_id": incident.id}


def route_after_approval(state: AgentState) -> str:
    return "remediate" if state.get("decision") == "approve" else "remember"


def _choose_action(state: AgentState) -> dict[str, str]:
    diagnosis = (state.get("diagnosis") or "").lower()
    metrics = state.get("metrics") or {}
    lag = float(metrics.get("consumer_lag_seconds") or 0)
    if lag >= 60 or "lag" in diagnosis:
        return {
            "action": "restart_consumer",
            "pipeline": state["pipeline"],
            "reason": "Consumer lag spike; restart the consumer to drain backlog after the bad config.",
        }
    if "partition" in diagnosis:
        return {
            "action": "scale_partitions",
            "pipeline": state["pipeline"],
            "reason": "Partition pressure suspected; scale partitions.",
        }
    return {
        "action": "open_ticket",
        "pipeline": state["pipeline"],
        "reason": state.get("diagnosis", "Needs human follow-up."),
    }


def _public_result(result: object, graph, config: dict) -> dict:
    """Normalize invoke output: either a pause payload or the finished state."""
    if isinstance(result, dict) and "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return {
            "status": "paused",
            "thread_id": config["configurable"]["thread_id"],
            "interrupt": payload,
            "state": dict(graph.get_state(config).values),
        }
    if isinstance(result, dict) and result.get("decision"):
        return {
            "status": "completed",
            "thread_id": config["configurable"]["thread_id"],
            "state": result,
        }
    # Interrupt may also leave the graph waiting without __interrupt__ in some versions.
    snapshot = graph.get_state(config)
    if snapshot.next:
        interrupts = []
        for task in snapshot.tasks:
            interrupts.extend(getattr(task, "interrupts", []) or [])
        if interrupts:
            return {
                "status": "paused",
                "thread_id": config["configurable"]["thread_id"],
                "interrupt": interrupts[0].value,
                "state": dict(snapshot.values),
            }
    return {
        "status": "completed",
        "thread_id": config["configurable"]["thread_id"],
        "state": result if isinstance(result, dict) else dict(snapshot.values),
    }


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


# Keep a simple helper for Week 1-style one-shot runs without HITL in tests.
def run_diagnosis(pipeline: str, fault: str = "consumer_lag_spike") -> AgentState:
    """Compatibility wrapper: start then auto-approve. Prefer start/resume in the CLI."""
    tid, paused = start_diagnosis(pipeline, fault)
    if paused["status"] == "paused":
        finished = resume_diagnosis(tid, "approve")
        return finished["state"]  # type: ignore[return-value]
    return paused["state"]  # type: ignore[return-value]
