"""LangGraph state schema for the orchestrator workflow."""

from typing import Annotated, Optional
from typing_extensions import TypedDict  # 3.9 compat
from langgraph.graph.message import add_messages


class AgentResult(TypedDict, total=False):
    agent_name: str
    status: str          # "pending" | "running" | "completed" | "failed"
    content: str
    error: Optional[str]


class IntentResult(TypedDict):
    agents: dict[str, str]   # {"agent_name": "task description", ...}
    summary: str


class OrchestratorState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_input: str
    session_id: str
    intent: dict              # IntentResult
    agent_results: dict[str, dict]   # str -> AgentResult
    final_response: str
    reference_urls: list[str]  # uploaded reference image URLs
    video_url: str              # uploaded video URL
