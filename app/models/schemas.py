"""Pydantic data models for the orchestrator state and API."""

from typing import Optional, Annotated
from typing_extensions import TypedDict  # 3.9 compat
from langgraph.graph.message import add_messages


class AgentResult(TypedDict, total=False):
    agent_name: str
    status: str          # "pending" | "running" | "completed" | "failed"
    content: str
    error: Optional[str]


class IntentResult(TypedDict):
    agents: dict[str, str]   # {"agent_name": "specific task description", ...}
    summary: str             # brief summary of what the user wants


class OrchestratorState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_input: str
    intent: IntentResult
    agent_results: dict[str, AgentResult]
    final_response: str


# ── Pydantic models for API ──────────────────────────────────────────

from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    user_input: str = Field(..., description="用户输入的指令", min_length=1)
    session_id: Optional[str] = Field(None, description="会话 ID (可选, 用于续接对话)")
    reference_urls: Optional[list[str]] = Field(None, description="参考图片 URL 列表")
    video_url: Optional[str] = Field(None, description="视频 URL")


class ChatResponse(BaseModel):
    session_id: str
    message: str


class SessionListItem(BaseModel):
    session_id: str
    user_input: str
    created_at: str


class SessionDetail(BaseModel):
    session_id: str
    user_input: str
    agent_results: dict
    created_at: str
