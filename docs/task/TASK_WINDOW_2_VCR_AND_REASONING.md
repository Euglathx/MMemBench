# 窗口2: VCR Rationale增强 + 跨轮推理链测试

> **目标**: 充分利用VCR数据集的rationale标注，实现跨轮逻辑推理能力测试
> **预计工时**: 4-5小时
> **依赖**: 无外部依赖，可独立开发

---

## 🌐 项目背景与整体架构

### M3Bench 是什么

M3Bench 是一个**多轮多模态对话能力评测框架**，用于测试视觉语言模型（VLM）在长上下文对话中的推理、记忆、鲁棒性等能力。核心流程：

1. **数据层**：从视觉数据集（MSCOCO、VCR、Visual Genome 等）中加载图-文对
2. **任务生成层**：自动生成多种推理任务（属性对比、桥式推理、噪声过滤等）
3. **模拟器层**：运行"用户模拟器"与被测VLM进行多轮对话
4. **评估层**：7维度评估（正确性、忠实性、鲁棒性、一致性、记忆保持、跨图区分、歧义识别）

### 端到端数据流中本窗口的位置

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          M3Bench 端到端流程                              │
│                                                                          │
│  ┌─────────┐    ┌──────────┐    ┌───────────────┐    ┌──────────────┐   │
│  │ 原始数据 │───>│ 任务生成  │───>│ Simulator运行  │───>│ 评估 & 报告  │   │
│  │ 集加载   │    │ (JSONL)  │    │ (多轮对话)     │    │ (7维度评分)  │   │
│  └─────────┘    └──────────┘    └───────────────┘    └──────────────┘   │
│       ▲               ▲                ▲                    ▲           │
│       │          ★窗口2★           窗口1-后半           ★窗口2★        │
│   窗口1-前半    (VCR rationale    (BatchSimulator)    (推理链评估     │
│   (数据加载)     → 推理链任务)                          新增维度)      │
└──────────────────────────────────────────────────────────────────────────┘
```

**本窗口横跨两个环节**：任务生成（将VCR的rationale转化为推理链任务）和评估（新增推理链一致性评估维度）。

### 三个并行窗口的关系

| 窗口 | 侧重层面 | 核心改进 | 本窗口输出供谁使用 |
|------|----------|----------|-------------------|
| **窗口1** | 数据层 + 运行层 | 修复数据集生成 + 批处理长对话 | 生成的任务JSONL → 本窗口的推理链任务来源 |
| **窗口2 (本文档)** | 数据层 + 评估层 | VCR rationale → 推理链任务 + 推理链评估 | 推理链任务 → 窗口1批处理调度；评估方法 → 所有窗口使用 |
| **窗口3** | 模拟器层 | LLM驱动Query生成 + 长度控制 | 增强的Query → 本窗口推理链query也可使用LLM生成 |

### 本窗口在整体中的位置

**窗口2是内容质量窗口**：它解决两个核心问题——

1. **数据利用不充分**：VCR数据集包含丰富的`rationale`标注（人工撰写的推理过程），但目前只使用了question和answer，rationale完全被浪费了
2. **缺乏跨轮推理测试**：当前模拟器的多轮对话没有显式的推理链结构，无法验证VLM是否真正在进行逐步推理，还是每轮独立回答

窗口2的核心思路是：**将VCR的rationale拆解为多轮推理链，每一步的query依赖前一步的答案，从而测试VLM的跨轮逻辑推理能力**。

---

## 🔗 跨窗口协作规范

### 本窗口的输入来源

| 输入 | 来源 | 说明 |
|------|------|------|
| VCR原始数据 | `data/VisualCommenReasoning/` | 包含question、answer_choices、rationale_choices |
| `dataprovider/loader.py` | 已有 | 当前VCR加载器，本窗口在此基础上扩展 |
| `src/simulator/strategic_simulator.py` | 已有 | 在此新增推理链测试模式 |
| `src/simulator/evaluator.py` | 已有 | 在此新增推理链评估方法 |

### 本窗口的输出（供其他窗口使用）

#### 1. 增强的VCR数据 → 供窗口1的生成管线使用

本窗口修改 `dataprovider/loader.py` 的 `_load_vcr()` 方法，使VCR样本包含解码后的rationale信息。这些增强数据会被窗口1的 `generate_all_tasks_v2.py` 自动使用。

**增强后的VCR样本格式**:

```python
{
    # 原有字段（不变）
    "dataset_id": "vcr",
    "sample_id": "vcr_12345",
    "image_path": "...",
    "question_text": "How is [person] feeling?",
    "answer_text": "[person] is upset and disgusted.",

    # ★ 新增字段（本窗口产出）★
    "rationale_text": str,           # 解码后的rationale文本
    "all_rationales": List[str],     # 所有候选rationale
    "reasoning_steps": List[str],    # 从rationale中拆解的推理步骤
}
```

> **协作约定**: 窗口1的 `DataGeneratorV2.generate_all_tasks_for_dataset()` 内部调用 `_load_vcr()`，拿到的数据自动包含这些新字段。无需窗口1额外修改。

#### 2. 推理链任务JSONL → 供窗口1的BatchTaskSimulator调度

本窗口生成的推理链任务会通过 `RationaleBasedABRGenerator` 写入JSONL文件，格式约定：

```python
{
    "task_id": "rationale_abr_vcr_12345",
    "task_type": "attribute_bridge_reasoning",
    "images": ["images/xxx.jpg"],
    "question": "How is [person] feeling?",
    "answer": "[person] is upset and disgusted.",

    # ★ 推理链专用字段（窗口1需能透传这些字段）★
    "reasoning_chain": [                    # 推理步骤列表
        "[person]'s expression is twisted",
        "Twisted expression indicates disgust",
        "Therefore [person] is upset and disgusted"
    ],
    "reasoning_depth": 3,                   # 推理链步骤数
    "ground_truth_rationale": "...",        # VCR原始rationale
    "metadata": {
        "source": "vcr_rationale",
        "has_explicit_reasoning": true
    }
}
```

> **协作约定**: 窗口1的 `BatchTaskSimulator` 将此类任务交给 `StrategicSimulator.run_task()`，后者检查 `reasoning_chain` 字段是否存在来决定是否进入推理链测试模式。

#### 3. 推理链测试模式 → 在StrategicSimulator中实现

本窗口修改 `StrategicSimulator.run_task()`:

```python
def run_task(self, task: Dict) -> Dict:
    # 如果任务包含推理链，使用推理链测试模式
    if 'reasoning_chain' in task and len(task['reasoning_chain']) > 1:
        return self._run_reasoning_chain_test(task)

    # 否则使用标准流程（不变）
    return self._run_standard_test(task)
```

> **协作约定**: 窗口1的BatchTaskSimulator不需要感知这个分支，它只负责将task传入。窗口3的LLMQueryGenerator可以被推理链模式调用来生成更自然的推理链query。

#### 4. 推理链评估方法 → 供所有窗口的评估使用

在 `evaluator.py` 中新增：

```python
class Evaluator:
    # 新增方法
    def evaluate_reasoning_step(self, vlm_response, expected_info,
                               dependencies, previous_responses) -> Dict:
        """评估单个推理步骤"""
        ...

    def evaluate_chain_coherence(self, conversation_log,
                                 expected_chain) -> float:
        """评估整体推理链一致性"""
        ...
