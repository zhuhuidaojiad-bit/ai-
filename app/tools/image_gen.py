"""Image generation tool — pluggable client for the user's image model."""

from app.models.llm import image_client
from app.utils.logger import logger


async def generate_image(
    prompt: str,
    style: str = "e-commerce-product",
    size: str = "1024x1024",
    on_progress = None,  # async callback(status_text) for polling progress
    reference_urls = None,  # Optional[list[str]] reference image URLs
) -> dict:
    """
    Generate a product cover image.

    Args:
        prompt: Image generation prompt describing the desired image.
        style: Style preset (e-commerce-product, social-media, minimalist, etc.)
        size: Output size (e.g., "1024x1024", "800x800").
        on_progress: Optional async callback for polling progress updates.
        reference_urls: Optional list of reference image URLs for style matching.

    Returns:
        dict with url, prompt, style, and possibly error info.
    """
    logger.info(f"Generating image: prompt='{prompt[:100]}...', style={style}, size={size}, refs={len(reference_urls or [])}")
    result = await image_client.generate_image(
        prompt=prompt, style=style, size=size, on_progress=on_progress, reference_urls=reference_urls,
    )
    return result
