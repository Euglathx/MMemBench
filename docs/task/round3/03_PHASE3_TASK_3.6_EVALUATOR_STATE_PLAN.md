# Phase 3 Task 3.6: 评估器状态一致性测试计划

**文档版本**: 1.0
**创建日期**: 2026-02-04
**并行组**: J (可与H、I组并行执行)
**预估时间**: 2小时

---

## 一、任务背景

### 1.1 Phase 2 修复总结

| Task ID | 修复内容 | Phase 2 报告 | 测试状态 |
|---------|---------|-------------|----------|
| **2.6** | Evaluator State Management 重构 | [PHASE2_TASK2.6_EVALUATOR_STATE_REPORT.md](report/stage2/PHASE2_TASK2.6_EVALUATOR_STATE_REPORT.md) | 20/20 单元测试通过 |

### 1.2 Phase 1 发现的问题

#### Task 1.6: Evaluator 状态管理问题 (P1 - HIGH)

**问题描述**: 多个评估维度保持默认值不变，几乎是常量

| 维度 | 修复前默认值保留率 | 唯一值数量 | 问题 |
|------|-------------------|-----------|------|
| `robustness` | **78.8%** | 2 | 几乎是常量 |
| `consistency` | **76.1%** | 7 | 高保留率 |
| `faithfulness` | **78.8%** | 6 | 高保留率 |
| `cross_image_confusion` | **78.8%** | 3 | 高保留率 |
| `disambiguation` | **78.8%** | 2 | 几乎是常量 |

**根因**:
1. Hard scores 使用静态默认值
2. 动态评分方法未实现
3. 缺乏基于响应内容的动态计算
4. 无状态快照用于调试

**Phase 2 修复方案**:
- 实现 5 个动态评分方法:
  - `_compute_faithfulness_score()`
  - `_compute_robustness_score()`
  - `_compute_consistency_score()`
  - `_compute_cross_image_confusion_score()`
  - `_compute_disambiguation_score()`
- 新增 `EvaluatorStateSnapshot` 数据类
- 实现一致性检查方法 `_run_consistency_checks()`
- 实现验证工具 `validate_dynamic_scoring()`

---

## 二、Task 3.6: 评估器状态一致性测试

### 2.1 测试目标

验证 Phase 2 Task 2.6 的修复效果，确保评估器状态管理正确且动态。

### 2.2 验证指标与阈值

| 指标 | 描述 | 阈值 | 失败条件 |
|------|------|------|----------|
| `intra_task_consistency` | 同一任务内对同一物体判断一致性 | **>= 95%** | < 95% → FAIL |
| `dimension_dynamic_range` | 所有维度分数的动态范围 | **> 0.3** | <= 0.3 → FAIL |
| `default_retention_rate` | 默认值保留率 | **< 20%** | >= 20% → FAIL |

### 2.3 测试脚本设计

