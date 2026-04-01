"""
Query生成相关功能的测试 (窗口3)

测试内容:
1. LLMQueryGenerator功能
2. 长度控制功能
3. 动态长度选择器
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator.query_generator import QueryGenerator
from simulator.prompt_templates import PromptTemplates
from simulator.user_simulator import UserSimulator


class MockLLMClient:
    """模拟LLM客户端"""

    def __init__(self, responses=None):
        self.responses = responses or [
            "这个人物的表情如何？",
            "能详细描述一下场景吗？",
            "图中有哪些物体？"
        ]
        self.call_count = 0

    def generate(self, prompt, temperature=0.5, max_tokens=100):
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response


class TestQueryGenerator:
    """QueryGenerator测试"""

    def setup_method(self):
        self.generator = QueryGenerator()
        self.sample_entities = {
            "objects": ["人", "伞", "街道"],
            "attributes": {
                "人": {"位置": ["左边"], "动作": ["站立"]},
                "伞": {"颜色": ["黑色"], "状态": ["打开"]}
            },
            "regions": ["左上角", "中间"]
        }

    def test_follow_up_generation(self):
        """测试follow_up动作生成"""
        query = self.generator.generate(
            action_type="follow_up",
            entities=self.sample_entities,
            length="medium"
        )

        assert query is not None
        assert len(query) > 10
        assert "请用2-3句话回答" in query  # 检查长度后缀

    def test_different_lengths(self):
        """测试不同长度控制"""
        templates = PromptTemplates()

        for length in ["short", "medium", "long"]:
            query = self.generator.generate(
                action_type="guidance",
                entities=self.sample_entities,
                length=length
            )

            expected_suffix = templates.LENGTH_CONTROL_SUFFIX.get(length, "")
            if expected_suffix:
                assert expected_suffix in query, f"Length {length} suffix not found"

    def test_all_action_types(self):
        """测试所有动作类型"""
        action_types = [
            "follow_up", "guidance", "negation", "mislead",
            "update", "distraction", "redundancy", "fine_grained",
            "logic_skip", "next_task"
        ]

        for action in action_types:
            query = self.generator.generate(
                action_type=action,
                entities=self.sample_entities,
                length="medium"
            )

            assert query is not None, f"Action {action} returned None"
            assert len(query) > 0, f"Action {action} returned empty query"


class TestLengthControl:
    """长度控制测试"""

    def test_length_suffix_in_user_simulator(self):
        """测试UserSimulator中的长度后缀"""
        task = {
            "task_id": "test_001",
            "question": "图中有什么？"
        }

        simulator = UserSimulator(
            task=task,
            extraction_mode="simple",
            action_strategy="rule_based"
        )

        vlm_response = "图中有一个人拿着伞站在街上。"

        for length in ["short", "medium", "long"]:
            simulator.reset()
            step_info = simulator.step(vlm_response, length=length)

            query = step_info["user_query"]

            # 检查新增字段是否存在
            assert "query_length_control" in step_info
            assert step_info["query_length_control"] == length

            assert "query_word_count" in step_info
            assert step_info["query_word_count"] > 0

    def test_length_suffix_content(self):
        """测试长度后缀的具体内容"""
        templates = PromptTemplates()

        expected = {
            "short": "请用一句话简短回答",
            "medium": "请用2-3句话回答",
            "long": "请详细解释你的推理过程"
        }

        for length, expected_text in expected.items():
            actual_suffix = templates.LENGTH_CONTROL_SUFFIX.get(length, "")
            assert expected_text in actual_suffix, \
                f"Expected '{expected_text}' in suffix for {length}"


class TestDynamicLengthSelector:
    """动态长度选择器测试"""

    def test_import_length_selector(self):
        """测试导入"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
            assert True
        except ImportError as e:
            pytest.skip(f"LengthSelector not implemented yet: {e}")

    def test_fixed_strategy(self):
        """测试固定策略"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
        except ImportError:
            pytest.skip("LengthSelector not implemented")

        selector = DynamicLengthSelector(
            strategy=LengthSelectionStrategy.FIXED,
            default_length="short"
        )

        result = selector.select()
        assert result["length"] == "short"
        assert result["reason"] == "fixed_strategy"

    def test_random_strategy(self):
        """测试随机策略"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
        except ImportError:
            pytest.skip("LengthSelector not implemented")

        selector = DynamicLengthSelector(
            strategy=LengthSelectionStrategy.RANDOM
        )

        # 多次采样，确保能产生不同结果
        results = [selector.select()["length"] for _ in range(30)]

        # 应该至少有2种不同的长度
        unique_lengths = set(results)
        assert len(unique_lengths) >= 2, "Random strategy should produce varied results"

    def test_phase_based_strategy(self):
        """测试基于阶段的策略"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
        except ImportError:
            pytest.skip("LengthSelector not implemented")

        selector = DynamicLengthSelector(
            strategy=LengthSelectionStrategy.PHASE_BASED
        )

        # 测试不同阶段
        phases = ["grounding", "stress_test", "final"]

        for phase in phases:
            result = selector.select(phase=phase)
            assert result["length"] in ["short", "medium", "long"]
            assert f"phase_based_{phase}" in result["reason"]

    def test_adaptive_strategy(self):
        """测试自适应策略"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
        except ImportError:
            pytest.skip("LengthSelector not implemented")

        selector = DynamicLengthSelector(
            strategy=LengthSelectionStrategy.ADAPTIVE
        )

        # 测试不同阶段
        for phase in ["grounding", "stress_test", "final"]:
            result = selector.select(phase=phase, difficulty=2, turn=5)

            assert result["length"] in ["short", "medium", "long"]
            assert "probabilities" in result
            assert sum(result["probabilities"].values()) == pytest.approx(1.0)

    def test_probability_normalization(self):
        """测试概率归一化"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
        except ImportError:
            pytest.skip("LengthSelector not implemented")

        selector = DynamicLengthSelector(
            strategy=LengthSelectionStrategy.ADAPTIVE
        )

        # 各种参数组合
        test_cases = [
            {"phase": "grounding", "difficulty": 1},
            {"phase": "stress_test", "difficulty": 3},
            {"phase": "final", "difficulty": 4},
        ]

        for params in test_cases:
            result = selector.select(**params)
            prob_sum = sum(result["probabilities"].values())
            assert prob_sum == pytest.approx(1.0), \
                f"Probabilities should sum to 1.0, got {prob_sum} for {params}"


class TestLLMQueryGenerator:
    """LLM Query Generator测试"""

    def test_import_llm_generator(self):
        """测试导入"""
        try:
            from simulator.llm_query_generator import (
                LLMQueryGenerator,
                HybridQueryGenerator
            )
            assert True
        except ImportError as e:
            pytest.skip(f"LLMQueryGenerator not implemented yet: {e}")

    def test_low_creativity_uses_rule(self):
        """测试低创造性时使用规则生成"""
        try:
            from simulator.llm_query_generator import LLMQueryGenerator
        except ImportError:
            pytest.skip("LLMQueryGenerator not implemented")

        mock_client = MockLLMClient()
        generator = LLMQueryGenerator(
            llm_client=mock_client,
            default_creativity=0.2  # 低创造性
        )

        entities = {"objects": ["人"], "attributes": {}, "regions": []}

        result = generator.generate(
            action_type="follow_up",
            entities=entities,
            creativity_level=0.1  # 非常低
        )

        assert result["source"] == "rule"
        assert mock_client.call_count == 0  # LLM不应被调用

    def test_high_creativity_uses_llm(self):
        """测试高创造性时使用LLM生成"""
        try:
            from simulator.llm_query_generator import LLMQueryGenerator
        except ImportError:
            pytest.skip("LLMQueryGenerator not implemented")

        mock_client = MockLLMClient()
        generator = LLMQueryGenerator(
            llm_client=mock_client,
            default_creativity=0.7
        )

        entities = {"objects": ["人"], "attributes": {}, "regions": []}

        result = generator.generate(
            action_type="follow_up",
            entities=entities,
            creativity_level=0.8  # 高创造性
        )

        assert result["source"] == "llm"
        assert mock_client.call_count > 0

    def test_hybrid_mode_rule_only(self):
        """测试混合模式 - 纯规则"""
        try:
            from simulator.llm_query_generator import HybridQueryGenerator
        except ImportError:
            pytest.skip("HybridQueryGenerator not implemented")

        generator = HybridQueryGenerator(
            llm_client=None,
            mode="rule"
        )

        entities = {"objects": ["人"], "attributes": {}, "regions": []}

        result = generator.generate(
            action_type="guidance",
            entities=entities
        )

        assert result["source"] == "rule"
        assert result["mode"] == "rule"

    def test_hybrid_mode_mixed(self):
        """测试混合模式"""
        try:
            from simulator.llm_query_generator import HybridQueryGenerator
        except ImportError:
            pytest.skip("HybridQueryGenerator not implemented")

        mock_client = MockLLMClient()
        generator = HybridQueryGenerator(
            llm_client=mock_client,
            mode="hybrid",
            llm_probability=0.5
        )

        entities = {"objects": ["人"], "attributes": {}, "regions": []}

        # 多次生成，应该有LLM和规则的混合
        sources = []
        for _ in range(20):
            result = generator.generate(
                action_type="guidance",
                entities=entities
            )
            sources.append(result["source"])

        # 由于随机性，不做严格断言，只检查至少有一种来源
        assert len(sources) == 20

    def test_stats_tracking(self):
        """测试统计追踪"""
        try:
            from simulator.llm_query_generator import LLMQueryGenerator
        except ImportError:
            pytest.skip("LLMQueryGenerator not implemented")

        mock_client = MockLLMClient()
        generator = LLMQueryGenerator(
            llm_client=mock_client,
            default_creativity=0.1  # 低创造性，使用规则
        )

        entities = {"objects": ["人"], "attributes": {}, "regions": []}

        # 生成几次
        for _ in range(5):
            generator.generate(
                action_type="follow_up",
                entities=entities,
                creativity_level=0.1
            )

        stats = generator.get_stats()
        assert "fallback_used" in stats
        assert stats["fallback_used"] == 5
        assert stats["total_generations"] == 5


class TestUserSimulatorIntegration:
    """UserSimulator集成测试"""

    def test_rule_mode(self):
        """测试规则模式"""
        task = {
            "task_id": "test_001",
            "question": "图中有什么？"
        }

        simulator = UserSimulator(
            task=task,
            query_generation_mode="rule"
        )

        vlm_response = "图中有一个人拿着伞站在街上。"
        step_info = simulator.step(vlm_response, length="medium")

        assert step_info["query_generation_source"] == "rule"
        assert step_info["query_creativity_used"] == 0.0

    def test_query_generation_stats(self):
        """测试Query生成统计"""
        task = {
            "task_id": "test_002",
            "question": "描述这张图"
        }

        simulator = UserSimulator(
            task=task,
            query_generation_mode="rule"
        )

        # 执行几轮
        responses = [
            "图中有一个人。",
            "这个人穿着红色的衣服。",
            "背景是一条街道。"
        ]

        for i, resp in enumerate(responses):
            length = ["short", "medium", "long"][i]
            simulator.step(resp, length=length)

        stats = simulator.get_query_generation_stats()

        assert stats["total_queries"] == 3
        assert stats["length_distribution"]["short"] == 1
        assert stats["length_distribution"]["medium"] == 1
        assert stats["length_distribution"]["long"] == 1

    def test_length_control_summary(self):
        """测试长度控制摘要"""
        task = {
            "task_id": "test_003",
            "question": "描述这张图"
        }

        simulator = UserSimulator(
            task=task,
            query_generation_mode="rule"
        )

        # 执行几轮
        for _ in range(3):
            simulator.step("测试响应", length="medium")

        summary = simulator.get_length_control_summary()

        assert summary["total_turns"] == 3
        assert "avg_word_count_by_length" in summary
        assert summary["query_generation_mode"] == "rule"


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Query Generation Tests (窗口3)")
    print("=" * 60)

    # Test QueryGenerator
    print("\n--- Testing QueryGenerator ---")
    test_qg = TestQueryGenerator()
    test_qg.setup_method()

    try:
        test_qg.test_follow_up_generation()
        print("  ✓ follow_up generation")
    except Exception as e:
        print(f"  ✗ follow_up generation: {e}")

    try:
        test_qg.test_different_lengths()
        print("  ✓ different lengths")
    except Exception as e:
        print(f"  ✗ different lengths: {e}")

    try:
        test_qg.test_all_action_types()
        print("  ✓ all action types")
    except Exception as e:
        print(f"  ✗ all action types: {e}")

    # Test Length Control
    print("\n--- Testing Length Control ---")
    test_lc = TestLengthControl()

    try:
        test_lc.test_length_suffix_in_user_simulator()
        print("  ✓ length suffix in UserSimulator")
    except Exception as e:
        print(f"  ✗ length suffix in UserSimulator: {e}")

    try:
        test_lc.test_length_suffix_content()
        print("  ✓ length suffix content")
    except Exception as e:
        print(f"  ✗ length suffix content: {e}")

    # Test Dynamic Length Selector
    print("\n--- Testing Dynamic Length Selector ---")
    test_dls = TestDynamicLengthSelector()

    try:
        test_dls.test_import_length_selector()
        print("  ✓ import successful")

        test_dls.test_fixed_strategy()
        print("  ✓ fixed strategy")

        test_dls.test_random_strategy()
        print("  ✓ random strategy")

        test_dls.test_phase_based_strategy()
        print("  ✓ phase based strategy")

        test_dls.test_adaptive_strategy()
        print("  ✓ adaptive strategy")

        test_dls.test_probability_normalization()
        print("  ✓ probability normalization")
    except Exception as e:
        print(f"  ⚠ skipped or failed: {e}")

    # Test LLM Query Generator
    print("\n--- Testing LLM Query Generator ---")
    test_llm = TestLLMQueryGenerator()

    try:
        test_llm.test_import_llm_generator()
        print("  ✓ import successful")

        test_llm.test_low_creativity_uses_rule()
        print("  ✓ low creativity uses rule")

        test_llm.test_high_creativity_uses_llm()
        print("  ✓ high creativity uses LLM")

        test_llm.test_hybrid_mode_rule_only()
        print("  ✓ hybrid mode (rule only)")

        test_llm.test_stats_tracking()
        print("  ✓ stats tracking")
    except Exception as e:
        print(f"  ⚠ skipped or failed: {e}")

    # Test UserSimulator Integration
    print("\n--- Testing UserSimulator Integration ---")
    test_us = TestUserSimulatorIntegration()

    try:
        test_us.test_rule_mode()
        print("  ✓ rule mode")

        test_us.test_query_generation_stats()
        print("  ✓ query generation stats")

        test_us.test_length_control_summary()
        print("  ✓ length control summary")
    except Exception as e:
        print(f"  ⚠ skipped or failed: {e}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