```

### 与窗口1的协作细节

```
窗口2 产出推理链任务           窗口1 调度执行
────────────────────          ──────────────
_load_vcr() 增强              generate_all_tasks_v2.py
    │                                │
    ▼                                ▼
VCR样本含 rationale_text      DataGeneratorV2 自动获取增强样本
    │                                │
    ▼                                ▼
RationaleBasedABRGenerator    生成推理链任务JSONL
    │                                │
    └────────────────────────────────┘
                    │
                    ▼
           BatchTaskSimulator.run_batch()
                    │
                    ▼
           StrategicSimulator.run_task()
                    │
                    ├─── task无reasoning_chain: 标准模式
                    └─── task有reasoning_chain: ★推理链模式（本窗口实现）★
```

**关键约定**:
- 本窗口修改 `_load_vcr()` 后，窗口1的 `generate_all_tasks_v2.py` 无需改动即可自动获取增强数据
- 推理链任务类型名为 `"attribute_bridge_reasoning"` (ABR)，这是已有的任务类型，本窗口只是丰富了其内容
- 本窗口需要在 `dataset_configs.yaml` 中为VCR数据集添加 `rationale_based_abr` 配置项

### 与窗口3的协作细节

```
窗口3 Query生成增强           窗口2 推理链query
──────────────────            ─────────────────
LLMQueryGenerator             ReasoningChainBuilder
     │                                │
     │  可选集成                        │
     └─────────────────────────────────┤
                                       ▼
                             推理链的每一步query:
                             turn 1: 初始query（模板或LLM）
                             turn 2: 基于前轮的衍生query
                             turn N: 综合验证query
```

**关键约定**:
- 本窗口的 `ReasoningChainBuilder` 内部使用模板生成推理链query（独立开发阶段）
- 合并后，可将窗口3的 `LLMQueryGenerator` 注入到 `ReasoningChainBuilder` 中，让推理链query更自然
- 接口预留：

```python
class ReasoningChainBuilder:
    def __init__(self, task_with_rationale: Dict,
                 query_generator: Optional[Any] = None):  # ← 窗口3注入点
        self.query_generator = query_generator  # None时使用内置模板
```

### 合并顺序建议

```
阶段1: 各窗口独立开发
          │
阶段2: 窗口1 + 窗口2 合并
          │  - _load_vcr()增强 → generate_all_tasks_v2.py自动生效
          │  - RationaleBasedABRGenerator注册到DataGeneratorV2
          │  - StrategicSimulator增加推理链模式
          │  - 验证: BatchTaskSimulator正确调度推理链任务
          │
阶段3: + 窗口3 合并
          │  - LLMQueryGenerator注入ReasoningChainBuilder（可选）
          │  - DynamicLengthSelector在推理链模式下使用"long"策略
          │
阶段4: 端到端集成测试
             - 推理链任务生成 → 批处理调度 → 推理链评估 完整闭环
```

---

## 📋 任务概览

| 子任务 | 优先级 | 复杂度 | 状态 |
|--------|--------|--------|------|
| 2.1 分析VCR数据格式 | P0 | 低 | 待开始 |
| 2.2 增强VCR加载器 | P0 | 中 | 待开始 |
| 2.3 创建Rationale任务生成器 | P1 | 高 | 待开始 |
| 2.4 实现推理链构建器 | P1 | 高 | 待开始 |
| 2.5 集成到StrategicSimulator | P1 | 中 | 待开始 |
| 2.6 添加推理链评估方法 | P2 | 中 | 待开始 |

---

## 📊 VCR数据格式详解

### 原始数据结构

**文件位置**: `E:\Code\M3Bench\M3Bench_new\data\VisualCommenReasoning\example\val.jsonl`

```json
{
  "movie": "1054_Harry_Potter_and_the_prisoner_of_azkaban",
  "objects": ["person", "person", "person", "car", "cellphone", "clock"],

  // 图片和元数据路径
  "img_fn": "lsmdc_1054_.../1054_Harry_Potter_...@0.jpg",
  "metadata_fn": "lsmdc_1054_.../1054_Harry_Potter_...@0.json",

  // 问题 - 使用token列表，[0]表示objects[0]
  "question": ["How", "is", [0], "feeling", "?"],
  "question_orig": "How is 1 feeling?",

  // 答案选项
  "answer_choices": [
    [[0], "is", "feeling", "amused", "."],
    [[0], "is", "upset", "and", "disgusted", "."],
    [[0], "is", "feeling", "very", "scared", "."],
    [[0], "is", "feeling", "uncomfortable", "with", [2], "."]
  ],
  "answer_label": 1,  // 正确答案索引
  "answer_orig": "1 is upset and disgusted.",

  // ⭐ Rationale选项 - 这是我们要重点利用的
  "rationale_choices": [
    [[0], "'", "s", "mouth", "has", "wide", "eyes", "..."],
    ["When", "people", "have", "their", "mouth", "back", "..."],
    [[2, 1, 0], "are", "seated", "at", "a", "dining", "table", "..."],
    [[0], "'", "s", "expression", "is", "twisted", "in", "disgust", "."]
  ],
  "rationale_label": 3,  // 正确rationale索引
  "rationale_orig": "1's expression is twisted in disgust.",

  // 其他元数据
  "img_id": "val-0",
  "annot_id": "val-0",
  "answer_likelihood": "likely"
}
```

### Token解码规则

```python
def decode_vcr_tokens(tokens: List, objects: List[str]) -> str:
    """
    将VCR的token列表解码为可读文本

    规则:
    - 字符串token: 直接拼接
    - [n]: 替换为objects[n]
    - [n, m, ...]: 替换为objects[n], objects[m], ...

    Example:
        tokens = [[0], "'", "s", "expression", "is", "twisted"]
        objects = ["person", "person", "car"]
        result = "[person_0]'s expression is twisted"
    """
    result = []
    for token in tokens:
        if isinstance(token, list):
            # 对象引用
            refs = [f"[{objects[i]}_{i}]" for i in token]
            result.append(" and ".join(refs))
        else:
            result.append(str(token))

    # 智能拼接（处理标点符号）
    text = ""
    for i, part in enumerate(result):
        if i > 0 and part not in ".,!?':;)" and not text.endswith("("):
            text += " "
        text += part

    return text.strip()
```

---

## 🔧 子任务 2.1: 分析VCR数据格式

### 分析脚本

```python
# scripts/analyze_vcr_data.py
"""分析VCR数据集的rationale特征"""

import json
from pathlib import Path
from collections import Counter

