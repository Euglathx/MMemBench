# Phase 3 Task 3.7: 回归测试套件计划

**文档版本**: 1.0
**创建日期**: 2026-02-04
**并行组**: K (需要等待 H+I+J 组全部完成)
**预估时间**: 2-3小时
**前置条件**: Task 3.1-3.6 全部 PASS

---

## 一、任务背景

### 1.1 回归测试的必要性

Phase 3 Task 3.1-3.6 验证了各个修复的**单点正确性**，但未验证：
1. **整体协同效果**: 所有修复一起工作时的综合效果
2. **修复前后对比**: 量化改进程度
3. **无退化**: 确保修复没有引入新问题
4. **真实场景**: 在完整任务流程中的表现

### 1.2 Phase 2 修复总览

| Task ID | 修复内容 | 核心改进 |
|---------|---------|---------|
| 2.1 | 图像发送管道 | 46.1% → 100% 图像发送率 |
| 2.2 | Turn-Level Ground Truth | 26.9% turns 使用正确 expected |
| 2.3 | 评分公式重构 | LLM 10/10 → final >= 0.9 |
| 2.4 | Simulator 真值验证 | 0% 伪确认率 |
| 2.5 | 多图策略统一 | 100% 策略一致性 |
| 2.6 | Evaluator 状态管理 | < 20% 默认值保留率 |

### 1.3 Phase 1 发现的关键问题回顾

| 问题ID | 问题描述 | 严重性 | Phase 2 修复 |
|--------|---------|--------|-------------|
| P1-1.1 | 46.1% turns 无图像发送 | P1 | Task 2.1 |
| P1-1.2 | LLM满分但final<0.7 | P0 | Task 2.3 |
| P1-1.3 | 100% turns用task-level expected | P1 | Task 2.2 |
| P1-1.4 | 28.57% 错误传播率 | P1 | Task 2.4 |
| P1-1.5 | 54% turns发送0图像 | P1 | Task 2.5 |
| P1-1.6 | 78.8% 默认值保留率 | P1 | Task 2.6 |

---

## 二、Task 3.7: 回归测试套件

### 2.1 测试目标

**对比修复前后，验证所有问题已被解决且无新问题引入。**

### 2.2 验证指标与阈值

| 指标 | 修复前基线 | 修复后目标 | 最低改进要求 |
|------|-----------|-----------|-------------|
| `image_sending_rate` | 53.9% | 100% | 必须达到100% |
| `score_reasonability` | ~65% | >= 95% | 提升至少30% |
| `judgment_consistency` | ~75% | >= 95% | 提升至少20% |
| `error_propagation_rate` | 28.57% | < 5% | 下降至少23% |
| `default_retention_rate` | 78.8% | < 20% | 下降至少58% |
| `misjudgment_rate` | ~10% | < 2% | 下降至少8% |

### 2.3 测试脚本设计

