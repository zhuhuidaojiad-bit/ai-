"""数据 Agent — 销售数据分析、趋势识别、爆款发现."""

from datetime import datetime, timedelta

from app.models.llm import call_deepseek_with_stream
from app.tools.database import query_sales, get_top_products
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个电商数据分析师。分析销售数据并提供 actionable 的洞察。

要求：
1. 用数据说话，给出具体数字
2. 提供可执行的建议
3. 用清晰的结构呈现（分点、对比）
4. 标注需要重点关注的数据
5. 语言简洁专业但易懂"""


async def run_data_analysis_agent(task: str, context: str = "", on_chunk=None) -> str:
    """Run the data analysis agent with streaming support."""
    logger.info(f"Data analysis agent: {task[:80]}...")

    # Determine date range
    days = 7
    if "30天" in task or "一个月" in task or "本月" in task:
        days = 30
    elif "90天" in task or "三个月" in task or "季度" in task:
        days = 90
    elif "今天" in task or "今日" in task:
        days = 1

    end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")

    sales_data = await query_sales(start_date, end_date)
    top_products = await get_top_products(5)

    data_context = f"""
销售数据 (最近{days}天):
- 总订单数: {sales_data['total_orders']}
- 总营收: ¥{sales_data['total_revenue']:,.2f}
- 总销量: {sales_data['total_quantity']}件

爆款产品 Top 5:
{chr(10).join(f'- [{p["category"]}] {p["name"]}: ¥{p["price"]}, 销量{p["sales_count"]}' for p in top_products)}

热门产品销售明细:
{chr(10).join(f'- {p["product_name"]}: {p["quantity"]}件, ¥{p["revenue"]:,.2f}' for p in sales_data['top_products'][:5])}
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"任务：{task}\n\n数据：\n{data_context}\n\n请分析并给出报告和建议。"},
    ]

    return await call_deepseek_with_stream(messages, temperature=0.5, max_tokens=1500, on_chunk=on_chunk)


AGENT_META = {
    "name": "data_analysis",
    "icon": "📊",
    "label": "数据分析",
    "description": "分析销售数据、趋势、爆款识别、生成报表",
    "trigger_keywords": ["数据", "分析", "趋势", "报表", "统计", "销量", "爆款", "运营", "周报"],
}
