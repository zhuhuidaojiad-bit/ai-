"""LLM factory — DeepSeek text model + pluggable image model."""

from openai import AsyncOpenAI
from app.config import config
from app.utils.logger import logger


def get_deepseek_client() -> AsyncOpenAI:
    """Create an async DeepSeek client (OpenAI-compatible)."""
    return AsyncOpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
    )


async def call_deepseek(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    stream: bool = False,
) -> str:
    """Call DeepSeek chat completion. Returns the response text."""
    client = get_deepseek_client()
    response = await client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    return response.choices[0].message.content or ""


async def call_deepseek_with_stream(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    on_chunk = None,  # async callback(chunk_text) for each piece
) -> str:
    """Call DeepSeek with streaming, collecting full result.
    If on_chunk callback is provided, calls it with each text chunk as it arrives.
    Returns the complete response text."""
    client = get_deepseek_client()
    full = []
    stream = await client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            full.append(content)
            if on_chunk:
                await on_chunk(content)
    return "".join(full)


async def call_deepseek_stream(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """Call DeepSeek with streaming. Yields content chunks. (legacy)"""
    client = get_deepseek_client()
    stream = await client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def call_deepseek_json(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """Call DeepSeek and parse the response as JSON. Returns parsed dict."""
    import json

    json_messages = messages + [
        {"role": "system", "content": "You MUST respond with valid JSON only. No markdown, no explanation."}
    ]
    raw = await call_deepseek(json_messages, temperature=temperature, max_tokens=max_tokens)
    # Strip possible markdown code fences
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from DeepSeek response: {raw[:500]}")
        return {"error": "JSON parse failed", "raw": raw[:1000]}


class ImageModelClient:
    """Pluggable image generation client — apidot.ai unified API."""

    def __init__(self):
        self.api_url = config.IMAGE_API_URL          # submit endpoint
        self.api_key = config.IMAGE_API_KEY
        self.model = config.IMAGE_MODEL              # e.g. "gpt-image-2"
        # Build status URL from base
        from urllib.parse import urlparse
        parsed = urlparse(self.api_url)
        self.status_url = f"{parsed.scheme}://{parsed.netloc}/api/generate/status"

    async def generate_image(
        self,
        prompt: str,
        style: str = "e-commerce",
        size: str = "1024x1024",
        on_progress = None,  # async callback(status_text) during polling
        reference_urls = None,  # Optional[list[str]] reference image URLs
    ) -> dict:
        """
        Generate an image via apidot.ai async API.
        1. POST to /api/generate/submit → get task_id
        2. Poll GET /api/generate/status/{task_id} → get file URLs
        If reference_urls provided, they are passed as input.images for style reference.
        Returns {"url": "...", "prompt": "...", "task_id": "..."}
        """
        if not self.api_url or not self.api_key:
            logger.warning("No image API configured. Returning placeholder.")
            return {
                "url": f"https://placehold.co/{size.replace('x', 'x')}?text=Cover+Image",
                "prompt": prompt,
                "style": style,
                "note": "Image API not configured — placeholder returned",
            }

        import httpx, asyncio

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                # Step 1: Submit generation request
                # quality: low (fastest) / medium / high (slowest, best detail)
                input_data = {
                    "prompt": prompt,
                    "image_size": size,
                    "quality": "low",
                }
                # Include reference images if provided
                # gpt-image-2-edit uses "image_urls" field, and is purpose-built for reference-based editing
                model = self.model
                if reference_urls:
                    input_data["image_urls"] = reference_urls
                    model = "gpt-image-2-edit"
                    logger.info(f"Using {len(reference_urls)} reference image(s) with {model}")

                request_body = {
                    "model": model,
                    "input": input_data,
                }

                logger.info(f"Submitting image task: model={self.model}, prompt={prompt[:80]}...")
                resp = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") not in (0, 200):
                    error_info = data.get("error", {})
                    err_msg = error_info.get("message", "") if isinstance(error_info, dict) else str(error_info)
                    return {"error": err_msg or "Unknown error", "prompt": prompt}

                task_data = data.get("data", {})
                task_id = task_data.get("task_id") or task_data.get("id")
                if not task_id:
                    return {"error": "No task ID in response", "prompt": prompt, "raw": data}

                logger.info(f"Image task submitted: {task_id}, polling...")

                # Step 2: Poll for result (max 360s, 120 attempts × 3s)
                # With reference images, gpt-image-2 can take 4-6 min.
                # IMPORTANT: Do NOT timeout early — if we give up but the task completes
                # later, credits are still charged and we lose the image.
                for attempt in range(120):
                    await asyncio.sleep(3)
                    try:
                        poll_resp = await client.get(
                            f"{self.status_url}/{task_id}",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                            },
                        )
                        if poll_resp.status_code != 200:
                            continue

                        poll_data = poll_resp.json()
                        poll_result = poll_data.get("data", {})
                        status = poll_result.get("status", "")
                        progress = poll_result.get("progress", 0)

                        if status == "finished":
                            files = poll_result.get("files", [])
                            image_url = files[0].get("file_url", "") if files else ""
                            logger.info(f"Image generated: {image_url}")
                            return {
                                "url": image_url,
                                "prompt": prompt,
                                "style": style,
                                "task_id": task_id,
                            }
                        elif status == "failed":
                            err_msg = poll_result.get("error_message", "")
                            # API returns "failed" for content filter rejections — these are NOT charged
                            if not err_msg:
                                err_msg = "内容审核未通过或生成失败（未扣费）"
                            logger.error(f"Image generation failed: {err_msg}")
                            return {
                                "error": err_msg,
                                "prompt": prompt,
                            }

                        # Emit progress updates (show percentage when available)
                        if on_progress:
                            elapsed = (attempt + 1) * 3
                            if progress is not None and progress > 0:
                                await on_progress(f"⏳ 图片生成中... {progress:.0f}% ({elapsed}秒)")
                            elif attempt % 3 == 0:
                                await on_progress(f"⏳ 图片生成中... ({elapsed}秒)")

                        logger.debug(f"Poll {attempt+1}: status={status}, progress={progress}%")
                    except Exception:
                        continue

                # Timed out — task may still complete later on the server
                logger.warning(f"Image poll timed out after 360s, task may still complete: {task_id}")
                return {
                    "error": f"图片生成超时（360秒）。任务ID: {task_id}，可能在网站上已完成，请查 https://api.apidot.ai",
                    "prompt": prompt,
                    "task_id": task_id,
                }

            except httpx.HTTPStatusError as e:
                logger.error(f"Image API HTTP error: {e.response.status_code}")
                return {"error": f"HTTP {e.response.status_code}", "prompt": prompt}
            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                return {"error": str(e), "prompt": prompt}


class VideoPackagingClient:
    """Video packaging client — wuyinkeji async API for AI video editing."""

    def __init__(self):
        self.api_url = config.VIDEO_API_URL
        self.api_key = config.VIDEO_API_KEY
        from urllib.parse import urlparse
        parsed = urlparse(self.api_url)
        self.query_url = f"{parsed.scheme}://{parsed.netloc}/api/async/detail"

    async def package_video(
        self,
        video_url: str,
        template: str = "",
        on_progress = None,
    ) -> dict:
        """
        Submit video for AI packaging (titles, subtitles, effects, auto-edit).
        1. POST to submit → get task id
        2. Poll GET /api/async/detail → get packaged video URL
        Returns {"url": "...", "task_id": "..."}
        """
        if not self.api_url or not self.api_key:
            return {"error": "Video API not configured", "video_url": video_url}

        import httpx, asyncio

        request_body = {"video": video_url}
        if template:
            request_body["template"] = template

        async with httpx.AsyncClient(timeout=300) as client:
            try:
                logger.info(f"Submitting video package: {video_url[:80]}...")
                resp = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": self.api_key,  # raw key, no Bearer
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 200:
                    return {"error": data.get("msg", "Unknown error"), "video_url": video_url}

                task_id = data.get("data", {}).get("id")
                if not task_id:
                    return {"error": "No task ID in response", "video_url": video_url}

                logger.info(f"Video task submitted: {task_id}, polling...")

                # Poll for result (max 300s, 100 attempts × 3s)
                for attempt in range(100):
                    await asyncio.sleep(3)
                    try:
                        poll_resp = await client.get(
                            self.query_url,
                            params={"key": self.api_key, "id": task_id},
                            headers={"Content-Type": "application/json"},
                        )
                        if poll_resp.status_code != 200:
                            continue

                        poll_data = poll_resp.json()
                        poll_result = poll_data.get("data", {})
                        status = poll_result.get("status", 0)

                        if status == 2:  # Completed
                            results = poll_result.get("result", [])
                            video_result_url = results[0] if results else ""
                            logger.info(f"Video packaged: {video_result_url}")
                            return {
                                "url": video_result_url,
                                "video_url": video_url,
                                "task_id": task_id,
                            }
                        elif status != 0:  # Failed (status=-1, 3, etc.)
                            err_msg = poll_result.get("message", f"处理失败 (status={status})")
                            logger.error(f"Video packaging failed: {err_msg}")
                            return {"error": err_msg, "video_url": video_url}

                        if on_progress and attempt % 3 == 0:
                            elapsed = (attempt + 1) * 3
                            await on_progress(f"⏳ 视频包装中... ({elapsed}秒)")

                        logger.debug(f"Video poll {attempt+1}: status={status}")
                    except Exception:
                        continue

                logger.warning(f"Video poll timed out after 300s: {task_id}")
                return {
                    "error": f"视频包装超时（300秒）。任务ID: {task_id}",
                    "video_url": video_url,
                    "task_id": task_id,
                }

            except Exception as e:
                logger.error(f"Video packaging failed: {e}")
                return {"error": str(e), "video_url": video_url}


# Singletons
image_client = ImageModelClient()
video_client = VideoPackagingClient()
