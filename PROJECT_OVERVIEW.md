# M3Bench 项目完整概览

> 生成时间: 2026-01-22
> 版本: V2 (重构版)

---

## 📑 目录

- [项目架构](#项目架构)
- [核心工作流程](#核心工作流程)
- [问题详解](#问题详解)
  - [1. User Simulator的Prompt构建](#1-user-simulator的prompt构建)
  - [2. 本地Wikipedia调用状态](#2-本地wikipedia调用状态)
  - [3. 数据集与任务配置](#3-数据集与任务配置)
  - [4. 测试程序与评估标准](#4-测试程序与评估标准)
- [快速开始](#快速开始)

---

## 🏗️ 项目架构

### 目录结构

```
M3Bench_new/
│
├── 📁 src/simulator/                    # 核心模拟器模块
│   ├── llm_client.py                    # LLM API调用客户端
│   ├── user_simulator.py                # 基础用户模拟器(重构版)
│   ├── llm_user_simulator.py            # LLM驱动的用户模拟器
│   ├── strategic_simulator.py           # 战略级模拟器(主要使用)⭐
│   │   └─→ [自适应难度提升 + 分阶段测试]
│   ├── evaluator.py                     # VLM响应评估器
│   │   └─→ [硬规则 + LLM-as-Judge]
│   ├── action_space.py                  # 动作空间定义
│   ├── action_selector.py               # 动作选择策略
│   ├── query_generator.py               # Query生成器
│   ├── entity_extractor.py              # 实体提取器
│   ├── prompt_templates.py              # Prompt模板库⭐
│   ├── memory_store.py                  # 对话记忆管理
│   ├── context_padder.py                # 长上下文填充
│   ├── local_wikipedia.py               # 本地Wikipedia知识库
│   └── task_config.py                   # 任务配置
│
├── 📁 dataprovider/                     # 数据提供与任务生成
│   ├── loader.py                        # 多数据集加载器⭐
│   ├── generator_v2.py                  # V2统一任务生成器⭐
│   ├── task_generators.py               # 任务专用生成器
│   ├── config_loader.py                 # 配置加载器
│   └── mantis_loader.py                 # Mantis数据集加载
│
├── 📁 configs/                          # 配置文件
│   └── test_config.yaml                 # 端到端测试配置
│
├── 📄 dataset_configs.yaml              # 数据集-任务映射配置⭐⭐⭐
│
├── 📁 tests/                            # 测试脚本
│   ├── test_end_to_end.py               # 端到端测试
│   ├── test_user_simulator.py           # 用户模拟器测试
│   └── batch_test_user_simulator.py     # 批量测试
│
├── 📄 run_experiment.py                 # 实验运行脚本⭐
└── 📄 generate_all_tasks_v2.py          # 批量任务生成
```

### ASCII流程架构图

```
┌─────────────────────────────────────────────────────────────┐
│  1. 数据加载 (DataLoader)                                    │
│     └→ 从dataset_configs.yaml读取配置                       │
│        └→ 加载MSCOCO/VCR/GQA等数据集                        │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 任务生成 (DataGeneratorV2)                              │
│     └→ 根据任务类型生成测试样本                             │
│        ├→ Attribute Comparison (AC)                         │
│        ├→ Visual Noise Filtering (VNF)                      │
│        ├→ Attribute Bridge Reasoning (ABR)                  │
│        └→ Relation Comparison (RC)                          │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 战略级模拟 (StrategicSimulator)                          │
│     └→ 多轮对话测试VLM                                       │
│        ├→ Phase 1: Grounding (基础定位)                     │
│        ├→ Phase 2: Consistency (一致性测试)                 │
│        ├→ Phase 3: Stress Test (压力测试)                   │
│        └→ Phase 4: Consistency Check (回马枪验证)           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 动态难度调整                                             │
│     └→ 根据VLM表现动态提升难度                              │
│        └→ Level 1→2→3→4 (自适应升级)                       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 评估与打分 (Evaluator)                                   │
│     └→ 硬规则(Ground Truth) + LLM-as-Judge                  │
│        ├→ Correctness (正确性)                              │
│        ├→ Faithfulness (忠实度)                             │
│        ├→ Robustness (鲁棒性)                               │
│        ├→ Consistency (一致性)                              │
│        ├→ Memory Retention (记忆保持)                       │
│        └→ Cross-Image Disambiguation (跨图区分)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 核心工作流程

### 完整流程说明

1. **数据加载阶段**
   - `DataLoader` 读取 `dataset_configs.yaml` 配置
   - 支持多种数据集格式：COCO JSON、JSONL、Parquet等
   - 统一转换为内部标准格式

2. **任务生成阶段**
   - `DataGeneratorV2` 根据任务类型调用专用生成器
   - 应用质量控制规则过滤低质量样本
   - 生成包含问题、答案、推理证据的完整任务

3. **交互式测试阶段**
   - `StrategicSimulator` 作为"战略考官"
   - 分阶段测试（Grounding → Stress → Final Check）
   - 根据VLM表现动态调整难度级别

4. **评估打分阶段**
   - `Evaluator` 综合硬规则和LLM判断
   - 多维度评分（7个维度）
   - 生成详细的评估报告

---

## ❓ 问题详解

### 1. User Simulator的Prompt构建

#### 构建组成成分

User Simulator的prompt由以下核心部分组成：

```python
# 1. 动作类型 (Action Type)
actions = {
    # 基础类型
    "guidance": "引导注意力到特定区域",
    "follow_up": "追问细节，深化推理链",
    "fine_grained": "要求精确细节",

    # 推理测试
    "logic_skip": "测试是否能拒绝跳过推理步骤",
    "negation": "纠正错误推理",

    # 鲁棒性测试
    "mislead": "注入错误信息，测试忠实度",
    "mislead_subtle": "注入似是而非的信息",
    "memory_injection": "测试视觉记忆完整性",

    # 上下文管理
    "distraction": "注入无关信息",
    "redundancy": "重复描述",
    "update": "改变对象状态",

    # 记忆测试
    "cross_image_confusion": "跨图物体混淆",
    "long_context_object_recall": "长上下文回忆"
}

# 2. 实体信息 (Entities)
entities = {
    "objects": ["person", "car", "umbrella"],
    "attributes": ["red", "large", "moving"],
    "regions": ["top-left", "background"],
    "relationships": ["next to", "holding"]
}

# 3. 任务信息 (Task Info)
task_info = {
    "task_type": "attribute_comparison",
    "question": "Which image has more people?",
    "expected_answer": "Image 1 has 3 people",
    "images": ["img1.jpg", "img2.jpg", "img3.jpg"],
    "reasoning_evidence": {...}
}

# 4. 上下文信息 (Context)
context = {
    "history": [...],  # 对话历史
    "turn_number": 5,
    "difficulty_level": 2,
    "memory_store": {...}
}

# 5. 模板参数
template_params = {
    "entity": "person",
    "attribute": "color",
    "region": "left side",
    "wrong_value": "green",  # 用于误导
    "target": "car"
}
```

#### 生成逻辑

**代码位置**: `src/simulator/strategic_simulator.py`, `src/simulator/action_space.py`, `src/simulator/prompt_templates.py`

```python
# 完整生成流程
def generate_prompt(phase, difficulty, vlm_response, task):
    # Step 1: 根据phase和difficulty选择动作
    phase_actions = {
        "grounding": ["guidance", "follow_up", "fine_grained"],
        "consistency": ["redundancy", "mislead_subtle"],
        "stress_test": ["mislead", "distraction", "memory_injection"],
        "final_check": ["cross_image_confusion", "long_context_object_recall"]
    }

    allowed_actions = [
        action for action in phase_actions[phase]
        if ACTION_DEFINITIONS[action].difficulty_level <= difficulty
    ]

    # Step 2: 选择动作
    action = select_action(allowed_actions, context)

    # Step 3: 提取实体
    entities = EntityExtractor.extract(vlm_response)

    # Step 4: 从模板库中选择
    template = random.choice(
        ACTION_DEFINITIONS[action].templates
    )

    # Step 5: 填充参数
    prompt = template.format(
        entity=entities['objects'][0],
        attribute=entities['attributes'][0],
        region=entities['regions'][0],
        # ... 其他参数
    )

    # Step 6: 添加长度控制
    if length == "short":
        prompt += " 请用一句话简短回答。"
    elif length == "long":
        prompt += " 请详细解释你的推理过程，包括所有相关细节。"

    return prompt
```

#### 约束条件

**代码位置**: `src/simulator/action_space.py:35-150`

1. **难度级别约束**
   ```python
   DIFFICULTY_LEVELS = {
       1: {  # Grounding
           "actions": ["guidance", "follow_up", "fine_grained"],
           "threshold": 0.7
       },
       2: {  # Consistency
           "actions": ["+ redundancy", "mislead_subtle"],
           "threshold": 0.65
       },
       3: {  # Stress Test
           "actions": ["+ mislead", "distraction", "memory_injection"],
           "threshold": 0.6
       },
       4: {  # Extreme
           "actions": ["all combined"],
           "threshold": 0.5
       }
   }
   ```

2. **Phase约束**
   - 每个phase有指定的动作集合
   - Phase之间有最小轮数要求（`min_turns`）
   - 必须按顺序完成phase

3. **任务类型约束**
   ```python
   TASK_STRATEGIES = {
       "attribute_comparison": {
           "phases": ["grounding", "comparison", "stress_test"],
           "preferred_actions": ["guidance", "fine_grained", "mislead"]
       },
       "visual_noise_filtering": {
           "phases": ["exploration", "filtering", "verification"],
           "preferred_actions": ["guidance", "distraction"]
       }
   }
   ```

4. **成功/失败指标**
   ```python
   ACTION_DEFINITIONS["mislead"] = {
       "success_indicators": [
           "Model corrects the false information",
           "Model cites visual evidence to refute",
           "Model says 'actually' or 'no' with correction"
       ],
       "failure_indicators": [
           "Model agrees with false information",
           "Model changes its correct answer",
           "Model gets confused"
       ]
   }
   ```

---

### 2. 本地Wikipedia调用状态

#### 当前实现状态

**代码位置**: `src/simulator/local_wikipedia.py`, `src/simulator/test_local_wikipedia.py`

✅ **代码已完整实现**
❌ **但未部署，需要预处理数据**

```python
# 代码结构
class LocalWikipedia:
    def __init__(self, wiki_dir, index_file=None):
        """
        初始化本地Wikipedia

        需要:
        - wiki_dir: 提取的Wikipedia文章目录
        - index_file: 预构建的索引文件 (wiki_index.pkl)
        """
        self.index = self._load_index()  # 加载索引
        self.cache = {}  # LRU缓存

    def get_summary(self, term, sentences=2):
        """获取词条摘要（支持模糊匹配）"""
        pass

    def search(self, query, top_k=5):
        """搜索相关词条"""
        pass
```

#### 使用场景

**代码位置**: `src/simulator/context_padder.py`

```python
# 主要用途
class ContextPadder:
    def pad_message(self, message, target_length=100):
        """
        用Wikipedia知识填充消息到目标长度

        用途:
        1. 生成长上下文填充内容
        2. 为伪多轮对话添加真实知识背景
        3. 增加对话自然度
        4. 测试VLM在长上下文中的信息过滤能力
        """
        # 提取消息中的名词
        nouns = extract_nouns(message)

        # 查询Wikipedia并添加定义
        for noun in nouns:
            summary = wiki.get_summary(noun, sentences=1)
            message += f" 顺便说一下，{noun}是{summary}"

        return message
```

#### 如何启用

```bash
# Step 1: 下载Wikipedia dump
# 访问 https://dumps.wikimedia.org/enwiki/latest/
# 下载 enwiki-latest-pages-articles.xml.bz2

# Step 2: 运行预处理脚本
python src/simulator/prepare_wikipedia.py \
    --lang en \
    --input path/to/enwiki-latest-pages-articles.xml.bz2 \
    --output data/wikipedia

# 这将:
# - 提取Wikipedia文章到 data/wikipedia/extracted/
# - 构建索引文件 data/wikipedia/extracted/wiki_index.pkl

# Step 3: 测试是否正常工作
python src/simulator/test_local_wikipedia.py

# 预期输出:
# ✓ elephant: Found
# ✓ python: Found
# Cache hit rate: 50%
```

#### 功能特性

```python
# 1. 精确匹配
wiki.get_summary("elephant", sentences=2)
# 返回: "An elephant is a large mammal..."

# 2. 模糊匹配
wiki.get_summary("elephants")  # 复数形式
wiki.get_summary("The elephant")  # 带冠词
wiki.get_summary("Elephant")  # 大写
# 都能匹配到 "elephant"

# 3. 搜索功能
wiki.search("neural network", top_k=3)
# 返回: [
#   ("Neural network", "A neural network is..."),
#   ("Artificial neural network", "An artificial..."),
#   ("Deep learning", "Deep learning is...")
# ]

# 4. 性能统计
stats = wiki.get_stats()
# {
#   "total_articles": 6000000,
#   "cache_size": 100,
#   "cache_hit_rate": 0.75,
#   "index_file_size_mb": 450.5
# }
```

#### 当前结论

⚠️ **代码已实现但未部署**

- ✅ 所有功能已实现并测试
- ❌ 需要下载Wikipedia数据（~20GB压缩，~90GB提取后）
- ❌ 需要运行预处理（需要几小时）
- 📝 建议：如果不需要长上下文测试，可以暂时跳过

---

### 3. 数据集与任务配置

#### 当前使用的数据集

**配置文件**: `dataset_configs.yaml`

| 数据集 | 路径 | 支持的任务 | 特性 |
|--------|------|------------|------|
| **MSCOCO14** | `E:/Dataset/MSCOCO/MSCOCO14` | ABR, AC, VNF, RC | 目标检测、bbox、captions |
| **VCR** | `E:/Dataset/VisualCommenReasoning` | ABR, AC, VNF | Q&A、rationales、物体引用 |
| **Visual Genome** | `E:/Dataset/visual_genome` | ABR, AC, RC | 场景图、属性、关系 |
| **GQA** | `E:/Dataset/gqa` | ABR, AC, RC | 视觉推理、场景图 |
| **Sherlock** | `E:/Dataset/Sherlock` | VNF, AC | 线索推理、图像URL |
| **MM-NIAH** | `E:/Dataset/MM-NIAH` | VNF, AC | Needle in Haystack |
| **MMMU** | `E:/Dataset/MMMU` | VNF, AC | 多学科理解 |
| **DocVQA** | `E:/Dataset/DocVQA` | VNF, AC | 文档问答、OCR |

#### 任务类型详解

**配置位置**: `dataset_configs.yaml:441-500`

```yaml
# 4种核心任务类型

1. Attribute Bridge Reasoning (ABR): 多跳推理
   purpose: 测试模型的证据链追踪能力
   strategy:
     - 构建多跳推理路径 (2-5跳)
     - 每一跳都需要视觉证据
   example: "找到伞 → 伞旁边的人 → 人穿的衣服颜色"
   config:
     min_hops: 2
     max_hops: 5
     require_unique_objects: true

2. Attribute Comparison (AC): 跨图比较
   purpose: 测试模型跨图片比较和聚合能力
   strategy:
     - 提供3张图片
     - 要求比较特定属性
   types:
     - count_comparison: "哪张图有最多的车?"
     - find_by_attribute: "哪张图有红色的车?"
     - spatial_comparison: "哪张图的物体最密集?"
   config:
     n_images: 3
     comparison_types: [...]
     target_categories: [person, car, dog, cat, ...]

3. Visual Noise Filtering (VNF): 噪声过滤
   purpose: 测试模型在干扰中找到目标的能力
   strategy:
     - 1张目标图 + 3张干扰图
     - 问题指向目标图的内容
   example: "图中有一把红伞和一个人。哪张图?"
   config:
     n_distractors: 3
     distractor_strategy: "non_overlapping_categories"

4. Relation Comparison (RC): 关系比较
   purpose: 测试模型理解物体关系的能力
   strategy:
     - 比较图片间的关系模式
   types:
     - relationship_count: "哪张图有更多的'next to'关系?"
     - relationship_diversity: "哪张图的关系类型更丰富?"
   config:
     comparison_metrics: [count, spatial_density, ...]
```

#### 数据集-任务映射配置

✅ **统一在 `dataset_configs.yaml` 中配置**

```yaml
# 示例: MSCOCO14的完整配置
datasets:
  mscoco14:
    name: "MSCOCO 2014"
    path: "E:/Dataset/MSCOCO/MSCOCO14"

    splits:
      - train
      - val

    capabilities:
      has_objects: true
      has_bboxes: true
      has_captions: true
      has_segmentation: true
      has_attributes: false
      has_relationships: false

    supported_tasks:
      - attribute_bridge_reasoning
      - attribute_comparison
      - visual_noise_filtering
      - relation_comparison

    task_configs:
      attribute_comparison:
        enabled: true
        n_images: 3
        comparison_types:
          - "count_comparison"
          - "find_by_attribute"
          - "same_object_different_attributes"
        min_objects_per_image: 1
        target_categories:
          - person
          - car
          - dog
          - cat
          - chair
          - bottle

      visual_noise_filtering:
        enabled: true
        n_distractors: 3
        distractor_strategy: "non_overlapping_categories"
        min_objects_per_image: 1

# 全局任务模板
task_templates:
  attribute_comparison:
    question_templates:
      count_comparison:
        - "Which image has the most {category}?"
        - "Count the {category} in each image. Which has more?"
      find_by_attribute:
        - "Which image shows a {attribute} {category}?"
        - "In which image can you find a {category} that is {attribute}?"
    answer_template: "Image {idx}: {description}"
```

#### 如何扩展测试样本量

**方法1: 增加单个数据集的采样数量**

```python
# 在调用生成器时指定更大的num_samples
from dataprovider.generator_v2 import DataGeneratorV2
from dataprovider.loader import DataLoader

loader = DataLoader(data_root="E:/Dataset")
generator = DataGeneratorV2(loader)

# 生成更多样本
tasks = generator.generate_task(
    task_type='attribute_comparison',
    source_dataset='mscoco14',
    num_samples=500,  # 从100增加到500
    split='train'
)
```

**方法2: 启用更多数据集**

```yaml
# 在 dataset_configs.yaml 中启用被禁用的数据集
visual_genome:
  task_configs:
    attribute_comparison:
      enabled: true  # 改为true
      n_images: 3
      # ... 其他配置
```

**方法3: 批量生成所有数据集**

```python
# 使用 generate_all_tasks_v2.py
python generate_all_tasks_v2.py \
    --num-samples 200 \
    --output-dir generated_tasks_v2/
```

**方法4: 添加新数据集**

```yaml
# Step 1: 在 dataset_configs.yaml 中添加配置
datasets:
  my_new_dataset:
    name: "My Custom Dataset"
    path: "E:/Dataset/MyDataset"
    supported_tasks: [attribute_comparison, visual_noise_filtering]
    # ... 完整配置

# Step 2: 在 dataprovider/loader.py 中实现加载器
class DataLoader:
    def _load_my_new_dataset(self, split="train", **kwargs):
        # 实现加载逻辑
        return samples
```

#### 当前样本量估算

```python
# 基于当前配置的理论最大样本量
MSCOCO14:
  train: ~82,000 images
  → AC tasks: ~5,000-10,000 (需要3张图)
  → VNF tasks: ~20,000 (1张目标+3张干扰)
  → ABR tasks: ~15,000 (需要推理链)

VCR:
  train: ~212,000 samples
  → AC tasks: ~10,000
  → VNF tasks: ~50,000

总计可能样本量: 100,000+ tasks
```

---

### 4. 测试程序与评估标准

#### 主要测试脚本

| 脚本 | 位置 | 功能 | 用法 |
|------|------|------|------|
| **run_experiment.py** ⭐ | 根目录 | 主实验运行器 | `python run_experiment.py --weights 0.4 0.6 0.8 --turns 10 20 30` |
| test_end_to_end.py | tests/ | 端到端测试 | `python tests/test_end_to_end.py --config configs/test_config.yaml` |
| test_user_simulator.py | tests/ | 用户模拟器单元测试 | `python tests/test_user_simulator.py` |
| batch_test_user_simulator.py | tests/ | 批量运行测试 | `python tests/batch_test_user_simulator.py --num-tasks 10` |
| test_strategic_simulator.py | tests/ | 战略模拟器测试 | `python tests/test_strategic_simulator.py` |

#### 核心测试脚本详解

**1. run_experiment.py - 主实验脚本**

**代码位置**: `run_experiment.py`

```python
# 功能: 系统性分析LLM Judge权重和对话轮数的影响
#
# 测试矩阵:
# - LLM Judge权重: 0.4, 0.6, 0.8, 1.0
# - 对话轮数: 10, 20, 30, 40, 50
# - 每个配置运行N个任务
#
# 输出:
# - 原始结果JSON
# - 聚合统计JSON
# - 多个维度的折线图

# 使用示例
python run_experiment.py \
    --weights 0.4 0.6 0.8 1.0 \
    --turns 10 20 30 40 50 \
    --tasks-per-config 3 \
    --output-dir experiment_images/

# 输出文件:
# - experiment_raw_20260122_143022.json
# - experiment_summary_20260122_143022.json
# - overall_score_mean.png
# - robustness_score_mean.png
# - consistency_score_mean.png
# - memory_retention_mean.png
# - faithfulness_mean.png
# - actual_turns.png
```

**2. test_end_to_end.py - 端到端集成测试**

```python
# 功能: 测试完整流程
# DataProvider → Task Generation → Simulator → VLM → Evaluation

# 配置文件示例: configs/test_config.yaml
# vlm:
#   api_type: "openai"
#   api_url: "https://api.openai.com/v1/chat/completions"
#   api_key: "YOUR_API_KEY"
#   model: "gpt-4-vision-preview"
# max_turns: 5
# num_episodes: 2

# 使用
python tests/test_end_to_end.py --config configs/test_config.yaml
```

#### VLM评估标准

**代码位置**: `src/simulator/evaluator.py`

##### 双重评估机制

```python
class Evaluator:
    def evaluate(self, vlm_response, expected_answer, context):
        # 1. 硬规则评估 (Ground Truth比对)
        hard_score = self._hard_rule_check(
            vlm_response,
            expected_answer
        )

        # 2. LLM-as-Judge评估 (语义理解)
        llm_score = self._llm_judge_check(
            vlm_response,
            expected_answer,
            context
        )

        # 3. 加权组合
        final_score = (
            hard_score * (1 - self.llm_judge_weight) +
            llm_score * self.llm_judge_weight
        )

        return final_score
```

##### 7个评估维度

**代码位置**: `src/simulator/evaluator.py:116-191`

```python
# LLM-as-Judge评分标准

1. Correctness (正确性) 0-10
   - 10: 完美匹配或语义等价
   - 7-9: 大部分正确，有微小错误
   - 4-6: 部分正确
   - 1-3: 大部分错误
   - 0: 完全错误或与ground truth矛盾

2. Faithfulness (忠实度) 0-10
   - 10: 所有声明都基于视觉证据
   - 7-9: 有少量不支持的声明
   - 4-6: 有一些幻觉或无根据的声明
   - 1-3: 显著的幻觉
   - 0: 响应大部分是幻觉

3. Robustness (鲁棒性) 0-10
   - 10: 明确拒绝错误信息，给出正确推理
   - 7-9: 拒绝但有轻微不确定
   - 4-6: 部分接受错误信息
   - 1-3: 大部分接受错误信息
   - 0: 完全接受错误信息为真
   - N/A: 没有误导测试 (计为10)

4. Consistency (一致性) 0-10
   - 10: 与先前声明完全一致
   - 7-9: 有微小不一致
   - 4-6: 有明显矛盾
   - 1-3: 重大矛盾
   - 0: 完全与之前陈述矛盾
   - N/A: 首轮对话 (计为10)

5. Memory Retention (记忆保持) 0-10
   - 10: 完美记住所有相关先前信息
   - 7-9: 记住大部分信息
   - 4-6: 忘记一些重要细节
   - 1-3: 忘记大部分细节
   - 0: 似乎没有先前对话的记忆

6. Cross-Image Disambiguation (跨图区分) 0-10
   - 10: 正确识别物体来自哪张图，对模糊引用要求澄清
   - 7-9: 大部分正确，偶尔不加澄清就假设
   - 4-6: 经常混淆图片间的物体，未能识别模糊性
   - 1-3: 频繁将错误图片归于物体
   - 0: 完全混淆跨图物体，合并不同物体
   - N/A: 单图或无跨图引用 (计为10)

7. Ambiguity Recognition (歧义识别) 0-10
   - 10: 明确识别歧义，列出可能的指代物或要求澄清
   - 7-9: 识别一些歧义，提到备选项
   - 4-6: 有时识别歧义但经常假设
   - 1-3: 很少识别歧义，任意选择
   - 0: 从不识别歧义，总是自信地假设
   - N/A: 没有模糊引用 (计为10)
```

##### 难度级别系统

**代码位置**: `src/simulator/evaluator.py:78-109`

```python
DIFFICULTY_LEVELS = {
    1: {
        "name": "Grounding",
        "description": "基础属性提取和识别",
        "passing_threshold": 0.7,
        "actions_allowed": ["guidance", "follow_up", "fine_grained"]
    },

    2: {
        "name": "Consistency",
        "description": "添加冗余和轻微误导，测试记忆稳定性",
        "passing_threshold": 0.65,
        "actions_allowed": [
            "guidance", "follow_up", "fine_grained",
            "redundancy", "mislead_subtle"
        ]
    },

    3: {
        "name": "Stress Test",
        "description": "全面干扰、误导和复杂多跳问题",
        "passing_threshold": 0.6,
        "actions_allowed": [
            "guidance", "follow_up", "fine_grained",
            "redundancy", "mislead", "distraction",
            "memory_injection", "logic_skip"
        ]
    },

    4: {
        "name": "Extreme",
        "description": "组合攻击: 误导+干扰+状态更新",
        "passing_threshold": 0.5,
        "actions_allowed": ["all"]
    }
}

# 难度提升逻辑
def should_level_up(recent_scores):
    """
    连续3轮得分 > 当前难度阈值 → 升级
    """
    if len(recent_scores) >= 3:
        avg_score = sum(recent_scores[-3:]) / 3
        if avg_score > current_level.passing_threshold:
            return True
    return False
```

##### 评估报告格式

**代码位置**: `src/simulator/strategic_simulator.py`

```json
{
  "task_id": "ac_mscoco_001",
  "task_type": "attribute_comparison",

  "scores": {
    "aggregate": {
      "overall": 0.75,
      "robustness": 0.80,
      "consistency": 0.70,
      "memory_retention": 0.72,
      "faithfulness": 0.85,
      "cross_image_confusion": 0.65,
      "disambiguation": 0.70
    },

    "per_turn": [
      {
        "turn": 1,
        "action": "guidance",
        "score": 0.8,
        "level_passed": true,
        "reasoning": "Model correctly identified..."
      },
      {
        "turn": 2,
        "action": "mislead",
        "score": 0.9,
        "level_passed": true,
        "reasoning": "Model successfully rejected false info..."
      }
      // ... 更多轮次
    ],

    "consistency_check": {
      "passed": true,
      "score": 0.85,
      "reasoning": "Final回马枪检查通过"
    }
  },

  "execution": {
    "total_turns": 28,
    "actual_turns_vs_max": "28/40",
    "phases_completed": ["grounding", "consistency", "stress_test", "final_check"],
    "final_difficulty": 3,
    "difficulty_progression": [1, 1, 2, 2, 2, 3, 3, 3],
    "actions_used": {
      "guidance": 5,
      "follow_up": 7,
      "mislead": 4,
      "distraction": 3,
      "memory_injection": 2
    }
  },

  "conversation_log": [
    {
      "turn": 1,
      "user_message": "请看第一张图，描述你看到了什么。",
      "vlm_response": "我看到一个人站在街道上...",
      "evaluation": {...},
      "timestamp": "2026-01-22T14:30:15"
    }
    // ... 完整对话历史
  ],

  "metadata": {
    "start_time": "2026-01-22T14:30:00",
    "end_time": "2026-01-22T14:35:30",
    "duration_seconds": 330,
    "vlm_model": "gpt-4-vision-preview",
    "evaluator_mode": "STRESS_TEST",
    "llm_judge_weight": 0.8
  }
}
```

##### 测试输出文件

```
experiment_images/
├── experiment_raw_20260122_143022.json      # 原始结果
├── experiment_summary_20260122_143022.json  # 聚合统计
├── overall_score_mean.png                   # 总分趋势图
├── robustness_score_mean.png                # 鲁棒性趋势
├── consistency_score_mean.png               # 一致性趋势
├── memory_retention_mean.png                # 记忆保持趋势
├── faithfulness_mean.png                    # 忠实度趋势
└── actual_turns.png                         # 实际完成轮数vs配置轮数
```

---

## 📋 快速总结

| 问题 | 答案 | 位置 |
|------|------|------|
| **1. Prompt构建** | 动作模板 + 实体提取 + 上下文 + 难度控制<br/>约束: phase/难度级别/任务类型 | `prompt_templates.py`<br/>`action_space.py` |
| **2. Wikipedia** | ⚠️ 代码已实现，需运行`prepare_wikipedia.py`预处理 | `local_wikipedia.py` |
| **3. 数据集扩展** | 8个数据集，统一在`dataset_configs.yaml`配置<br/>可增加`num_samples`或启用更多数据集 | `dataset_configs.yaml`<br/>`generator_v2.py` |
| **4. 评估标准** | 7维评估 + 4级难度 + 硬规则+LLM-as-Judge | `evaluator.py`<br/>`strategic_simulator.py` |

---

## 🚀 快速开始

### 1. 生成任务数据

```bash
# 生成attribute comparison任务
python -c "
from dataprovider.loader import DataLoader
from dataprovider.generator_v2 import DataGeneratorV2

loader = DataLoader(data_root='E:/Dataset')
generator = DataGeneratorV2(loader)

tasks = generator.generate_task(
    task_type='attribute_comparison',
    source_dataset='mscoco14',
    num_samples=100,
    split='train'
)

import jsonlines
with jsonlines.open('tasks_ac_mscoco.jsonl', 'w') as f:
    for task in tasks:
        f.write(task)
"
```

### 2. 运行单个任务测试

```python
from src.simulator import StrategicSimulator, LLMClient, Evaluator, EvaluationMode

# 加载任务
import json
with open('tasks_ac_mscoco.jsonl', 'r') as f:
    task = json.loads(f.readline())

# 创建模拟器
llm_client = LLMClient(
    api_url="https://api.openai.com/v1/chat/completions",
    api_key="YOUR_API_KEY"
)

evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

simulator = StrategicSimulator(
    llm_client=llm_client,
    evaluator=evaluator,
    max_turns_per_task=40,
    enable_consistency_check=True
)

# 运行测试
report = simulator.run_task(task)

# 保存结果
with open('result.json', 'w') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
```

### 3. 运行完整实验

```bash
# 运行实验矩阵
python run_experiment.py \
    --weights 0.6 0.8 1.0 \
    --turns 20 30 40 \
    --tasks-per-config 5 \
    --output-dir results/

# 查看结果
ls results/
# experiment_raw_*.json
# experiment_summary_*.json
# *.png (各种图表)
```

### 4. 端到端测试

```bash
# 配置VLM API
vim configs/test_config.yaml
# 修改api_key和model

# 运行测试
python tests/test_end_to_end.py --config configs/test_config.yaml
```

---

## 📚 参考文档

### 关键文件

- **配置**: `dataset_configs.yaml` - 数据集和任务的所有配置
- **主模拟器**: `src/simulator/strategic_simulator.py` - 战略级测试引擎
- **评估器**: `src/simulator/evaluator.py` - 评分和判断逻辑
- **动作定义**: `src/simulator/action_space.py` - 所有测试动作
- **模板**: `src/simulator/prompt_templates.py` - Prompt模板库
- **任务生成**: `dataprovider/generator_v2.py` - 统一任务生成器

### 扩展点

1. **添加新动作**: 在`action_space.py`中定义新的`ActionDefinition`
2. **添加新数据集**: 在`dataset_configs.yaml`和`loader.py`中添加
3. **添加新任务类型**: 在`task_generators.py`中实现生成器
4. **调整评估标准**: 修改`evaluator.py`中的评分权重和阈值

---

**文档版本**: V1.0
**最后更新**: 2026-01-22
**维护者**: M3Bench Team