```python
# tests/phase3/test_3_7_regression_suite.py

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import statistics


@dataclass
class RegressionTestResult:
    test_id: str = "3.7"
    test_name: str = "Regression Test Suite"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = None
    overall_pass: bool = False
    failure_reasons: List[str] = None
    evidence: Dict[str, Any] = None
    comparison: Dict[str, Any] = None  # 修复前后对比


@dataclass
class BaselineMetrics:
    """修复前基线指标 (来自 Phase 1 报告)"""
    image_sending_rate: float = 0.539  # 46.1% 空 → 53.9% 有
    score_reasonability: float = 0.65  # 估计值
    judgment_consistency: float = 0.75  # 估计值
    error_propagation_rate: float = 0.2857
    default_retention_rate: float = 0.788
    misjudgment_rate: float = 0.10  # 估计值

    # 详细基线数据
    llm_perfect_final_score: float = 0.664  # LLM 10/10 时的 final score
    turn_level_expected_usage: float = 0.0  # 0% 使用 turn-level
    false_confirmation_rate: float = 0.10  # 估计值


@dataclass
class PostFixMetrics:
    """修复后指标"""
    image_sending_rate: float = 0.0
    score_reasonability: float = 0.0
    judgment_consistency: float = 0.0
    error_propagation_rate: float = 0.0
    default_retention_rate: float = 0.0
    misjudgment_rate: float = 0.0

    llm_perfect_final_score: float = 0.0
    turn_level_expected_usage: float = 0.0
    false_confirmation_rate: float = 0.0


# ====================
# 核心回归测试
# ====================

def run_100_tasks_regression(
    task_list: List[Dict],
    baseline_logs_dir: str,
    output_dir: str
) -> Tuple[PostFixMetrics, Dict[str, Any]]:
    """
    运行相同的100个任务，收集修复后指标

    Args:
        task_list: 100个任务定义
        baseline_logs_dir: 修复前的运行日志目录
        output_dir: 输出目录

    Returns:
        (PostFixMetrics, detailed_results)
    """
    pass


def compare_before_after(
    baseline: BaselineMetrics,
    postfix: PostFixMetrics
) -> Dict[str, Dict]:
    """
    对比修复前后指标

    Returns:
        {
            "metric_name": {
                "before": value,
                "after": value,
                "improvement": value,
                "improvement_pct": "X%",
                "meets_threshold": bool
            }
        }
    """
    pass


# ====================
# 指标 1: 图像发送率
# ====================

def test_image_sending_rate_improvement():
    """
    验证图像发送率从 53.9% 提升到 100%

    测试方法:
    - 运行 100 个任务
    - 统计 images_sent 不为空的 turns 比率

    验证:
    - 修复后: 100%
    - 改进: >= 46.1%
    """
    pass


def collect_image_sending_statistics(log_dir: str) -> Dict[str, Any]:
    """
    收集图像发送统计

    Returns:
        {
            "total_turns": int,
            "turns_with_images": int,
            "rate": float,
            "failed_cases": [...]
        }
    """
    pass


# ====================
# 指标 2: 评分合理性
# ====================

def test_score_reasonability_improvement():
    """
    验证评分合理性提升至少 30%

    评分合理性定义:
    - LLM Judge 高分 (>=8/10) → final score >= 0.7
    - LLM Judge 低分 (<=3/10) → final score <= 0.4
    - 无异常: LLM高分但final低 的案例 = 0

    测试方法:
    - 分析 100 个任务的所有评分
    - 计算合理性比率

    验证:
    - 修复后: >= 95%
    - 改进: >= 30%
    """
    pass


def analyze_score_reasonability(log_dir: str) -> Dict[str, Any]:
    """
    分析评分合理性

    Returns:
        {
            "total_evaluations": int,
            "reasonable_evaluations": int,
            "reasonability_rate": float,
            "anomaly_cases": [
                {
                    "task_id": str,
                    "turn": int,
                    "llm_score": float,
                    "final_score": float,
                    "anomaly_type": str
                }
            ]
        }
    """
    pass


# ====================
# 指标 3: 判断一致性
# ====================

def test_judgment_consistency_improvement():
    """
    验证判断一致性提升至少 20%

    判断一致性定义:
    - 同一任务内对同一对象的描述一致
    - 无矛盾声明
    - 跨 turn 引用正确

    测试方法:
    - 分析 100 个任务的所有 turns
    - 检测矛盾和不一致

    验证:
    - 修复后: >= 95%
    - 改进: >= 20%
    """
    pass


def analyze_judgment_consistency(log_dir: str) -> Dict[str, Any]:
    """
    分析判断一致性

    Returns:
        {
            "total_tasks": int,
            "consistent_tasks": int,
            "consistency_rate": float,
            "inconsistency_cases": [
                {
                    "task_id": str,
                    "turn_a": int,
                    "turn_b": int,
                    "claim_a": str,
                    "claim_b": str,
                    "inconsistency_type": str
                }
            ]
        }
    """
    pass


# ====================
# 指标 4: 错误传播率
# ====================

def test_error_propagation_rate_reduction():
    """
    验证错误传播率从 28.57% 下降到 < 5%

    错误传播定义:
    - Turn N 的错误被 Turn N+1 引用或强化
    - Simulator 确认了模型的错误

    测试方法:
    - 分析 100 个任务中的错误 turns
    - 检测错误是否传播到后续 turns

    验证:
    - 修复后: < 5%
    - 改进: >= 23%
    """
    pass


def analyze_error_propagation(log_dir: str) -> Dict[str, Any]:
    """
    分析错误传播

    Returns:
        {
            "total_error_turns": int,
            "propagated_errors": int,
            "propagation_rate": float,
            "propagation_cases": [...]
        }
    """
    pass


# ====================
# 指标 5: 默认值保留率
# ====================

def test_default_retention_rate_reduction():
    """
    验证默认值保留率从 78.8% 下降到 < 20%

    测试方法:
    - 收集所有评估的维度分数
    - 统计保持默认值 (0.5) 的比率

    验证:
    - 修复后: < 20%
    - 改进: >= 58%
    """
    pass


def analyze_default_retention(log_dir: str) -> Dict[str, Any]:
    """
    分析默认值保留率

    Returns:
        {
            "dimensions": {
                "faithfulness": {"total": int, "default": int, "rate": float},
                "robustness": {...},
                ...
            },
            "overall_rate": float
        }
    """
    pass


# ====================
# 指标 6: 误判率
# ====================

def test_misjudgment_rate_reduction():
    """
    验证误判率从 ~10% 下降到 < 2%

    误判定义:
    - 模型回答正确但评估为错误
    - 模型回答错误但评估为正确
    - 使用错误的 expected_answer 进行评估

    测试方法:
    - 人工标注子集 or 使用 ground truth 验证
    - 统计误判比率

    验证:
    - 修复后: < 2%
    - 改进: >= 8%
    """
    pass


def analyze_misjudgment(log_dir: str) -> Dict[str, Any]:
    """
    分析误判

    Returns:
        {
            "total_evaluations": int,
            "misjudgments": int,
            "misjudgment_rate": float,
            "misjudgment_cases": [
                {
                    "task_id": str,
                    "turn": int,
                    "response": str,
                    "evaluation": str,
                    "correct_evaluation": str,
                    "misjudgment_type": str
                }
            ]
        }
    """
    pass


# ====================
# 退化检测
# ====================

def test_no_regression():
    """
    验证修复没有引入新问题

    检查项:
    - 原本正确的评估没有变成错误
    - 性能没有明显下降
    - 无新的边界 case 失败
    """
    pass


def detect_regression(
    baseline_results: Dict[str, Any],
    postfix_results: Dict[str, Any]
) -> List[Dict]:
    """
    检测退化

    Returns:
        [
            {
                "task_id": str,
                "metric": str,
                "before": value,
                "after": value,
                "regression_type": str,
                "severity": str
            }
        ]
    """
    pass


# ====================
# 特定问题回归验证
# ====================

def test_phase1_issue_1_1_fixed():
    """
    验证 Phase 1 Issue 1.1 (图像发送空) 已修复

    原问题: 46.1% turns 的 images_sent 为空
    预期: 0% 为空 (100% 有图像)
    """
    pass


def test_phase1_issue_1_2_fixed():
    """
    验证 Phase 1 Issue 1.2 (评分异常) 已修复

    原问题: LLM 10/10 但 final < 0.7
    预期: LLM 10/10 → final >= 0.9
    """
    pass


def test_phase1_issue_1_3_fixed():
    """
    验证 Phase 1 Issue 1.3 (Expected Answer) 已修复

    原问题: 100% turns 使用 task-level expected
    预期: 中间 turns 使用 turn-level expected
    """
    pass


def test_phase1_issue_1_4_fixed():
    """
    验证 Phase 1 Issue 1.4 (错误传播) 已修复

    原问题: 28.57% 错误传播率
    预期: < 5%
    """
    pass


def test_phase1_issue_1_5_fixed():
    """
    验证 Phase 1 Issue 1.5 (多图策略) 已修复

    原问题: 54% turns 发送 0 图像
    预期: 100% 一致策略
    """
    pass


def test_phase1_issue_1_6_fixed():
    """
    验证 Phase 1 Issue 1.6 (默认值保留) 已修复

    原问题: 78.8% 默认值保留率
    预期: < 20%
    """
    pass


# ====================
# 综合测试
# ====================

def run_comprehensive_regression_test(
    baseline_logs_dir: str,
    output_dir: str
) -> RegressionTestResult:
    """
    运行完整回归测试套件

    步骤:
    1. 加载基线数据 (Phase 1 报告)
    2. 运行 100 个任务
    3. 收集修复后指标
    4. 对比分析
    5. 检测退化
    6. 生成报告

    Args:
        baseline_logs_dir: 修复前运行日志
        output_dir: 输出目录

    Returns:
        RegressionTestResult
    """
    result = RegressionTestResult()
    result.metrics = {}
    result.failure_reasons = []
    result.evidence = {
        "tasks_run": 100,
        "baseline_source": baseline_logs_dir,
        "run_timestamp": datetime.now().isoformat()
    }
    result.comparison = {}

    # 1. 加载基线
    baseline = BaselineMetrics()

    # 2. 运行任务并收集指标
    postfix = PostFixMetrics()
    # ... 运行逻辑 ...

    # 3. 对比分析
    comparison = compare_before_after(baseline, postfix)
    result.comparison = comparison

    # 4. 验证各指标
    metrics_to_check = [
        ("image_sending_rate", postfix.image_sending_rate, 1.0, ">="),
        ("score_reasonability", postfix.score_reasonability, 0.95, ">="),
        ("judgment_consistency", postfix.judgment_consistency, 0.95, ">="),
        ("error_propagation_rate", postfix.error_propagation_rate, 0.05, "<"),
        ("default_retention_rate", postfix.default_retention_rate, 0.20, "<"),
        ("misjudgment_rate", postfix.misjudgment_rate, 0.02, "<"),
    ]

    for name, value, threshold, operator in metrics_to_check:
        if operator == ">=":
            passed = value >= threshold
        else:  # "<"
            passed = value < threshold

        result.metrics[name] = {
            "value": value,
            "threshold": threshold,
            "operator": operator,
            "pass": passed,
            "baseline": getattr(baseline, name),
            "improvement": value - getattr(baseline, name) if operator == ">=" else getattr(baseline, name) - value
        }

        if not passed:
            result.failure_reasons.append(
                f"{name}: {value:.3f} does not meet threshold {operator} {threshold}"
            )

    # 5. 检测退化
    regressions = detect_regression({}, {})
    if regressions:
        result.evidence["regressions"] = regressions
        for reg in regressions:
            if reg["severity"] == "critical":
                result.failure_reasons.append(
                    f"Regression detected: {reg['metric']} in {reg['task_id']}"
                )

    # 6. 判断最终结果
    result.overall_pass = len(result.failure_reasons) == 0
    result.status = "PASS" if result.overall_pass else "FAIL"

    return result
```

