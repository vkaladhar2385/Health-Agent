"""MCP server exposing pipeline health tools for Claude Code / Cursor."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from pipeline_health_agent.data import PIPELINES, build_scenario
from pipeline_health_agent.memory import IncidentStore
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
    set_tool_step,
)

server = MCPServer(
    name="pipeline-health-agent",
    instructions=(
        "Read tools are free. Write tools (restart_consumer, scale_partitions, open_ticket) "
        "are simulated remediations. Prefer diagnosing with metrics, logs, and deploys first."
    ),
)


def _ensure_bound(pipeline: str) -> None:
    # MCP calls are stateless; bind a default lag-spike scenario for the named pipeline.
    set_tool_step("mcp")
    bind_scenario(build_scenario(pipeline if pipeline in PIPELINES else "egress"))
    bind_store(IncidentStore())


@server.tool(description="Return latest metrics for a mock pipeline (ingest|stream|egress).")
def tool_get_pipeline_metrics(pipeline: str) -> dict:
    _ensure_bound(pipeline)
    return get_pipeline_metrics(pipeline)


@server.tool(description="Search recent log lines for a mock pipeline.")
def tool_search_logs(pipeline: str, query: str = "", limit: int = 20) -> list[str]:
    _ensure_bound(pipeline)
    return search_logs(pipeline, query=query, limit=limit)


@server.tool(description="Return recent deploys for a mock pipeline.")
def tool_get_recent_deploys(pipeline: str, limit: int = 5) -> list[dict]:
    _ensure_bound(pipeline)
    return get_recent_deploys(pipeline, limit=limit)


@server.tool(description="Look up past incidents for a pipeline from SQLite memory.")
def tool_lookup_incidents(pipeline: str, limit: int = 5) -> list[dict]:
    _ensure_bound(pipeline)
    return lookup_incidents(pipeline, limit=limit)


@server.tool(description="WRITE: simulate restarting a consumer. Prefer human approval in the agent CLI.")
def tool_restart_consumer(pipeline: str) -> dict:
    _ensure_bound(pipeline)
    return restart_consumer(pipeline)


@server.tool(description="WRITE: simulate scaling partitions.")
def tool_scale_partitions(pipeline: str, partitions: int = 6) -> dict:
    _ensure_bound(pipeline)
    return scale_partitions(pipeline, partitions=partitions)


@server.tool(description="WRITE: simulate opening an incident ticket.")
def tool_open_ticket(pipeline: str, summary: str) -> dict:
    _ensure_bound(pipeline)
    return open_ticket(pipeline, summary=summary)


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
