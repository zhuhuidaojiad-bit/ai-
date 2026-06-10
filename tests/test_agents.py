"""Test agent runners have correct signatures and handle basic calls."""

import pytest
from app.config import config
from app.agents.copywriting import run_copywriting_agent, AGENT_META as CW_META
from app.agents.cover_image import run_cover_image_agent
from app.agents.data_analysis import run_data_analysis_agent
from app.agents.orders import run_orders_agent
from app.agents.video_script import run_video_script_agent
from app.agents.video_analysis import run_video_analysis_agent

requires_api_key = pytest.mark.skipif(
    not config.DEEPSEEK_API_KEY or config.DEEPSEEK_API_KEY == "your_deepseek_api_key_here",
    reason="DeepSeek API key not configured — set DEEPSEEK_API_KEY in .env to run",
)


class TestAgentMeta:
    """Verify all agents have proper metadata."""

    AGENTS = [
        ("copywriting", CW_META),
        ("cover_image", __import__("app.agents.cover_image", fromlist=["AGENT_META"]).AGENT_META),
        ("data_analysis", __import__("app.agents.data_analysis", fromlist=["AGENT_META"]).AGENT_META),
        ("orders", __import__("app.agents.orders", fromlist=["AGENT_META"]).AGENT_META),
        ("video_script", __import__("app.agents.video_script", fromlist=["AGENT_META"]).AGENT_META),
        ("video_analysis", __import__("app.agents.video_analysis", fromlist=["AGENT_META"]).AGENT_META),
    ]

    @pytest.mark.parametrize("name,meta", AGENTS)
    def test_agent_meta_structure(self, name, meta):
        assert "name" in meta
        assert "icon" in meta
        assert "label" in meta
        assert "description" in meta
        assert "trigger_keywords" in meta
        assert len(meta["trigger_keywords"]) > 0


class TestAgentSignatures:
    """Verify agents are callable with expected signature. Requires API key."""

    @requires_api_key
    async def test_copywriting_signature(self):
        result = await run_copywriting_agent("test task")
        assert isinstance(result, str)

    @requires_api_key
    async def test_video_script_signature(self):
        result = await run_video_script_agent("test task")
        assert isinstance(result, str)
