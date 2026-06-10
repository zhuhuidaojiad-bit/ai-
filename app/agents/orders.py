"""订单 Agent — 订单查询、管理、统计分析."""

from app.models.llm import call_deepseek_with_stream
from app.tools.database import query_orders
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个电商订单管理专家。帮助用户查询和管理订单。

要求：
1. 清晰展示订单信息
2. 对异常情况给出提醒
3. 按重要性排序
4. 语言简洁"""


async def run_orders_agent(task: str, context: str = "", on_chunk=None) -> str:
    """Run the orders agent with streaming support."""
    logger.info(f"Orders agent: {task[:80]}...")

    filters = {}
    if "待" in task or "pending" in task.lower():
        filters["status"] = "pending"
    elif "已完成" in task or "completed" in task.lower():
        filters["status"] = "completed"
    elif "已发货" in task or "shipped" in task.lower():
        filters["status"] = "shipped"
    elif "退货" in task or "退款" in task or "returned" in task.lower():
        filters["status"] = "returned"

    days = 7
    if "30天" in task or "一个月" in task:
        days = 30
    if "今天" in task:
        days = 1
    filters["days"] = days

    orders = await query_orders(filters)

    if not orders:
        return f"📦 没有找到符合条件的订单（最近{days}天）"

    orders_text = "\n".join(
        f"- [{o['status']}] {o['product_name']} x{o['quantity']} ¥{o['price']} "
        f"(订单号:{o['id']}, 时间:{o['created_at']})"
        for o in orders[:20]
    )

    status_counts = {}
    for o in orders:
        status_counts[o["status"]] = status_counts.get(o["status"], 0) + 1
    stats = "\n".join(f"- {s}: {c}单" for s, c in status_counts.items())

    data_context = f"""
订单数据 (最近{days}天，共{len(orders)}单):
状态分布:
{stats}

订单列表:
{orders_text}
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"任务：{task}\n\n{data_context}\n\n请分析订单情况。"},
    ]

    return await call_deepseek_with_stream(messages, temperature=0.5, max_tokens=1200, on_chunk=on_chunk)


AGENT_META = {
    "name": "orders",
    "icon": "📦",
    "label": "订单查询",
    "description": "查询和管理订单状态、统计、异常预警",
    "trigger_keywords": ["订单", "购买", "付款", "发货", "退货", "退款", "物流"],
}
