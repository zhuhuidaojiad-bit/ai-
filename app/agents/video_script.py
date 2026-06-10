"""短视频脚本 Agent — 生成抖音/快手风格的短视频脚本."""

from app.models.llm import call_deepseek_with_stream
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个抖音/TikTok 短视频脚本创作专家。创作高互动率的短视频脚本。

生成完整脚本包含：
1. 视频类型（开箱/测评/教程/剧情/vlog/好物推荐）+ 目标人群 + 时长
2. 分镜表格：镜号|时长|画面|口播|字幕|BGM
3. 黄金前3秒 hook、中间卖点展示、结尾CTA
4. 运营建议：发布时间、标签(hashtags)、标题文案3个版本

要求：口播口语化有节奏感，分镜具体可执行，适应抖音/快手风格"""


async def run_video_script_agent(task: str, context: str = "", on_chunk=None) -> str:
    """Run the video script agent with streaming support."""
    logger.info(f"Video script agent: {task[:80]}...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"任务：{task}\n\n额外上下文：{context}" if context else f"任务：{task}"},
    ]

    return await call_deepseek_with_stream(messages, temperature=0.85, max_tokens=2500, on_chunk=on_chunk)


AGENT_META = {
    "name": "video_script",
    "icon": "🎬",
    "label": "视频脚本",
    "description": "生成抖音/快手风格的短视频拍摄脚本",
    "trigger_keywords": ["脚本", "视频脚本", "短视频", "拍摄", "抖音", "口播", "分镜"],
}