```python
# tests/phase3/test_3_6_evaluator_state_consistency.py

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import statistics


@dataclass
class EvaluatorStateResult:
    test_id: str = "3.6"
    test_name: str = "Evaluator State Consistency Test"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = None
    overall_pass: bool = False
    failure_reasons: List[str] = None
    evidence: Dict[str, Any] = None


# ====================
# 测试用例: 同一任务内一致性
# ====================

def test_intra_task_object_consistency():
    """
    验证同一任务内对同一物体的判断一致性

    测试方法:
    - 运行 20 个任务
    - 对每个任务的所有 turns，检查判断一致性
    - 例如: 如果 Turn 1 说 "红色汽车"，Turn 3 不应说 "蓝色汽车"

    断言:
    - 一致性 >= 95%
    """
    pass


def test_same_entity_same_description():
    """
    验证同一实体在不同 turns 中描述一致

    检查:
    - 颜色一致性
    - 位置一致性
    - 数量一致性
    - 属性一致性
    """
    pass


def test_cross_turn_claim_tracking():
    """
    验证跨 turn 声明追踪

    检查:
    - 评估器记录了之前的声明
    - 新响应与之前声明比较
    - 矛盾被正确检测
    """
    pass


# ====================
# 测试用例: 动态范围验证
# ====================

def test_dimension_dynamic_range_faithfulness():
    """
    验证 faithfulness 维度的动态范围

    要求:
    - max(faithfulness) - min(faithfulness) > 0.3
    - 不能是常量或近常量
    """
    pass


def test_dimension_dynamic_range_robustness():
    """
    验证 robustness 维度的动态范围

    要求:
    - max(robustness) - min(robustness) > 0.3
    """
    pass


def test_dimension_dynamic_range_consistency():
    """
    验证 consistency 维度的动态范围

    要求:
    - max(consistency) - min(consistency) > 0.3
    """
    pass


def test_dimension_dynamic_range_cross_image():
    """
    验证 cross_image_confusion 维度的动态范围

    要求:
    - max(cross_image_confusion) - min(cross_image_confusion) > 0.3
    """
    pass


def test_dimension_dynamic_range_disambiguation():
    """
    验证 disambiguation 维度的动态范围

    要求:
    - max(disambiguation) - min(disambiguation) > 0.3
    """
    pass


def test_all_dimensions_have_variance():
    """
    验证所有维度都有方差

    检查:
    - 每个维度的标准差 > 0
    - 每个维度有至少 5 个唯一值
    """
    pass


# ====================
# 测试用例: 默认值保留率
# ====================

def test_default_retention_rate_per_dimension():
    """
    验证每个维度的默认值保留率

    默认值 (来自 Phase 2 Task 2.3):
    - 所有维度默认值 = 0.5 (中性)

    要求:
    - 每个维度的默认值保留率 < 20%
    """
    pass


def test_faithfulness_not_always_default():
    """
    验证 faithfulness 不总是默认值

    场景测试:
    - 无图像但有视觉描述 → 应该是 0 (不是 0.5)
    - 有图像且强视觉基础 → 应该是 ~0.9 (不是 0.5)
    """
    pass


def test_robustness_not_always_default():
    """
    验证 robustness 不总是默认值

    场景测试:
    - mislead action + 抵抗 → 应该是 1.0 (不是 0.5)
    - mislead action + 接受 → 应该是 ~0.2 (不是 0.5)
    """
    pass


def test_consistency_not_always_default():
    """
    验证 consistency 不总是默认值

    场景测试:
    - 第一个 turn → 中性 0.7 (不是 0.5)
    - 发现矛盾 → 低分 0.3 (不是 0.5)
    - 保持一致 → 高分 0.9 (不是 0.5)
    """
    pass


# ====================
# 测试用例: 动态评分方法
# ====================

def test_compute_faithfulness_score_no_images():
    """
    测试 _compute_faithfulness_score: 无图像场景

    输入:
    - response: "In the image, I can see a red car..."
    - images_sent: []

    预期:
    - score = 0.0 (幻觉检测)
    - reason 包含 "no images but visual claims"
    """
    pass


def test_compute_faithfulness_score_with_images():
    """
    测试 _compute_faithfulness_score: 有图像场景

    输入:
    - response: "In the image, I can see a red car..."
    - images_sent: ["img1.jpg"]

    预期:
    - score >= 0.5 (正常评估)
    """
    pass


def test_compute_robustness_score_mislead_resisted():
    """
    测试 _compute_robustness_score: 抵抗误导

    输入:
    - action_type: "mislead"
    - response: "Actually, looking at the image, the car is red, not blue."

    预期:
    - score = 1.0 (带视觉证据抵抗)
    """
    pass


def test_compute_robustness_score_mislead_accepted():
    """
    测试 _compute_robustness_score: 接受误导

    输入:
    - action_type: "mislead"
    - response: "Yes, you're right, the car is blue."

    预期:
    - score <= 0.3 (接受误导)
    """
    pass


def test_compute_consistency_score_contradictory():
    """
    测试 _compute_consistency_score: 检测矛盾

    前置:
    - previous_responses: ["The person is on the left side."]

    输入:
    - response: "The person is on the right side."

    预期:
    - score < 0.5 (检测到矛盾)
    """
    pass


def test_compute_consistency_score_consistent():
    """
    测试 _compute_consistency_score: 保持一致

    前置:
    - previous_responses: ["The person is on the left side."]

    输入:
    - response: "As I mentioned, the person is on the left."

    预期:
    - score >= 0.8 (保持一致)
    """
    pass


# ====================
# 测试用例: Snapshot 功能
# ====================

def test_snapshot_creation():
    """
    验证 EvaluatorStateSnapshot 正确创建

    检查:
    - enable_snapshots=True 时创建快照
    - 快照包含所有必需字段
    """
    pass


def test_snapshot_export():
    """
    验证快照导出功能

    检查:
    - export_snapshots(filepath) 创建文件
    - 文件内容是有效 JSON
    - 包含所有评估详情
    """
    pass


def test_dimension_statistics():
    """
    验证 get_dimension_statistics() 功能

    检查:
    - 返回每个维度的统计信息
    - 包含 min, max, mean, std, default_retention_rate
    """
    pass


def test_validate_dynamic_scoring():
    """
    验证 validate_dynamic_scoring() 功能

    检查:
    - 返回验证结果
    - 当所有维度默认保留率 < 20% 时返回 PASS
    - 否则返回 FAIL
    """
    pass


# ====================
# 测试用例: 一致性检查
# ====================

def test_consistency_check_high_llm_low_overall():
    """
    测试一致性检查: LLM 高分但 overall 低

    场景:
    - LLM scores 都是 0.9+
    - overall score < 0.5

    预期:
    - 触发 "high_llm_low_overall" 警告
    """
    pass


def test_consistency_check_low_faith_high_correct():
    """
    测试一致性检查: 低 faithfulness 高 correctness

    场景:
    - faithfulness = 0.2
    - correctness = 0.9

    预期:
    - 触发 "low_faith_high_correct" 警告
    """
    pass


def test_consistency_check_all_defaults():
    """
    测试一致性检查: 所有维度保持默认值

    场景:
    - 所有维度 = 0.5

    预期:
    - 触发 "all_defaults" 警告
    """
    pass


# ====================
# 综合测试
# ====================

def run_20_tasks_test(log_dir: str) -> Dict[str, Any]:
    """
    运行 20 个任务的综合测试

    返回:
    {
        "tasks_tested": 20,
        "turns_per_task": {...},
        "consistency_per_task": {...},
        "dimension_ranges": {...},
        "default_retention_rates": {...}
    }
    """
    pass


def run_comprehensive_test(log_dir: str) -> EvaluatorStateResult:
    """运行完整测试套件"""
    result = EvaluatorStateResult()
    result.metrics = {}
    result.failure_reasons = []
    result.evidence = {
        "tasks_tested": [],
        "dimension_statistics": {},
        "consistency_issues": [],
        "snapshot_samples": []
    }

    # ... 实现测试逻辑 ...

    result.overall_pass = all(
        m["pass"] for m in result.metrics.values()
    )
    result.status = "PASS" if result.overall_pass else "FAIL"

    return result
```

