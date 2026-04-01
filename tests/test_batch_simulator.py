"""
BatchTaskSimulator 集成测试
===========================

测试批处理任务模拟器的各项功能。

运行方法:
    python -m pytest tests/test_batch_simulator.py -v
    python tests/test_batch_simulator.py  # 直接运行
"""

import unittest
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator import (
    BatchTaskSimulator,
    BatchConfig,
    BatchResult,
    LLMClient,
    Evaluator,
    EvaluationMode,
    StateAwareEvaluator,
)


class TestBatchConfig(unittest.TestCase):
    """测试BatchConfig配置类"""

    def test_default_config(self):
        """测试默认配置创建"""
        config = BatchConfig()

        self.assertEqual(config.max_turns_per_session, 50)
        self.assertEqual(config.min_turns_per_task, 8)
        self.assertEqual(config.max_turns_per_task, 15)
        self.assertEqual(config.transition_style, "natural")
        self.assertTrue(config.enable_cross_task_memory_test)
        self.assertEqual(config.cross_task_memory_interval, 3)

    def test_custom_config(self):
        """测试自定义配置"""
        config = BatchConfig(
            max_turns_per_session=30,
            min_turns_per_task=5,
            max_turns_per_task=10,
            transition_style="contextual",
            enable_cross_task_memory_test=False
        )

        self.assertEqual(config.max_turns_per_session, 30)
        self.assertEqual(config.min_turns_per_task, 5)
        self.assertEqual(config.max_turns_per_task, 10)
        self.assertEqual(config.transition_style, "contextual")
        self.assertFalse(config.enable_cross_task_memory_test)

    def test_window3_integration_fields(self):
        """测试窗口3集成接口字段"""
        config = BatchConfig()

        # 检查窗口3集成字段的默认值
        self.assertEqual(config.query_generation_mode, "rule")
        self.assertEqual(config.creativity_level, 0.5)
        self.assertEqual(config.length_selection_strategy, "adaptive")
        self.assertFalse(config.enable_stateful_runtime)
        self.assertFalse(config.require_state_schema)


class TestBatchResult(unittest.TestCase):
    """测试BatchResult结果类"""

    def test_result_to_dict(self):
        """测试结果转换为字典"""
        from datetime import datetime

        result = BatchResult(
            batch_id="test_batch_001",
            start_time=datetime.now(),
            tasks_attempted=4,
            tasks_completed=3,
            total_turns=30
        )

        result_dict = result.to_dict()

        self.assertEqual(result_dict['batch_id'], "test_batch_001")
        self.assertEqual(result_dict['tasks_attempted'], 4)
        self.assertEqual(result_dict['tasks_completed'], 3)
        self.assertEqual(result_dict['total_turns'], 30)
        self.assertIn('start_time', result_dict)

    def test_result_with_transitions(self):
        """测试带过渡记录的结果"""
        from datetime import datetime
        from src.simulator.batch_task_simulator import TaskTransition

        result = BatchResult(
            batch_id="test_batch_002",
            start_time=datetime.now()
        )

        result.transitions.append(TaskTransition(
            from_task_id="task_1",
            to_task_id="task_2",
            transition_message="下一个任务",
            turn_number=10,
            transition_style="natural"
        ))

        result_dict = result.to_dict()

        self.assertEqual(len(result_dict['transitions']), 1)
        self.assertEqual(result_dict['transitions'][0]['from_task'], "task_1")
        self.assertEqual(result_dict['transitions'][0]['to_task'], "task_2")


