"""爆款拆解 Agent — 分析爆款视频结构，生成同类合规原创脚本."""

from app.models.llm import call_deepseek_with_stream
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个抖音/TikTok 爆款视频拆解专家。你的任务是：

1. **拆解爆款视频**：分析其成功要素
   - 选题角度和切入方式
   - 前3秒 hook 技巧（悬念/痛点/反转/数字）
   - 内容结构（总分总/问题解决/对比测评/剧情反转）
   - 节奏把控（镜头切换频率、语速、情绪曲线）
   - 互动设计（评论区引导、点赞动机、转发理由）
   - BGM 和音效的使用规律

2. **生成同类合规原创脚本**：
   - 借鉴爆款的「公式」而非「内容」
   - 完全原创的产品和场景
   - 保持相同的情绪节奏和结构骨架
   - 严格遵守平台规则（不得虚假宣传、不得抄袭）

⚠️ 合规红线：
- 禁止直接复制原视频文案
- 禁止虚假功效宣传（如"7天美白"需有资质证明）
- 禁止使用绝对化用语（"最好""第一""100%"需谨慎）
- 禁止贬低竞品
- 需标注广告（如涉及商业推广）

输出格式：
## 📊 爆款拆解分析
- 视频类型：
- 核心公式：
- Hook 技巧：
- 结构骨架：
- 情绪曲线：
- 可复用要素：

## 🎬 同类原创脚本
（完整的原创脚本，包含分镜、口播、字幕、BGM、标签建议）"""


async def run_video_breakdown_agent(task: str, context: str = "", on_chunk=None) -> str:
    """Run the video breakdown agent — analyze viral video and generate similar script."""
    logger.info(f"Video breakdown agent: {task[:80]}...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"任务：{task}\n\n额外上下文：{context}" if context else f"任务：{task}"},
    ]

    return await call_deepseek_with_stream(messages, temperature=0.8, max_tokens=3000, on_chunk=on_chunk)


AGENT_META = {
    "name": "video_breakdown",
    "icon": "🔍",
    "label": "爆款拆解",
    "description": "分析爆款视频结构公式，生成同类合规原创脚本",
    "trigger_keywords": ["爆款", "拆解", "模仿", "同类", "参考", "借鉴", "热门视频", "对标"],
}