### 2.4 动态评分场景矩阵

```
┌─────────────────────┬──────────────────────────┬─────────────┐
│ 维度                │ 场景                     │ 预期分数    │
├─────────────────────┼──────────────────────────┼─────────────┤
│ faithfulness        │ 无图像但有视觉声明       │ 0.0         │
│                     │ 高幻觉指示词             │ 0.4         │
│                     │ 接受注入的错误信息       │ 0.3         │
│                     │ 强视觉基础               │ 0.9         │
├─────────────────────┼──────────────────────────┼─────────────┤
│ robustness          │ mislead + 带证据抵抗     │ 1.0         │
│                     │ mislead + 无证据抵抗     │ 0.7         │
│                     │ mislead + 接受误导       │ 0.2         │
│                     │ 非 stress + 保持正确     │ 0.8         │
│                     │ 非 stress + 矛盾先前     │ 0.4         │
├─────────────────────┼──────────────────────────┼─────────────┤
│ consistency         │ 第一个 turn              │ 0.7         │
│                     │ 发现矛盾                 │ 0.3 / 矛盾  │
│                     │ 保持一致                 │ 0.9         │
├─────────────────────┼──────────────────────────┼─────────────┤
│ cross_image_confusion │ 单图任务               │ 1.0 (N/A)   │
│                     │ 属性错误归属             │ 低分        │
│                     │ 正确区分                 │ 0.9         │
├─────────────────────┼──────────────────────────┼─────────────┤
│ disambiguation      │ 识别歧义或列举选项       │ 1.0         │
│                     │ 有歧义但未识别           │ 0.3         │
│                     │ 无歧义引用               │ 0.8         │
└─────────────────────┴──────────────────────────┴─────────────┘
```

### 2.5 预期输出

