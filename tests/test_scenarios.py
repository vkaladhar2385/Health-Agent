"""Cheap offline checks for the Week 3 eval pack."""

from pipeline_health_agent.data import FAULTS, PIPELINES, build_scenario
from pipeline_health_agent.evals.scenarios import SCENARIOS, all_scenarios


def test_there_are_exactly_25_scenarios() -> None:
    assert len(all_scenarios()) == 25
    assert len({s["id"] for s in SCENARIOS}) == 25


def test_scenarios_use_known_pipelines_and_faults() -> None:
    for scenario in SCENARIOS:
        assert scenario["pipeline"] in PIPELINES
        assert scenario["fault"] in FAULTS
        build_scenario(scenario["pipeline"], scenario["fault"])


def test_negative_and_ambiguous_cases_exist() -> None:
    actions = {s["expected_action"] for s in SCENARIOS}
    assert "none" in actions
    assert "escalate" in actions
    assert "restart_consumer" in actions
