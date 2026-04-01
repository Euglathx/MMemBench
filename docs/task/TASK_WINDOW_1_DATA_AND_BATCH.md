# 窗口1: 数据生成修复 + 任务批处理实现

> **目标**: 修复多数据集生成问题，实现任务批处理以延长对话轮数
> **预计工时**: 4-5小时
> **依赖**: 无外部依赖，可独立开发

---

## 🌐 项目背景与整体架构

### M3Bench 是什么

M3Bench 是一个**多轮多模态对话能力评测框架**，用于测试视觉语言模型（VLM）在长上下文对话中的推理、记忆、鲁棒性等能力。其核心思路是：

1. **数据层**：从多个视觉数据集（MSCOCO、VCR、Visual Genome 等）中加载图-文对
2. **任务生成层**：从数据中自动生成多种推理任务（属性对比、桥式推理、噪声过滤、关系对比等）
3. **模拟器层**：运行一个"用户模拟器（User Simulator）"与被测VLM进行多轮对话
4. **评估层**：对每轮对话进行7维度评估（正确性、忠实性、鲁棒性、一致性、记忆保持、跨图区分、歧义识别）

### 端到端数据流

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          M3Bench 端到端流程                              │
│                                                                          │
│  ┌─────────┐    ┌──────────┐    ┌───────────────┐    ┌──────────────┐   │
│  │ 原始数据 │───>│ 任务生成  │───>│ Simulator运行  │───>│ 评估 & 报告  │   │
│  │ 集加载   │    │ (JSONL)  │    │ (多轮对话)     │    │ (7维度评分)  │   │
│  └─────────┘    └──────────┘    └───────────────┘    └──────────────┘   │
│       ▲               ▲                ▲                    ▲           │
│   窗口1-前半      窗口2产出         窗口1-后半            窗口2,3        │
│   (数据加载)    (VCR rationale    (BatchSimulator)    (推理链评估,     │
│                  任务生成)                              长度/prompt)    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 三个并行窗口的关系

本次改进被拆分为三个可并行开发的窗口，各自侧重不同层面：

| 窗口 | 侧重层面 | 核心改进 | 本窗口输出供谁使用 |
|------|----------|----------|-------------------|
| **窗口1 (本文档)** | 数据层 + 运行层 | 修复数据集生成 + 批处理长对话 | 生成的任务JSONL → 窗口2、3的测试用例 |
| **窗口2** | 数据层 + 评估层 | VCR rationale → 推理链任务 + 推理链评估 | 推理链任务 → 窗口1批处理调度 |
| **窗口3** | 模拟器层 | LLM驱动Query生成 + 长度控制 | 增强的UserSimulator → 窗口1批处理调用 |

### 本窗口在整体中的位置

**窗口1是基础设施窗口**：它解决两个核心问题——

1. **上游问题**：很多数据集虽然在配置中声明了 `enabled: true`，但实际生成脚本中硬编码只处理了2个数据集，导致任务来源单一
2. **下游问题**：当前每个任务独立运行5-6轮，总轮数不足30轮，无法充分测试VLM的长上下文能力

窗口1的产出（更多数据集的任务JSONL + BatchTaskSimulator）为窗口2、3提供了运行基础。

---

## 🔗 跨窗口协作规范

### 本窗口的输入来源

| 输入 | 来源 | 说明 |
|------|------|------|
| `dataset_configs.yaml` | 已有 | 数据集配置，定义每个数据集的路径和支持的任务类型 |
| `dataprovider/generator_v2.py` | 已有 | 任务生成器，根据配置生成不同类型的任务 |
| `src/simulator/strategic_simulator.py` | 已有 | 当前的单任务模拟器，BatchTaskSimulator将调用它 |

### 本窗口的输出（供其他窗口使用）

#### 1. 生成的任务JSONL文件 → 供窗口2、3测试

**文件格式约定**: `generated_tasks_v2/run_{N}/tasks/{task_type}_{dataset_id}.jsonl`

每行一个JSON对象，必须包含以下字段：

```python
{
    "task_id": str,           # 全局唯一，格式: "{task_type}_{dataset_id}_{index}"
    "task_type": str,         # "attribute_comparison" | "attribute_bridge_reasoning" | ...
    "images": List[str],      # 图片相对路径列表
    "question": str,          # 任务问题
    "answer": str,            # 期望答案
    "metadata": Dict,         # 源数据集信息

    # 可选（窗口2会用到）
    "reasoning_chain": List[str],    # 推理链步骤
    "reasoning_depth": int,          # 推理深度
    "ground_truth_rationale": str    # VCR的rationale原文
}
```

> **协作约定**: 窗口2会往 `reasoning_chain` 和 `ground_truth_rationale` 字段写入VCR推理链数据。本窗口的加载逻辑需要能处理这些字段的有/无两种情况。

#### 2. BatchTaskSimulator → 供窗口2、3的推理链和长度控制使用