### 2.4 对比指标矩阵

```
┌─────────────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ 指标                    │ 修复前       │ 修复后目标   │ 最低改进     │ 验证方式     │
├─────────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ image_sending_rate      │ 53.9%        │ 100%         │ +46.1%       │ 统计         │
│ score_reasonability     │ ~65%         │ >= 95%       │ +30%         │ 公式验证     │
│ judgment_consistency    │ ~75%         │ >= 95%       │ +20%         │ 矛盾检测     │
│ error_propagation_rate  │ 28.57%       │ < 5%         │ -23%         │ 链路追踪     │
│ default_retention_rate  │ 78.8%        │ < 20%        │ -58%         │ 值分布       │
│ misjudgment_rate        │ ~10%         │ < 2%         │ -8%          │ GT 对比      │
├─────────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ llm_perfect_final_score │ 0.664        │ >= 0.9       │ +0.236       │ 直接计算     │
│ turn_level_expected     │ 0%           │ 100%*        │ +26.9%**     │ 代码检查     │
│ false_confirmation_rate │ ~10%         │ 0%           │ -10%         │ 场景测试     │
└─────────────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘

* 指中间 turns 使用 turn-level expected 的比率
** 中间 turns 占总 turns 的 26.9%
```

### 2.5 预期输出

```json
{
  "test_id": "3.7",
  "test_name": "Regression Test Suite",
  "status": "PASS",
  "metrics": {
    "image_sending_rate": {
      "value": 1.0,
      "threshold": 1.0,
      "operator": ">=",
      "pass": true,
      "baseline": 0.539,
      "improvement": 0.461,
      "improvement_pct": "85.5%"
    },
    "score_reasonability": {
      "value": 0.97,
      "threshold": 0.95,
      "operator": ">=",
      "pass": true,
      "baseline": 0.65,
      "improvement": 0.32,
      "improvement_pct": "49.2%"
    },
    "judgment_consistency": {
      "value": 0.96,
      "threshold": 0.95,
      "operator": ">=",
      "pass": true,
      "baseline": 0.75,
      "improvement": 0.21,
      "improvement_pct": "28.0%"
    },
    "error_propagation_rate": {
      "value": 0.02,
      "threshold": 0.05,
      "operator": "<",
      "pass": true,
      "baseline": 0.2857,
      "improvement": 0.2657,
      "improvement_pct": "93.0%"
    },
    "default_retention_rate": {
      "value": 0.12,
      "threshold": 0.20,
      "operator": "<",
      "pass": true,
      "baseline": 0.788,
      "improvement": 0.668,
      "improvement_pct": "84.8%"
    },
    "misjudgment_rate": {
      "value": 0.015,
      "threshold": 0.02,
      "operator": "<",
      "pass": true,
      "baseline": 0.10,
      "improvement": 0.085,
      "improvement_pct": "85.0%"
    }
  },
  "overall_pass": true,
  "failure_reasons": [],
  "comparison": {
    "summary": "All metrics show significant improvement over baseline",
    "total_improvements": 6,
    "total_regressions": 0,
    "improvement_details": {
      "image_sending_rate": "+85.5% (0.539 → 1.0)",
      "score_reasonability": "+49.2% (0.65 → 0.97)",
      "judgment_consistency": "+28.0% (0.75 → 0.96)",
      "error_propagation_rate": "-93.0% (0.2857 → 0.02)",
      "default_retention_rate": "-84.8% (0.788 → 0.12)",
      "misjudgment_rate": "-85.0% (0.10 → 0.015)"
    }
  },
  "evidence": {
    "tasks_run": 100,
    "baseline_source": "generated_tasks_v2/run_baseline",
    "run_timestamp": "2026-02-04T15:30:00Z",
    "phase1_issues_fixed": {
      "1.1_image_sending": "FIXED",
      "1.2_score_calculation": "FIXED",
      "1.3_expected_answer": "FIXED",
      "1.4_error_propagation": "FIXED",
      "1.5_multi_image_strategy": "FIXED",
      "1.6_evaluator_state": "FIXED"
    },
    "regressions": [],
    "sample_improvements": [
      {
        "task_id": "abr_example_001",
        "metric": "llm_perfect_final_score",
        "before": 0.664,
        "after": 0.90,
        "status": "IMPROVED"
      }
    ]
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
class RegressionComparison:
    """修复前后对比结果"""
    metric_name: str
    baseline_value: float
    postfix_value: float
    threshold: float
    operator: str  # ">=" or "<"
    improvement: float
    improvement_pct: float
    meets_threshold: bool
    meets_improvement_requirement: bool


@dataclass
class RegressionEvidence:
    """回归测试证据"""
    tasks_run: int
    baseline_source: str
    postfix_source: str
    run_timestamp: str
    phase1_issues_status: Dict[str, str]
    regressions_detected: List[Dict]
    sample_improvements: List[Dict]
    sample_failures: List[Dict]
```

