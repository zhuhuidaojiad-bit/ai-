"""合规检测 Agent — 检查短视频脚本是否符合平台规则和广告法."""

from app.models.llm import call_deepseek_with_stream
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个短视频平台合规审查专家。你的任务是审查短视频脚本是否违反平台规则和法律法规。

审查维度：

## 🚨 红线违规（一票否决）
1. **虚假宣传**：夸大产品功效、伪造数据、虚假承诺
2. **违禁品类**：烟草、枪支、毒品、赌博、色情
3. **医疗误导**：宣称治疗功效（需药监局备案）
4. **金融欺诈**：虚假理财、非法集资、传销
5. **侵犯隐私**：未经许可使用他人肖像/声音/作品

## ⚠️ 高风险（需要修改）
1. **绝对化用语**："最好""第一""国家级""100%"
2. **贬低竞品**：直接或间接攻击其他品牌
3. **诱导分享**："转发到3个群免费领"
4. **敏感话题**：政治、宗教、地域歧视
5. **版权风险**：未经授权的BGM、字体、素材

## 📋 平台规则（各平台通用）
1. **广告标识**：商业推广需明确标注"广告"或"合作"
2. **特殊品类资质**：美妆/食品/保健品需提供相关证明
3. **价格表述**：不得使用"原价999现价99"若无真实成交记录
4. **赠品规则**：需明确赠品内容和获取方式
5. **未成年人保护**：不得诱导未成年人消费

## 📝 内容建议（非违规但可优化）
1. 标题是否夸大引起反感
2. 口播是否清晰易懂
3. 卖点是否有依据支撑
4. 评论区引导是否自然

输出格式：
## 🛡️ 合规审查报告

### 违规项
| 级别 | 问题 | 位置 | 法规依据 | 修改建议 |
|------|------|------|----------|----------|

### 风险提示
（潜在风险点）

### 修改后的合规版本
（如需修改，提供合规版本）

### 审查结论
✅ 合规 / ⚠️ 需修改（X处）/ 🚫 不予通过"""


async def run_compliance_check_agent(task: str, context: str = "", on_chunk=None) -> str:
    """
    Run the compliance check agent.
    Pass the script content as task, or a video URL/description to check.
    """
    logger.info(f"Compliance check agent: {task[:80]}...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请审查以下内容是否合规：\n\n{task}\n\n" + (f"额外信息：{context}" if context else "")},
    ]

    return await call_deepseek_with_stream(messages, temperature=0.3, max_tokens=2500, on_chunk=on_chunk)


AGENT_META = {
    "name": "compliance_check",
    "icon": "🛡️",
    "label": "合规检测",
    "description": "检查短视频脚本是否符合平台规则和广告法",
    "trigger_keywords": ["合规", "审查", "违规", "广告法", "规则", "过审", "检测", "审核", "红线", "能不能发"],
}