```python
# BatchTaskSimulator 调用 StrategicSimulator 时的接口约定
class BatchTaskSimulator:
    def _run_single_task_in_batch(self, task, ...):
        """
        内部创建 StrategicSimulator 实例来运行单个任务。

        窗口2的推理链测试: StrategicSimulator 检查 task 中是否有
        'reasoning_chain' 字段，如果有则进入推理链测试模式。

        窗口3的长度控制: StrategicSimulator 内部使用
        DynamicLengthSelector 选择每轮的长度，无需本窗口额外处理。
        """
        simulator = StrategicSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            # 窗口3的增强：这里可以传入 query_generation_mode
            # 但本窗口不直接处理，留给窗口3集成
        )
        return simulator.run_task(task)
```

### 与窗口2的协作细节

```
窗口1 生成任务                    窗口2 增强任务
─────────────                    ──────────────
generate_all_tasks_v2.py         VCR加载器增强
       │                                │
       ▼                                ▼
{task_id, images,                {reasoning_chain,
 question, answer}                ground_truth_rationale}
       │                                │
       └──────── 合并到同一 JSONL ────────┘
                      │
                      ▼
              BatchTaskSimulator (窗口1)
                      │
                      ├─── 普通任务: 正常多轮对话
                      └─── 推理链任务: 调用 StrategicSimulator
                           的推理链模式 (窗口2实现)
```

**关键约定**:
- 窗口1的 `BatchTaskSimulator.run_batch()` 接收的 `tasks` 列表中，如果某个 task 含有 `reasoning_chain` 字段，表示这是窗口2生成的推理链任务
- `BatchTaskSimulator` 本身**不区分**任务是否含推理链，它只是将每个 task 交给 `StrategicSimulator.run_task()`
- 推理链任务的特殊处理逻辑由**窗口2在 StrategicSimulator 中实现**

### 与窗口3的协作细节

```
窗口3 改进Simulator                窗口1 批处理
──────────────────                ──────────────
LLMQueryGenerator                BatchTaskSimulator
DynamicLengthSelector                    │
       │                                 │
       ▼                                 ▼
UserSimulator 增强参数:          创建 StrategicSimulator 时
  query_generation_mode          可传入窗口3的增强参数
  llm_client                     (或使用默认值)
  creativity_level
```

**关键约定**:
- 窗口3修改的 `UserSimulator` 和 `StrategicSimulator` 参数均有**默认值**，窗口1不传这些参数时行为不变
- 窗口1的 `BatchTaskSimulator` 可选地接受一个 `simulator_kwargs` 字典，透传给 `StrategicSimulator`
- 合并时只需在 `BatchConfig` 中增加可选字段即可：

```python
@dataclass
class BatchConfig:
    # ... 现有字段 ...

    # 窗口3的集成接口（合并后启用）
    query_generation_mode: str = "rule"      # 默认rule，窗口3合并后可改为"hybrid"
    creativity_level: float = 0.5            # 默认0.5
    length_selection_strategy: str = "adaptive"  # 默认adaptive
```

### 合并顺序建议

```
阶段1: 三个窗口各自独立开发（互不干扰）
          │
阶段2: 窗口1 + 窗口2 合并
          │  - 将窗口2的VCR rationale任务放入窗口1的生成管线
          │  - 将窗口2的推理链模式集成到StrategicSimulator
          │  - 验证: BatchTaskSimulator 能正确调度推理链任务
          │
阶段3: 合并结果 + 窗口3 合并
          │  - 将窗口3的LLMQueryGenerator集成到UserSimulator
          │  - 将窗口3的DynamicLengthSelector集成到StrategicSimulator
          │  - 更新BatchConfig添加窗口3参数
          │
阶段4: 端到端集成测试
             - 运行完整批处理流程
             - 检查推理链 + LLM Query + 动态长度 是否协同工作
```

---

## 📋 任务概览

| 子任务 | 优先级 | 复杂度 | 状态 |
|--------|--------|--------|------|
| 1.1 修复数据集生成配置 | P0 | 低 | 待开始 |
| 1.2 实现/验证各数据集加载器 | P0 | 中 | 待开始 |
| 1.3 创建BatchTaskSimulator | P1 | 高 | 待开始 |
| 1.4 编写批处理运行脚本 | P1 | 中 | 待开始 |
| 1.5 集成测试 | P2 | 低 | 待开始 |

---

## 🔧 子任务 1.1: 修复数据集生成配置

### 问题诊断

**当前问题**: `generate_all_tasks_v2.py` 第373-382行硬编码只包含 `mscoco14` 和 `vcr`。

```python
# 当前代码 (Line 373-398)
generation_config = {
    'mscoco14': {'num_samples': 10, 'split': 'val'},
    'vcr': {'num_samples': 10, 'split': 'train'},
    'visual_genome': {'num_samples': 10, 'split': 'train'},  # 已添加但需验证
    'gqa': {'num_samples': 10, 'split': 'train'},
    'sherlock': {'num_samples': 10, 'split': 'train'},
    'docvqa': {'num_samples': 10, 'split': 'train'}
}
```

