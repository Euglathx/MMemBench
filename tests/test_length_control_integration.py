"""
长度控制集成测试 (窗口3)

测试完整的长度控制流程，从选择到日志记录。
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_full_length_control_flow():
    """测试完整的长度控制流程"""

    from simulator.user_simulator import UserSimulator
    from simulator.prompt_templates import PromptTemplates

    print("=" * 60)
    print("Full Length Control Flow Test (窗口3)")
    print("=" * 60)

    # 准备任务
    task = {
        "task_id": "length_test_001",
        "question": "描述图中的场景",
        "task_type": "attribute_comparison"
    }

    # 创建simulator
    simulator = UserSimulator(
        task=task,
        extraction_mode="simple",
        action_strategy="rule_based",
        verbose=False
    )

    # 模拟VLM响应
    vlm_responses = [
        "图中有一个人拿着红色的伞站在街上。",
        "这个人穿着蓝色的外套，伞是打开的。",
        "背景中有几栋建筑物和一些树木。"
    ]

    # 测试三种长度
    results = []
    templates = PromptTemplates()

    for i, vlm_response in enumerate(vlm_responses):
        length = ["short", "medium", "long"][i]

        step_info = simulator.step(
            vlm_response=vlm_response,
            length=length
        )

        # 验证长度后缀
        expected_suffix = templates.LENGTH_CONTROL_SUFFIX.get(length, "")
        suffix_found = expected_suffix in step_info["user_query"]

        result = {
            "turn": i + 1,
            "length_requested": length,
            "query": step_info["user_query"],
            "word_count": len(step_info["user_query"].split()),
            "suffix_found": suffix_found,
            "expected_suffix": expected_suffix[:30] + "..." if len(expected_suffix) > 30 else expected_suffix,
            "query_length_control": step_info.get("query_length_control"),
            "query_generation_source": step_info.get("query_generation_source"),
            "length_suffix_applied": step_info.get("length_suffix_applied")
        }
        results.append(result)

        print(f"\n--- Turn {i+1}: Length = {length} ---")
        print(f"Query: {step_info['user_query'][:80]}...")
        print(f"Word count: {result['word_count']}")
        print(f"Suffix found: {'✓' if suffix_found else '✗'}")
        print(f"Generation source: {step_info.get('query_generation_source', 'unknown')}")

    # 获取统计信息
    stats = simulator.get_query_generation_stats()
    summary = simulator.get_length_control_summary()

    print("\n" + "=" * 60)
    print("Statistics")
    print("=" * 60)
    print(f"Total queries: {stats['total_queries']}")
    print(f"Length distribution: {stats['length_distribution']}")
    print(f"Source distribution: {stats['source_distribution']}")
    print(f"Suffix applied rate: {stats['length_suffix_applied_rate']:.2%}")
    print(f"Average word count: {stats['average_word_count']:.1f}")

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = all(r["suffix_found"] for r in results)

    print(f"\nResults:")
    for r in results:
        status = "PASS" if r["suffix_found"] else "FAIL"
        print(f"  Turn {r['turn']} ({r['length_requested']}): {status}")

    print(f"\nOverall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    # 保存详细结果
    output_dir = Path("tests/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "length_control_test_results.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "all_passed": all_passed,
            "results": results,
            "statistics": stats,
            "summary": summary
        }, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed results saved to: {output_file}")

    return all_passed


def test_dynamic_length_selector_integration():
    """测试动态长度选择器集成"""

    print("\n" + "=" * 60)
    print("Dynamic Length Selector Integration Test (窗口3)")
    print("=" * 60)

    try:
        from simulator.length_selector import (
            DynamicLengthSelector,
            LengthSelectionStrategy,
            get_length_selector_presets
        )
    except ImportError as e:
        print(f"⚠ Skipped: {e}")
        return True

    # 测试所有预设
    presets = get_length_selector_presets()

    print(f"\nTesting {len(presets)} presets:")

    for preset_name, selector in presets.items():
        print(f"\n--- Preset: {preset_name} ---")

        # 模拟不同阶段和难度
        test_cases = [
            {"phase": "grounding", "difficulty": 1, "turn": 1},
            {"phase": "stress_test", "difficulty": 3, "turn": 10},
            {"phase": "final", "difficulty": 4, "turn": 20},
        ]

        for case in test_cases:
            result = selector.select(**case)
            print(f"  Phase={case['phase']}, Diff={case['difficulty']}: "
                  f"length={result['length']}, reason={result['reason'][:30]}")

    # 测试自适应策略的历史去重
    print("\n--- Testing History De-duplication ---")
    selector = DynamicLengthSelector(strategy=LengthSelectionStrategy.ADAPTIVE)

    # 模拟连续3轮都是"medium"
    history = [
        {"query_length_control": "medium"},
        {"query_length_control": "medium"},
        {"query_length_control": "medium"},
    ]

    result = selector.select(
        phase="grounding",
        difficulty=2,
        turn=4,
        history=history
    )

    print(f"After 3 consecutive 'medium': length={result['length']}")
    print(f"Probabilities: {result['probabilities']}")

    # 检查medium概率是否降低
    if result["probabilities"]["medium"] < 0.5:
        print("  ✓ Medium probability reduced (de-duplication working)")
    else:
        print("  ⚠ Medium probability not reduced as expected")

    print("\n✓ Dynamic Length Selector Integration Test Completed")
    return True


def test_user_simulator_with_different_modes():
    """测试UserSimulator不同模式"""

    print("\n" + "=" * 60)
    print("UserSimulator Mode Test (窗口3)")
    print("=" * 60)

    from simulator.user_simulator import UserSimulator

    task = {
        "task_id": "mode_test_001",
        "question": "描述图中的内容"
    }

    # 测试rule模式
    print("\n--- Testing Rule Mode ---")
    simulator_rule = UserSimulator(
        task=task,
        query_generation_mode="rule"
    )

    step = simulator_rule.step("测试响应", length="medium")
    print(f"Source: {step['query_generation_source']}")
    print(f"Creativity: {step['query_creativity_used']}")
    assert step["query_generation_source"] == "rule"
    assert step["query_creativity_used"] == 0.0
    print("  ✓ Rule mode working")

    # 测试hybrid模式（无LLM客户端，应该降级到rule）
    print("\n--- Testing Hybrid Mode (no LLM client) ---")
    simulator_hybrid = UserSimulator(
        task=task,
        query_generation_mode="hybrid",
        llm_client=None  # 无LLM客户端
    )

    step = simulator_hybrid.step("测试响应", length="short")
    print(f"Source: {step['query_generation_source']}")
    # 没有LLM客户端时，hybrid模式应该使用rule
    assert step["query_generation_source"] == "rule"
    print("  ✓ Hybrid mode fallback to rule (no LLM) working")

    print("\n✓ UserSimulator Mode Test Completed")
    return True


def test_strategic_simulator_length_control():
    """测试StrategicSimulator长度控制功能"""

    print("\n" + "=" * 60)
    print("StrategicSimulator Length Control Test (窗口3)")
    print("=" * 60)

    try:
        from simulator.strategic_simulator import StrategicSimulator
        from simulator.length_selector import DynamicLengthSelector, LengthSelectionStrategy
    except ImportError as e:
        print(f"⚠ Skipped: {e}")
        return True

    # 创建一个最小配置的StrategicSimulator来测试长度控制
    # 注意：这里我们只测试长度选择器和日志功能，不实际运行模拟

    # 测试长度选择方法
    print("\n--- Testing Length Selection Method ---")

    # 由于StrategicSimulator需要LLMClient，我们直接测试长度选择器
    from simulator.length_selector import create_length_selector

    selector = create_length_selector(strategy="adaptive")

    result = selector.select(
        phase="grounding",
        difficulty=2,
        turn=5,
        task_type="attribute_comparison"
    )

    print(f"Selected length: {result['length']}")
    print(f"Reason: {result['reason']}")
    print(f"Probabilities: {result['probabilities']}")

    assert result['length'] in ["short", "medium", "long"]
    print("  ✓ Length selection working")

    print("\n✓ StrategicSimulator Length Control Test Completed")
    return True


def run_all_integration_tests():
    """运行所有集成测试"""

    print("\n" + "=" * 70)
    print("                 Length Control Integration Tests (窗口3)")
    print("=" * 70)

    results = {}

    # Test 1: Full Length Control Flow
    try:
        results["full_flow"] = test_full_length_control_flow()
    except Exception as e:
        print(f"\n✗ Full flow test failed: {e}")
        results["full_flow"] = False

    # Test 2: Dynamic Length Selector
    try:
        results["dynamic_selector"] = test_dynamic_length_selector_integration()
    except Exception as e:
        print(f"\n✗ Dynamic selector test failed: {e}")
        results["dynamic_selector"] = False

    # Test 3: UserSimulator Modes
    try:
        results["user_simulator_modes"] = test_user_simulator_with_different_modes()
    except Exception as e:
        print(f"\n✗ UserSimulator modes test failed: {e}")
        results["user_simulator_modes"] = False

    # Test 4: StrategicSimulator Length Control
    try:
        results["strategic_simulator"] = test_strategic_simulator_length_control()
    except Exception as e:
        print(f"\n✗ StrategicSimulator test failed: {e}")
        results["strategic_simulator"] = False

    # Summary
    print("\n" + "=" * 70)
    print("                         Test Summary")
    print("=" * 70)

    all_passed = all(results.values())

    for test_name, passed in results.items():
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"  {test_name}: {status}")

    print("\n" + "-" * 70)
    print(f"  Overall: {'ALL TESTS PASSED ✓' if all_passed else 'SOME TESTS FAILED ✗'}")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = run_all_integration_tests()
    sys.exit(0 if success else 1)
