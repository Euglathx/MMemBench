# M3Bench

M3Bench 是一个用于评估视觉语言模型（VLM）记忆机制的推理与上下文管理能力的动态测试基准框架与评估系统。旨在解决推理能力测试中的全局信息作弊问题，以及上下文管理能力测试中缺少状态管理的问题。

## 项目结构

```
M3Bench_new/
├── dataprovider/           # 数据加载与任务生成
│   ├── loader.py           # 数据集加载器
│   ├── generator_v2.py     # V2 任务生成器（配置驱动）
│   ├── config_loader.py    # 配置管理
│   └── task_generators.py  # 专用任务生成器
├── src/
│   └── simulator/          # 模拟器与评估
│       ├── strategic_simulator.py  # 战略模拟器（新）
│       ├── evaluator.py            # 评估器
│       ├── llm_client.py           # API客户端
│       ├── memory_store.py         # 对话记忆管理
│       ├── action_space.py         # 动作空间定义
│       └── context_padder.py       # 长上下文支持
├── tests/                  # 测试套件
│   ├── test_dataprovider.py
│   ├── test_strategic_simulator.py
│   └── test_user_simulator.py
├── data/                   # 数据集存储
├── generated_tasks_v2/     # 生成的测试任务
├── simulator_test_log/     # 模拟器运行日志
└── dataset_configs.yaml    # 数据集配置文件
```

## 支持的任务类型

| 任务类型 | 英文缩写 | 说明 |
|---------|---------|------|
| 属性比较 | AC (Attribute Comparison) | 跨图像比较对象属性 |
| 视觉噪声过滤 | VNF (Visual Noise Filtering) | 从干扰信息中提取目标信息 |
| 属性桥接推理 | ABR (Attribute Bridge Reasoning) | 多跳空间推理 |
| 关系比较 | RC (Relation Comparison) | 跨图像比较对象关系 |

## 支持的数据集

- MSCOCO 2014
- VCR (Visual Commonsense Reasoning)
- Visual Genome
- MMMU (Multi-discipline Multimodal Understanding)
- MM-NIAH (Needle in a Haystack)
- MMDocIR (Document Retrieval)
- DocVQA, InfoGraphVQA, SlideVQA
- MMStar, Sherlock, ScienceQA, RealworldQA

## 快速开始

### 1. 生成测试任务（V2 配置驱动）

```bash
python generate_all_tasks_v2.py
```

生成的任务保存在 `generated_tasks_v2/` 目录下，包含：
- 任务 JSONL 文件
- 复制的图像文件
- 原始标注文件
- 生成日志

### 2. 运行战略模拟器

```bash
python tests/test_strategic_simulator.py
```

模拟器会：
- 加载生成的任务
- 使用战略模拟器进行多阶段测试
- 测试目标VLM模型
- 记录详细日志到 `simulator_test_log/`

### 3. 运行实验

```bash
python run_experiment.py
```

运行完整的实验流程，包括：
- 任务加载
- 多轮对话测试
- 评估指标计算
- 结果可视化

### 4. 查看生成的任务

```bash
python view_tasks.py
```

## 核心功能

### 数据提供器（DataProvider）

**V2 配置驱动生成器**（推荐）:
```python
from dataprovider import DataLoader, DataGeneratorV2, load_config

loader = DataLoader(data_root="data")
config = load_config("dataset_configs.yaml")
generator = DataGeneratorV2(loader, config)

# 生成任务
tasks = generator.generate_tasks(
    dataset_id="mscoco14",
    task_type="ABR",
    num_tasks=10,
    split="train"
)
```

### 战略模拟器（Strategic Simulator）

新的战略模拟器提供：
- **阶段化测试**: Grounding → Stress Test → Final Check
- **自适应难度**: 根据模型表现动态调整
- **记忆注入攻击**: 测试长期记忆能力
- **一致性检查**: "回马枪"测试
- **解耦评估**: STRESS_TEST / LENIENT 模式