### 修改要求

**文件**: `generate_all_tasks_v2.py`

**修改1**: 将 `generation_config` 改为从配置文件动态读取

```python
def load_generation_config(config_loader) -> Dict[str, Dict]:
    """
    从dataset_configs.yaml动态加载生成配置

    Returns:
        Dict[str, Dict]:
            key: dataset_id
            value: {
                'num_samples': int,
                'split': str,
                'enabled': bool
            }
    """
    generation_config = {}

    for dataset_id in config_loader.get_all_dataset_ids():
        dataset_config = config_loader.get_dataset_config(dataset_id)

        if dataset_config and dataset_config.is_any_task_enabled():
            generation_config[dataset_id] = {
                'num_samples': dataset_config.get_default_num_samples(),
                'split': dataset_config.get_default_split(),
                'enabled': True
            }

    return generation_config
```

**修改2**: 添加命令行参数支持

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--datasets', nargs='+',
                       help='指定要生成的数据集，默认所有已启用的')
    parser.add_argument('--num-samples', type=int, default=10,
                       help='每个任务类型的样本数')
    parser.add_argument('--split', default='train',
                       help='数据集划分')
    args = parser.parse_args()

    # ... 使用args覆盖配置
```

### 验证标准

- [ ] 运行 `python generate_all_tasks_v2.py` 后，`generated_tasks_v2/run_*/tasks/` 目录下出现所有已配置数据集的任务文件
- [ ] 每个数据集至少生成一种任务类型的文件

---

## 🔧 子任务 1.2: 实现/验证各数据集加载器

### 需要检查的加载器

**文件**: `dataprovider/loader.py`

| 数据集 | 加载方法 | 数据路径 | 状态 |
|--------|----------|----------|------|
| visual_genome | `_load_visual_genome()` | `E:/Dataset/visual_genome/` | 需验证 |
| gqa | `_load_gqa()` | `E:/Dataset/gqa/` | 需验证 |
| sherlock | `_load_sherlock()` | `E:/Dataset/Sherlock/` | 需验证 |
| docvqa | `_load_docvqa()` | `E:/Dataset/DocVQA/` | 需验证 |

### Visual Genome 加载器规范

**预期数据格式**:
```
E:/Dataset/visual_genome/
├── scene_graphs.json 或 scene_graphs/
├── objects.json
├── attributes.json
├── relationships.json
└── images/
    └── VG_100K/ 或 VG_100K_2/
```

**加载器接口定义**:

```python
def _load_visual_genome(self, split: str = "train", **kwargs) -> List[Dict]:
    """
    加载Visual Genome数据集

    Args:
        split: 数据划分 ("train" | "val" | "test")
        **kwargs:
            max_objects_per_image: int = 50  # 每张图最多加载的物体数
            include_attributes: bool = True
            include_relationships: bool = True

    Returns:
        List[Dict]: 统一格式的样本列表
        [
            {
                'dataset_id': 'visual_genome',
                'sample_id': str,           # e.g., "vg_2417904"
                'image_path': str,          # 绝对路径
                'image_id': int,
                'width': int,
                'height': int,
                'objects': [
                    {
                        'id': int,
                        'name': str,        # e.g., "person"
                        'synsets': List[str],  # WordNet synsets
                        'bbox': [x, y, w, h],
                        'attributes': List[str],  # e.g., ["tall", "wearing hat"]
                    }
                ],
                'relationships': [
                    {
                        'id': int,
                        'subject_id': int,
                        'object_id': int,
                        'predicate': str,   # e.g., "holding"
                        'synsets': List[str]
                    }
                ],
                'region_descriptions': [
                    {
                        'id': int,
                        'phrase': str,
                        'bbox': [x, y, w, h]
                    }
                ]
            }
        ]

    Raises:
        FileNotFoundError: 数据文件不存在
        ValueError: 数据格式错误
    """
```

### GQA 加载器规范

**预期数据格式**:
```
E:/Dataset/gqa/
├── train_sceneGraphs.json
├── val_sceneGraphs.json
├── train_balanced_questions.json
├── val_balanced_questions.json
└── images/
```

**加载器接口定义**:

```python
def _load_gqa(self, split: str = "train", **kwargs) -> List[Dict]:
    """
    加载GQA数据集

    Args:
        split: "train" | "val" | "testdev"
        **kwargs:
            load_questions: bool = True  # 是否加载问题
            load_scene_graphs: bool = True

    Returns:
        List[Dict]:
        [
            {
                'dataset_id': 'gqa',
                'sample_id': str,           # question_id
                'image_path': str,
                'image_id': str,
                'question': str,
                'answer': str,
                'full_answer': str,         # 完整答案
                'question_type': str,       # e.g., "verify", "query"
                'semantic_type': str,       # e.g., "attribute", "relation"
                'scene_graph': {            # 如果load_scene_graphs=True
                    'objects': {...},
                    'relations': [...]
                }
            }
        ]
    """
