"""视频审阅 Agent — 提取视频帧，用 Claude 视觉分析 + DeepSeek 合规网感审查."""

import os
import base64
import asyncio
from app.utils.logger import logger

SYSTEM_PROMPT = """你是一个抖音/快手/TikTok 短视频审阅专家。根据视觉AI对视频帧的分析，从「合规」和「网感」两个维度审查。

## 审查框架

### 合规审查（广告法 + 平台规则）
1. 虚假宣传：夸大功效、伪造数据、虚假承诺
2. 绝对化用语：「最好」「第一」「国家级」「100%」「全网」
3. 贬低竞品：直接或间接攻击其他品牌
4. 诱导互动：「转发抽奖」「评论领福利」「双击屏幕」
5. 敏感内容：政治、色情、暴力、违规医疗宣称
6. 广告标识：商业推广是否标注「广告」或「合作」

### 网感审查（传播力 + 用户心理）
1. 前3秒 Hook：是否有吸引力？
2. 节奏把控：信息密度是否合适？
3. 情绪曲线：能否引发共鸣？
4. 人设匹配：语言风格是否符合账号定位？
5. 互动设计：是否自然引导互动？
6. 话题势能：是否具备传播基因？
7. 完播率设计：结尾是否有钩子？

### 修改建议
- 🎯 问题定位（帧位置/时间点）
- 💡 修改方案（具体改写）
- 📈 预期效果

## 输出格式
## 🔍 视频审阅报告

### 📊 综合评分
| 维度 | 得分(1-10) | 评价 |
|------|-----------|------|
| 合规度 | X | ... |
| 完播潜力 | X | ... |
| 互动潜力 | X | ... |
| 转化潜力 | X | ... |
| 传播潜力 | X | ... |

### 🚨 合规风险
| 级别 | 问题 | 帧位置 | 法规依据 | 修改建议 |
|------|------|--------|----------|----------|

### 🎯 网感优化
| 问题 | 优化建议 | 改写示例 | 预期提升 |
|------|----------|----------|----------|

### ✅ 过审结论
🟢 可直接发布 / 🟡 修改后可发 / 🔴 不建议发布"""


