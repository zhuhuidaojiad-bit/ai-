"""SQLite database initialization, demo data, and query tools."""

import aiosqlite
import os
import json
from datetime import datetime, timedelta
import random
from app.config import config
from app.utils.logger import logger

DB_PATH = config.DATABASE_PATH

# ── Demo data ─────────────────────────────────────────────────────────

DEMO_PRODUCTS = [
    ("p001", "无线蓝牙耳机 Pro", "电子产品", 299.00, "主动降噪，40小时续航，Hi-Fi音质", 1523),
    ("p002", "夏季纯棉T恤", "服装", 89.00, "100%新疆长绒棉，透气亲肤", 2341),
    ("p003", "便携充电宝 20000mAh", "电子产品", 129.00, "快充PD3.0，可上飞机", 987),
    ("p004", "智能手表 S3", "电子产品", 599.00, "血氧监测，运动模式，7天续航", 756),
    ("p005", "瑜伽垫加厚防滑", "运动户外", 69.00, "NBR材质，双面防滑", 1102),
    ("p006", "冻干咖啡粉礼盒", "食品", 149.00, "哥伦比亚产区，12颗装", 623),
    ("p007", "大容量双肩包", "箱包", 199.00, "防水面料，可放15.6寸笔记本", 445),
    ("p008", "桌面加湿器", "家居", 79.00, "静音大雾量，500ml容量", 1890),
]

DEMO_ORDERS = [
    ("o001", "p001", "无线蓝牙耳机 Pro", 2, 299.00, "completed", "2026-06-09 10:30:00"),
    ("o002", "p003", "便携充电宝 20000mAh", 1, 129.00, "completed", "2026-06-09 11:00:00"),
    ("o003", "p002", "夏季纯棉T恤", 3, 89.00, "completed", "2026-06-08 14:20:00"),
    ("o004", "p001", "无线蓝牙耳机 Pro", 1, 299.00, "pending", "2026-06-10 08:15:00"),
    ("o005", "p005", "瑜伽垫加厚防滑", 2, 69.00, "completed", "2026-06-07 16:45:00"),
    ("o006", "p006", "冻干咖啡粉礼盒", 1, 149.00, "shipped", "2026-06-09 09:30:00"),
    ("o007", "p004", "智能手表 S3", 1, 599.00, "completed", "2026-06-06 12:00:00"),
    ("o008", "p008", "桌面加湿器", 4, 79.00, "completed", "2026-06-08 20:10:00"),
    ("o009", "p002", "夏季纯棉T恤", 2, 89.00, "returned", "2026-06-05 15:30:00"),
    ("o010", "p007", "大容量双肩包", 1, 199.00, "completed", "2026-06-10 07:00:00"),
    ("o011", "p001", "无线蓝牙耳机 Pro", 1, 299.00, "pending", "2026-06-10 09:45:00"),
    ("o012", "p003", "便携充电宝 20000mAh", 3, 129.00, "shipped", "2026-06-09 13:20:00"),
]

DEMO_VIDEOS = [
    ("v001", "p001", 125000, 8900, 2300, 456, "2026-06-08 18:00:00", "蓝牙耳机沉浸式开箱 #数码"),
    ("v002", "p002", 45000, 3200, 890, 123, "2026-06-07 12:00:00", "百元T恤怎么选？3个技巧"),
    ("v003", "p004", 89000, 5600, 1500, 234, "2026-06-06 20:00:00", "智能手表一周使用体验"),
    ("v004", "p005", 67000, 4100, 1200, 189, "2026-06-05 10:00:00", "在家健身必备好物推荐"),
    ("v005", "p008", 210000, 15000, 5600, 890, "2026-06-09 08:00:00", "办公桌布置神器！加湿器测评"),
    ("v006", "p001", 34000, 2100, 450, 67, "2026-06-10 06:00:00", "降噪耳机对比评测"),
]


# ── Database initialization ───────────────────────────────────────────

