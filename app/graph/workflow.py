"""LangGraph workflow — streaming parallel agent execution with SSE."""

import asyncio
from typing import Any

from langgraph.graph import StateGraph, END

from app.graph.state import OrchestratorState
from app.agents.orchestrator import parse_intent
from app.utils.logger import logger
from app.utils.streaming import sse_manager as global_sse

# Agent runners
from app.agents.copywriting import run_copywriting_agent
from app.agents.cover_image import run_cover_image_agent
from app.agents.data_analysis import run_data_analysis_agent
from app.agents.orders import run_orders_agent
from app.agents.video_script import run_video_script_agent
from app.agents.video_analysis import run_video_analysis_agent
from app.agents.video_breakdown import run_video_breakdown_agent
from app.agents.compliance_check import run_compliance_check_agent
from app.agents.video_review import run_video_review_agent
AGENT_RUNNERS = {
    "copywriting": run_copywriting_agent,
    "cover_image": run_cover_image_agent,
    "data_analysis": run_data_analysis_agent,
    "orders": run_orders_agent,
    "video_script": run_video_script_agent,
    "video_analysis": run_video_analysis_agent,
    "video_breakdown": run_video_breakdown_agent,
    "compliance_check": run_compliance_check_agent,
    "video_review": run_video_review_agent,
}


# ── Graph nodes ──────────────────────────────────────────────────────

async def parse_intent_node(state: OrchestratorState) -> dict:
    """Node: Parse user intent to determine which agents to invoke."""
    user_input = state["user_input"]
    intent = await parse_intent(user_input)
    return {"intent": intent}


async def execute_agents_node(state: OrchestratorState) -> dict:
    """Node: Execute all required agents in parallel with streaming SSE output."""
    intent = state.get("intent", {})
    agents_to_call: dict[str, str] = intent.get("agents", {})
    session_id = state.get("session_id", "")
    user_input = state.get("user_input", "")
    sse = global_sse  # use global singleton — state strips extra keys

    if not agents_to_call:
        logger.warning("No agents to execute")
        return {"agent_results": {}}

    logger.info(f"Executing {len(agents_to_call)} agents in parallel: {list(agents_to_call.keys())}")

    async def run_single_agent(agent_name: str, task: str) -> tuple[str, dict]:
        """Run a single agent with streaming SSE emission."""
        runner = AGENT_RUNNERS.get(agent_name)
        if not runner:
            return agent_name, {
                "agent_name": agent_name,
                "status": "failed",
                "content": f"Agent '{agent_name}' not found",
                "error": f"Unknown agent: {agent_name}",
            }

        # Emit start
        await sse.emit(session_id, "agent_start", {"agent": agent_name})

        # Create streaming callback for this agent
        async def on_chunk(chunk_text: str):
            await sse.emit(session_id, "agent_chunk", {
                "agent": agent_name,
                "chunk": chunk_text,
            })

        # Pass extra kwargs to agents that need them
        extra_kwargs = {}
        if agent_name == "cover_image":
            extra_kwargs["reference_urls"] = state.get("reference_urls", [])
        if agent_name == "video_review":
            extra_kwargs["video_url"] = state.get("video_url", "")
        try:
            result = await runner(task, context=user_input, on_chunk=on_chunk, **extra_kwargs)
            await sse.emit(session_id, "agent_complete", {
                "agent": agent_name,
                "result": result,
            })
            return agent_name, {
                "agent_name": agent_name,
                "status": "completed",
                "content": result,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Agent {agent_name} failed: {e}")
            await sse.emit(session_id, "agent_error", {
                "agent": agent_name,
                "error": str(e),
            })
            return agent_name, {
                "agent_name": agent_name,
                "status": "failed",
                "content": "",
                "error": str(e),
            }

    # Run all agents in parallel
    tasks = [run_single_agent(name, task) for name, task in agents_to_call.items()]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect results
    agent_results = {}
    for item in results_list:
        if isinstance(item, Exception):
            logger.error(f"Agent execution exception: {item}")
            continue
        agent_name, result = item
        agent_results[agent_name] = result

    return {"agent_results": agent_results}


async def aggregate_node(state: OrchestratorState) -> dict:
    """Node: Aggregate results — just emit summary via SSE, no extra LLM call."""
    agent_results = state.get("agent_results", {})
    user_input = state.get("user_input", "")
    session_id = state.get("session_id", "")
    sse = global_sse  # use global singleton — state strips extra keys

    if not agent_results:
        return {"final_response": "没有 Agent 被触发。"}

    # Build a simple summary without extra LLM call
    completed = sum(1 for r in agent_results.values() if r.get("status") == "completed")
    failed = sum(1 for r in agent_results.values() if r.get("status") == "failed")
    agent_names = ", ".join(agent_results.keys())

    summary = f"✅ 已完成 {completed} 个 Agent（{agent_names}）"
    if failed:
        summary += f"\n⚠️ {failed} 个 Agent 执行失败"

    # Emit aggregate event
    await sse.emit(session_id, "aggregate_complete", {
            "summary": summary,
            "results": {name: r for name, r in agent_results.items()},
        })

    return {"final_response": summary}


# ── Build the graph ──────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and compile the orchestrator StateGraph."""
    workflow = StateGraph(OrchestratorState)

    workflow.add_node("parse_intent", parse_intent_node)
    workflow.add_node("execute_agents", execute_agents_node)
    workflow.add_node("aggregate", aggregate_node)

    workflow.set_entry_point("parse_intent")
    workflow.add_edge("parse_intent", "execute_agents")
    workflow.add_edge("execute_agents", "aggregate")
    workflow.add_edge("aggregate", END)

    return workflow.compile()


# ── Top-level runner ─────────────────────────────────────────────────

async def run_orchestrator(
    session_id: str,
    user_input: str,
    reference_urls=None,  # Optional[list[str]]
    video_url=None,       # Optional[str]
    _sse: Any = None,  # deprecated — uses global singleton now
) -> dict:
    """Run the full orchestrator workflow for a user input."""
    graph = build_graph()

    initial_state: OrchestratorState = {
        "messages": [],
        "user_input": user_input,
        "session_id": session_id,
        "intent": {},
        "agent_results": {},
        "final_response": "",
        "reference_urls": reference_urls or [],
        "video_url": video_url or "",
    }

    logger.info(f"Running orchestrator for session {session_id}")
    final_state = await graph.ainvoke(initial_state)

    return {
        "agent_results": final_state.get("agent_results", {}),
        "final_response": final_state.get("final_response", ""),
    }
