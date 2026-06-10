"""Configuration management for Merchant Agents."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env from project root, regardless of CWD
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


class Config:
    """Application configuration loaded from environment variables."""

    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # Image model (pluggable)
    IMAGE_API_KEY: str = os.getenv("IMAGE_API_KEY", "")
    IMAGE_API_URL: str = os.getenv("IMAGE_API_URL", "")
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "")

    # Video packaging (wuyinkeji)
    VIDEO_API_KEY: str = os.getenv("VIDEO_API_KEY", "")
    VIDEO_API_URL: str = os.getenv("VIDEO_API_URL", "")

    # Database
    DATABASE_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "merchant.db",
    )

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required config. Returns list of missing keys."""
        missing = []
        if not cls.DEEPSEEK_API_KEY or cls.DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
            missing.append("DEEPSEEK_API_KEY")
        return missing


config = Config()