```python
from src.simulator import StrategicSimulator, Evaluator, EvaluationMode

simulator = StrategicSimulator(
    task=task,
    llm_client=client,
    evaluator=Evaluator(mode=EvaluationMode.STRESS_TEST)
)

results = simulator.run_episode(max_turns=10)
```

### 动作空间

系统支持多种测试动作：
- **guidance**: 引导模型关注特定区域
- **follow_up**: 追问细节
- **logic_skip**: 跳过复杂推理
- **negation**: 纠正错误推理
- **mislead**: 注入错误信息测试鲁棒性
- **distraction**: 注入干扰信息
- **redundancy**: 提供重复描述
- **fine_grained**: 要求精确细节
- **update**: 改变对象状态
- **next_task**: 结束当前任务

详细设计见 [ACTION_SPACE_DESIGN.md](ACTION_SPACE_DESIGN.md)

## 配置

### API 配置

API配置在 `src/simulator/llm_client.py` 中设置。

### 数据集配置

数据集配置在 `dataset_configs.yaml` 中管理，包括：
- 数据集路径和分割
- 标注格式
- 支持的任务类型
- 任务特定参数
- 质量过滤器

## 输出文件

### 任务生成
- `generated_tasks_v2/run_*/tasks/*.jsonl` - 生成的任务文件
- `generated_tasks_v2/run_*/images/` - 复制的图像
- `generated_tasks_v2/run_*/annotations/` - 原始标注
- `generated_tasks_v2/run_*/logs/` - 生成日志

### 模拟器日志
- `simulator_test_log/run_log_*.json` - 详细运行日志
- `memory_state_*.json` - 记忆状态
- `summary_*.json` - 运行摘要
- `readable_summary.txt` - 可读摘要

### 实验结果
- `experiment_images/` - 实验可视化图表
- `results/` - 评估结果

## 任务示例

### Attribute-Bridge Reasoning (ABR)

**2跳推理**:
```json
{
  "question": "In the image, find the large person. Find the object above it. What is it?",
  "answer": "The final object is a small book",
  "reasoning_depth": 2,
  "reasoning_path": [
    {
      "hop": 1,
      "object": "person",
      "size": "large",
      "description": "a large person",
      "relation_to_next": "above"
    },
    {
      "hop": 2,
      "object": "book",
      "size": "small",
      "description": "a small book"
    }
  ]
}
```

### Visual Noise Filtering (VNF)

```json
{
  "question": "Why are person and person smiling?",
  "answer": "Image 1: They just got off work.",
  "images": [
    "vcr1images/lsmdc_0001/...",
    "vcr1images/lsmdc_0002/...",
    "vcr1images/lsmdc_0003/...",
    "vcr1images/lsmdc_0004/..."
  ],
  "target_image_idx": 1
}
```

## 评估模式

### STRESS_TEST 模式
- 严格评分
- 用于基准测试
- 测试模型极限能力

### LENIENT 模式
- 宽松评分
- 关注记忆保持
- 测试长期记忆能力

## 依赖

- Python 3.8+
- requests
- jsonlines
- pycocotools（MSCOCO数据集）
- matplotlib（可选，用于可视化）

安装依赖：
```bash
pip install -r requirements.txt
```

## 文档

- [ACTION_SPACE_DESIGN.md](ACTION_SPACE_DESIGN.md) - 动作空间设计详解
- [DATAPROVIDER_SUMMARY.md](DATAPROVIDER_SUMMARY.md) - 数据提供器总结
- [DATASET_SETUP_CN.md](DATASET_SETUP_CN.md) - 数据集设置指南
- [docs/](docs/) - 架构文档

## 版本历史

- **v0.4.0** (2026-01-19): 简化代码库，统一使用 V2 生成器
- **v0.3.0** (2025-12-31): 添加战略模拟器和解耦评估
- **v0.2.0** (2025-12-25): 改进 ABR 问题生成，整合 MSCOCO 和 VCR
- **v0.1.0** (2025-12-18): 初始版本

## 许可

仅供研究使用。
