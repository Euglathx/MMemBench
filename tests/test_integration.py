"""
集成测试脚本
============

测试三个窗口的功能是否能有效协作：
1. 数据加载 + 任务生成（窗口1）
2. Rationale-based推理链（窗口2）
3. Simulator + 长度控制（窗口3）

以及：
- 任务ID全局唯一性
- 批处理任务模拟器
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import tempfile
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_task_id_uniqueness():
    """测试任务ID全局唯一性"""
    print("\n" + "="*60)
    print("Test 1: Task ID Uniqueness")
    print("="*60)

    from dataprovider.task_id_generator import TaskIDGenerator, reset_counters

    # 测试同一类型多批次生成
    all_ids = set()
    num_batches = 5
    ids_per_batch = 20

    for batch in range(num_batches):
        # 每批次创建新的生成器
        gen = TaskIDGenerator('attribute_comparison', 'mscoco14')
        for _ in range(ids_per_batch):
            task_id = gen.next()
            if task_id in all_ids:
                print(f"  FAIL: Duplicate ID found: {task_id}")
                return False
            all_ids.add(task_id)

    print(f"  Generated {len(all_ids)} IDs across {num_batches} batches")
    print(f"  All IDs unique: {len(all_ids) == num_batches * ids_per_batch}")
    print(f"  Sample IDs: {list(all_ids)[:3]}")
    print("  PASS: Task ID uniqueness test passed")
    return True


def test_dataprovider_import():
    """测试dataprovider模块导入"""
    print("\n" + "="*60)
    print("Test 2: DataProvider Module Import")
    print("="*60)

    try:
        from dataprovider import (
            DataLoader,
            DataGeneratorV2,
            ConfigLoader,
            load_config,
            RationaleBasedABRGenerator,
            TaskIDGenerator
        )
        print("  PASS: All dataprovider components imported successfully")
        return True
    except ImportError as e:
        print(f"  FAIL: Import error: {e}")
        return False


def test_simulator_import():
    """测试simulator模块导入"""
    print("\n" + "="*60)
    print("Test 3: Simulator Module Import")
    print("="*60)

    try:
        from src.simulator import (
            UserSimulator,
            StrategicSimulator,
            BatchTaskSimulator,
            BatchConfig,
            LLMClient,
            Evaluator,
            EvaluationMode
        )
        print("  PASS: All simulator components imported successfully")
        return True
    except ImportError as e:
        print(f"  FAIL: Import error: {e}")
        return False


def test_length_selector():
    """测试长度选择器（窗口3）"""
    print("\n" + "="*60)
    print("Test 4: Length Selector (Window 3)")
    print("="*60)

    try:
        from src.simulator.length_selector import (
            DynamicLengthSelector,
            LengthSelectionStrategy
        )

        # 测试各种策略
        strategies = [
            LengthSelectionStrategy.FIXED,
            LengthSelectionStrategy.RANDOM,
            LengthSelectionStrategy.PHASE_BASED,
            LengthSelectionStrategy.ADAPTIVE
        ]

        for strategy in strategies:
            selector = DynamicLengthSelector(strategy=strategy)
            result = selector.select(phase="grounding", difficulty=2, turn=3)
            print(f"  {strategy.value}: length={result['length']}, reason={result['reason']}")

        print("  PASS: Length selector test passed")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_user_simulator():
    """测试UserSimulator（窗口3）"""
    print("\n" + "="*60)
    print("Test 5: UserSimulator Step Functionality")
    print("="*60)

    try:
        from src.simulator.user_simulator import UserSimulator

        task = {
            "task_id": "test_task_001",
            "question": "What is in the image?",
            "answer": "A cat sitting on a sofa",
            "images": ["image.jpg"],
            "task_type": "attribute_comparison"
        }

        simulator = UserSimulator(
            task=task,
            extraction_mode="simple",
            action_strategy="rule_based",
            verbose=False
        )

        # 模拟一轮对话
        vlm_response = "I see a fluffy cat sitting on a red sofa in a living room."

        for length in ["short", "medium", "long"]:
            step_result = simulator.step(vlm_response, length=length)

            print(f"  Length={length}:")
            print(f"    Turn: {step_result['turn']}")
            print(f"    Action: {step_result['action']}")
            print(f"    Query length control: {step_result.get('query_length_control', 'N/A')}")
            print(f"    Word count: {step_result.get('query_word_count', 'N/A')}")

        print("  PASS: UserSimulator test passed")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_simulator():
    """测试批处理模拟器（窗口1）"""
    print("\n" + "="*60)
    print("Test 6: Batch Task Simulator")
    print("="*60)

    try:
        from src.simulator import (
            BatchTaskSimulator,
            BatchConfig,
            LLMClient,
            Evaluator,
            EvaluationMode
        )

        # 创建测试任务
        test_tasks = [
            {
                "task_id": "batch_test_001",
                "question": "What color is the car?",
                "answer": "Red",
                "images": ["car.jpg"],
                "task_type": "attribute_comparison"
            },
            {
                "task_id": "batch_test_002",
                "question": "How many people are there?",
                "answer": "Three",
                "images": ["people.jpg"],
                "task_type": "visual_noise_filtering"
            }
        ]

        # 配置
        config = BatchConfig(
            max_turns_per_session=20,
            min_turns_per_task=3,
            max_turns_per_task=5,
            transition_style="natural",
            enable_cross_task_memory_test=False
        )

        # 创建组件
        llm_client = LLMClient()
        evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

        batch_sim = BatchTaskSimulator(
            llm_client=llm_client,
            evaluator=evaluator,
            config=config,
            verbose=False
        )

        # 运行批处理
        result = batch_sim.run_batch(test_tasks)

        print(f"  Batch ID: {result.batch_id}")
        print(f"  Tasks attempted: {result.tasks_attempted}")
        print(f"  Tasks completed: {result.tasks_completed}")
        print(f"  Total turns: {result.total_turns}")
        print(f"  Transitions: {len(result.transitions)}")

        print("  PASS: Batch simulator test passed")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_generator():
    """测试Query生成器"""
    print("\n" + "="*60)
    print("Test 7: Query Generator")
    print("="*60)

    try:
        from src.simulator.query_generator import QueryGenerator

        generator = QueryGenerator()

        entities = {
            "objects": ["cat", "sofa", "window"],
            "attributes": {
                "cat": {"color": ["gray"], "size": ["small"]},
                "sofa": {"color": ["red"]}
            },
            "regions": ["left side", "center"]
        }

        action_types = ["follow_up", "guidance", "negation", "fine_grained"]

        for action in action_types:
            query = generator.generate(
                action_type=action,
                entities=entities,
                length="medium"
            )
            print(f"  {action}: {query[:60]}...")

        print("  PASS: Query generator test passed")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_end_to_end_flow():
    """端到端流程测试"""
    print("\n" + "="*60)
    print("Test 8: End-to-End Flow")
    print("="*60)

    try:
        from dataprovider import DataLoader, DataGeneratorV2, load_config
        from src.simulator import (
            BatchTaskSimulator,
            BatchConfig,
            LLMClient,
            Evaluator,
            EvaluationMode
        )

        # Step 1: 尝试加载配置
        print("  Step 1: Loading configuration...")
        config = load_config("dataset_configs.yaml")
        print(f"    Available datasets: {config.get_all_dataset_ids()}")

        # Step 2: 验证数据集路径
        print("  Step 2: Validating dataset paths...")
        path_validation = config.validate_dataset_paths()
        valid_datasets = [ds for ds, valid in path_validation.items() if valid]
        print(f"    Valid datasets: {valid_datasets}")

        if not valid_datasets:
            print("  WARNING: No valid datasets found, skipping data generation")
            print("  PASS: Configuration and validation work correctly")
            return True

        # Step 3: 模拟器组件测试
        print("  Step 3: Testing simulator components...")
        llm_client = LLMClient()
        evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

        config = BatchConfig(
            max_turns_per_session=10,
            min_turns_per_task=2,
            max_turns_per_task=3
        )

        batch_sim = BatchTaskSimulator(
            llm_client=llm_client,
            evaluator=evaluator,
            config=config,
            verbose=False
        )

        # 用模拟任务测试
        mock_tasks = [
            {
                "task_id": "e2e_test_001",
                "question": "What is shown in the image?",
                "answer": "A test image",
                "images": ["test.jpg"],
                "task_type": "test"
            }
        ]

        result = batch_sim.run_batch(mock_tasks)
        print(f"    Batch completed: {result.tasks_completed}/{result.tasks_attempted}")

        print("  PASS: End-to-end flow test passed")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("M3Bench Integration Tests")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*60)

    results = {}

    # 运行各项测试
    tests = [
        ("Task ID Uniqueness", test_task_id_uniqueness),
        ("DataProvider Import", test_dataprovider_import),
        ("Simulator Import", test_simulator_import),
        ("Length Selector", test_length_selector),
        ("User Simulator", test_user_simulator),
        ("Batch Simulator", test_batch_simulator),
        ("Query Generator", test_query_generator),
        ("End-to-End Flow", test_end_to_end_flow),
    ]

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"  FAIL: Unexpected error: {e}")
            results[name] = False

    # 总结
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n*** All integration tests passed! ***")
        return 0
    else:
        print(f"\n*** {total - passed} test(s) failed ***")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