```

### Sherlock 加载器规范

**预期数据格式**:
```
E:/Dataset/Sherlock/
├── sherlock_train_v1_1.json
├── sherlock_val_with_split_idxs_v1_1.json
└── images/  # 或者URL形式
```

**加载器接口定义**:

```python
def _load_sherlock(self, split: str = "train", **kwargs) -> List[Dict]:
    """
    加载Sherlock数据集 (线索-推理对)

    Returns:
        List[Dict]:
        [
            {
                'dataset_id': 'sherlock',
                'sample_id': str,
                'image_path': str,          # 或 'image_url'
                'clue': str,                # 线索描述
                'inference': str,           # 推理结论
                'bounding_box': [x1, y1, x2, y2],  # 线索区域
                'instance_id': str
            }
        ]
    """
```

### 错误处理要求

每个加载器必须包含:

```python
def _load_xxx(self, split: str = "train", **kwargs) -> List[Dict]:
    # 1. 路径验证
    data_dir = self._find_dataset_path("xxx")
    if data_dir is None:
        logger.warning(f"Dataset 'xxx' not found. Tried paths: {self._get_tried_paths('xxx')}")
        return []

    # 2. 文件存在性检查
    required_files = ["file1.json", "file2.json"]
    missing = [f for f in required_files if not (data_dir / f).exists()]
    if missing:
        logger.error(f"Missing required files for 'xxx': {missing}")
        return []

    # 3. 数据加载
    try:
        # ... 加载逻辑
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in xxx: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading xxx: {e}")
        import traceback
        traceback.print_exc()
        return []

    # 4. 数据验证
    valid_samples = [s for s in samples if self._validate_sample(s)]
    logger.info(f"Loaded {len(valid_samples)}/{len(samples)} valid samples from xxx")

    return valid_samples
```

### 验证标准

- [ ] 每个加载器能正确处理数据不存在的情况（返回空列表+警告，不崩溃）
- [ ] 每个加载器返回的数据格式符合上述规范
- [ ] 运行测试脚本验证:

```python
# tests/test_data_loaders.py
def test_all_loaders():
    loader = DataLoader(data_root="E:/Dataset")

    for dataset_id in ["visual_genome", "gqa", "sherlock", "docvqa"]:
        try:
            samples = loader.load_dataset(dataset_id, split="train", max_samples=5)
            print(f"✓ {dataset_id}: {len(samples)} samples")

            if samples:
                # 验证字段
                required_fields = ['dataset_id', 'sample_id', 'image_path']
                for field in required_fields:
                    assert field in samples[0], f"Missing field: {field}"

        except Exception as e:
            print(f"✗ {dataset_id}: {e}")