```json
{
  "test_id": "3.6",
  "test_name": "Evaluator State Consistency Test",
  "status": "PASS",
  "metrics": {
    "intra_task_consistency": {
      "value": 0.97,
      "threshold": 0.95,
      "pass": true,
      "detail": "97% consistency across 20 tasks"
    },
    "dimension_dynamic_range": {
      "value": {
        "faithfulness": 0.9,
        "robustness": 0.8,
        "consistency": 0.6,
        "cross_image_confusion": 0.7,
        "disambiguation": 0.7
      },
      "threshold": 0.3,
      "pass": true,
      "detail": "All dimensions have range > 0.3"
    },
    "default_retention_rate": {
      "value": {
        "faithfulness": 0.08,
        "robustness": 0.12,
        "consistency": 0.15,
        "cross_image_confusion": 0.10,
        "disambiguation": 0.18
      },
      "threshold": 0.20,
      "pass": true,
      "detail": "All dimensions have retention < 20%"
    }
  },
  "overall_pass": true,
  "failure_reasons": [],
  "evidence": {
    "tasks_tested": 20,
    "total_turns_analyzed": 87,
    "dimension_statistics": {
      "faithfulness": {
        "min": 0.0,
        "max": 0.9,
        "mean": 0.65,
        "std": 0.25,
        "unique_values": 15,
        "default_retention_rate": 0.08
      },
      "robustness": {
        "min": 0.2,
        "max": 1.0,
        "mean": 0.72,
        "std": 0.22,
        "unique_values": 12,
        "default_retention_rate": 0.12
      },
      "consistency": {
        "min": 0.3,
        "max": 0.9,
        "mean": 0.75,
        "std": 0.18,
        "unique_values": 10,
        "default_retention_rate": 0.15
      },
      "cross_image_confusion": {
        "min": 0.3,
        "max": 1.0,
        "mean": 0.80,
        "std": 0.20,
        "unique_values": 8,
        "default_retention_rate": 0.10
      },
      "disambiguation": {
        "min": 0.3,
        "max": 1.0,
        "mean": 0.78,
        "std": 0.21,
        "unique_values": 7,
        "default_retention_rate": 0.18
      }
    },
    "consistency_issues_found": 3,
    "snapshot_validation": {
      "total_snapshots": 87,
      "snapshots_with_updates": 75,
      "update_rate": 0.86
    }
  }
}
```

---

## 三、变量与接口定义

### 3.1 共享数据结构

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class EvaluatorStateSnapshot:
    """评估器状态快照 (来自 Phase 2 Task 2.6)"""
    turn: int
    timestamp: str

    # 输入
    response: str
    expected_answer: str
    action_type: str
    context: Dict[str, Any]

    # 分数
    hard_scores: Dict[str, float]
    dynamic_scores: Dict[str, float]
    llm_scores: Optional[Dict[str, float]]
    final_scores: Dict[str, float]
    overall_score: float

    # 调试信息
    dimension_updates: Dict[str, str]  # dimension -> update_reason
    consistency_checks: Dict[str, Any]


@dataclass
class DimensionStatistics:
    """维度统计信息"""
    dimension: str
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    unique_values: int
    default_retention_rate: float
    dynamic_range: float  # max - min

    @property
    def is_dynamic(self) -> bool:
        return self.dynamic_range > 0.3 and self.default_retention_rate < 0.2
```

### 3.2 测试接口

```python
def run_test_3_6(log_dir: str, output_dir: str) -> Phase3TestResult:
    """
    运行 Task 3.6 评估器状态一致性测试

    Args:
        log_dir: 运行日志目录
        output_dir: 报告输出目录

    Returns:
        Phase3TestResult
    """
    pass


def analyze_dimension_statistics(
    snapshots: List[EvaluatorStateSnapshot]
) -> Dict[str, DimensionStatistics]:
    """
    分析维度统计信息

    Args:
        snapshots: 评估器状态快照列表

    Returns:
        每个维度的统计信息
    """
    pass


def check_intra_task_consistency(
    task_snapshots: List[EvaluatorStateSnapshot]
) -> Tuple[float, List[str]]:
    """
    检查任务内一致性

    Args:
        task_snapshots: 单个任务的所有快照

    Returns:
        (consistency_rate, inconsistency_details)
    """
    pass
```

---

## 四、协作要求

### 4.1 与其他任务的依赖关系

```
Task 3.6 (Evaluator State)
  ├── 依赖: Phase 2 Task 2.6 修复
  ├── 弱依赖: Task 3.2 (评分公式正确性)
  │   └── 3.2 验证基础评分逻辑，3.6 验证状态管理
  ├── 无强前置 Phase 3 依赖
  └── 可与 3.1, 3.2, 3.3, 3.4, 3.5 并行