### 3.2 测试接口

```python
def run_test_3_7(
    baseline_logs_dir: str,
    output_dir: str,
    task_count: int = 100
) -> Phase3TestResult:
    """
    运行 Task 3.7 回归测试套件

    Args:
        baseline_logs_dir: 修复前运行日志目录
        output_dir: 报告输出目录
        task_count: 测试任务数量 (默认100)

    Returns:
        Phase3TestResult
    """
    pass


def get_baseline_metrics(logs_dir: str) -> BaselineMetrics:
    """
    从修复前日志提取基线指标

    Args:
        logs_dir: 修复前运行日志目录

    Returns:
        BaselineMetrics
    """
    pass


def run_tasks_and_collect_metrics(
    task_list: List[Dict],
    output_dir: str
) -> PostFixMetrics:
    """
    运行任务并收集修复后指标

    Args:
        task_list: 任务列表
        output_dir: 输出目录

    Returns:
        PostFixMetrics
    """
    pass
```

---

## 四、协作要求

### 4.1 与其他任务的依赖关系

```
Task 3.7 (回归测试)
  ├── 强依赖: Task 3.1-3.6 全部 PASS
  │   ├── 3.1: 图像发送完整性 ✓
  │   ├── 3.2: 评分公式正确性 ✓
  │   ├── 3.3: Turn-Level GT 覆盖 ✓
  │   ├── 3.4: Simulator 真值一致性 ✓
  │   ├── 3.5: 多图任务 E2E ✓
  │   └── 3.6: Evaluator 状态一致性 ✓
  ├── 依赖: Phase 1 报告 (基线数据)
  └── 不可与其他任务并行

执行顺序:
1. 组H (3.1+3.2) + 组I (3.3+3.4) + 组J (3.5+3.6) 并行执行
2. 等待全部 PASS
3. 执行 Task 3.7 回归测试
4. 如果 FAIL，回到 Phase 2 修复
```