```

---

## 🔧 子任务 1.3: 创建 BatchTaskSimulator

### 设计目标

- 在单个对话session中测试多个任务（3-5个）
- 实现任务间的自然过渡
- 支持50+轮的长对话测试
- 保持完整的评估和日志

### 文件位置

`src/simulator/batch_task_simulator.py` (新建)

### 类定义

```python
"""
BatchTaskSimulator - 批处理任务模拟器

功能:
1. 在一个session中测试多个任务
2. 任务间通过自然过渡衔接
3. 保持长上下文测试
4. 支持跨任务记忆测试
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import random
import logging

from .llm_client import LLMClient
from .evaluator import Evaluator, EvaluationResult
from .strategic_simulator import StrategicSimulator, TaskState
from .memory_store import MemoryStore

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """批处理配置"""
    max_turns_per_session: int = 50      # 单session最大轮数
    min_turns_per_task: int = 8          # 每任务最少轮数
    max_turns_per_task: int = 15         # 每任务最多轮数
    transition_style: str = "natural"     # "natural" | "abrupt" | "contextual"
    enable_cross_task_memory_test: bool = True  # 是否测试跨任务记忆
    cross_task_memory_interval: int = 3   # 每N个任务后进行跨任务记忆测试


@dataclass
class TaskTransition:
    """任务过渡记录"""
    from_task_id: str
    to_task_id: str
    transition_message: str
    turn_number: int
    transition_style: str


@dataclass
class BatchResult:
    """批处理结果"""
    batch_id: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # 任务执行结果
    tasks_attempted: int = 0
    tasks_completed: int = 0
    task_results: List[Dict[str, Any]] = field(default_factory=list)

    # 轮次统计
    total_turns: int = 0
    turns_per_task: List[int] = field(default_factory=list)

    # 过渡记录
    transitions: List[TaskTransition] = field(default_factory=list)

    # 跨任务记忆测试
    cross_task_memory_tests: List[Dict[str, Any]] = field(default_factory=list)

    # 完整对话日志
    conversation_log: List[Dict[str, Any]] = field(default_factory=list)

    # 聚合分数
    aggregate_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            'batch_id': self.batch_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'tasks_attempted': self.tasks_attempted,
            'tasks_completed': self.tasks_completed,
            'task_results': self.task_results,
            'total_turns': self.total_turns,
            'turns_per_task': self.turns_per_task,
            'transitions': [
                {
                    'from_task': t.from_task_id,
                    'to_task': t.to_task_id,
                    'message': t.transition_message,
                    'turn': t.turn_number,
                    'style': t.transition_style
                }
                for t in self.transitions
            ],
            'cross_task_memory_tests': self.cross_task_memory_tests,
            'conversation_log': self.conversation_log,
            'aggregate_scores': self.aggregate_scores
        }


class BatchTaskSimulator:
    """
    批处理任务模拟器

    在单个对话session中执行多个任务，支持:
    - 任务间自然过渡
    - 长上下文测试
    - 跨任务记忆测试

    Usage:
        batch_sim = BatchTaskSimulator(llm_client, evaluator)
        result = batch_sim.run_batch(tasks)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        evaluator: Evaluator,
        config: Optional[BatchConfig] = None,
        verbose: bool = True
    ):
        """
        初始化批处理模拟器

        Args:
            llm_client: LLM客户端
            evaluator: 评估器
            config: 批处理配置
            verbose: 是否输出详细日志
        """
        self.llm_client = llm_client
        self.evaluator = evaluator
        self.config = config or BatchConfig()
        self.verbose = verbose

        # 会话状态
        self.session_memory = MemoryStore()
        self.session_history: List[Dict[str, Any]] = []
        self.total_turns: int = 0
        self.completed_tasks: List[Dict[str, Any]] = []

    def run_batch(self, tasks: List[Dict[str, Any]]) -> BatchResult:
        """
        运行批处理任务

        Args:
            tasks: 任务列表，每个任务是一个包含task_id, question, answer等的字典

        Returns:
            BatchResult: 批处理结果
        """
        pass  # 实现见下文

    def _run_single_task_in_batch(
        self,
        task: Dict[str, Any],
        task_index: int,
        is_first: bool,
        is_last: bool
    ) -> Tuple[Dict[str, Any], int]:
        """
        在batch中运行单个任务

        Args:
            task: 任务数据
            task_index: 任务在batch中的索引
            is_first: 是否是第一个任务
            is_last: 是否是最后一个任务

        Returns:
            Tuple[task_report, turns_used]
        """
        pass

    def _generate_transition(
        self,
        from_task: Dict[str, Any],
        to_task: Dict[str, Any],
        style: str = "natural"
    ) -> TaskTransition:
        """
        生成任务间过渡

        Args:
            from_task: 上一个任务
            to_task: 下一个任务
            style: 过渡风格
                - "natural": 自然过渡，有承接语
                - "abrupt": 直接切换
                - "contextual": 基于上下文的过渡

        Returns:
            TaskTransition
        """
        pass

    def _run_cross_task_memory_test(
        self,
        completed_tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        跨任务记忆测试

        从已完成的任务中随机选择信息，测试模型是否还记得

        Args:
            completed_tasks: 已完成的任务列表

        Returns:
            测试结果字典
        """
        pass

    def _inject_session_context(
        self,
        simulator: StrategicSimulator
    ) -> None:
        """
        将session上下文注入到task simulator

        Args:
            simulator: 任务模拟器
        """
        pass

    def _calculate_aggregate_scores(
        self,
        task_results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        计算聚合分数

        Args:
            task_results: 所有任务的结果

        Returns:
            聚合分数字典
        """
        pass
```

### 核心方法实现

```python
def run_batch(self, tasks: List[Dict[str, Any]]) -> BatchResult:
    """运行批处理任务"""

    result = BatchResult(
        batch_id=f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        start_time=datetime.now(),
        tasks_attempted=len(tasks)
    )

    if self.verbose:
        print(f"\n{'='*60}")
        print(f"开始批处理: {result.batch_id}")
        print(f"任务数: {len(tasks)}")
        print(f"配置: max_turns={self.config.max_turns_per_session}, "
              f"min_per_task={self.config.min_turns_per_task}")
        print(f"{'='*60}\n")

    for task_idx, task in enumerate(tasks):
        # 检查是否超过最大轮数
        if self.total_turns >= self.config.max_turns_per_session:
            if self.verbose:
                print(f"达到最大轮数限制 ({self.config.max_turns_per_session}), 停止")
            break

        is_first = (task_idx == 0)
        is_last = (task_idx == len(tasks) - 1)

        # 运行任务
        if self.verbose:
            print(f"\n--- 任务 {task_idx + 1}/{len(tasks)}: {task['task_id']} ---")

        task_report, turns_used = self._run_single_task_in_batch(
            task=task,
            task_index=task_idx,
            is_first=is_first,
            is_last=is_last
        )

        result.task_results.append(task_report)
        result.turns_per_task.append(turns_used)
        self.total_turns += turns_used
        result.total_turns = self.total_turns

        if task_report.get('completed', False):
            result.tasks_completed += 1
            self.completed_tasks.append({
                'task': task,
                'report': task_report
            })

        # 任务过渡
        if not is_last and task_idx < len(tasks) - 1:
            next_task = tasks[task_idx + 1]
            transition = self._generate_transition(
                from_task=task,
                to_task=next_task,
                style=self.config.transition_style
            )
            result.transitions.append(transition)

            # 将过渡消息添加到对话历史
            self.session_history.append({
                'type': 'transition',
                'turn': self.total_turns,
                'content': transition.transition_message
            })

            if self.verbose:
                print(f"  [过渡] {transition.transition_message}")

        # 跨任务记忆测试
        if (self.config.enable_cross_task_memory_test and
            len(self.completed_tasks) > 0 and
            (task_idx + 1) % self.config.cross_task_memory_interval == 0):

            memory_test = self._run_cross_task_memory_test(self.completed_tasks)
            result.cross_task_memory_tests.append(memory_test)

            if self.verbose:
                print(f"  [跨任务记忆测试] score={memory_test.get('score', 0):.2f}")

    # 完成
    result.end_time = datetime.now()
    result.conversation_log = self.session_history.copy()
    result.aggregate_scores = self._calculate_aggregate_scores(result.task_results)

    if self.verbose:
        duration = (result.end_time - result.start_time).total_seconds()
        print(f"\n{'='*60}")
        print(f"批处理完成: {result.batch_id}")
        print(f"总轮数: {result.total_turns}")
        print(f"完成任务: {result.tasks_completed}/{result.tasks_attempted}")
        print(f"耗时: {duration:.1f}s")
        print(f"聚合分数: {result.aggregate_scores}")
        print(f"{'='*60}\n")

    return result


def _generate_transition(
    self,
    from_task: Dict[str, Any],
    to_task: Dict[str, Any],
    style: str = "natural"
) -> TaskTransition:
    """生成任务间过渡"""

    # 过渡模板
    natural_transitions = [
        "好的，现在让我们看另一个场景。",
        "明白了。接下来我想问你关于另一张图的问题。",
        "了解。那现在换一个话题。",
        "很好，我们继续下一个任务。",
        "OK, let's move to a different image now.",
        "Understood. Let me show you another scenario.",
        "Great. Now I have a different question for you."
    ]

    abrupt_transitions = [
        "下一个。",
        "Next.",
        "看这个。"
    ]

    contextual_templates = [
        "刚才我们讨论了{from_topic}，现在来看看{to_topic}。",
        "关于{from_topic}的问题先到这里，接下来是{to_topic}相关的问题。",
        "We've covered {from_topic}, now let's discuss {to_topic}."
    ]

    if style == "natural":
        message = random.choice(natural_transitions)
    elif style == "abrupt":
        message = random.choice(abrupt_transitions)
    elif style == "contextual":
        template = random.choice(contextual_templates)
        from_topic = from_task.get('task_type', '上一个话题')
        to_topic = to_task.get('task_type', '新话题')
        message = template.format(from_topic=from_topic, to_topic=to_topic)
    else:
        message = random.choice(natural_transitions)

    return TaskTransition(
        from_task_id=from_task['task_id'],
        to_task_id=to_task['task_id'],
        transition_message=message,
        turn_number=self.total_turns,
        transition_style=style
    )


def _run_cross_task_memory_test(
    self,
    completed_tasks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """跨任务记忆测试"""

    # 随机选择一个已完成的任务
    target = random.choice(completed_tasks)
    target_task = target['task']
    target_report = target['report']

    # 构建记忆测试query
    test_queries = [
        f"还记得之前关于{target_task.get('task_type', '那个')}的问题吗？答案是什么来着？",
        f"Earlier we discussed something. What was the answer to the question about {target_task.get('task_type', 'that')}?",
        f"刚才的{target_task['task_id']}任务，你给的结论是什么？",
        f"我想确认一下，之前那个问题的答案是不是{target_task.get('answer', '')}？"
    ]

    query = random.choice(test_queries)

    # 发送测试query (这里需要调用LLM)
    # 简化实现：直接评估
    expected_answer = target_task.get('answer', '')

    test_result = {
        'target_task_id': target_task['task_id'],
        'test_query': query,
        'expected_answer': expected_answer,
        'turn_number': self.total_turns,
        'score': 0.0,  # 需要实际评估
        'response': None
    }

    return test_result
```

### 导出到 `__init__.py`

**文件**: `src/simulator/__init__.py`

添加:
```python
from .batch_task_simulator import BatchTaskSimulator, BatchConfig, BatchResult
```

---

## 🔧 子任务 1.4: 编写批处理运行脚本

### 文件位置

`run_batch_test.py` (新建)

### 完整代码

```python
"""
批处理测试运行脚本

用法:
    python run_batch_test.py --tasks-per-batch 4 --num-batches 5
    python run_batch_test.py --task-file generated_tasks_v2/run_12/tasks/*.jsonl
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from src.simulator import (
    BatchTaskSimulator,
    BatchConfig,
    LLMClient,
    Evaluator,
    EvaluationMode
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_tasks_from_files(task_files: List[str], max_tasks: int = None) -> List[Dict]:
    """从JSONL文件加载任务"""
    all_tasks = []

    for file_pattern in task_files:
        for file_path in Path().glob(file_pattern):
            logger.info(f"Loading tasks from: {file_path}")

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            task = json.loads(line)
                            all_tasks.append(task)
                        except json.JSONDecodeError:
                            continue

    if max_tasks:
        all_tasks = all_tasks[:max_tasks]

    logger.info(f"Total tasks loaded: {len(all_tasks)}")
    return all_tasks


def split_into_batches(tasks: List[Dict], batch_size: int) -> List[List[Dict]]:
    """将任务分成批次"""
    batches = []
    for i in range(0, len(tasks), batch_size):
        batches.append(tasks[i:i + batch_size])
    return batches


def main():
    parser = argparse.ArgumentParser(description="批处理任务测试")

    # 任务来源
    parser.add_argument('--task-files', nargs='+',
                       default=['generated_tasks_v2/run_*/tasks/*.jsonl'],
                       help='任务文件路径模式')
    parser.add_argument('--max-tasks', type=int, default=50,
                       help='最大加载任务数')

    # 批处理配置
    parser.add_argument('--tasks-per-batch', type=int, default=4,
                       help='每批任务数')
    parser.add_argument('--num-batches', type=int, default=5,
                       help='运行批次数')
    parser.add_argument('--max-turns-per-session', type=int, default=50,
                       help='每session最大轮数')
    parser.add_argument('--min-turns-per-task', type=int, default=8,
                       help='每任务最小轮数')
    parser.add_argument('--max-turns-per-task', type=int, default=15,
                       help='每任务最大轮数')

    # 输出
    parser.add_argument('--output-dir', default='batch_test_results',
                       help='输出目录')
    parser.add_argument('--verbose', action='store_true',
                       help='详细输出')

    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载任务
    tasks = load_tasks_from_files(args.task_files, args.max_tasks)

    if not tasks:
        logger.error("No tasks loaded!")
        return

    # 分批
    batches = split_into_batches(tasks, args.tasks_per_batch)
    batches = batches[:args.num_batches]

    logger.info(f"Will run {len(batches)} batches, {args.tasks_per_batch} tasks each")

    # 初始化
    llm_client = LLMClient()
    evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

    config = BatchConfig(
        max_turns_per_session=args.max_turns_per_session,
        min_turns_per_task=args.min_turns_per_task,
        max_turns_per_task=args.max_turns_per_task,
        transition_style="natural",
        enable_cross_task_memory_test=True
    )

    batch_simulator = BatchTaskSimulator(
        llm_client=llm_client,
        evaluator=evaluator,
        config=config,
        verbose=args.verbose
    )

    # 运行批处理
    all_results = []

    for batch_idx, batch in enumerate(batches):
        logger.info(f"\n{'='*60}")
        logger.info(f"Running Batch {batch_idx + 1}/{len(batches)}")
        logger.info(f"Tasks: {[t['task_id'] for t in batch]}")
        logger.info(f"{'='*60}")

        try:
            result = batch_simulator.run_batch(batch)
            all_results.append(result.to_dict())

            logger.info(f"Batch {batch_idx + 1} completed:")
            logger.info(f"  Total turns: {result.total_turns}")
            logger.info(f"  Tasks completed: {result.tasks_completed}/{result.tasks_attempted}")
            logger.info(f"  Aggregate scores: {result.aggregate_scores}")

        except Exception as e:
            logger.error(f"Batch {batch_idx + 1} failed: {e}")
            import traceback
            traceback.print_exc()

    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f"batch_results_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'run_time': timestamp,
            'config': {
                'tasks_per_batch': args.tasks_per_batch,
                'num_batches': len(batches),
                'max_turns_per_session': args.max_turns_per_session
            },
            'results': all_results,
            'summary': {
                'total_batches': len(all_results),
                'total_turns': sum(r['total_turns'] for r in all_results),
                'total_tasks_completed': sum(r['tasks_completed'] for r in all_results),
                'average_turns_per_batch': sum(r['total_turns'] for r in all_results) / len(all_results) if all_results else 0
            }
        }, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✅ Results saved to: {output_file}")

    # 打印总结
    print("\n" + "="*60)
    print("批处理测试完成")
    print("="*60)
    print(f"总批次: {len(all_results)}")
    print(f"总轮数: {sum(r['total_turns'] for r in all_results)}")
    print(f"平均轮数/批: {sum(r['total_turns'] for r in all_results) / len(all_results):.1f}" if all_results else "N/A")
    print(f"结果文件: {output_file}")


if __name__ == "__main__":
    main()
```

---

## 🔧 子任务 1.5: 集成测试

### 测试脚本

**文件**: `tests/test_batch_simulator.py`

```python
"""
BatchTaskSimulator 集成测试
"""

import unittest
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator import (
    BatchTaskSimulator,
    BatchConfig,
    LLMClient,
    Evaluator,
    EvaluationMode
)


class TestBatchTaskSimulator(unittest.TestCase):

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
        task_files = list(Path("generated_tasks_v2").rglob("*.jsonl"))

        tasks = []
        for f in task_files[:1]:  # 只取第一个文件
            with open(f, 'r', encoding='utf-8') as fp:
                for line in fp:
                    if line.strip():
                        tasks.append(json.loads(line))
                        if len(tasks) >= 8:
                            break
                if len(tasks) >= 8:
                    break

        return tasks

    def test_batch_config(self):
        """测试配置创建"""
        config = BatchConfig(
            max_turns_per_session=30,
            min_turns_per_task=5,
            max_turns_per_task=10
        )

        self.assertEqual(config.max_turns_per_session, 30)
        self.assertEqual(config.min_turns_per_task, 5)

    def test_simulator_creation(self):
        """测试模拟器创建"""
        config = BatchConfig()
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config
        )

        self.assertIsNotNone(simulator)

    def test_transition_generation(self):
        """测试过渡生成"""
        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator
        )

        if len(self.test_tasks) >= 2:
            transition = simulator._generate_transition(
                from_task=self.test_tasks[0],
                to_task=self.test_tasks[1],
                style="natural"
            )

            self.assertIsNotNone(transition.transition_message)
            self.assertTrue(len(transition.transition_message) > 0)

    def test_small_batch(self):
        """测试小批量运行"""
        if len(self.test_tasks) < 2:
            self.skipTest("Not enough test tasks")

        config = BatchConfig(
            max_turns_per_session=15,
            min_turns_per_task=3,
            max_turns_per_task=5
        )

        simulator = BatchTaskSimulator(
            llm_client=self.llm_client,
            evaluator=self.evaluator,
            config=config,
            verbose=True
        )

        result = simulator.run_batch(self.test_tasks[:2])

        self.assertIsNotNone(result)
        self.assertGreater(result.total_turns, 0)
        self.assertEqual(result.tasks_attempted, 2)


if __name__ == '__main__':
    unittest.main()
```

### 验证清单

运行以下命令验证所有功能:

```bash
# 1. 数据集生成
python generate_all_tasks_v2.py
ls generated_tasks_v2/run_*/tasks/  # 应该看到多个数据集的文件

# 2. 数据加载器测试
python -c "
from dataprovider import DataLoader
loader = DataLoader(data_root='E:/Dataset')
for ds in ['visual_genome', 'gqa', 'sherlock']:
    try:
        samples = loader.load_dataset(ds, max_samples=3)
        print(f'{ds}: {len(samples)} samples')
    except Exception as e:
        print(f'{ds}: ERROR - {e}')
"

# 3. 批处理测试
python run_batch_test.py --tasks-per-batch 3 --num-batches 2 --verbose

# 4. 单元测试
python -m pytest tests/test_batch_simulator.py -v

# 5. 检查结果
cat batch_test_results/*.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Batches: {len(data[\"results\"])}')
print(f'Total turns: {data[\"summary\"][\"total_turns\"]}')
print(f'Average turns/batch: {data[\"summary\"][\"average_turns_per_batch\"]:.1f}')
"
```

---

## 📁 输出文件结构

完成本窗口任务后，应该新增/修改以下文件:

```
M3Bench_new/
├── generate_all_tasks_v2.py          # [修改] 动态配置加载
├── run_batch_test.py                 # [新建] 批处理运行脚本
│
├── dataprovider/
│   └── loader.py                     # [修改] 完善各数据集加载器
│
├── src/simulator/
│   ├── __init__.py                   # [修改] 导出BatchTaskSimulator
│   └── batch_task_simulator.py       # [新建] 批处理模拟器
│
├── tests/
│   ├── test_data_loaders.py          # [新建] 数据加载器测试
│   └── test_batch_simulator.py       # [新建] 批处理测试
│
└── batch_test_results/               # [新建] 批处理结果目录
    └── batch_results_*.json
```

---

## ⚠️ 注意事项

1. **数据路径**: 确保 `E:/Dataset/` 下的各数据集目录结构正确
2. **API限制**: 批处理会产生大量API调用，注意rate limiting
3. **内存管理**: 长对话会累积大量历史，注意内存使用
4. **错误恢复**: 实现checkpoint保存，支持从中断处恢复

---

## 📊 预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| 支持数据集 | 2 (mscoco, vcr) | 6+ |
| 平均轮数/任务 | 5-6 | 10-15 |
| 单session总轮数 | ~30 | 40-50 |
| 跨任务记忆测试 | 无 | 有 |