def analyze_vcr_rationales(data_file: str, num_samples: int = 100):
    """
    分析VCR数据集中的rationale特征

    输出:
    - Rationale平均长度
    - 推理类型分布
    - 物体引用频率
    - 复杂推理链占比
    """

    stats = {
        'total_samples': 0,
        'rationale_lengths': [],
        'object_references': [],  # rationale中的物体引用数
        'reasoning_types': Counter(),
        'has_causal': 0,  # 包含因果关系
        'has_comparison': 0,  # 包含比较
        'has_temporal': 0,  # 包含时序
    }

    causal_keywords = ['because', 'so', 'therefore', 'thus', 'since', '因为', '所以']
    comparison_keywords = ['like', 'similar', 'different', 'more', 'less', '比', '像']
    temporal_keywords = ['before', 'after', 'then', 'when', 'while', '之前', '之后']

    with open(data_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= num_samples:
                break

            data = json.loads(line)
            stats['total_samples'] += 1

            # 获取正确的rationale
            rationale = data['rationale_choices'][data['rationale_label']]

            # 统计长度
            stats['rationale_lengths'].append(len(rationale))

            # 统计物体引用
            obj_refs = sum(1 for t in rationale if isinstance(t, list))
            stats['object_references'].append(obj_refs)

            # 解码为文本进行关键词分析
            text = decode_vcr_tokens(rationale, data['objects']).lower()

            # 检测推理类型
            if any(kw in text for kw in causal_keywords):
                stats['has_causal'] += 1
            if any(kw in text for kw in comparison_keywords):
                stats['has_comparison'] += 1
            if any(kw in text for kw in temporal_keywords):
                stats['has_temporal'] += 1

    # 计算统计
    print(f"VCR Rationale Analysis (n={stats['total_samples']})")
    print("="*50)
    print(f"Average rationale length: {sum(stats['rationale_lengths'])/len(stats['rationale_lengths']):.1f} tokens")
    print(f"Average object references: {sum(stats['object_references'])/len(stats['object_references']):.1f}")
    print(f"Causal reasoning: {stats['has_causal']/stats['total_samples']*100:.1f}%")
    print(f"Comparison: {stats['has_comparison']/stats['total_samples']*100:.1f}%")
    print(f"Temporal: {stats['has_temporal']/stats['total_samples']*100:.1f}%")

    return stats

if __name__ == "__main__":
    analyze_vcr_rationales(
        "data/VisualCommenReasoning/example/val.jsonl",
        num_samples=200
    )
```

### 预期发现

基于数据样本分析，VCR rationale具有以下特征:

1. **因果推理**: 约60-70%的rationale包含因果关系
2. **物体引用**: 平均每个rationale引用1.5-2个物体
3. **推理深度**: 大部分是1-2步推理，少数3步以上
4. **语言模式**:
   - "X is Y because Z"
   - "When X happens, Y follows"
   - "X looks like Y, indicating Z"

---

## 🔧 子任务 2.2: 增强VCR加载器

### 文件位置

`dataprovider/loader.py`

### 修改内容

找到 `_load_vcr` 方法，增强为:

```python
def _load_vcr(self, split: str = "train", **kwargs) -> List[Dict]:
    """
    加载VCR数据集 (增强版 - 包含rationale)

    Args:
        split: "train" | "val" | "test"
        **kwargs:
            include_rationale: bool = True  # 是否包含rationale
            include_all_choices: bool = False  # 是否包含所有选项
            decode_tokens: bool = True  # 是否解码token为文本

    Returns:
        List[Dict]: 统一格式样本列表
        [
            {
                'dataset_id': 'vcr',
                'sample_id': str,
                'image_path': str,

                # 问题和答案
                'question_text': str,        # 解码后的问题文本
                'question_tokens': List,     # 原始token
                'answer_text': str,          # 正确答案文本
                'answer_tokens': List,       # 正确答案token

                # ⭐ Rationale (新增)
                'rationale_text': str,       # 正确rationale文本
                'rationale_tokens': List,    # 原始token
                'reasoning_steps': List[str],  # 拆分的推理步骤

                # 物体信息
                'objects': List[str],        # 物体类别列表
                'object_metadata': Dict,     # 详细物体信息(如果有)

                # 所有选项 (可选)
                'all_answer_choices': List[str],
                'all_rationale_choices': List[str],
                'answer_label': int,
                'rationale_label': int,

                # 元数据
                'movie': str,
                'img_id': str,
                'annot_id': str
            }
        ]
    """
    include_rationale = kwargs.get('include_rationale', True)
    include_all_choices = kwargs.get('include_all_choices', False)
    decode_tokens = kwargs.get('decode_tokens', True)

    # 查找数据目录
    data_dir = self._find_vcr_directory()
    if data_dir is None:
        logger.warning("VCR directory not found")
        return []

    # 确定数据文件
    data_file = data_dir / f"{split}.jsonl"
    if not data_file.exists():
        # 尝试其他路径
        data_file = data_dir / "example" / f"{split}.jsonl"

    if not data_file.exists():
        logger.warning(f"VCR data file not found: {data_file}")
        return []

    samples = []

    with open(data_file, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            objects = data.get('objects', [])

            # 构建图片路径
            img_fn = data.get('img_fn', '')
            image_path = self._resolve_vcr_image_path(data_dir, img_fn)

            # 解码问题
            question_tokens = data.get('question', [])
            question_text = self._decode_vcr_tokens(question_tokens, objects) if decode_tokens else str(question_tokens)

            # 解码正确答案
            answer_choices = data.get('answer_choices', [])
            answer_label = data.get('answer_label', 0)
            answer_tokens = answer_choices[answer_label] if answer_label < len(answer_choices) else []
            answer_text = self._decode_vcr_tokens(answer_tokens, objects) if decode_tokens else str(answer_tokens)

            sample = {
                'dataset_id': 'vcr',
                'sample_id': data.get('annot_id', f'vcr_{idx}'),
                'image_path': image_path,

                'question_text': question_text,
                'question_tokens': question_tokens,
                'answer_text': answer_text,
                'answer_tokens': answer_tokens,

                'objects': objects,

                'movie': data.get('movie', ''),
                'img_id': data.get('img_id', ''),
                'annot_id': data.get('annot_id', '')
            }

            # ⭐ 添加Rationale
            if include_rationale:
                rationale_choices = data.get('rationale_choices', [])
                rationale_label = data.get('rationale_label', 0)

                if rationale_label < len(rationale_choices):
                    rationale_tokens = rationale_choices[rationale_label]
                    rationale_text = self._decode_vcr_tokens(rationale_tokens, objects) if decode_tokens else str(rationale_tokens)

                    # 拆分推理步骤
                    reasoning_steps = self._extract_reasoning_steps(rationale_text)

                    sample.update({
                        'rationale_text': rationale_text,
                        'rationale_tokens': rationale_tokens,
                        'reasoning_steps': reasoning_steps
                    })

            # 添加所有选项
            if include_all_choices:
                sample.update({
                    'all_answer_choices': [
                        self._decode_vcr_tokens(c, objects) if decode_tokens else str(c)
                        for c in answer_choices
                    ],
                    'all_rationale_choices': [
                        self._decode_vcr_tokens(c, objects) if decode_tokens else str(c)
                        for c in data.get('rationale_choices', [])
                    ],
                    'answer_label': answer_label,
                    'rationale_label': rationale_label
                })

            samples.append(sample)

    logger.info(f"Loaded {len(samples)} VCR samples with rationale")
    return samples


def _decode_vcr_tokens(self, tokens: List, objects: List[str]) -> str:
    """解码VCR token列表为文本"""
    if not tokens:
        return ""

    result = []
    for token in tokens:
        if isinstance(token, list):
            # 物体引用 [0] 或 [0, 1]
            refs = []
            for obj_idx in token:
                if obj_idx < len(objects):
                    refs.append(f"[{objects[obj_idx]}_{obj_idx}]")
                else:
                    refs.append(f"[object_{obj_idx}]")
            result.append(" and ".join(refs))
        else:
            result.append(str(token))

    # 智能拼接
    text = ""
    for i, part in enumerate(result):
        # 不在标点符号前加空格
        if i > 0 and part not in ".,!?':;)\"" and not text.endswith("(\"'"):
            text += " "
        text += part

    return text.strip()


def _extract_reasoning_steps(self, rationale_text: str) -> List[str]:
    """
    从rationale文本中提取推理步骤

    策略:
    1. 按句号分割
    2. 识别因果连接词
    3. 保持步骤间的逻辑关系

    Returns:
        List[str]: 推理步骤列表
    """
    if not rationale_text:
        return []

    # 分割句子
    import re
    sentences = re.split(r'[.!?]+', rationale_text)
    sentences = [s.strip() for s in sentences if s.strip()]

    # 如果只有一句，尝试用连接词分割
    if len(sentences) == 1:
        # 尝试按因果词分割
        causal_patterns = [
            r'\s+because\s+',
            r'\s+so\s+',
            r'\s+therefore\s+',
            r'\s+since\s+',
            r',\s+and\s+',
        ]
        for pattern in causal_patterns:
            parts = re.split(pattern, sentences[0], flags=re.IGNORECASE)
            if len(parts) > 1:
                sentences = [p.strip() for p in parts if p.strip()]
                break

    return sentences


def _find_vcr_directory(self) -> Optional[Path]:
    """查找VCR数据目录"""
    possible_paths = [
        self.data_root / "VisualCommenReasoning",
        self.data_root / "VCR",
        self.data_root / "vcr",
        Path("E:/Dataset/VisualCommenReasoning"),
        Path("data/VisualCommenReasoning")
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def _resolve_vcr_image_path(self, data_dir: Path, img_fn: str) -> str:
    """解析VCR图片路径"""
    if not img_fn:
        return ""

    # 尝试多种路径
    candidates = [
        data_dir / img_fn,
        data_dir / "images" / img_fn,
        data_dir / "example" / img_fn,
        data_dir / "vcr1images" / img_fn
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # 返回第一个候选路径（即使不存在）
    return str(candidates[0])
```

### 验证方法

```python
# tests/test_vcr_loader.py

def test_vcr_with_rationale():
    from dataprovider import DataLoader

    loader = DataLoader(data_root="E:/Dataset")
    samples = loader.load_dataset(
        "vcr",
        split="val",
        max_samples=10,
        include_rationale=True
    )

    assert len(samples) > 0, "No samples loaded"

    for sample in samples[:3]:
        print(f"\n{'='*60}")
        print(f"Sample: {sample['sample_id']}")
        print(f"Question: {sample['question_text']}")
        print(f"Answer: {sample['answer_text']}")
        print(f"Rationale: {sample.get('rationale_text', 'N/A')}")
        print(f"Reasoning steps: {sample.get('reasoning_steps', [])}")

        # 验证必要字段
        assert 'rationale_text' in sample, "Missing rationale_text"
        assert 'reasoning_steps' in sample, "Missing reasoning_steps"
        assert isinstance(sample['reasoning_steps'], list)
```

---

## 🔧 子任务 2.3: 创建Rationale任务生成器

### 文件位置

`dataprovider/rationale_based_generator.py` (新建)

### 完整代码

```python
"""
Rationale-Based Task Generator
==============================

使用VCR等数据集的rationale标注生成多跳推理任务。

核心思想:
- Rationale包含推理链: 观察A → 推断B → 结论C
- 将推理链拆解为多个验证点
- 每一步都需要基于前一步的答案
"""

import random
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """推理链中的单个步骤"""
    step_index: int
    step_type: str  # "observation" | "inference" | "conclusion"
    content: str
    depends_on: List[int]  # 依赖的前置步骤索引
    verification_query: str  # 用于验证的问题
    expected_response_hints: List[str]  # 期望回答中应包含的关键词


@dataclass
class ReasoningChain:
    """完整的推理链"""
    chain_id: str
    source_sample_id: str
    question: str
    final_answer: str
    steps: List[ReasoningStep]
    total_hops: int

    def to_dict(self) -> Dict:
        return {
            'chain_id': self.chain_id,
            'source_sample_id': self.source_sample_id,
            'question': self.question,
            'final_answer': self.final_answer,
            'total_hops': self.total_hops,
            'steps': [
                {
                    'step_index': s.step_index,
                    'step_type': s.step_type,
                    'content': s.content,
                    'depends_on': s.depends_on,
                    'verification_query': s.verification_query,
                    'expected_hints': s.expected_response_hints
                }
                for s in self.steps
            ]
        }


class RationaleBasedABRGenerator:
    """
    基于Rationale的属性桥接推理任务生成器

    生成的任务包含:
    - 明确的推理链
    - 每步的验证问题
    - 预期的回答提示
    """

    # 推理步骤类型的验证问题模板
    VERIFICATION_TEMPLATES = {
        "observation": [
            "你能看到{observation_target}吗？",
            "图中的{observation_target}是什么样的？",
            "描述一下{observation_target}。",
            "Can you see {observation_target}?",
            "What does {observation_target} look like?"
        ],
        "inference": [
            "根据{evidence}，你能推断出什么？",
            "这说明了什么？",
            "基于这个观察，{inference_question}？",
            "Based on {evidence}, what can you infer?",
            "What does this indicate?"
        ],
        "conclusion": [
            "所以，{conclusion_question}？",
            "综合以上，你的结论是什么？",
            "因此，{final_question}",
            "So, {conclusion_question}?",
            "What's your final conclusion?"
        ]
    }

    @classmethod
    def generate_from_vcr(
        cls,
        source_data: List[Dict],
        num_samples: int,
        task_config: Dict[str, Any],
        templates: Dict[str, Any]
    ) -> List[Dict]:
        """
        从VCR数据生成基于rationale的ABR任务

        Args:
            source_data: VCR样本列表（必须包含rationale）
            num_samples: 目标样本数
            task_config: 任务配置
                - min_reasoning_steps: int = 2
                - max_reasoning_steps: int = 5
                - require_visual_grounding: bool = True
            templates: 问题模板

        Returns:
            生成的任务列表
        """
        min_steps = task_config.get('min_reasoning_steps', 2)
        max_steps = task_config.get('max_reasoning_steps', 5)
        require_grounding = task_config.get('require_visual_grounding', True)

        tasks = []
        attempts = 0
        max_attempts = num_samples * 5

        # 筛选有效样本
        valid_samples = [
            s for s in source_data
            if s.get('reasoning_steps') and len(s.get('reasoning_steps', [])) >= min_steps
        ]

        if not valid_samples:
            logger.warning(f"No valid VCR samples with >= {min_steps} reasoning steps")
            # 降低要求，使用所有有rationale的样本
            valid_samples = [
                s for s in source_data
                if s.get('rationale_text')
            ]

        logger.info(f"Found {len(valid_samples)} valid VCR samples for rationale-based ABR")

        for sample in valid_samples:
            if len(tasks) >= num_samples:
                break

            attempts += 1
            if attempts > max_attempts:
                break

            # 构建推理链
            reasoning_chain = cls._build_reasoning_chain(sample)

            if reasoning_chain is None:
                continue

            if len(reasoning_chain.steps) < min_steps:
                continue

            # 构建任务
            task = cls._build_task_from_chain(
                sample=sample,
                reasoning_chain=reasoning_chain,
                task_index=len(tasks)
            )

            if task:
                tasks.append(task)

        logger.info(f"Generated {len(tasks)} rationale-based ABR tasks from {attempts} attempts")
        return tasks

    @classmethod
    def _build_reasoning_chain(cls, sample: Dict) -> Optional[ReasoningChain]:
        """
        从VCR样本构建推理链

        策略:
        1. 将rationale_text作为整体推理
        2. 使用reasoning_steps作为分步验证
        3. 为每步生成验证问题
        """
        try:
            sample_id = sample.get('sample_id', 'unknown')
            question = sample.get('question_text', '')
            answer = sample.get('answer_text', '')
            rationale = sample.get('rationale_text', '')
            reasoning_steps_text = sample.get('reasoning_steps', [])

            if not reasoning_steps_text:
                # 如果没有分步，使用整个rationale作为一步
                reasoning_steps_text = [rationale] if rationale else []

            if not reasoning_steps_text:
                return None

            # 构建推理步骤
            steps = []
            for i, step_text in enumerate(reasoning_steps_text):
                # 确定步骤类型
                if i == 0:
                    step_type = "observation"
                elif i == len(reasoning_steps_text) - 1:
                    step_type = "conclusion"
                else:
                    step_type = "inference"

                # 提取关键词作为期望回答提示
                hints = cls._extract_key_hints(step_text)

                # 生成验证问题
                verification_query = cls._generate_verification_query(
                    step_type=step_type,
                    step_content=step_text,
                    question=question,
                    previous_steps=[s.content for s in steps]
                )

                step = ReasoningStep(
                    step_index=i,
                    step_type=step_type,
                    content=step_text,
                    depends_on=list(range(i)) if i > 0 else [],
                    verification_query=verification_query,
                    expected_response_hints=hints
                )
                steps.append(step)

            return ReasoningChain(
                chain_id=f"chain_{sample_id}",
                source_sample_id=sample_id,
                question=question,
                final_answer=answer,
                steps=steps,
                total_hops=len(steps)
            )

        except Exception as e:
            logger.debug(f"Failed to build reasoning chain: {e}")
            return None

    @classmethod
    def _generate_verification_query(
        cls,
        step_type: str,
        step_content: str,
        question: str,
        previous_steps: List[str]
    ) -> str:
        """为推理步骤生成验证问题"""

        templates = cls.VERIFICATION_TEMPLATES.get(step_type, cls.VERIFICATION_TEMPLATES["inference"])
        template = random.choice(templates)

        # 提取step_content中的关键部分
        key_part = cls._extract_observation_target(step_content)

        # 填充模板
        query = template.format(
            observation_target=key_part,
            evidence=key_part if previous_steps else "你看到的",
            inference_question=f"关于{key_part}",
            conclusion_question=question.rstrip("?？"),
            final_question=question
        )

        return query

    @staticmethod
    def _extract_observation_target(step_content: str) -> str:
        """从步骤内容中提取观察目标"""
        # 简化实现：提取第一个名词短语或物体引用
        import re

        # 优先提取[object_n]格式的引用
        obj_refs = re.findall(r'\[([^\]]+)\]', step_content)
        if obj_refs:
            return obj_refs[0]

        # 否则提取前几个词
        words = step_content.split()[:5]
        return " ".join(words)

    @staticmethod
    def _extract_key_hints(step_content: str) -> List[str]:
        """提取关键词作为回答提示"""
        import re

        hints = []

        # 提取物体引用
        obj_refs = re.findall(r'\[([^\]]+)\]', step_content)
        hints.extend(obj_refs)

        # 提取形容词和名词（简化）
        # 这里可以使用NLP工具进行更精确的提取
        key_words = ['expression', 'face', 'looking', 'standing', 'sitting',
                     'holding', 'wearing', 'walking', 'running',
                     '表情', '看', '站', '坐', '拿', '穿', '走']

        for word in key_words:
            if word.lower() in step_content.lower():
                hints.append(word)

        return hints[:5]  # 最多5个提示

    @classmethod
    def _build_task_from_chain(
        cls,
        sample: Dict,
        reasoning_chain: ReasoningChain,
        task_index: int
    ) -> Optional[Dict]:
        """从推理链构建任务"""

        try:
            task = {
                'task_id': f"rationale_abr_vcr_{task_index}",
                'task_type': 'rationale_based_abr',

                # 图片
                'images': [sample.get('image_path', '')],

                # 问题和答案
                'question': reasoning_chain.question,
                'answer': reasoning_chain.final_answer,

                # ⭐ 推理链核心信息
                'reasoning_chain': reasoning_chain.to_dict(),
                'reasoning_depth': reasoning_chain.total_hops,

                # 原始rationale作为ground truth
                'ground_truth_rationale': sample.get('rationale_text', ''),

                # 分步验证信息
                'verification_queries': [
                    {
                        'step': step.step_index,
                        'query': step.verification_query,
                        'expected_hints': step.expected_response_hints
                    }
                    for step in reasoning_chain.steps
                ],

                # 元数据
                'metadata': {
                    'source_dataset': 'vcr',
                    'source_sample_id': sample.get('sample_id', ''),
                    'has_explicit_reasoning': True,
                    'movie': sample.get('movie', ''),
                    'objects': sample.get('objects', [])
                }
            }

            return task

        except Exception as e:
            logger.debug(f"Failed to build task from chain: {e}")
            return None
```

### 集成到 generator_v2.py

**文件**: `dataprovider/generator_v2.py`

添加:

```python
from .rationale_based_generator import RationaleBasedABRGenerator

class DataGeneratorV2:
    def __init__(self, ...):
        # 添加新生成器
        self.task_generators['rationale_based_abr'] = self._generate_rationale_based_abr

    def _generate_rationale_based_abr(
        self,
        source_dataset: str,
        source_data: List[Dict],
        num_samples: int,
        task_config: Dict,
        templates: Dict
    ) -> List[Dict]:
        """生成基于rationale的ABR任务"""

        if source_dataset == 'vcr':
            return RationaleBasedABRGenerator.generate_from_vcr(
                source_data=source_data,
                num_samples=num_samples,
                task_config=task_config,
                templates=templates
            )

        logger.warning(f"rationale_based_abr not supported for {source_dataset}")
        return []
```

### 更新 dataset_configs.yaml

```yaml
vcr:
  task_configs:
    # 新增
    rationale_based_abr:
      enabled: true
      min_reasoning_steps: 2
      max_reasoning_steps: 5
      require_visual_grounding: true
      use_rationale_as_evidence: true
```

---

## 🔧 子任务 2.4: 实现推理链构建器

### 文件位置

`src/simulator/reasoning_chain_builder.py` (新建)

### 完整代码

```python
"""
Reasoning Chain Builder
=======================

将任务的推理链转换为可执行的多轮对话序列。

功能:
1. 将rationale拆解为多轮验证
2. 生成引导模型逐步推理的问题
3. 跟踪推理链的完成度
"""

import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChainQuery:
    """推理链中的单个查询"""
    turn: int
    step_index: int
    step_type: str  # "initial" | "intermediate" | "final"
    query: str
    expected_info: str  # 期望模型提供的信息
    depends_on: List[str]  # 依赖的前置信息
    validation_hints: List[str]  # 用于验证回答的提示词


@dataclass
class ChainExecutionState:
    """推理链执行状态"""
    total_steps: int
    current_step: int = 0
    steps_passed: List[bool] = field(default_factory=list)
    collected_facts: List[str] = field(default_factory=list)
    chain_broken: bool = False
    break_reason: Optional[str] = None


class ReasoningChainBuilder:
    """
    推理链构建器

    将任务的推理链转换为可执行的对话序列。

    Usage:
        builder = ReasoningChainBuilder(task)
        queries = builder.build_chain_queries()

        for query in queries:
            response = vlm.generate(query.query)
            passed = builder.validate_response(response, query)
    """

    # 初始问题模板
    INITIAL_TEMPLATES = [
        "让我们一步步分析这个问题。首先，{hint}是什么？",
        "To answer this question, let's start with: {hint}?",
        "第一步，请观察{hint}。",
        "让我们从{hint}开始分析。"
    ]

    # 中间推理模板
    INTERMEDIATE_TEMPLATES = [
        "你刚才提到{previous_fact}。基于这个，{next_question}？",
        "根据{previous_fact}，现在{next_question}？",
        "知道了{previous_fact}之后，{next_question}？",
        "Based on {previous_fact}, {next_question}?",
        "Given that {previous_fact}, can you tell me {next_question}?"
    ]

    # 最终验证模板
    FINAL_TEMPLATES = [
        "综合以上分析: {chain_summary}。所以，{original_question}",
        "根据推理链 {chain_summary}，最终结论是？",
        "Putting it together: {chain_summary}. Therefore, {original_question}",
        "我们分析了{chain_summary}。最终，{original_question}"
    ]

    def __init__(self, task: Dict[str, Any]):
        """
        初始化推理链构建器

        Args:
            task: 任务数据，必须包含 'reasoning_chain' 字段
        """
        self.task = task
        self.reasoning_chain = task.get('reasoning_chain', {})
        self.steps = self.reasoning_chain.get('steps', [])
        self.original_question = task.get('question', '')
        self.expected_answer = task.get('answer', '')

        # 执行状态
        self.state = ChainExecutionState(total_steps=len(self.steps))

    def build_chain_queries(self) -> List[ChainQuery]:
        """
        构建推理链查询序列

        Returns:
            ChainQuery列表，每个对应一轮对话
        """
        if not self.steps:
            # 如果没有明确的步骤，使用简单的单步验证
            return [self._build_simple_query()]

        queries = []

        for i, step in enumerate(self.steps):
            step_type = self._determine_step_type(i)

            if step_type == "initial":
                query = self._build_initial_query(step)
            elif step_type == "final":
                query = self._build_final_query(step, queries)
            else:
                query = self._build_intermediate_query(step, queries)

            queries.append(query)

        return queries

    def _determine_step_type(self, index: int) -> str:
        """确定步骤类型"""
        if index == 0:
            return "initial"
        elif index == len(self.steps) - 1:
            return "final"
        else:
            return "intermediate"

    def _build_initial_query(self, step: Dict) -> ChainQuery:
        """构建初始查询"""
        step_content = step.get('content', '')
        hint = self._extract_hint(step_content)

        template = random.choice(self.INITIAL_TEMPLATES)
        query_text = template.format(hint=hint)

        return ChainQuery(
            turn=1,
            step_index=0,
            step_type="initial",
            query=query_text,
            expected_info=step_content,
            depends_on=[],
            validation_hints=step.get('expected_hints', [])
        )

    def _build_intermediate_query(
        self,
        step: Dict,
        previous_queries: List[ChainQuery]
    ) -> ChainQuery:
        """构建中间推理查询"""
        step_content = step.get('content', '')
        step_index = step.get('step_index', len(previous_queries))

        # 获取前一步的信息
        if previous_queries:
            previous_fact = self._simplify(previous_queries[-1].expected_info)
        else:
            previous_fact = "之前的观察"

        next_question = self._to_question(step_content)

        template = random.choice(self.INTERMEDIATE_TEMPLATES)
        query_text = template.format(
            previous_fact=previous_fact,
            next_question=next_question
        )

        return ChainQuery(
            turn=len(previous_queries) + 1,
            step_index=step_index,
            step_type="intermediate",
            query=query_text,
            expected_info=step_content,
            depends_on=[pq.expected_info for pq in previous_queries[-2:]],
            validation_hints=step.get('expected_hints', [])
        )

    def _build_final_query(
        self,
        step: Dict,
        previous_queries: List[ChainQuery]
    ) -> ChainQuery:
        """构建最终验证查询"""
        # 构建推理链摘要
        chain_summary = " → ".join(
            self._simplify(q.expected_info)
            for q in previous_queries[-3:]  # 最多取最近3步
        )

        template = random.choice(self.FINAL_TEMPLATES)
        query_text = template.format(
            chain_summary=chain_summary,
            original_question=self.original_question
        )

        return ChainQuery(
            turn=len(previous_queries) + 1,
            step_index=len(self.steps) - 1,
            step_type="final",
            query=query_text,
            expected_info=self.expected_answer,
            depends_on=[q.expected_info for q in previous_queries],
            validation_hints=step.get('expected_hints', []) + [self.expected_answer]
        )

    def _build_simple_query(self) -> ChainQuery:
        """构建简单的单步查询"""
        return ChainQuery(
            turn=1,
            step_index=0,
            step_type="final",
            query=self.original_question,
            expected_info=self.expected_answer,
            depends_on=[],
            validation_hints=[self.expected_answer]
        )

    def validate_response(
        self,
        response: str,
        query: ChainQuery
    ) -> Tuple[bool, float, str]:
        """
        验证VLM的回答

        Args:
            response: VLM的回答
            query: 对应的查询

        Returns:
            Tuple[passed, score, reasoning]
        """
        response_lower = response.lower()

        # 检查关键词匹配
        hints_found = 0
        total_hints = len(query.validation_hints)

        for hint in query.validation_hints:
            if hint.lower() in response_lower:
                hints_found += 1

        # 计算分数
        if total_hints > 0:
            score = hints_found / total_hints
        else:
            # 无明确提示时，假设通过
            score = 0.6

        # 判断是否通过
        passed = score >= 0.5

        # 构建评估理由
        if passed:
            reasoning = f"Found {hints_found}/{total_hints} expected elements"
        else:
            missing = [h for h in query.validation_hints if h.lower() not in response_lower]
            reasoning = f"Missing elements: {missing[:3]}"

        # 更新状态
        self.state.current_step = query.step_index + 1
        self.state.steps_passed.append(passed)

        if passed:
            self.state.collected_facts.append(response[:200])
        else:
            self.state.chain_broken = True
            self.state.break_reason = reasoning

        return passed, score, reasoning

    def get_chain_progress(self) -> Dict[str, Any]:
        """获取推理链进度"""
        return {
            'total_steps': self.state.total_steps,
            'current_step': self.state.current_step,
            'steps_passed': self.state.steps_passed,
            'pass_rate': sum(self.state.steps_passed) / len(self.state.steps_passed) if self.state.steps_passed else 0,
            'chain_broken': self.state.chain_broken,
            'break_reason': self.state.break_reason,
            'collected_facts_count': len(self.state.collected_facts)
        }

    def is_chain_complete(self) -> bool:
        """检查推理链是否完成"""
        return (
            self.state.current_step >= self.state.total_steps and
            not self.state.chain_broken
        )

    # ========== 辅助方法 ==========

    def _extract_hint(self, text: str) -> str:
        """从文本中提取提示"""
        # 取前30个字符或第一个分句
        if '.' in text:
            return text.split('.')[0][:30]
        return text[:30]

    def _simplify(self, text: str) -> str:
        """简化文本"""
        if '.' in text:
            return text.split('.')[0][:40]
        return text[:40]

    def _to_question(self, statement: str) -> str:
        """将陈述转换为问题"""
        statement = statement.strip().rstrip('.')

        # 简单转换
        if statement.startswith(('The ', 'A ', 'An ')):
            return f"what about {statement.lower()}"
        else:
            return f"{statement}?"
```

---

## 🔧 子任务 2.5: 集成到StrategicSimulator

### 文件位置

`src/simulator/strategic_simulator.py`

### 修改内容

在 `StrategicSimulator` 类中添加推理链测试支持:

```python
# 在文件开头添加导入
from .reasoning_chain_builder import ReasoningChainBuilder, ChainQuery

class StrategicSimulator:
    # ... 现有代码 ...

    def run_task(self, task: Dict) -> Dict:
        """
        运行任务

        根据任务类型选择执行模式:
        - 普通任务: 标准多轮测试
        - rationale_based_abr: 推理链测试
        """
        task_type = task.get('task_type', '')

        # 如果是推理链任务，使用专门的处理流程
        if task_type == 'rationale_based_abr' and 'reasoning_chain' in task:
            return self._run_reasoning_chain_test(task)

        # 否则使用标准流程
        return self._run_standard_test(task)

    def _run_reasoning_chain_test(self, task: Dict) -> Dict:
        """
        运行推理链测试

        流程:
        1. 构建推理链查询序列
        2. 逐步验证模型回答
        3. 评估推理链完整性
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"[推理链测试] Task: {task['task_id']}")
            print(f"{'='*60}")

        # 初始化
        chain_builder = ReasoningChainBuilder(task)
        chain_queries = chain_builder.build_chain_queries()

        report = {
            'task_id': task['task_id'],
            'task_type': 'reasoning_chain_test',
            'reasoning_depth': len(chain_queries),
            'execution': {
                'total_turns': 0,
                'phases_completed': ['reasoning_chain'],
                'final_difficulty': 2
            },
            'conversation_log': [],
            'reasoning_chain_evaluation': [],
            'scores': {
                'aggregate': {},
                'per_turn': []
            }
        }

        # 构建初始消息
        conversation_history = []
        images = task.get('images', [])

        # 逐步执行推理链
        for query_info in chain_queries:
            turn_num = query_info.turn

            if self.verbose:
                print(f"\n  [Turn {turn_num}/{len(chain_queries)}] Type: {query_info.step_type}")
                print(f"  Query: {query_info.query[:80]}...")

            # 调用VLM
            vlm_response = self._call_vlm(
                messages=conversation_history,
                new_message=query_info.query,
                images=images
            )

            if self.verbose:
                print(f"  Response: {vlm_response[:80]}...")

            # 验证回答
            passed, score, reasoning = chain_builder.validate_response(
                response=vlm_response,
                query=query_info
            )

            if self.verbose:
                print(f"  Validation: passed={passed}, score={score:.2f}")

            # 记录
            turn_log = {
                'turn': turn_num,
                'user_query': query_info.query,
                'vlm_response': vlm_response,
                'step_type': query_info.step_type,
                'expected_info': query_info.expected_info[:100],
                'evaluation': {
                    'passed': passed,
                    'score': score,
                    'reasoning': reasoning
                }
            }

            conversation_history.append({
                'role': 'user',
                'content': query_info.query
            })
            conversation_history.append({
                'role': 'assistant',
                'content': vlm_response
            })

            report['conversation_log'].append(turn_log)
            report['reasoning_chain_evaluation'].append({
                'step': turn_num,
                'step_type': query_info.step_type,
                'passed': passed,
                'score': score,
                'memory_intact': not chain_builder.state.chain_broken
            })
            report['scores']['per_turn'].append({
                'turn': turn_num,
                'score': score
            })

            report['execution']['total_turns'] = turn_num

            # 如果推理链断裂，可以选择继续或停止
            if chain_builder.state.chain_broken:
                if self.verbose:
                    print(f"  [!] Chain broken at step {turn_num}")
                # 继续测试，但记录断裂

        # 计算最终结果
        progress = chain_builder.get_chain_progress()

        report['scores']['aggregate'] = {
            'overall': progress['pass_rate'],
            'robustness': 1.0 if not progress['chain_broken'] else 0.5,
            'consistency': progress['pass_rate'],
            'memory_retention': len(progress.get('collected_facts_count', 0)) / len(chain_queries) if chain_queries else 0,
            'faithfulness': progress['pass_rate'],
            'reasoning_chain_coherence': 1.0 if chain_builder.is_chain_complete() else 0.5
        }

        report['reasoning_chain_progress'] = progress

        if self.verbose:
            print(f"\n  [完成] Chain coherence: {report['scores']['aggregate']['reasoning_chain_coherence']:.2f}")
            print(f"  Pass rate: {progress['pass_rate']:.2f}")

        return report

    def _call_vlm(
        self,
        messages: List[Dict],
        new_message: str,
        images: List[str]
    ) -> str:
        """调用VLM获取回答"""
        # 构建完整消息列表
        full_messages = messages.copy()
        full_messages.append({
            'role': 'user',
            'content': new_message
        })

        try:
            response = self.llm_client.generate(
                messages=full_messages,
                images=images if images else None
            )
            return response
        except Exception as e:
            logger.error(f"VLM call failed: {e}")
            return f"[Error: {str(e)}]"
```

---

## 🔧 子任务 2.6: 添加推理链评估方法

### 文件位置

`src/simulator/evaluator.py`

### 添加内容

```python
class Evaluator:
    # ... 现有代码 ...

    def evaluate_reasoning_step(
        self,
        vlm_response: str,
        expected_info: str,
        dependencies: List[str],
        previous_responses: List[str]
    ) -> Dict[str, Any]:
        """
        评估推理链中的单个步骤

        Args:
            vlm_response: VLM的回答
            expected_info: 期望的信息
            dependencies: 依赖的前置信息
            previous_responses: 之前的回答

        Returns:
            评估结果字典
        """
        result = {
            'passed': False,
            'score': 0.0,
            'reasoning': '',
            'remembers_dependencies': True,
            'introduces_hallucination': False
        }

        # 1. 检查是否包含期望信息
        expected_lower = expected_info.lower()
        response_lower = vlm_response.lower()

        # 简单关键词匹配
        expected_keywords = set(expected_lower.split())
        response_keywords = set(response_lower.split())
        overlap = len(expected_keywords & response_keywords)

        if len(expected_keywords) > 0:
            keyword_score = overlap / len(expected_keywords)
        else:
            keyword_score = 0.5

        # 2. 检查是否记住依赖信息
        for dep in dependencies:
            dep_keywords = dep.lower().split()[:3]  # 取前3个关键词
            if not any(kw in response_lower for kw in dep_keywords):
                result['remembers_dependencies'] = False
                break

        # 3. 检查是否引入幻觉（简化检测）
        # 这里可以扩展为更复杂的幻觉检测
        hallucination_indicators = ['我不确定', '可能是', '我猜', 'I think', 'maybe', 'perhaps']
        if any(ind in response_lower for ind in hallucination_indicators):
            result['introduces_hallucination'] = True

        # 4. 综合评分
        base_score = keyword_score
        if not result['remembers_dependencies']:
            base_score *= 0.8
        if result['introduces_hallucination']:
            base_score *= 0.9

        result['score'] = base_score
        result['passed'] = base_score >= 0.5
        result['reasoning'] = f"Keyword overlap: {keyword_score:.2f}, Dependencies remembered: {result['remembers_dependencies']}"

        return result

    def evaluate_reasoning_chain(
        self,
        step_evaluations: List[Dict],
        expected_final_answer: str,
        actual_final_answer: str
    ) -> Dict[str, Any]:
        """
        评估完整的推理链

        Args:
            step_evaluations: 各步骤的评估结果
            expected_final_answer: 期望的最终答案
            actual_final_answer: 实际的最终答案

        Returns:
            推理链整体评估
        """
        if not step_evaluations:
            return {
                'chain_coherence': 0.0,
                'steps_passed_ratio': 0.0,
                'final_answer_correct': False,
                'overall_reasoning_score': 0.0
            }

        # 计算各项指标
        steps_passed = sum(1 for e in step_evaluations if e.get('passed', False))
        total_steps = len(step_evaluations)
        pass_ratio = steps_passed / total_steps

        # 检查最终答案
        final_correct = self._check_answer_match(actual_final_answer, expected_final_answer)

        # 链条连贯性（所有步骤都记住依赖 = 完全连贯）
        all_remember = all(e.get('remembers_dependencies', True) for e in step_evaluations)
        coherence = 1.0 if all_remember else 0.5 + 0.5 * pass_ratio

        # 整体分数
        overall = (pass_ratio * 0.4 + coherence * 0.3 + (1.0 if final_correct else 0.0) * 0.3)

        return {
            'chain_coherence': coherence,
            'steps_passed_ratio': pass_ratio,
            'steps_passed': steps_passed,
            'total_steps': total_steps,
            'final_answer_correct': final_correct,
            'overall_reasoning_score': overall
        }

    def _check_answer_match(self, actual: str, expected: str) -> bool:
        """检查答案是否匹配"""
        actual_lower = actual.lower().strip()
        expected_lower = expected.lower().strip()

        # 完全匹配
        if actual_lower == expected_lower:
            return True

        # 包含匹配
        if expected_lower in actual_lower:
            return True

        # 关键词匹配
        expected_keywords = set(expected_lower.split())
        actual_keywords = set(actual_lower.split())
        overlap = len(expected_keywords & actual_keywords)

        return overlap >= len(expected_keywords) * 0.7
```

---

## 📁 输出文件结构

完成本窗口任务后，应该新增/修改以下文件:

```
M3Bench_new/
├── dataprovider/
│   ├── loader.py                         # [修改] VCR加载器增强
│   ├── generator_v2.py                   # [修改] 添加rationale_based_abr
│   └── rationale_based_generator.py      # [新建] Rationale任务生成器
│
├── src/simulator/
│   ├── strategic_simulator.py            # [修改] 添加推理链测试
│   ├── evaluator.py                      # [修改] 添加推理链评估
│   └── reasoning_chain_builder.py        # [新建] 推理链构建器
│
├── dataset_configs.yaml                  # [修改] 添加rationale_based_abr配置
│
├── scripts/
│   └── analyze_vcr_data.py               # [新建] VCR数据分析脚本
│
└── tests/
    ├── test_vcr_loader.py                # [新建] VCR加载器测试
    └── test_reasoning_chain.py           # [新建] 推理链测试
```

---

## ✅ 验证清单

```bash
# 1. VCR加载器测试
python -c "
from dataprovider import DataLoader
loader = DataLoader()
samples = loader.load_dataset('vcr', split='val', max_samples=5, include_rationale=True)
for s in samples:
    print(f\"Q: {s['question_text'][:50]}...\")
    print(f\"R: {s.get('rationale_text', 'N/A')[:50]}...\")
    print(f\"Steps: {s.get('reasoning_steps', [])}\")
    print()
"

# 2. Rationale任务生成
python generate_all_tasks_v2.py
cat generated_tasks_v2/run_*/tasks/rationale_based_abr_vcr.jsonl | head -1 | python -m json.tool

# 3. 推理链构建测试
python -c "
from src.simulator.reasoning_chain_builder import ReasoningChainBuilder
import json

# 加载一个任务
with open('generated_tasks_v2/run_13/tasks/rationale_based_abr_vcr.jsonl') as f:
    task = json.loads(f.readline())

builder = ReasoningChainBuilder(task)
queries = builder.build_chain_queries()

for q in queries:
    print(f'Turn {q.turn} [{q.step_type}]: {q.query[:60]}...')
"

# 4. 完整推理链测试
python tests/test_reasoning_chain.py

# 5. 端到端测试
python run_experiment.py --turns 30 --tasks-per-config 2
```

---

## 📊 预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| VCR rationale利用 | 未使用 | 完全利用 |
| 推理链任务 | 0 | 每个VCR样本生成1个 |
| 平均推理步骤 | N/A | 2-4步 |
| 跨轮推理验证 | 无 | 每步验证 |
| 推理链完整性评估 | 无 | 有 |
