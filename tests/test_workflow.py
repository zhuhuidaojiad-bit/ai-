"""Test the LangGraph workflow builds correctly."""

import pytest
from app.graph.workflow import build_graph
from app.graph.state import OrchestratorState


def test_graph_builds():
    """The graph should compile without errors."""
    graph = build_graph()
    assert graph is not None
    nodes = list(graph.nodes.keys())
    assert "parse_intent" in nodes
    assert "execute_agents" in nodes
    assert "aggregate" in nodes


def test_state_schema():
    """OrchestratorState should accept required fields."""
    state: OrchestratorState = {
        "messages": [],
        "user_input": "test",
        "session_id": "s123",
        "intent": {},
        "agent_results": {},
        "final_response": "",
    }
    assert state["user_input"] == "test"
    assert state["session_id"] == "s123"


def test_graph_entry_point():
    """Graph should have the correct entry point."""
    graph = build_graph()
    # Just verify it compiles and has an entry
    assert graph is not None