### 4.2 输出文件约定

| 文件 | 路径 | 格式 |
|------|------|------|
| Task 3.7 JSON 报告 | `report/stage3/phase3_3.7_regression.json` | JSON |
| Task 3.7 文本报告 | `report/stage3/phase3_3.7_regression_report.txt` | TXT |
| 对比详情 | `report/stage3/phase3_3.7_comparison_details.json` | JSON |
| 任务级结果 | `report/stage3/phase3_3.7_task_results.csv` | CSV |

### 4.3 失败处理流程

```
如果 Task 3.7 FAIL:

1. 识别失败类型:
   a. 指标未达标:
      - 检查哪个指标未达标
      - 回溯到对应的 Phase 2 任务
      - 可能需要重新修复

   b. 检测到退化:
      - 分析退化的具体表现
      - 确定引入退化的修复
      - 修复退化问题

   c. 新问题:
      - 记录新发现的问题
      - 创建新的 Phase 2 任务
      - 修复后重新验证

2. 修复流程:
   - 返回 Phase 2 进行修复
   - 重新运行对应的 Phase 3 验证 (3.1-3.6)
   - 确认单点修复通过
   - 重新运行 Task 3.7

3. 迭代直到:
   - 所有 6 个指标达标
   - 无检测到退化
   - 所有 Phase 1 问题已确认修复
```

