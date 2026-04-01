# M3Bench 项目架构

## 项目概述

M3Bench 是一个用于评估视觉语言模型（VLM）的动态基准测试框架，专注于测试模型的记忆机制、推理能力、上下文管理和鲁棒性。

## 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         M3Bench 系统                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌──────────────┐    ┌─────────────────┐
│ DataProvider  │    │  Simulator   │    │   Evaluator     │
│               │    │              │    │                 │
│ 数据加载与     │───▶│  交互式测试   │───▶│   多维评估      │
│ 任务生成       │    │  动作管理     │    │   打分输出      │
└───────────────┘    └──────────────┘    └─────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   原始数据集            模拟对话日志            评估报告
```

## 数据流程

```
原始数据集 (14+数据集)
    │
    ├─ MSCOCO14, VCR, Visual Genome, GQA, DocVQA...
    │
    ▼
┌─────────────────────────────────────────┐
│ DataLoader (统一格式转换)                 │
│   - 加载各类数据集                        │
│   - 转换为统一格式                        │
│   - 提取对象、属性、关系                   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ DataGeneratorV2 (任务生成)                │
│   - AttributeComparison (AC)             │
│   - VisualNoiseFiltering (VNF)           │
│   - AttributeBridgeReasoning (ABR)       │
│   - RelationComparison (RC)              │
└─────────────────────────────────────────┘
    │
    ▼
生成的测试任务 (JSONL格式)
    │
    ▼
┌─────────────────────────────────────────┐
│ StrategicSimulator (交互式测试)           │
│   - Phase管理 (4阶段测试)                 │
│   - 难度自适应 (4级难度)                  │
│   - 动作选择 (10种动作类型)               │
│   - 记忆管理与注入                        │
└─────────────────────────────────────────┘
    │
    ▼
对话日志与记忆状态
    │
    ▼
┌─────────────────────────────────────────┐
│ Evaluator (多维评估)                      │
│   - 7维度评分系统                         │
│   - 硬规则 + LLM-as-Judge                │
│   - 难度阈值检查                          │
└─────────────────────────────────────────┘
    │
    ▼
评估报告 (JSON + 可视化)
```

## 核心模块

### 1. DataProvider 模块

**位置**: `dataprovider/`

**功能**:
- 加载14+个主流视觉理解数据集
- 统一数据格式转换
- 配置驱动的任务生成
- 4种任务类型生成器

**核心文件**:
```
dataprovider/
├── loader.py                      # 多数据集加载器
├── generator_v2.py                # V2任务生成器
├── task_generators.py             # 任务生成器实现
├── config_loader.py               # 配置加载
└── rationale_based_generator.py   # 基于rationale的生成器
```

**支持的任务类型**:
- **AC** (Attribute Comparison): 跨图属性对比
- **VNF** (Visual Noise Filtering): 目标图像+干扰图像
- **ABR** (Attribute Bridge Reasoning): 多跳推理链
- **RC** (Relation Comparison): 关系对比分析

### 2. Simulator 模块

**位置**: `src/simulator/`

**功能**:
- 主持多轮交互式测试
- 阶段化和自适应难度管理
- 实体提取、动作选择、查询生成
- 记忆管理与长上下文支持

**核心架构**:
```
┌─────────────────────────────────────────────────────────────┐
│                  StrategicSimulator                          │
│              (主控制器，多阶段自适应测试)                       │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Entity       │  │  Action      │  │  Query       │
│ Extractor    │─▶│  Selector    │─▶│  Generator   │
│              │  │              │  │              │
│ 提取实体      │  │  选择动作     │  │  生成查询     │
└──────────────┘  └──────────────┘  └──────────────┘
```

**测试阶段**:
```
Phase 1: Grounding         - 基础定位和理解
    ↓
Phase 2: Consistency       - 一致性测试
    ↓
Phase 3: Stress Test       - 压力测试（误导、干扰）
    ↓
Phase 4: Final Check       - 回马枪验证
```

**难度等级**:
- Level 1: 基础能力测试
- Level 2: 记忆稳定性测试
- Level 3: 综合压力测试
- Level 4: 极限挑战测试

**动作类型** (10种):
```
reasoning 层:
  ├─ follow_up      # 追问细节
  ├─ logic_skip     # 跳过推理
  └─ negation       # 纠正错误

aggregation 层:
  └─ guidance       # 引导关注

context_management 层:
  ├─ mislead        # 注入错误信息
  ├─ distraction    # 注入干扰信息
  ├─ redundancy     # 重复描述
  ├─ memory_injection   # 测试记忆
  ├─ update         # 改变状态
  └─ fine_grained   # 精细要求