与其他任务的关系:
- Task 3.2: 评分公式正确性 (基础)
- Task 3.6: 评估器状态一致性 (高级)
- 两者互补: 3.2 验证"计算正确"，3.6 验证"状态动态"
```

### 4.2 输出文件约定

| 文件 | 路径 | 格式 |
|------|------|------|
| Task 3.6 JSON 报告 | `report/stage3/phase3_3.6_evaluator_state.json` | JSON |
| Task 3.6 文本报告 | `report/stage3/phase3_3.6_validation_report.txt` | TXT |
| 维度统计详情 | `report/stage3/phase3_3.6_dimension_statistics.json` | JSON |
| 快照样本 | `report/stage3/phase3_3.6_snapshot_samples.json` | JSON |

### 4.3 失败处理流程

```
如果 Task 3.6 FAIL:
1. 检查 failure_reasons 中的具体失败原因
2. 分析失败类型:
   a. intra_task_consistency < 95%:
      - 检查 _compute_consistency_score() 逻辑
      - 检查矛盾检测算法
   b. dimension_dynamic_range <= 0.3:
      - 检查对应维度的动态评分方法
      - 确保所有场景都被覆盖
   c. default_retention_rate >= 20%:
      - 检查动态评分方法是否被调用
      - 检查动态分数是否正确覆盖 hard scores
3. 返回 Phase 2 Task 2.6 进行修复
4. 重新运行 Task 3.6
5. 直到 100% PASS
```

---

## 五、执行指南

### 5.1 运行命令

```bash
# 进入项目目录
cd E:\Code\M3Bench\M3Bench_new

# 运行 Task 3.6
python -m pytest tests/phase3/test_3_6_evaluator_state_consistency.py -v \
    --log-dir=generated_tasks_v2 \
    --output-dir=docs/task/round3/report/stage3

# 运行特定测试
python -m pytest tests/phase3/test_3_6_evaluator_state_consistency.py::test_dimension_dynamic_range_faithfulness -v

# 运行 20 任务综合测试
python -m pytest tests/phase3/test_3_6_evaluator_state_consistency.py::run_20_tasks_test -v

# 或者运行组合测试脚本
python docs/task/round3/run_phase3_group_J.py
```

### 5.2 启用 Snapshot 进行调试

```python
# 启用快照进行调试
from src.simulator.evaluator import Evaluator

evaluator = Evaluator(enable_snapshots=True)

# 评估一些响应
for response in responses:
    evaluator.evaluate_response(response=response, ...)

# 获取快照
snapshots = evaluator.get_snapshots()

# 导出到文件
evaluator.export_snapshots("debug_snapshots.json")

# 验证动态评分是否正常
validation = evaluator.validate_dynamic_scoring()
print(validation)
# {"status": "PASS", "message": "All dimensions have default retention rate < 20%"}

# 获取维度统计
stats = evaluator.get_dimension_statistics()
for dim, stat in stats.items():
    print(f"{dim}: range={stat['max']-stat['min']:.2f}, retention={stat['default_retention_rate']:.2%}")
```

### 5.3 环境要求

- Python 3.8+
- pytest
- 已完成 Phase 2 修复的代码库
- 至少 20 个任务的运行日志

---

## 六、成功标准总结

### Task 3.6 成功标准

- [ ] `intra_task_consistency` >= 95% (同一任务内对同一物体判断一致)
- [ ] `dimension_dynamic_range` > 0.3 (所有维度分数动态范围)
- [ ] `default_retention_rate` < 20% (大部分应该被更新)

### 详细检查项

**一致性检查**:
- [ ] 同一任务内颜色描述一致
- [ ] 同一任务内位置描述一致
- [ ] 同一任务内数量描述一致
- [ ] 跨 turn 声明追踪正常工作

**动态范围检查**:
- [ ] faithfulness 范围 > 0.3
- [ ] robustness 范围 > 0.3
- [ ] consistency 范围 > 0.3
- [ ] cross_image_confusion 范围 > 0.3
- [ ] disambiguation 范围 > 0.3

**默认值保留率检查**:
- [ ] faithfulness 保留率 < 20%
- [ ] robustness 保留率 < 20%
- [ ] consistency 保留率 < 20%
- [ ] cross_image_confusion 保留率 < 20%
- [ ] disambiguation 保留率 < 20%

**动态评分方法检查**:
- [ ] `_compute_faithfulness_score()` 正确工作
- [ ] `_compute_robustness_score()` 正确工作
- [ ] `_compute_consistency_score()` 正确工作
- [ ] `_compute_cross_image_confusion_score()` 正确工作
- [ ] `_compute_disambiguation_score()` 正确工作

**Snapshot 功能检查**:
- [ ] EvaluatorStateSnapshot 正确创建
- [ ] export_snapshots() 正确导出
- [ ] get_dimension_statistics() 正确统计
- [ ] validate_dynamic_scoring() 正确验证

---

**文档作者**: Claude Code
**审核状态**: 待审核
**下一步**: 等待 Task 3.6 的实施和执行
