"""Orchestrator Agent — Supervisor that parses intent and dispatches to specialized agents."""

import json
from app.models.llm import call_deepseek, call_deepseek_json
from app.utils.logger import logger

# Collect all agent meta for the orchestrator prompt
from app.agents.copywriting import AGENT_META as COPYWRITING_META
from app.agents.cover_image import AGENT_META as COVER_IMAGE_META
from app.agents.data_analysis import AGENT_META as DATA_ANALYSIS_META
from app.agents.orders import AGENT_META as ORDERS_META
from app.agents.video_script import AGENT_META as VIDEO_SCRIPT_META
from app.agents.video_analysis import AGENT_META as VIDEO_ANALYSIS_META
from app.agents.video_breakdown import AGENT_META as VIDEO_BREAKDOWN_META
from app.agents.compliance_check import AGENT_META as COMPLIANCE_CHECK_META
from app.agents.video_review import AGENT_META as VIDEO_REVIEW_META
ALL_AGENTS = [
    COPYWRITING_META,
    COVER_IMAGE_META,
    DATA_ANALYSIS_META,
    ORDERS_META,
    VIDEO_SCRIPT_META,
    VIDEO_ANALYSIS_META,
    VIDEO_BREAKDOWN_META,
    COMPLIANCE_CHECK_META,
    VIDEO_REVIEW_META,
]

AGENTS_DESC = "\n".join(
    f"- **{a['name']}** ({a['icon']} {a['label']}): {a['description']} "
    f"[触发词: {', '.join(a['trigger_keywords'])}]"
    for a in ALL_AGENTS
)

ORCHESTRATOR_SYSTEM_PROMPT = f"""你是一个电商运营 Agent 调度器 (Supervisor)。用户会用自然语言描述他们的需求。

你的工作是：
1. **理解用户意图**：用户在说什么？想达成什么目标？
2. **确定需要的 Agent**：根据意图，确定需要调用哪些专业 Agent
3. **为每个 Agent 生成任务**：将用户的笼统需求拆解成每个 Agent 能执行的具体任务

可用的 Agent:
{AGENTS_DESC}

你需要输出严格的 JSON 格式：
{{
  "summary": "用一句话概括用户需求",
  "agents": {{
    "agent_name": "为该 agent 生成的具体任务描述"
  }}
}}

规则：
- 如果用户提到"爆款"，需要 data_analysis + 相关的生成 agent
- 如果用户提到"短视频"或"抖音"，需要 video_script + video_analysis
- 如果用户提到"封面"或"主图"或"图片"，需要 cover_image
- 如果用户提到"文案"或"描述"或"广告"，需要 copywriting
- 如果用户提到"订单"或"发货"或"退货"，需要 orders
- 如果用户要求生成/创作型任务，需要调用对应的生成 agent
- 如果用户说"分析"，需要 data_analysis 或 video_analysis
- 允许同时调用多个 agent（1-8个都可以）
- 如果用户需求模糊，倾向于多调用几个相关 agent
- 每个 agent 的任务描述要具体明确，包含关键参数（如时间范围、产品名称等）"""


async def parse_intent(user_input: str) -> dict:
    """
    Parse the user's natural language input to determine intent and required agents.

    Returns: {"summary": "...", "agents": {"agent_name": "task", ...}}
    """
    logger.info(f"Parsing intent: {user_input[:100]}...")

    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": f"用户说：{user_input}\n\n请解析意图并返回 JSON。"},
    ]

    result = await call_deepseek_json(messages, temperature=0.3, max_tokens=1024)

    if "error" in result:
        logger.error(f"Intent parsing failed: {result}")
        # Fallback: try to match keywords manually
        return _fallback_intent(user_input)

    # Validate
    if "agents" not in result:
        result["agents"] = {}

    valid_agents = [a["name"] for a in ALL_AGENTS]
    result["agents"] = {
        k: v for k, v in result["agents"].items()
        if k in valid_agents
    }

    # Ensure at least one agent
    if not result["agents"]:
        logger.warning("No agents matched, using fallback")
        return _fallback_intent(user_input)

    logger.info(f"Intent parsed: summary='{result.get('summary', '')}', agents={list(result['agents'].keys())}")
    return result


def _fallback_intent(user_input: str) -> dict:
    """Keyword-based fallback when JSON parsing fails."""
    keyword_map = {}
    for agent in ALL_AGENTS:
        for kw in agent["trigger_keywords"]:
            keyword_map[kw] = agent["name"]

    matched_agents = set()
    for kw, agent_name in keyword_map.items():
        if kw in user_input:
            matched_agents.add(agent_name)

    if not matched_agents:
        # Default: data + orders (most common query)
        matched_agents = {"data_analysis", "orders"}

    return {
        "summary": "用户查询（自动识别）",
        "agents": {name: f"根据用户需求'{user_input[:50]}'执行{name}任务" for name in matched_agents},
    }