async def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                price REAL,
                description TEXT,
                sales_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                product_id TEXT,
                product_name TEXT,
                quantity INTEGER,
                price REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS video_metrics (
                id TEXT PRIMARY KEY,
                product_id TEXT,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                publish_time TIMESTAMP,
                script TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_input TEXT,
                results TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()

    # Seed demo data if empty
    await _seed_if_empty()


async def _seed_if_empty() -> None:
    """Insert demo data if tables are empty."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM products")
        count = (await cursor.fetchone())[0]
        if count > 0:
            return

        await db.executemany(
            "INSERT INTO products (id, name, category, price, description, sales_count) VALUES (?,?,?,?,?,?)",
            DEMO_PRODUCTS,
        )
        await db.executemany(
            "INSERT INTO orders (id, product_id, product_name, quantity, price, status, created_at) VALUES (?,?,?,?,?,?,?)",
            DEMO_ORDERS,
        )
        await db.executemany(
            "INSERT INTO video_metrics (id, product_id, views, likes, shares, comments, publish_time, script) VALUES (?,?,?,?,?,?,?,?)",
            DEMO_VIDEOS,
        )
        await db.commit()
        logger.info("Demo data seeded successfully.")


# ── Query tools (called by agents) ────────────────────────────────────

async def query_sales(start_date: str = None, end_date: str = None) -> dict:
    """Query sales stats within a date range."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        where = "WHERE status != 'returned'"
        params = []
        if start_date:
            where += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            where += " AND created_at <= ?"
            params.append(end_date)

        cursor = await db.execute(
            f"SELECT COUNT(*) as total_orders, SUM(quantity * price) as total_revenue, "
            f"SUM(quantity) as total_quantity FROM orders {where}",
            params,
        )
        row = await cursor.fetchone()

        # Top products
        cursor = await db.execute(
            f"SELECT product_name, SUM(quantity) as qty, SUM(quantity * price) as rev "
            f"FROM orders {where} GROUP BY product_name ORDER BY rev DESC LIMIT 10",
            params,
        )
        top_products = [
            {"product_name": r["product_name"], "quantity": r["qty"], "revenue": round(r["rev"], 2)}
            async for r in cursor
        ]

        return {
            "total_orders": row["total_orders"],
            "total_revenue": round(row["total_revenue"] or 0, 2),
            "total_quantity": row["total_quantity"] or 0,
            "top_products": top_products,
            "period": {"start": start_date or "all", "end": end_date or "now"},
        }


async def get_top_products(limit: int = 5) -> list[dict]:
    """Get top-selling products."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, category, price, sales_count, description FROM products "
            "ORDER BY sales_count DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def query_orders(filters: dict = None) -> list[dict]:
    """Query orders with optional filters. filters: {status, product_name, days}"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conditions = []
        params = []

        if filters:
            if "status" in filters:
                conditions.append("status = ?")
                params.append(filters["status"])
            if "product_name" in filters:
                conditions.append("product_name LIKE ?")
                params.append(f"%{filters['product_name']}%")
            if "days" in filters:
                cutoff = (datetime.now() - timedelta(days=filters["days"])).strftime("%Y-%m-%d")
                conditions.append("created_at >= ?")
                params.append(cutoff)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        cursor = await db.execute(
            f"SELECT * FROM orders {where} ORDER BY created_at DESC LIMIT 50", params
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_order_detail(order_id: str) -> "dict | None":
    """Get a single order by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_video_stats(video_id: str = None, product_id: str = None) -> list[dict]:
    """Get video metrics. Filter by video_id or product_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if video_id:
            cursor = await db.execute("SELECT * FROM video_metrics WHERE id = ?", (video_id,))
        elif product_id:
            cursor = await db.execute("SELECT * FROM video_metrics WHERE product_id = ?", (product_id,))
        else:
            cursor = await db.execute("SELECT * FROM video_metrics ORDER BY publish_time DESC")
        return [dict(r) for r in await cursor.fetchall()]


async def analyze_trends() -> dict:
    """Analyze video performance trends."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT product_id, SUM(views) as total_views, SUM(likes) as total_likes, "
            "SUM(shares) as total_shares, SUM(comments) as total_comments, "
            "COUNT(*) as video_count "
            "FROM video_metrics GROUP BY product_id ORDER BY total_views DESC"
        )
        products = []
        async for r in cursor:
            engagement = (r["total_likes"] + r["total_shares"] + r["total_comments"]) / max(r["total_views"], 1)
            products.append({
                "product_id": r["product_id"],
                "total_views": r["total_views"],
                "total_likes": r["total_likes"],
                "total_shares": r["total_shares"],
                "total_comments": r["total_comments"],
                "video_count": r["video_count"],
                "engagement_rate": round(engagement * 100, 2),
            })

        # Best performing video
        cursor = await db.execute(
            "SELECT id, product_id, views, likes, shares, comments, script, publish_time "
            "FROM video_metrics ORDER BY (likes + shares * 2 + comments * 3) DESC LIMIT 1"
        )
        best = await cursor.fetchone()

        return {
            "product_breakdown": products,
            "best_performing_video": dict(best) if best else None,
        }


async def save_session(session_id: str, user_input: str, results: dict) -> None:
    """Save a session to the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO sessions (id, user_input, results, created_at) VALUES (?, ?, ?, ?)",
            (session_id, user_input, json.dumps(results, ensure_ascii=False), datetime.now().isoformat()),
        )
        await db.commit()


async def get_sessions() -> list[dict]:
    """Get all session history."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, user_input, created_at FROM sessions ORDER BY created_at DESC LIMIT 20")
        return [dict(r) for r in await cursor.fetchall()]


async def get_session(session_id: str) -> "dict | None":
    """Get a single session by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            d["results"] = json.loads(d["results"]) if isinstance(d["results"], str) else d["results"]
            return d
        return None
