"""Test the orchestrator intent parsing and fallback logic."""

import pytest
from app.agents.orchestrator import _fallback_intent, ALL_AGENTS


class TestFallbackIntent:
    def test_orders_keyword(self):
        intent = _fallback_intent("帮我查最近7天的订单情况")
        assert "orders" in intent["agents"]

    def test_data_keyword(self):
        intent = _fallback_intent("分析本周销售数据")
        assert "data_analysis" in intent["agents"]

    def test_video_keyword(self):
        intent = _fallback_intent("为新品生成短视频脚本")
        assert "video_script" in intent["agents"]

    def test_copywriting_keyword(self):
        intent = _fallback_intent("写一段产品文案")
        assert "copywriting" in intent["agents"]

    def test_cover_image_keyword(self):
        intent = _fallback_intent("生成产品封面图片")
        assert "cover_image" in intent["agents"]

    def test_multi_agent(self):
        intent = _fallback_intent("分析订单数据并为爆款生成短视频脚本和封面")
        agents = intent["agents"]
        assert len(agents) >= 3  #至少匹配到3个

    def test_default_fallback(self):
        intent = _fallback_intent("你好")
        assert len(intent["agents"]) > 0  # 至少返回默认agent

    def test_all_agents_have_meta(self):
        agent_names = [a["name"] for a in ALL_AGENTS]
        assert "copywriting" in agent_names
        assert "cover_image" in agent_names
        assert "data_analysis" in agent_names
        assert "orders" in agent_names
        assert "video_script" in agent_names
        assert "video_analysis" in agent_names