def extract_video_frames(video_path: str, num_frames: int = 6) -> tuple[dict, list[bytes]]:
    """Extract metadata and evenly-spaced frames from a video file."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open video"}, []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0

    metadata = {
        "duration": round(duration, 1),
        "fps": round(fps, 1),
        "resolution": f"{width}x{height}",
        "total_frames": total_frames,
    }

    frames = []
    positions = [int(total_frames * p) for p in [0.10, 0.28, 0.46, 0.64, 0.82, 0.95]]
    for i, pos in enumerate(positions):
        if pos >= total_frames:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            if max(w, h) > 1024:
                scale = 1024 / max(w, h)
                frame = cv2.resize(frame, (int(w*scale), int(h*scale)))
            _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            frames.append((i, pos, jpg.tobytes()))

    cap.release()
    return metadata, frames


async def analyze_frames_claude(frames: list, task: str) -> str:
    """Send video frames to Claude Vision for content analysis."""
    import httpx
    from app.config import config

    frame_contents = []
    for idx, pos, frame_bytes in frames:
        frame_contents.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(frame_bytes).decode(),
            }
        })

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": (
                f"These are {len(frames)} frames from a short video (douyin/TikTok/Reels format). "
                f"Analyze each frame carefully:\n"
                f"1. Read ALL visible text, captions, subtitles, product names, prices\n"
                f"2. Describe the scene: product, person, background, colors, lighting\n"
                f"3. Identify any compliance issues: banned words (最好/第一/100%/国家级/全网最低), "
                f"fake claims, induced sharing, competitor attacks\n"
                f"4. Assess the video quality: professional look, hook strength, visual appeal\n"
                f"5. Note the overall vibe: 网感 (internet-savvy), trendy or outdated\n\n"
                f"User context: {task}\n\n"
                f"Be specific about which frame has which issue. Return detailed analysis."
            )},
            *frame_contents
        ]
    }]

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                "https://api.apidot.ai/v1/messages",
                headers={
                    "Authorization": f"Bearer {config.IMAGE_API_KEY}",
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1500,
                    "messages": messages,
                },
            )
            data = resp.json()
            if data.get("code") == 200:
                content = data["data"]["content"]
                return content[0]["text"] if content else ""
            else:
                logger.error(f"Claude vision error: {resp.status_code} {str(data)[:300]}")
                return f"[视觉分析失败: {data.get('error', {}).get('message', str(data))}]"
    except Exception as e:
        logger.error(f"Claude vision call failed: {e}")
        return f"[视觉分析失败: {e}]"


async def run_video_review_agent(task: str, context: str = "", on_chunk=None, video_url="", **kwargs) -> str:
    """Review a video: extract frames → Claude vision analysis → DeepSeek compliance review."""
    logger.info(f"Video review: {task[:100]}..., video={video_url}")

    has_video = bool(video_url)
    vision_analysis = ""

    if on_chunk:
        await on_chunk("🔎 正在审阅视频...\n")

    if has_video:
        # Resolve video path
        if video_url.startswith("/api/media/"):
            filename = video_url.split("/")[-1]
            upload_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "data", "uploads"
            )
            video_path = os.path.join(upload_dir, filename)
        else:
            video_path = video_url

        if not os.path.exists(video_path):
            if on_chunk:
                await on_chunk("⚠️ 视频文件未找到。\n\n")
        else:
            # Extract frames
            if on_chunk:
                await on_chunk("📹 正在提取视频关键帧...\n")

            metadata, frames = await asyncio.get_event_loop().run_in_executor(
                None, extract_video_frames, video_path, 6
            )

            if "error" in metadata:
                if on_chunk:
                    await on_chunk(f"⚠️ 视频读取失败: {metadata['error']}\n\n")
            elif frames:
                if on_chunk:
                    await on_chunk(
                        f"✅ 视频读取成功: {metadata['duration']}秒, {metadata['resolution']}\n"
                        f"🖼️ 已提取 {len(frames)} 帧，正在用 Claude 视觉 AI 分析视频内容...\n\n"
                    )

                vision_analysis = await analyze_frames_claude(frames, task)

                if on_chunk and vision_analysis:
                    await on_chunk(f"📋 **视觉 AI 分析结果:**\n{vision_analysis}\n\n")
            else:
                if on_chunk:
                    await on_chunk("⚠️ 未能提取有效帧。\n\n")

    # Step 2: DeepSeek compliance + 网感 review
    if on_chunk:
        await on_chunk("📝 正在进行合规+网感深度审查...\n\n")

    from app.models.llm import call_deepseek_with_stream

    user_content = "请审查以下视频：\n\n"
    if has_video and metadata:
        user_content += f"📹 视频: {metadata['duration']}秒, {metadata['resolution']}, 已分析 {len(frames) if frames else 0} 帧\n"
    if vision_analysis and "[视觉分析失败" not in vision_analysis:
        user_content += f"\n🖼️ Claude 视觉 AI 逐帧分析:\n{vision_analysis}\n"
    user_content += f"\n📝 用户描述: {task}\n"
    if context:
        user_content += f"📋 补充: {context}\n"
    user_content += "\n结合视觉分析结果和用户描述，从合规和网感两个维度全面审查，给出具体修改建议。"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    result = await call_deepseek_with_stream(messages, temperature=0.5, max_tokens=2500, on_chunk=on_chunk)
    return result


AGENT_META = {
    "name": "video_review",
    "icon": "🔎",
    "label": "视频审阅",
    "description": "提取视频帧→Claude视觉分析→DeepSeek合规网感审查，真正看懂视频内容",
    "trigger_keywords": ["视频审阅", "审阅视频", "视频审查", "视频检测", "视频合规", "视频分析", "视频诊断", "看看视频", "检查视频", "视频质量"],
}