```

**核心文件**:
```
src/simulator/
├── strategic_simulator.py     # 主模拟器
├── evaluator.py               # 评估器
├── entity_extractor.py        # 实体提取
├── action_selector.py         # 动作选择
├── query_generator.py         # 查询生成
├── memory_store.py            # 记忆管理
├── context_padder.py          # 长上下文填充
├── llm_client.py              # LLM API客户端
└── prompt_templates.py        # Prompt模板
```

### 3. Evaluator 模块

**位置**: `src/simulator/evaluator.py`

**功能**:
- 7维度评分系统
- 硬规则 + LLM-as-Judge 双重评估
- 难度阈值检查
- 一致性分析

**评估维度**:
```
1. Correctness          正确性 (0-10分)
2. Faithfulness         忠实度 (0-10分)
3. Robustness           鲁棒性 (0-10分)
4. Consistency          一致性 (0-10分)
5. Memory Retention     记忆保持 (0-10分)
6. Cross-Image Disambiguation   跨图区分 (0-10分)
7. Ambiguity Recognition        歧义识别 (0-10分)
```

**评分流程**:
```
硬规则评估 (精确匹配)
    │
    ├─ Ground Truth对比
    └─ 关键字检查
          │
          ▼
    LLM-as-Judge评估 (语义理解)
          │
          ├─ 语义相似度
          ├─ 推理连贯性
          └─ 一致性分析
                │
                ▼
          加权组合
                │
    final_score = hard_score × (1-w) + llm_score × w
                │
                ▼
          难度阈值检查
                │
    Level 1: 0.7  Level 2: 0.65
    Level 3: 0.6  Level 4: 0.5
                │
                ▼
            Pass/Fail
```

## 支持的数据集

```
数据集            容量      任务类型            特性
─────────────────────────────────────────────────────
MSCOCO14         82K       AC,VNF,ABR,RC      bbox, captions
VCR              212K      AC,VNF,ABR         Q&A, rationale
Visual Genome    100K      AC,VNF,ABR,RC      场景图, 关系
GQA              ~20K      AC,VNF,ABR,RC      推理问题
DocVQA           12K       AC,VNF             文档QA, OCR
MM-NIAH          多个      AC,VNF             长上下文
MMMU             多学科     AC,VNF             多选题
Sherlock         多个      AC,VNF             线索推理
```

## 配置系统

**核心配置**: `dataset_configs.yaml`

```
dataset_configs.yaml (626行)
    │
    ├─ 数据集定义 (14+个)
    │   ├─ 路径配置
    │   ├─ 格式说明
    │   └─ 支持的任务类型
    │
    ├─ 任务模板定义
    │   ├─ AC模板 (跨图对比)
    │   ├─ VNF模板 (噪声过滤)
    │   ├─ ABR模板 (推理链)
    │   └─ RC模板 (关系对比)
    │
    └─ 质量控制规则
        ├─ 图像分辨率要求
        ├─ 对象数量要求
        └─ 推理链连贯性
```

## 主要入口脚本

```
generate_all_tasks_v2.py       批量生成测试任务
    │
    ├─ 读取dataset_configs.yaml
    ├─ 加载数据集
    ├─ 生成任务
    └─ 输出到generated_tasks_v2/

run_experiment.py              实验矩阵分析
    │
    ├─ 加载生成的任务
    ├─ 运行StrategicSimulator
    ├─ 多参数组合测试
    └─ 输出实验报告

run_batch_test.py              批量测试脚本
    │
    ├─ 批量加载任务
    ├─ 并行执行测试
    └─ 汇总评估结果

tests/test_strategic_simulator.py   单任务测试
tests/test_end_to_end.py            端到端测试
```

## 输出结构

```
generated_tasks_v2/               # 生成的任务
├── run_1/
│   ├── tasks/
│   │   ├── ac_mscoco14_*.jsonl
│   │   ├── vnf_vcr_*.jsonl
│   │   ├── abr_visual_genome_*.jsonl
│   │   └── rc_gqa_*.jsonl
│   ├── images/                   # 复制的图像
│   └── annotations/              # 原始标注

simulator_test_log/               # 模拟器日志
├── run_log_*.json                # 详细对话日志
├── memory_state_*.json           # 记忆状态
├── summary_*.json                # 运行摘要
└── readable_summary.txt          # 可读摘要

experiment_images/                # 实验结果
├── experiment_raw_*.json         # 原始结果
├── experiment_summary_*.json     # 聚合统计
└── *.png                         # 可视化图表
```

## 模块间依赖

```
底层工具:
  ├─ LLMClient          # API调用
  ├─ MemoryStore        # 对话记忆
  └─ PromptTemplates    # 模板库
        │
        ▼
中层处理:
  ├─ EntityExtractor    # 实体提取
  ├─ ActionSelector     # 动作选择
  ├─ QueryGenerator     # 查询生成
  ├─ ContextPadder      # 上下文填充
  └─ Evaluator          # 评估(独立)
        │
        ▼
上层控制:
  ├─ StrategicSimulator # 主控制器
  ├─ DataLoader         # 数据加载
  ├─ DataGeneratorV2    # 任务生成
  └─ ConfigLoader       # 配置管理
```

## 项目特色

1. **多源数据支持**: 14+个主流视觉理解数据集
2. **自适应难度**: 根据VLM表现动态提升测试难度
3. **阶段化测试**: 4阶段系统评估（Grounding → Consistency → Stress → Final）
4. **7维评分系统**: 多角度评估模型能力
5. **记忆测试**: 虚假信息注入、记忆保留评估
6. **长上下文支持**: Wikipedia填充、伪多轮对话
7. **解耦设计**: 实体提取、动作选择、查询生成完全独立
8. **配置驱动**: 通过YAML配置灵活定义数据集和任务

## 快速开始

```bash
# 1. 生成测试任务
python generate_all_tasks_v2.py --num-samples 100

# 2. 运行单任务测试
python tests/test_strategic_simulator.py

# 3. 运行实验矩阵
python run_experiment.py --weights 0.6 0.8 1.0 --turns 20 30 40

# 4. 端到端集成测试
python tests/test_end_to_end.py --config configs/test_config.yaml
```
