"""
DataGenerator V2: Config-driven task generation for M3Bench
===========================================================
Unified generator that uses dataset_configs.yaml to drive task generation.

Supports:
1. Attribute Bridge Reasoning (ABR)
2. Attribute Comparison (AC) - NEW!
3. Visual Noise Filtering (VNF)
4. Relation Comparison (RC)
"""

import random
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from .config_loader import ConfigLoader
from .task_generators import (
    AttributeComparisonGenerator,
    EnhancedVNFGenerator,
    AttributeBridgeReasoningGenerator,
    RelationComparisonGenerator,
    QADatasetGenerators
)
# 窗口2新增: 基于Rationale的ABR生成器
from .rationale_based_generator import RationaleBasedABRGenerator

logger = logging.getLogger(__name__)


class DataGeneratorV2:
    """Config-driven data generator for M3Bench tasks."""

    def __init__(self, data_loader, config_file: str = "dataset_configs.yaml"):
        """
        Initialize DataGenerator with config support.

        Args:
            data_loader: DataLoader instance
            config_file: Path to dataset configuration file
        """
        self.loader = data_loader
        self.config = ConfigLoader(config_file)

        # Task generator registry
        self.task_generators = {
            # Full names
            'attribute_comparison': self._generate_attribute_comparison,
            'visual_noise_filtering': self._generate_visual_noise_filtering,
            'attribute_bridge_reasoning': self._generate_attribute_bridge_reasoning,
            'relation_comparison': self._generate_relation_comparison,
            # 窗口2新增: 基于Rationale的ABR
            'rationale_based_abr': self._generate_rationale_based_abr,
            # Short names
            'AC': self._generate_attribute_comparison,
            'VNF': self._generate_visual_noise_filtering,
            'ABR': self._generate_attribute_bridge_reasoning,
            'RC': self._generate_relation_comparison,
            'LNF': self._generate_logical_noise_filtering,
            'logical_noise_filtering': self._generate_logical_noise_filtering
        }

    @staticmethod
    def _vcr_tokens_to_text(tokens, objects: List[str]) -> str:
        """
        将 VCR 的 token 列表转换为自然语言文本。

        VCR 数据集使用特殊格式，其中对象引用以整数列表形式嵌入，如：
        ["Does", [2], "feel", "comfortable", "?"]
        其中 [2] 表示 objects[2] 对应的对象。

        Args:
            tokens: VCR 格式的 token 列表
            objects: 对象名称列表（通常来自 sample['objects']）

        Returns:
            转换后的自然语言文本
        """
        if not tokens:
            return ""

        # 如果已经是字符串，直接返回
        if isinstance(tokens, str):
            return tokens

        text_parts = []
        for token in tokens:
            if isinstance(token, str):
                text_parts.append(token)
            elif isinstance(token, list):
                # 对象索引列表，如 [0, 1] 表示 "person1 and person2"
                obj_names = []
                for idx in token:
                    if isinstance(idx, int) and 0 <= idx < len(objects):
                        obj_names.append(objects[idx])
                    else:
                        obj_names.append("someone")
                if len(obj_names) == 1:
                    text_parts.append(obj_names[0])
                elif len(obj_names) == 2:
                    text_parts.append(f"{obj_names[0]} and {obj_names[1]}")
                else:
                    text_parts.append(", ".join(obj_names[:-1]) + f" and {obj_names[-1]}")
            elif isinstance(token, int):
                # 单个整数索引
                if 0 <= token < len(objects):
                    text_parts.append(objects[token])
                else:
                    text_parts.append("someone")
            else:
                text_parts.append(str(token))

        return " ".join(text_parts)

    def generate_task(self,
                     task_type: str,
                     source_dataset: str,
                     num_samples: int = 100,
                     split: str = "train",
                     **kwargs) -> List[Dict[str, Any]]:
        """
        Generate tasks using dataset configuration.

        Args:
            task_type: Task type (e.g., 'attribute_comparison')
            source_dataset: Dataset ID (e.g., 'mscoco14')
            num_samples: Number of samples to generate
            split: Data split to use
            **kwargs: Override config parameters

        Returns:
            List of generated task samples
        """
        # Validate dataset and task
        dataset_config = self.config.get_dataset_config(source_dataset)
        if not dataset_config:
            raise ValueError(f"Unknown dataset: {source_dataset}")

        if not dataset_config.supports_task(task_type):
            logger.warning(f"{source_dataset} does not support {task_type}")
            return []

        if not dataset_config.is_task_enabled(task_type):
            logger.warning(f"{task_type} is disabled for {source_dataset}")
            return []

        # Get task configuration
        task_config = dataset_config.get_task_config(task_type)
        task_config.update(kwargs)  # Allow runtime overrides

        # Get templates
        templates = {
            'question_templates': self.config.get_task_template(task_type, 'question_templates'),
            'answer_template': self.config.get_task_template(task_type, 'answer_template')
        }

        # Load source data
        logger.info(f"Loading {source_dataset} data (split={split})...")
        source_data = self.loader.load_dataset(
            source_dataset,
            split=split,
            max_samples=num_samples * 10  # Load extra for filtering
        )

        if not source_data:
            logger.warning(f"No data loaded from {source_dataset}")
            return []

        # Generate tasks
        generator_func = self.task_generators.get(task_type)
        if not generator_func:
            raise ValueError(f"No generator for task type: {task_type}")

        logger.info(f"Generating {task_type} tasks from {source_dataset}...")
        tasks = generator_func(
            source_dataset,
            source_data,
            num_samples,
            task_config,
            templates
        )
        tasks = [self._attach_state_schema(task) for task in tasks]

        # Apply quality control
        tasks = self._apply_quality_control(tasks, task_type)

        logger.info(f"Generated {len(tasks)} {task_type} tasks from {source_dataset}")
        return tasks

    def generate_all_tasks_for_dataset(self,
                                      dataset_id: str,
                                      num_samples_per_task: int = 10,
                                      split: str = "train") -> Dict[str, List[Dict]]:
        """
        Generate all enabled tasks for a dataset.

        Args:
            dataset_id: Dataset ID
            num_samples_per_task: Samples to generate per task type
            split: Data split

        Returns:
            Dictionary mapping task_type -> List[task_samples]
        """
        dataset_config = self.config.get_dataset_config(dataset_id)
        if not dataset_config:
            logger.error(f"Unknown dataset: {dataset_id}")
            return {}

        all_tasks = {}

        for task_type in dataset_config.supported_tasks:
            if dataset_config.is_task_enabled(task_type):
                try:
                    tasks = self.generate_task(
                        task_type=task_type,
                        source_dataset=dataset_id,
                        num_samples=num_samples_per_task,
                        split=split
                    )
                    if tasks:
                        all_tasks[task_type] = tasks
                except Exception as e:
                    logger.error(f"Failed to generate {task_type} for {dataset_id}: {e}")
                    import traceback
                    traceback.print_exc()

        return all_tasks

    # ==================== Task Generators ====================

    def _generate_attribute_comparison(self,
                                      source_dataset: str,
                                      source_data: List[Dict],
                                      num_samples: int,
                                      task_config: Dict[str, Any],
                                      templates: Dict[str, Any]) -> List[Dict]:
        """Generate Attribute Comparison tasks."""

        if source_dataset == "mscoco14":
            return AttributeComparisonGenerator.generate_from_mscoco(
                source_data, num_samples, task_config, templates
            )
        elif source_dataset == "vcr":
            return AttributeComparisonGenerator.generate_from_vcr(
                source_data, num_samples, task_config, templates
            )
        elif source_dataset == "visual_genome":
            return AttributeComparisonGenerator.generate_from_visual_genome(
                source_data, num_samples, task_config, templates
            )
        elif source_dataset == "scienceqa":
            return QADatasetGenerators.generate_ac_from_scienceqa(
                source_data, num_samples, task_config, templates
            )
        elif source_dataset in ["docvqa", "realworldqa"]:
            return QADatasetGenerators.generate_ac_from_qa(
                source_data, source_dataset, num_samples, task_config, templates
            )
        else:
            # 通用 fallback
            return self._generate_generic_ac(source_dataset, source_data, num_samples, task_config)

    def _generate_visual_noise_filtering(self,
                                        source_dataset: str,
                                        source_data: List[Dict],
                                        num_samples: int,
                                        task_config: Dict[str, Any],
                                        templates: Dict[str, Any]) -> List[Dict]:
        """Generate Visual Noise Filtering tasks."""

        if source_dataset == "mscoco14":
            return EnhancedVNFGenerator.generate_from_mscoco(
                source_data, num_samples, task_config, templates
            )
        elif source_dataset == "vcr":
            return EnhancedVNFGenerator.generate_from_vcr(
                source_data, num_samples, task_config, templates
            )
        elif source_dataset in ["scienceqa", "docvqa", "realworldqa"]:
            return QADatasetGenerators.generate_vnf_from_qa(
                source_data, source_dataset, num_samples, task_config, templates
            )
        else:
            # 通用 fallback
            return self._generate_generic_vnf(source_dataset, source_data, num_samples, task_config)

    def _generate_attribute_bridge_reasoning(self,
                                            source_dataset: str,
                                            source_data: List[Dict],
                                            num_samples: int,
                                            task_config: Dict[str, Any],
                                            templates: Dict[str, Any]) -> List[Dict]:
        """Generate Attribute Bridge Reasoning tasks."""

        # MSCOCO14 专用生成器
        if source_dataset == "mscoco14":
            return AttributeBridgeReasoningGenerator.generate_from_mscoco(
                source_data, num_samples, task_config, templates
            )

        # 使用旧版生成器桥接（VCR, Visual Genome）
        from .generator import DataGenerator as LegacyDataGenerator

        temp_gen = LegacyDataGenerator(self.loader)

        min_hops = task_config.get('min_hops', 2)
        max_hops = task_config.get('max_hops', 3)

        if source_dataset == "vcr":
            return temp_gen._abr_from_vcr(source_data, num_samples, min_hops, max_hops)
        elif source_dataset == "visual_genome":
            return temp_gen._abr_from_visual_genome(source_data, num_samples, min_hops, max_hops)
        else:
            # 通用 fallback（支持 scienceqa, docvqa, realworldqa 等 QA 数据集）
            return self._generate_generic_abr(source_dataset, source_data, num_samples, task_config)

    def _generate_relation_comparison(self,
                                     source_dataset: str,
                                     source_data: List[Dict],
                                     num_samples: int,
                                     task_config: Dict[str, Any],
                                     templates: Dict[str, Any]) -> List[Dict]:
        """Generate Relation Comparison tasks."""

        # MSCOCO14 专用生成器
        if source_dataset == "mscoco14":
            return RelationComparisonGenerator.generate_from_mscoco(
                source_data, num_samples, task_config, templates
            )

        # VCR 专用生成器
        if source_dataset == "vcr":
            return RelationComparisonGenerator.generate_from_vcr(
                source_data, num_samples, task_config, templates
            )

        # 使用旧版生成器桥接（Visual Genome）
        from .generator import DataGenerator as LegacyDataGenerator
        temp_gen = LegacyDataGenerator(self.loader)
        n_images = task_config.get('n_images', 3)

        if source_dataset == "visual_genome":
            return temp_gen._rc_from_visual_genome(source_data, num_samples, n_images)

        # QA数据集专用生成器
        if source_dataset == "scienceqa":
            return QADatasetGenerators.generate_rc_from_scienceqa(
                source_data, num_samples, task_config, templates
            )
        if source_dataset == "docvqa":
            return QADatasetGenerators.generate_rc_from_docvqa(
                source_data, num_samples, task_config, templates
            )
        if source_dataset == "realworldqa":
            return QADatasetGenerators.generate_rc_from_realworldqa(
                source_data, num_samples, task_config, templates
            )

        # 通用 fallback
        return self._generate_generic_rc(source_dataset, source_data, num_samples, task_config)

    # ==================== LNF: Logical Noise Filtering ====================

    def _generate_logical_noise_filtering(self,
                                          source_dataset: str,
                                          source_data: List[Dict],
                                          num_samples: int,
                                          task_config: Dict[str, Any],
                                          templates: Dict[str, Any]) -> List[Dict]:
        """Generate Logical Noise Filtering tasks."""

        if source_dataset == "scienceqa":
            return QADatasetGenerators.generate_lnf_from_scienceqa(
                source_data, num_samples, task_config, templates
            )
        elif source_dataset in ["docvqa", "realworldqa"]:
            if hasattr(QADatasetGenerators, 'generate_lnf_from_qa'):
                return QADatasetGenerators.generate_lnf_from_qa(
                    source_data, source_dataset, num_samples, task_config, templates
                )
            else:
                logger.warning(f"LNF generator for {source_dataset} not fully implemented yet.")
                return []

        logger.warning(f"LNF not supported for {source_dataset}")
        return []

    # ==================== 窗口2新增: Rationale-Based ABR ====================

    def _generate_rationale_based_abr(self,
                                      source_dataset: str,
                                      source_data: List[Dict],
                                      num_samples: int,
                                      task_config: Dict[str, Any],
                                      templates: Dict[str, Any]) -> List[Dict]:
        """
        生成基于Rationale的属性桥接推理任务 (窗口2新增)

        仅支持VCR数据集（具有rationale标注）

        Args:
            source_dataset: 源数据集ID
            source_data: 源数据
            num_samples: 目标样本数
            task_config: 任务配置
            templates: 问题模板

        Returns:
            生成的任务列表
        """
        if source_dataset != "vcr":
            logger.warning(f"Rationale-based ABR only supports VCR dataset, got {source_dataset}")
            return []

        # 验证数据是否包含rationale
        samples_with_rationale = [
            s for s in source_data
            if s.get('rationale_text') or s.get('reasoning_steps')
        ]

        if not samples_with_rationale:
            logger.warning("No VCR samples with rationale found. "
                          "Make sure to load with include_rationale=True")
            return []

        logger.info(f"Generating rationale-based ABR from {len(samples_with_rationale)} VCR samples with rationale")

        # 使用Rationale生成器
        tasks = RationaleBasedABRGenerator.generate_from_vcr(
            source_data=samples_with_rationale,
            num_samples=num_samples,
            task_config=task_config,
            templates=templates
        )

        logger.info(f"Generated {len(tasks)} rationale-based ABR tasks")
        return tasks

    # ==================== Generic Fallback Generators ====================

    @staticmethod
    def _safe_get(data, key, default=None):
        """安全地获取和转换数据，兼容 numpy 类型"""
        val = data.get(key, default)
        if val is None:
            return default
        try:
            import numpy as np
            if isinstance(val, np.ndarray):
                if val.size == 1:
                    return val.item()
                else:
                    return val.tolist()
            elif isinstance(val, (np.integer, np.floating)):
                return val.item()
        except ImportError:
            pass
        if isinstance(val, bytes):
            return val.decode('utf-8', errors='ignore') if len(val) < 1000 else None
        return val

    @staticmethod
    def _build_answer(answer_idx, choices):
        """从 answer index 和 choices 构建答案字符串"""
        try:
            has_choices = isinstance(choices, (list, tuple)) and len(choices) > 0
        except TypeError:
            has_choices = False

        if has_choices:
            try:
                if isinstance(answer_idx, int) and 0 <= answer_idx < len(choices):
                    answer = choices[answer_idx]
                else:
                    answer = str(answer_idx)
            except (TypeError, IndexError):
                answer = str(answer_idx)
        else:
            answer = str(answer_idx)

        # 确保answer是字符串
        if isinstance(answer, (list, tuple)):
            answer = ', '.join(str(a) for a in answer)
        elif isinstance(answer, bytes):
            answer = answer.decode('utf-8', errors='ignore')
        else:
            answer = str(answer)
        return answer, has_choices

    def _generate_generic_ac(self, source_dataset, source_data, num_samples, task_config):
        """通用 Attribute Comparison 生成器（支持各种 QA 数据集）"""
        logger.info(f"Generating attribute comparison tasks for {source_dataset} (generic)")
        samples = []
        comparison_metric = task_config.get('comparison_metric', 'position')

        for i in range(min(num_samples, len(source_data))):
            sample = source_data[i]
            images = self._safe_get(sample, 'image_path')
            if not images:
                continue
            images = [images] if isinstance(images, str) else images

            question = self._safe_get(sample, 'question', 'Compare attributes in this data')
            answer_idx = self._safe_get(sample, 'answer', 0)
            choices = self._safe_get(sample, 'choices', [])
            answer, has_choices = self._build_answer(answer_idx, choices)

            subject = self._safe_get(sample, 'subject', '')
            topic = self._safe_get(sample, 'topic', '')
            category = self._safe_get(sample, 'category', '')
            skill = self._safe_get(sample, 'skill', '')

            task = {
                'task_id': f"ac_{source_dataset}_{len(samples)}",
                'task_type': 'attribute_comparison',
                'images': images,
                'question': question,
                'answer': answer,
                'choices': choices if has_choices else [],
                'reasoning_evidence': {
                    'question': question, 'answer': answer,
                    'choices': choices if has_choices else [],
                    'subject': subject, 'topic': topic,
                    'category': category, 'skill': skill,
                    'comparison_metric': comparison_metric
                },
                'metadata': {
                    'source_dataset': source_dataset,
                    'comparison_metric': comparison_metric,
                    'subject': subject, 'topic': topic,
                    'category': category, 'skill': skill,
                    'grade': self._safe_get(sample, 'grade', '')
                }
            }
            samples.append(task)

        logger.info(f"Generated {len(samples)} attribute comparison tasks from {source_dataset}")
        return samples

    def _generate_generic_vnf(self, source_dataset, source_data, num_samples, task_config):
        """通用 Visual Noise Filtering 生成器"""
        logger.info(f"Generating VNF tasks for {source_dataset} (generic)")
        samples = []

        for i in range(min(num_samples, len(source_data))):
            sample = source_data[i]
            images = self._safe_get(sample, 'image_path')
            if not images:
                continue
            images = [images] if isinstance(images, str) else images

            question = self._safe_get(sample, 'question', 'Identify valid information in this data')
            answer_idx = self._safe_get(sample, 'answer', 0)
            choices = self._safe_get(sample, 'choices', [])
            answer, has_choices = self._build_answer(answer_idx, choices)

            subject = self._safe_get(sample, 'subject', '')
            topic = self._safe_get(sample, 'topic', '')
            category = self._safe_get(sample, 'category', '')

            task = {
                'task_id': f"vnf_{source_dataset}_{len(samples)}",
                'task_type': 'visual_noise_filtering',
                'images': images,
                'question': question,
                'answer': answer,
                'choices': choices if has_choices else [],
                'reasoning_evidence': {
                    'question': question, 'answer': answer,
                    'choices': choices if has_choices else [],
                    'subject': subject, 'topic': topic,
                    'category': category,
                    'noise_level': task_config.get('noise_level', 'moderate')
                },
                'metadata': {
                    'source_dataset': source_dataset,
                    'noise_level': task_config.get('noise_level', 'moderate'),
                    'subject': subject, 'topic': topic,
                    'category': category
                }
            }
            samples.append(task)

        logger.info(f"Generated {len(samples)} VNF tasks from {source_dataset}")
        return samples

    def _generate_generic_abr(self, source_dataset, source_data, num_samples, task_config):
        """通用 Attribute Bridge Reasoning 生成器"""
        min_hops = task_config.get('min_hops', 2)
        max_hops = task_config.get('max_hops', 3)
        samples = []

        for i in range(min(num_samples, len(source_data))):
            sample = source_data[i]
            images = self._safe_get(sample, 'image_path')
            if not images:
                continue
            images = [images] if isinstance(images, str) else images

            # VCR 特殊处理
            if source_dataset == 'vcr':
                objects = sample.get('objects', [])
                raw_question = sample.get('question', [])
                question = self._vcr_tokens_to_text(raw_question, objects)
                raw_answer_choices = sample.get('answer_choices', [])
                choices = [self._vcr_tokens_to_text(c, objects) for c in raw_answer_choices]
                answer_label = sample.get('answer_label', 0)
                if isinstance(answer_label, int) and 0 <= answer_label < len(choices):
                    answer = choices[answer_label]
                else:
                    answer = str(answer_label)
                has_choices = len(choices) > 0
            else:
                question = self._safe_get(sample, 'question', 'What is the relationship in this data?')
                answer_idx = self._safe_get(sample, 'answer', 0)
                choices = self._safe_get(sample, 'choices', [])
                answer, has_choices = self._build_answer(answer_idx, choices)

            subject = self._safe_get(sample, 'subject', '')
            topic = self._safe_get(sample, 'topic', '')
            category = self._safe_get(sample, 'category', '')
            skill = self._safe_get(sample, 'skill', '')

            task = {
                'task_id': f"abr_{source_dataset}_{len(samples)}",
                'task_type': 'attribute_bridge_reasoning',
                'images': images,
                'question': question,
                'answer': answer,
                'choices': choices if has_choices else [],
                'reasoning_evidence': {
                    'question': question, 'answer': answer,
                    'choices': choices if has_choices else [],
                    'subject': subject, 'topic': topic,
                    'category': category, 'skill': skill
                },
                'metadata': {
                    'source_dataset': source_dataset,
                    'min_hops': min_hops, 'max_hops': max_hops,
                    'subject': subject, 'topic': topic,
                    'category': category, 'skill': skill,
                    'grade': self._safe_get(sample, 'grade', '')
                }
            }
            samples.append(task)

        logger.info(f"Generated {len(samples)} ABR tasks from {source_dataset}")
        return samples

    def _generate_generic_rc(self, source_dataset, source_data, num_samples, task_config):
        """通用 Relation Comparison 生成器"""
        n_images = task_config.get('n_images', 3)
        samples = []

        for i in range(min(num_samples, len(source_data))):
            sample = source_data[i]
            images = self._safe_get(sample, 'image_path')
            if not images:
                continue
            images = [images] if isinstance(images, str) else images

            # VCR 特殊处理
            if source_dataset == 'vcr':
                objects = sample.get('objects', [])
                raw_question = sample.get('question', [])
                question = self._vcr_tokens_to_text(raw_question, objects)
                raw_answer_choices = sample.get('answer_choices', [])
                choices = [self._vcr_tokens_to_text(c, objects) for c in raw_answer_choices]
                answer_label = sample.get('answer_label', 0)
                if isinstance(answer_label, int) and 0 <= answer_label < len(choices):
                    answer = choices[answer_label]
                else:
                    answer = str(answer_label)
                has_choices = len(choices) > 0
            else:
                question = self._safe_get(sample, 'question', 'Compare the elements in this data.')
                answer_idx = self._safe_get(sample, 'answer', 0)
                choices = self._safe_get(sample, 'choices', [])
                answer, has_choices = self._build_answer(answer_idx, choices)

            subject = self._safe_get(sample, 'subject', '')
            topic = self._safe_get(sample, 'topic', '')
            category = self._safe_get(sample, 'category', '')
            skill = self._safe_get(sample, 'skill', '')

            task = {
                'task_id': f"rc_{source_dataset}_{len(samples)}",
                'task_type': 'relation_comparison',
                'images': images,
                'question': question,
                'answer': answer,
                'choices': choices if has_choices else [],
                'reasoning_evidence': {
                    'question': question, 'answer': answer,
                    'choices': choices if has_choices else [],
                    'subject': subject, 'topic': topic,
                    'category': category, 'skill': skill,
                    'comparison_type': 'count'
                },
                'metadata': {
                    'source_dataset': source_dataset,
                    'n_images': n_images,
                    'subject': subject, 'topic': topic,
                    'category': category, 'skill': skill,
                    'grade': self._safe_get(sample, 'grade', '')
                }
            }
            samples.append(task)

        logger.info(f"Generated {len(samples)} RC tasks from {source_dataset}")
        return samples

    def _apply_quality_control(self,
                              tasks: List[Dict],
                              task_type: str) -> List[Dict]:
        """Apply quality control filters to generated tasks."""

        qc_rules = self.config.get_quality_rules(task_type)
        if not qc_rules:
            return tasks

        filtered_tasks = []

        for task in tasks:
            # Check reasoning depth
            if 'min_reasoning_depth' in qc_rules:
                min_depth = qc_rules['min_reasoning_depth']
                if task.get('reasoning_depth', 0) < min_depth:
                    continue

            if 'max_reasoning_depth' in qc_rules:
                max_depth = qc_rules['max_reasoning_depth']
                if task.get('reasoning_depth', 999) > max_depth:
                    continue

            # Check required fields
            if 'question' not in task or 'answer' not in task or 'images' not in task:
                logger.warning(f"Task {task.get('task_id')} missing required fields")
                continue

            # Check image paths exist (if configured)
            global_qc = self.config.get_quality_rules()
            if global_qc.get('require_valid_image_path', False):
                all_exist = True
                for img_path in task['images']:
                    if not Path(img_path).exists():
                        logger.debug(f"Image not found: {img_path}")
                        all_exist = False
                        break

                if not all_exist:
                    continue

            filtered_tasks.append(task)

        if len(filtered_tasks) < len(tasks):
            logger.info(f"Quality control: kept {len(filtered_tasks)}/{len(tasks)} tasks")

        return filtered_tasks

    def _apply_quality_control(self,
                              tasks: List[Dict],
                              task_type: str) -> List[Dict]:
        """Apply quality control filters to generated tasks."""

        qc_rules = self.config.get_quality_rules(task_type)
        if not qc_rules:
            return tasks

        filtered_tasks = []

        for task in tasks:
            # Check reasoning depth
            if 'min_reasoning_depth' in qc_rules:
                min_depth = qc_rules['min_reasoning_depth']
                if task.get('reasoning_depth', 0) < min_depth:
                    continue

            if 'max_reasoning_depth' in qc_rules:
                max_depth = qc_rules['max_reasoning_depth']
                if task.get('reasoning_depth', 999) > max_depth:
                    continue

            # Check required fields
            if 'question' not in task or 'answer' not in task or 'images' not in task:
                logger.warning(f"Task {task.get('task_id')} missing required fields")
                continue

            # Check image paths exist (if configured)
            global_qc = self.config.get_quality_rules()
            if global_qc.get('require_valid_image_path', False):
                all_exist = True
                for img_path in task['images']:
                    if not Path(img_path).exists():
                        logger.debug(f"Image not found: {img_path}")
                        all_exist = False
                        break

                if not all_exist:
                    continue

            filtered_tasks.append(task)

        if len(filtered_tasks) < len(tasks):
            logger.info(f"Quality control: kept {len(filtered_tasks)}/{len(tasks)} tasks")

        return filtered_tasks

    @staticmethod
    def _infer_state_var_type(value: Any) -> str:
        """Infer a simple state variable type from a Python value."""
        if isinstance(value, bool):
            return 'boolean'
        if isinstance(value, int):
            return 'integer'
        if isinstance(value, float):
            return 'number'
        if isinstance(value, list):
            return 'list'
        if isinstance(value, dict):
            return 'object'
        return 'string'

    def _add_state_variable(
        self,
        schema: Dict[str, Any],
        name: str,
        value: Any,
        *,
        source: str = 'task',
        relevance: str = 'primary',
        observable_from: Optional[List[str]] = None,
        depends_on: Optional[List[str]] = None,
        description: str = '',
        keywords: Optional[List[str]] = None,
        var_type: Optional[str] = None,
    ) -> None:
        """Add one variable to a schema dict if it has a meaningful value."""
        if value is None or name in schema['variables']:
            return
        if isinstance(value, str) and not value.strip():
            return

        schema['variables'][name] = {
            'value': value,
            'type': var_type or self._infer_state_var_type(value),
            'source': source,
            'relevance': relevance,
            'observable_from': observable_from or [],
            'depends_on': depends_on or [],
            'description': description or name.replace('_', ' '),
            'keywords': keywords or [],
        }

    def _attach_state_schema(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Attach a minimal but non-empty state_schema derived from task evidence."""
        existing_schema = task.get('state_schema')
        if isinstance(existing_schema, dict) and existing_schema.get('variables'):
            return task

        schema = {
            'variables': {},
            'dependencies': {},
            'final_question_variables': [],
            'probing_variables': [],
        }
        final_vars: List[str] = []
        probing_vars: List[str] = []

        def add_var(name: str, value: Any, **kwargs) -> None:
            self._add_state_variable(schema, name, value, **kwargs)

        answer = task.get('answer')
        add_var(
            'expected_answer',
            answer,
            source='task',
            relevance='primary',
            description='Expected final answer for the task',
            keywords=['answer'],
            var_type='answer',
        )
        if 'expected_answer' in schema['variables']:
            final_vars.append('expected_answer')

        answer_image_idx = task.get('answer_image_idx')
        if isinstance(answer_image_idx, int):
            add_var(
                'answer_image_idx',
                answer_image_idx,
                source=f'image_{answer_image_idx}',
                relevance='primary',
                observable_from=[f'image_{answer_image_idx}'],
                description='Index of the image that supports the final answer',
                keywords=[f'image {answer_image_idx}'],
                var_type='index',
            )
            if 'answer_image_idx' in schema['variables']:
                final_vars.append('answer_image_idx')

        target_image_idx = task.get('target_image_idx')
        if isinstance(target_image_idx, int):
            add_var(
                'target_image_idx',
                target_image_idx,
                source=f'image_{target_image_idx}',
                relevance='primary',
                observable_from=[f'image_{target_image_idx}'],
                description='Index of the target image to identify or verify',
                keywords=[f'image {target_image_idx}'],
                var_type='index',
            )
            if 'target_image_idx' in schema['variables']:
                final_vars.append('target_image_idx')

        add_var(
            'task_type',
            task.get('task_type'),
            source='task',
            relevance='auxiliary',
            description='Task type for this benchmark item',
            keywords=[task.get('task_type', '')],
        )
        add_var(
            'reasoning_depth',
            task.get('reasoning_depth'),
            source='task',
            relevance='auxiliary',
            description='Annotated reasoning depth for this task',
            keywords=['reasoning'],
        )
        add_var(
            'comparison_metric',
            task.get('comparison_metric'),
            source='task',
            relevance='primary',
            description='Metric used to compare candidate images',
            keywords=[str(task.get('comparison_metric', ''))],
        )

        comparison_values = task.get('comparison_values')
        if isinstance(comparison_values, list):
            dependency_names = []
            for idx, value in enumerate(comparison_values):
                name = f'image_{idx}_comparison_value'
                add_var(
                    name,
                    value,
                    source=f'image_{idx}',
                    relevance='primary',
                    observable_from=[f'image_{idx}'],
                    description=f'Comparison value extracted from image {idx}',
                    keywords=[f'image {idx}', 'comparison'],
                )
                if name in schema['variables']:
                    probing_vars.append(name)
                    dependency_names.append(name)
            if dependency_names:
                for final_name in ('answer_image_idx', 'target_image_idx'):
                    if final_name in schema['variables']:
                        schema['dependencies'][final_name] = dependency_names

        evidence = task.get('reasoning_evidence')
        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                img_idx = item.get('image_idx')
                source = f'image_{img_idx}' if isinstance(img_idx, int) else 'task'
                observable_from = [source] if source != 'task' else []

                scalar_fields = {
                    'count': 'Object count relevant to the task',
                    'people_count': 'People count relevant to the task',
                    'total_objects': 'Total number of objects in the image',
                }
                for field_name, description in scalar_fields.items():
                    if field_name in item:
                        var_name = f'{source}_{field_name}' if source != 'task' else field_name
                        add_var(
                            var_name,
                            item.get(field_name),
                            source=source,
                            relevance='primary',
                            observable_from=observable_from,
                            description=description,
                            keywords=[field_name.replace('_', ' ')],
                        )
                        if var_name in schema['variables']:
                            probing_vars.append(var_name)

                obj = item.get('object')
                if isinstance(obj, dict):
                    category = obj.get('category')
                    area = obj.get('area')
                    if category:
                        var_name = f'{source}_primary_object_category'
                        add_var(
                            var_name,
                            category,
                            source=source,
                            relevance='primary',
                            observable_from=observable_from,
                            description=f'Primary object category in {source}',
                            keywords=[category],
                        )
                        if var_name in schema['variables']:
                            probing_vars.append(var_name)
                    if area is not None:
                        var_name = f'{source}_primary_object_area'
                        add_var(
                            var_name,
                            area,
                            source=source,
                            relevance='auxiliary',
                            observable_from=observable_from,
                            description=f'Primary object area in {source}',
                            keywords=['area'],
                        )
                        if var_name in schema['variables']:
                            probing_vars.append(var_name)

                objects = item.get('objects')
                if isinstance(objects, list) and objects:
                    categories = []
                    for obj_item in objects:
                        if isinstance(obj_item, dict) and obj_item.get('category'):
                            categories.append(obj_item['category'])
                        elif isinstance(obj_item, str):
                            categories.append(obj_item)
                    if categories:
                        unique_categories = sorted(set(categories))
                        var_name = f'{source}_object_categories'
                        add_var(
                            var_name,
                            unique_categories,
                            source=source,
                            relevance='auxiliary',
                            observable_from=observable_from,
                            description=f'Observed object categories in {source}',
                            keywords=unique_categories[:5],
                            var_type='object_list',
                        )
                        if var_name in schema['variables']:
                            probing_vars.append(var_name)

        elif isinstance(evidence, dict):
            for field_name, description in {
                'subject': 'Main subject discussed by the task',
                'topic': 'Topic of the task',
                'category': 'Category of the task evidence',
                'skill': 'Skill required by the task',
                'noise_level': 'Noise level configured for the task',
                'comparison_metric': 'Comparison metric from evidence',
            }.items():
                var_name = f'evidence_{field_name}'
                add_var(
                    var_name,
                    evidence.get(field_name),
                    source='task',
                    relevance='auxiliary',
                    description=description,
                    keywords=[str(evidence.get(field_name, ''))],
                )
                if var_name in schema['variables']:
                    probing_vars.append(var_name)

        formal = task.get('formal_representation')
        if isinstance(formal, dict):
            objects = formal.get('objects')
            attributes = formal.get('attributes')
            relations = formal.get('relations')
            add_var(
                'formal_objects_total',
                len(objects) if isinstance(objects, dict) else None,
                source='task',
                relevance='auxiliary',
                description='Number of objects in formal representation',
                keywords=['objects'],
            )
            add_var(
                'formal_relations_total',
                len(relations) if isinstance(relations, list) else None,
                source='task',
                relevance='auxiliary',
                description='Number of relations in formal representation',
                keywords=['relations'],
            )
            add_var(
                'formal_attributes_total',
                len(attributes) if isinstance(attributes, dict) else None,
                source='task',
                relevance='auxiliary',
                description='Number of attribute groups in formal representation',
                keywords=['attributes'],
            )
            for var_name in ('formal_objects_total', 'formal_relations_total', 'formal_attributes_total'):
                if var_name in schema['variables']:
                    probing_vars.append(var_name)

        metadata = task.get('metadata')
        if isinstance(metadata, dict):
            add_var(
                'source_dataset',
                metadata.get('source_dataset'),
                source='task',
                relevance='auxiliary',
                description='Source dataset identifier',
                keywords=[str(metadata.get('source_dataset', ''))],
            )

        if not probing_vars:
            probing_vars = [name for name in schema['variables'] if name not in final_vars][:3]

        schema['final_question_variables'] = list(dict.fromkeys(final_vars))
        schema['probing_variables'] = list(dict.fromkeys(probing_vars))
        task['state_schema'] = schema
        return task

    def get_supported_datasets(self, task_type: Optional[str] = None) -> List[str]:
        """Get datasets that support a specific task type."""
        if task_type:
            return self.config.get_datasets_supporting_task(task_type)
        return self.config.get_all_dataset_ids()

    def get_supported_tasks(self, dataset_id: Optional[str] = None) -> List[str]:
        """Get supported task types for a dataset."""
        if dataset_id:
            dataset_config = self.config.get_dataset_config(dataset_id)
            if dataset_config:
                return dataset_config.supported_tasks
            return []
        return self.config.get_supported_tasks()

    def save_generated_tasks(self, tasks: List[Dict], output_path: str) -> None:
        """Save generated tasks to file in JSONL format."""
        import json

        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write tasks in JSONL format
        with open(output_path, 'w', encoding='utf-8') as f:
            for task in tasks:
                json.dump(task, f, ensure_ascii=False)
                f.write('\n')

        logger.info(f"Saved {len(tasks)} tasks to {output_path}")


# Backward compatibility: keep original DataGenerator interface
class DataGenerator(DataGeneratorV2):
    """Backward compatible DataGenerator using V2 implementation."""
    pass
