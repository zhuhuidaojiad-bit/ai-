"""文案 Agent — 生成电商文案、产品描述、广告语."""

from app.models.llm import call_deepseek_with_stream
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个顶级电商文案专家。根据用户需求生成高质量的电商文案。

可以生成：产品标题、产品描述、广告语、详情页文案、营销话术

要求：
1. 文案有感染力，突出产品核心卖点
2. 根据目标人群调整语气和风格
3. 包含适当的表情符号（适合社交媒体）
4. 给出多个版本供选择（2-3个变体）
5. 从数据库查询相关产品信息来丰富内容"""


async def run_copywriting_agent(task: str, context: str = "", on_chunk=None) -> str:
    """Run the copywriting agent with streaming support."""
    logger.info(f"Copywriting agent: {task[:80]}...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"任务：{task}\n\n额外上下文：{context}" if context else f"任务：{task}"},
    ]

    return await call_deepseek_with_stream(messages, temperature=0.8, max_tokens=2048, on_chunk=on_chunk)


AGENT_META = {
    "name": "copywriting",
    "icon": "📝",
    "label": "文案生成",
    "description": "生成产品标题、描述、广告语等电商文案",
    "trigger_keywords": ["文案", "描述", "标题", "广告语", "话术", "详情页", "卖点"],
}
