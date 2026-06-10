"""封面图片 Agent — 生成产品封面图、主图、推广图."""

from app.models.llm import call_deepseek_with_stream
from app.tools.image_gen import generate_image
from app.utils.logger import logger

SYSTEM_PROMPT = (
    "You write prompts for AI image editing. When reference images are provided, "
    "the AI will edit those images. Write a prompt that tells the AI to REPLACE "
    "the main product/subject in the reference image with the user's requested product, "
    "while KEEPING IDENTICAL: background, lighting, composition, camera angle, colors. "
    "CRITICAL: Start with 'Replace the product in this image with...' "
    "Output ONLY the prompt, max 80 words, English only."
)


async def run_cover_image_agent(task: str, context: str = "", on_chunk=None, reference_urls=None) -> str:
    """Run the cover image agent with streaming support."""
    logger.info(f"Cover image agent: {task[:80]}..., refs={len(reference_urls or [])}")

    has_refs = reference_urls and len(reference_urls) > 0

    # Step 1: Generate the image prompt (streaming)
    if has_refs:
        if on_chunk:
            await on_chunk(f"🎨 正在根据 {len(reference_urls)} 张参考图构思设计...\n\n")
        user_msg = (
            f"New product to insert: {task}\n"
            f"The AI will REPLACE the product in {len(reference_urls)} reference image(s) "
            f"with this new product. Tell the AI to keep EVERYTHING ELSE exactly the same: "
            f"background, lighting, composition, camera angle, colors, shadows, styling.\n"
            f"Context: {context}" if context else ""
        )
    else:
        if on_chunk:
            await on_chunk("🎨 正在构思封面设计...\n\n")
        user_msg = f"Product: {task}" + (f"\nContext: {context}" if context else "")

    prompt_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    image_prompt = await call_deepseek_with_stream(prompt_messages, temperature=0.3, max_tokens=150)

    if on_chunk:
        await on_chunk(f"\n\n📝 **生成 Prompt:**\n{image_prompt}\n\n🖼️ 正在调用图片模型生成...\n")

    # Step 2: Call image generation API with progress updates
    result = await generate_image(
        prompt=image_prompt.strip(),
        style="social-media",
        size="1024x1024",
        on_progress=on_chunk,
        reference_urls=reference_urls,
    )

    if result.get("error"):
        error_msg = f"\n\n⚠️ 图片生成失败: {result['error']}\n\n生成的 Prompt:\n{image_prompt}"
        if on_chunk:
            await on_chunk(error_msg)
        return error_msg

    url = result.get("url", "")
    final = f"\n\n✅ 封面图片已生成\n\n📝 Prompt:\n{image_prompt}\n\n🖼️ 图片链接:\n{url}"
    if on_chunk:
        await on_chunk(final)
    return final


AGENT_META = {
    "name": "cover_image",
    "icon": "🎨",
    "label": "封面图片",
    "description": "生成产品封面图、主图、推广海报",
    "trigger_keywords": ["封面", "图片", "海报", "主图", "banner", "图", "视觉"],
}