class TestBatchTaskSimulator(unittest.TestCase):
    """测试BatchTaskSimulator类"""

    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.llm_client = LLMClient()
        cls.evaluator = Evaluator(mode=EvaluationMode.LENIENT)

        # 加载测试任务
        cls.test_tasks = cls._load_test_tasks()

    @staticmethod
    def _load_test_tasks():
        """加载测试任务"""
        # 首先尝试从生成的任务文件加载
        task_files = list(Path("generated_tasks_v2").rglob("*.jsonl"))

        tasks = []
        for f in task_files[:1]:  # 只取第一个文件
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    for line in fp:
                        if line.strip():
                            tasks.append(json.loads(line))
                            if len(tasks) >= 8:
                                break
            except Exception:
                continue
            if len(tasks) >= 8:
                break

        # 如果没有找到任务文件，使用模拟任务
        if not tasks:
            tasks = [
                {
                    'task_id': f'test_task_{i}',
                    'task_type': 'attribute_comparison',
                    'question': f'这是测试问题 {i}',
                    'answer': f'这是测试答案 {i}',
                    'images': [f'test_image_{i}.jpg']
                }
                for i in range(8)
            ]

        return tasks

    def test_simulator_creation(self):
        """测试模拟器创建"""
        config = BatchConfig()
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config
        )

        self.assertIsNotNone(simulator)
        self.assertEqual(simulator.config.max_turns_per_session, 50)

    def test_simulator_creation_with_custom_config(self):
        """测试使用自定义配置创建模拟器"""
        config = BatchConfig(
            max_turns_per_session=30,
            min_turns_per_task=5
        )

        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config,
            verbose=False
        )

        self.assertEqual(simulator.config.max_turns_per_session, 30)
        self.assertEqual(simulator.config.min_turns_per_task, 5)
        self.assertFalse(simulator.verbose)

    def test_transition_generation(self):
        """测试过渡生成"""
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            verbose=False
        )

        if len(self.test_tasks) >= 2:
            # 测试natural风格
            transition = simulator._generate_transition(
                from_task=self.test_tasks[0],
                to_task=self.test_tasks[1],
                style="natural"
            )

            self.assertIsNotNone(transition.transition_message)
            self.assertTrue(len(transition.transition_message) > 0)
            self.assertEqual(transition.transition_style, "natural")

            # 测试contextual风格
            transition_contextual = simulator._generate_transition(
                from_task=self.test_tasks[0],
                to_task=self.test_tasks[1],
                style="contextual"
            )

            self.assertEqual(transition_contextual.transition_style, "contextual")

            # 测试abrupt风格
            transition_abrupt = simulator._generate_transition(
                from_task=self.test_tasks[0],
                to_task=self.test_tasks[1],
                style="abrupt"
            )

            self.assertEqual(transition_abrupt.transition_style, "abrupt")

    def test_small_batch(self):
        """测试小批量运行"""
        if len(self.test_tasks) < 2:
            self.skipTest("Not enough test tasks")

        config = BatchConfig(
            max_turns_per_session=20,
            min_turns_per_task=3,
            max_turns_per_task=5,
            enable_cross_task_memory_test=False
        )

        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config,
            verbose=False
        )

        result = simulator.run_batch(self.test_tasks[:2])

        self.assertIsNotNone(result)
        self.assertEqual(result.tasks_attempted, 2)
        self.assertGreater(result.total_turns, 0)
        self.assertIsNotNone(result.batch_id)
        self.assertIsNotNone(result.start_time)
        self.assertIsNotNone(result.end_time)

    def test_batch_with_memory_test(self):
        """测试带跨任务记忆测试的批处理"""
        if len(self.test_tasks) < 4:
            self.skipTest("Not enough test tasks")

        config = BatchConfig(
            max_turns_per_session=40,
            min_turns_per_task=3,
            max_turns_per_task=5,
            enable_cross_task_memory_test=True,
            cross_task_memory_interval=2  # 每2个任务测试一次
        )

        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config,
            verbose=False
        )

        result = simulator.run_batch(self.test_tasks[:4])

        self.assertIsNotNone(result)
        self.assertEqual(result.tasks_attempted, 4)
        # 应该有至少一次跨任务记忆测试
        # (取决于实际完成的任务数)

    def test_batch_transitions(self):
        """测试批处理中的任务过渡"""
        if len(self.test_tasks) < 3:
            self.skipTest("Not enough test tasks")

        config = BatchConfig(
            max_turns_per_session=30,
            min_turns_per_task=3,
            max_turns_per_task=5,
            transition_style="natural"
        )

        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config,
            verbose=False
        )

        result = simulator.run_batch(self.test_tasks[:3])

        # 应该有2个过渡（3个任务之间）
        self.assertEqual(len(result.transitions), 2)

    def test_aggregate_scores(self):
        """测试聚合分数计算"""
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            verbose=False
        )

        per_dimension = simulator._build_empty_official_per_dimension()
        per_dimension['correctness'] = {'score': 0.8, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}
        per_dimension['faithfulness'] = {'score': 0.9, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}
        per_dimension['robustness'] = {'score': 0.7, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}
        per_dimension['overall'] = {'score': 0.8, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}

        per_dimension_2 = simulator._build_empty_official_per_dimension()
        per_dimension_2['correctness'] = {'score': 0.9, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}
        per_dimension_2['faithfulness'] = {'score': 0.85, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}
        per_dimension_2['robustness'] = {'score': 0.8, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}
        per_dimension_2['overall'] = {'score': 0.85, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'}

        task_results = [
            {
                'task_id': 'test_1',
                'completed': True,
                'task_validity': {'status': 'valid'},
                'official_report': {
                    'included': True,
                    'excluded_reason': None,
                    'aggregate': {'overall': 0.8, 'turn_count_valid': 1, 'total_turns': 1, 'per_dimension': per_dimension},
                    'per_dimension': per_dimension,
                    'overall': 0.8,
                    'task_count_valid': 1,
                    'turn_count_valid': 1,
                    'turn_count_total': 1,
                    'invalid_sample_summary': {'invalid_task_count': 0, 'invalid_turn_count': 0, 'excluded_reasons': {}},
                }
            },
            {
                'task_id': 'test_2',
                'completed': True,
                'task_validity': {'status': 'valid'},
                'official_report': {
                    'included': True,
                    'excluded_reason': None,
                    'aggregate': {'overall': 0.85, 'turn_count_valid': 1, 'total_turns': 1, 'per_dimension': per_dimension_2},
                    'per_dimension': per_dimension_2,
                    'overall': 0.85,
                    'task_count_valid': 1,
                    'turn_count_valid': 1,
                    'turn_count_total': 1,
                    'invalid_sample_summary': {'invalid_task_count': 0, 'invalid_turn_count': 0, 'excluded_reasons': {}},
                }
            }
        ]

        aggregate = simulator._calculate_aggregate_scores(task_results)

        self.assertIn('per_dimension', aggregate)
        self.assertAlmostEqual(aggregate['per_dimension']['correctness']['score'], 0.85, places=2)
        self.assertAlmostEqual(aggregate['per_dimension']['faithfulness']['score'], 0.875, places=2)
        self.assertAlmostEqual(aggregate['per_dimension']['robustness']['score'], 0.75, places=2)

    def test_invalid_without_schema_when_required(self):
        """require_state_schema=True 时缺少 schema 应直接 invalid"""
        config = BatchConfig(
            enable_stateful_runtime=True,
            require_state_schema=True,
            enable_cross_task_memory_test=False,
        )
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=StateAwareEvaluator(mode=EvaluationMode.LENIENT),
            config=config,
            verbose=False,
        )

        task_report, turns_used = simulator._run_single_task_in_batch(
            task={
                'task_id': 'missing_schema_task',
                'task_type': 'attribute_comparison',
                'question': 'q',
                'answer': 'a',
                'images': [],
            },
            task_index=0,
            is_first=True,
            is_last=True,
        )

        self.assertEqual(turns_used, 0)
        self.assertFalse(task_report['completed'])
        self.assertFalse(task_report['state_eval_valid'])
        self.assertEqual(task_report['state_eval_invalid_reason'], 'missing_state_schema')
        self.assertIn('state_report', task_report)
        self.assertEqual(task_report['state_report']['evaluator_state']['status'], 'invalid')

    def test_degraded_without_schema_when_not_required(self):
        """stateful runtime 开启但不强制 schema 时，缺少 schema 应明确 degraded"""
        config = BatchConfig(
            enable_stateful_runtime=True,
            require_state_schema=False,
            enable_cross_task_memory_test=False,
        )
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=StateAwareEvaluator(mode=EvaluationMode.LENIENT),
            config=config,
            verbose=False,
        )

        task_report, turns_used = simulator._run_single_task_in_batch(
            task={
                'task_id': 'legacy_mode_task',
                'task_type': 'attribute_comparison',
                'question': 'q',
                'answer': 'a',
                'images': [],
            },
            task_index=0,
            is_first=True,
            is_last=True,
        )

        self.assertEqual(turns_used, 0)
        self.assertFalse(task_report['completed'])
        self.assertTrue(task_report['state_eval_valid'])
        self.assertTrue(task_report['state_eval_degraded'])
        self.assertTrue(task_report['state_schema_present'] is False)
        self.assertIsNone(task_report['state_eval_invalid_reason'])
        self.assertEqual(task_report['state_report']['evaluator_state']['status'], 'degraded_legacy_mode')

    def test_aggregate_excludes_non_valid_task_validity(self):
        """aggregate 只统计 task_validity.status=valid 的任务"""
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            verbose=False
        )

        task_results = [
            {
                'task_id': 'valid_task',
                'completed': True,
                'task_validity': {'status': 'valid'},
                'official_report': {
                    'included': True,
                    'excluded_reason': None,
                    'aggregate': {
                        'overall': 0.8,
                        'turn_count_valid': 2,
                        'total_turns': 2,
                        'per_dimension': {
                            'correctness': {'score': 0.8, 'support': 2, 'applicable': True, 'reason': 'applicable_only_mean'},
                            'faithfulness': {'score': 0.9, 'support': 2, 'applicable': True, 'reason': 'applicable_only_mean'},
                            'robustness': {'score': 0.7, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                            'consistency': {'score': 0.8, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                            'memory_retention': {'score': 0.75, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                            'cross_image_disambiguation': {'score': None, 'support': 0, 'applicable': False, 'reason': 'not_measured'},
                            'ambiguity_recognition': {'score': None, 'support': 0, 'applicable': False, 'reason': 'not_measured'},
                            'overall': {'score': 0.8, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                        },
                    },
                    'per_dimension': {
                        'correctness': {'score': 0.8, 'support': 2, 'applicable': True, 'reason': 'applicable_only_mean'},
                        'faithfulness': {'score': 0.9, 'support': 2, 'applicable': True, 'reason': 'applicable_only_mean'},
                        'robustness': {'score': 0.7, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                        'consistency': {'score': 0.8, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                        'memory_retention': {'score': 0.75, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                        'cross_image_disambiguation': {'score': None, 'support': 0, 'applicable': False, 'reason': 'not_measured'},
                        'ambiguity_recognition': {'score': None, 'support': 0, 'applicable': False, 'reason': 'not_measured'},
                        'overall': {'score': 0.8, 'support': 1, 'applicable': True, 'reason': 'applicable_only_mean'},
                    },
                    'overall': 0.8,
                    'task_count_valid': 1,
                    'turn_count_valid': 2,
                    'turn_count_total': 2,
                    'invalid_sample_summary': {'invalid_task_count': 0, 'invalid_turn_count': 0, 'excluded_reasons': {}},
                },
            },
            {
                'task_id': 'excluded_task',
                'completed': True,
                'task_validity': {'status': 'excluded_unverified_delivery'},
                'official_report': {
                    'included': False,
                    'excluded_reason': 'excluded_unverified_delivery',
                    'aggregate': {'overall': None, 'turn_count_valid': 0, 'total_turns': 2, 'per_dimension': simulator._build_empty_official_per_dimension()},
                    'per_dimension': simulator._build_empty_official_per_dimension(),
                    'overall': None,
                    'task_count_valid': 0,
                    'turn_count_valid': 0,
                    'turn_count_total': 2,
                    'invalid_sample_summary': {'invalid_task_count': 1, 'invalid_turn_count': 2, 'excluded_reasons': {'excluded_unverified_delivery': 1}},
                },
            },
            {
                'task_id': 'legacy_task',
                'completed': True,
                'task_validity': {'status': 'legacy_unverified'},
                'official_report': {
                    'included': False,
                    'excluded_reason': 'legacy_unverified',
                    'aggregate': {'overall': None, 'turn_count_valid': 0, 'total_turns': 1, 'per_dimension': simulator._build_empty_official_per_dimension()},
                    'per_dimension': simulator._build_empty_official_per_dimension(),
                    'overall': None,
                    'task_count_valid': 0,
                    'turn_count_valid': 0,
                    'turn_count_total': 1,
                    'invalid_sample_summary': {'invalid_task_count': 1, 'invalid_turn_count': 1, 'excluded_reasons': {'legacy_unverified': 1}},
                },
            },
        ]

        aggregate = simulator._calculate_aggregate_scores(task_results)
        self.assertEqual(aggregate['task_count_valid'], 1)
        self.assertAlmostEqual(aggregate['per_dimension']['correctness']['score'], 0.8, places=2)
        self.assertEqual(aggregate['invalid_sample_summary']['task_count_excluded_unverified_delivery'], 1)
        self.assertEqual(aggregate['invalid_sample_summary']['task_count_legacy_unverified'], 1)

    def test_run_batch_counts_only_formally_valid_completed_tasks(self):
        """tasks_completed 只统计 completed 且 task_validity=valid 的任务"""
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            verbose=False
        )

        reports = [
            ({'task_id': 't1', 'completed': True, 'state_eval_valid': True, 'task_validity': {'status': 'valid'}, 'official_report': {'included': True, 'excluded_reason': None, 'aggregate': {'overall': 0.9, 'turn_count_valid': 1, 'total_turns': 1, 'per_dimension': simulator._build_empty_official_per_dimension()}, 'per_dimension': simulator._build_empty_official_per_dimension(), 'overall': 0.9, 'task_count_valid': 1, 'turn_count_valid': 1, 'turn_count_total': 1, 'invalid_sample_summary': {'invalid_task_count': 0, 'invalid_turn_count': 0, 'excluded_reasons': {}}}}, 1),
            ({'task_id': 't2', 'completed': True, 'state_eval_valid': True, 'task_validity': {'status': 'excluded_unverified_delivery'}, 'official_report': {'included': False, 'excluded_reason': 'excluded_unverified_delivery', 'aggregate': {'overall': None, 'turn_count_valid': 0, 'total_turns': 1, 'per_dimension': simulator._build_empty_official_per_dimension()}, 'per_dimension': simulator._build_empty_official_per_dimension(), 'overall': None, 'task_count_valid': 0, 'turn_count_valid': 0, 'turn_count_total': 1, 'invalid_sample_summary': {'invalid_task_count': 1, 'invalid_turn_count': 1, 'excluded_reasons': {'excluded_unverified_delivery': 1}}}}, 1),
        ]

        original = simulator._run_single_task_in_batch
        try:
            simulator._run_single_task_in_batch = lambda **kwargs: reports.pop(0)
            result = simulator.run_batch([
                {'task_id': 't1', 'task_type': 'attribute_comparison'},
                {'task_id': 't2', 'task_type': 'attribute_comparison'},
            ])
        finally:
            simulator._run_single_task_in_batch = original

        self.assertEqual(result.tasks_completed, 1)
        self.assertEqual(len(result.task_results), 2)
        self.assertEqual(result.batch_validity_summary['task_count_valid'], 1)
        self.assertEqual(result.batch_validity_summary['task_count_excluded_unverified_delivery'], 1)


    def test_empty_batch(self):
        """测试空批次处理"""
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            verbose=False
        )

        result = simulator.run_batch([])

        self.assertEqual(result.tasks_attempted, 0)
        self.assertEqual(result.tasks_completed, 0)
        self.assertEqual(result.total_turns, 0)
        self.assertEqual(result.batch_validity_summary['task_count_total'], 0)

    def test_max_turns_limit(self):
        """测试最大轮数限制"""
        if len(self.test_tasks) < 4:
            self.skipTest("Not enough test tasks")

        config = BatchConfig(
            max_turns_per_session=15,  # 严格限制
            min_turns_per_task=5,
            max_turns_per_task=10
        )

        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config,
            verbose=False
        )

        result = simulator.run_batch(self.test_tasks[:4])

        # 总轮数不应超过限制
        self.assertLessEqual(result.total_turns, config.max_turns_per_session)


class TestBatchResultSerialization(unittest.TestCase):
    """测试BatchResult的序列化功能"""

    def test_result_json_serializable(self):
        """测试结果可以序列化为JSON"""
        from datetime import datetime

        result = BatchResult(
            batch_id="test_batch",
            start_time=datetime.now(),
            tasks_attempted=3,
            tasks_completed=2,
            total_turns=25
        )
        result.end_time = datetime.now()
        result.aggregate_scores = {
            'correctness': 0.85,
            'overall': 0.82
        }

        # 转换为字典
        result_dict = result.to_dict()

        # 尝试JSON序列化
        try:
            json_str = json.dumps(result_dict)
            self.assertTrue(len(json_str) > 0)

            # 反序列化验证
            parsed = json.loads(json_str)
            self.assertEqual(parsed['batch_id'], "test_batch")
            self.assertEqual(parsed['tasks_completed'], 2)

        except (TypeError, ValueError) as e:
            self.fail(f"JSON序列化失败: {e}")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