---

## 五、执行指南

### 5.1 前置条件检查

```bash
# 进入项目目录
cd E:\Code\M3Bench\M3Bench_new

# 确认 Task 3.1-3.6 全部通过
python -c "
import json
from pathlib import Path

stage3_dir = Path('docs/task/round3/report/stage3')
required_tests = ['3.1', '3.2', '3.3', '3.4', '3.5', '3.6']
all_pass = True

for test_id in required_tests:
    report_file = stage3_dir / f'phase3_{test_id}_*.json'
    files = list(stage3_dir.glob(f'phase3_{test_id}_*.json'))
    if not files:
        print(f'Task {test_id}: NOT FOUND')
        all_pass = False
    else:
        with open(files[0]) as f:
            result = json.load(f)
            status = result.get('status', 'UNKNOWN')
            print(f'Task {test_id}: {status}')
            if status != 'PASS':
                all_pass = False

print(f'\\nAll prerequisites met: {all_pass}')
"
```

### 5.2 运行命令

```bash
# 确认前置条件通过后，运行回归测试
python -m pytest tests/phase3/test_3_7_regression_suite.py -v \
    --baseline-logs=generated_tasks_v2/run_baseline \
    --output-dir=docs/task/round3/report/stage3 \
    --task-count=100

# 或者运行专用脚本
python docs/task/round3/run_phase3_regression.py \
    --baseline-logs generated_tasks_v2/run_baseline \
    --output-dir docs/task/round3/report/stage3
```

### 5.3 环境要求

- Python 3.8+
- pytest
- **已完成 Phase 2 修复的代码库**
- **Task 3.1-3.6 全部 PASS**
- 修复前的运行日志 (作为基线)
- 足够的计算资源运行 100 个任务

---

## 六、成功标准总结

### Task 3.7 成功标准

**指标达标**:
- [ ] `image_sending_rate` = 100% (从 53.9% 提升)
- [ ] `score_reasonability` >= 95% (从 ~65% 提升至少 30%)
- [ ] `judgment_consistency` >= 95% (从 ~75% 提升至少 20%)
- [ ] `error_propagation_rate` < 5% (从 28.57% 下降)
- [ ] `default_retention_rate` < 20% (从 78.8% 下降)
- [ ] `misjudgment_rate` < 2% (从 ~10% 下降)

**Phase 1 问题确认修复**:
- [ ] Issue 1.1 (图像发送空) - FIXED
- [ ] Issue 1.2 (评分异常) - FIXED
- [ ] Issue 1.3 (Expected Answer) - FIXED
- [ ] Issue 1.4 (错误传播) - FIXED
- [ ] Issue 1.5 (多图策略) - FIXED
- [ ] Issue 1.6 (默认值保留) - FIXED

**无退化**:
- [ ] 无检测到退化
- [ ] 无新引入的问题
- [ ] 原本正确的评估保持正确

---

## 七、Phase 3 整体成功标准

当 Task 3.7 通过时，Phase 3 整体成功，需满足：

- [x] Task 3.1 图像发送完整性测试 PASS
- [x] Task 3.2 评分公式正确性测试 PASS
- [x] Task 3.3 Turn-Level GT 覆盖测试 PASS
- [x] Task 3.4 Simulator 真值一致性测试 PASS
- [x] Task 3.5 多图任务端到端测试 PASS
- [x] Task 3.6 评估器状态一致性测试 PASS
- [x] **Task 3.7 回归测试套件 PASS**

**Phase 3 完成后**:
- 所有 Phase 1 发现的问题已确认修复
- 系统评估准确性显著提升
- 无退化或新问题
- 可以进入生产使用

---

**文档作者**: Claude Code
**审核状态**: 待审核
**下一步**: 等待 Task 3.1-3.6 全部 PASS 后执行
