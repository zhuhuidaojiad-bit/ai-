"""短视频分析 Agent — 视频数据分析、优化建议."""

from app.models.llm import call_deepseek_with_stream
from app.tools.database import get_video_stats, analyze_trends
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个短视频运营分析师。分析短视频数据并提供优化建议。

给出：数据总结、内容优化建议、发布策略建议、明确的下一步行动
要求：基于真实数据用数字说话，建议具体可执行"""


async def run_video_analysis_agent(task: str, context: str = "", on_chunk=None) -> str:
    """Run the video analysis agent with streaming support."""
    logger.info(f"Video analysis agent: {task[:80]}...")

    videos = await get_video_stats()
    trends = await analyze_trends()

    videos_text = "\n".join(
        f"- [{v['product_id']}] 播放{v['views']:,} | 赞{v['likes']:,} | "
        f"分享{v['shares']:,} | 评论{v['comments']:,} | {v['script'][:30]}... | {v['publish_time']}"
        for v in videos
    )

    best = trends.get("best_performing_video", {})
    best_text = f"最佳视频: {best.get('script', 'N/A')[:50]}... | 播放{best.get('views',0):,}"

    trends_text = "\n".join(
        f"- {t['product_id']}: 总播放{t['total_views']:,}, 互动率{t['engagement_rate']}%, {t['video_count']}个视频"
        for t in trends.get("product_breakdown", [])
    )

    data_context = f"""
视频数据:
{videos_text}

趋势分析:
{trends_text}

{best_text}
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"任务：{task}\n\n{data_context}\n\n请分析视频表现并给出优化建议。"},
    ]

    return await call_deepseek_with_stream(messages, temperature=0.5, max_tokens=1500, on_chunk=on_chunk)


AGENT_META = {
    "name": "video_analysis",
    "icon": "📈",
    "label": "视频分析",
    "description": "分析短视频数据表现，给出优化建议",
    "trigger_keywords": ["视频分析", "视频数据", "播放量", "互动率", "优化", "标签策略"],
}
