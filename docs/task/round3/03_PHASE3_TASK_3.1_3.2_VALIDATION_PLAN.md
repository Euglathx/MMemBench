# Phase 3 Task 3.1 & 3.2: 基础验证测试计划

**文档版本**: 1.0
**创建日期**: 2026-02-04
**并行组**: H (可与I、J组并行执行)
**预估时间**: 1-2小时 (并行)

---

## 一、任务背景

### 1.1 Phase 2 修复总结

| Task ID | 修复内容 | Phase 2 报告 | 测试状态 |
|---------|---------|-------------|----------|
| **2.1** | 图像发送管道修复 | [PHASE2_TASK2.1_IMAGE_PIPELINE_FIX_REPORT.md](report/stage2/PHASE2_TASK2.1_IMAGE_PIPELINE_FIX_REPORT.md) | 10/10 单元测试通过 |
| **2.3** | 评分公式重构 | [PHASE2_TASKS_2.2_2.3_COMPLETION_REPORT.md](report/stage2/PHASE2_TASKS_2.2_2.3_COMPLETION_REPORT.md) | 12/12 单元测试通过 |

### 1.2 Phase 1 发现的问题

#### Task 1.1: 图像发送问题 (P1 - HIGH)

**问题描述**:
- **46.1% 的 turns (150/325)** 的 `images_sent` 字段为空
- 模型回复 "I'm unable to view images directly"
- 所有受影响 turns 的评估结果无效
- 问题与时间相关（Feb 1日运行失败，Feb 2日成功）

**根因**:
- `_get_images_for_turn()` 方法的路径解析逻辑脆弱
- 工作目录不匹配
- 搜索策略有限
- 无错误日志或验证机制

**Phase 2 修复方案**:
- 实现 4 策略路径解析系统
- 添加综合日志系统 (DEBUG/INFO/WARNING/ERROR)
- 添加验证以防止空 `images_sent`
- 10 个单元测试全部通过

#### Task 1.2: 评分公式问题 (P0 - CRITICAL)

**问题描述**:
- LLM Judge 给出 10/10 满分，但 `final_score < 0.7`
- 导致 `level_passed = false`
- 10+ 个异常案例被确认

**根因** (代码位置: `evaluator.py:907-914`):
```python
# 问题代码:
if llm_scores:
    w = self.llm_judge_weight  # w = 0.6
    final_scores = {
        k: w * llm_scores[k] + (1 - w) * hard_scores[k]
        for k in hard_scores
    }
# hard_scores 默认值为 0.1-0.3 (惩罚性)，污染最终分数
```

**Phase 2 修复方案**:
- Hard scores 默认值从 0.1-0.3 调整为 0.5 (中性)
- LLM Judge 权重从 0.6 调整为 0.8
- 添加详细评分计算日志

---

## 二、Task 3.1: 图像发送完整性测试

### 2.1 测试目标

验证 Phase 2 Task 2.1 的修复效果，确保图像发送管道 100% 可靠。

### 2.2 验证指标与阈值 (零容忍)

| 指标 | 描述 | 阈值 | 失败条件 |
|------|------|------|----------|
| `images_sent_rate` | `images_sent` 不为空的比率 | **100%** | < 100% → FAIL |
| `image_exists_rate` | 图像文件实际存在的比率 | **100%** | < 100% → FAIL |
| `api_payload_correct_rate` | API payload 包含正确 image_url | **100%** | < 100% → FAIL |

### 2.3 测试脚本设计

```python
# tests/phase3/test_3_1_image_completeness.py

import os
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class ImageValidationResult:
    test_id: str = "3.1"
    test_name: str = "Image Sending Completeness Test"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = None
    overall_pass: bool = False
    failure_reasons: List[str] = None
    evidence: Dict[str, Any] = None


def test_images_sent_not_empty():
    """
    验证所有应发送图像的 turn 的 images_sent 不为空

    遍历条件:
    - task.images 不为空的任务
    - 所有 turns (不仅是 guidance)

    断言:
    - images_sent != [] for all relevant turns
    """
    pass


def test_image_files_exist():
    """
    验证所有 images_sent 中的路径对应的文件实际存在

    检查:
    - os.path.exists(image_path) == True
    - os.path.isfile(image_path) == True
    """
    pass


def test_api_payload_contains_images():
    """
    验证发送到模型的 API payload 包含正确的 image_url

    检查:
    - payload["messages"] 包含 image content
    - image_url 格式正确 (base64 或 URL)
    """
    pass


def test_resolution_strategies():
    """
    验证 4 策略路径解析的正确性:
    1. Direct path (relative to CWD)
    2. Absolute path check
    3. Search in generated_tasks_v2/run_*/images
    4. Common directories at project root
    """
    pass


def run_comprehensive_test(log_dir: str) -> ImageValidationResult:
    """
    运行完整测试套件

    Args:
        log_dir: 运行日志目录 (e.g., "generated_tasks_v2/run_18")

    Returns:
        ImageValidationResult with all metrics
    """
    result = ImageValidationResult()
    result.metrics = {}
    result.failure_reasons = []
    result.evidence = {"failed_cases": [], "sample_logs": []}

    # ... 实现测试逻辑 ...

    # 判断是否通过
    result.overall_pass = all(
        m["pass"] for m in result.metrics.values()
    )
    result.status = "PASS" if result.overall_pass else "FAIL"

    return result
```

### 2.4 测试数据要求

| 数据项 | 来源 | 最小数量 |
|--------|------|----------|
| 运行日志 | `generated_tasks_v2/run_*/` | 至少 3 个 run |
| 任务类型 | ABR, AC, AR 等 | 覆盖所有类型 |
| 图像数量 | 单图/多图任务 | 各至少 20 个 |

### 2.5 预期输出

```json
{
  "test_id": "3.1",
  "test_name": "Image Sending Completeness Test",
  "status": "PASS",
  "metrics": {
    "images_sent_rate": {"value": 1.0, "threshold": 1.0, "pass": true},
    "image_exists_rate": {"value": 1.0, "threshold": 1.0, "pass": true},
    "api_payload_correct_rate": {"value": 1.0, "threshold": 1.0, "pass": true}
  },
  "overall_pass": true,
  "failure_reasons": [],
  "evidence": {
    "total_turns_checked": 325,
    "images_per_turn_avg": 2.3,
    "resolution_strategy_usage": {
      "direct": 45,
      "absolute": 12,
      "run_directory": 268,
      "common_directory": 0
    }
  }
}
```

---

## 三、Task 3.2: 评分公式正确性测试

### 3.1 测试目标

验证 Phase 2 Task 2.3 的修复效果，确保评分公式逻辑正确。

### 3.2 验证指标与阈值

| 指标 | 描述 | 阈值 | 失败条件 |
|------|------|------|----------|
| `perfect_score_threshold` | LLM Judge 10/10 → final score | **>= 0.9** | < 0.9 → FAIL |
| `low_score_threshold` | LLM Judge <= 3/10 → final score | **<= 0.3** | > 0.3 → FAIL |
| `calculation_error_rate` | 计算误差率 | **< 5%** | >= 5% → FAIL |

### 3.3 测试用例设计

```python
# tests/phase3/test_3_2_score_formula.py

from dataclasses import dataclass
from typing import Dict, List, Any

@dataclass
class ScoreFormulaResult:
    test_id: str = "3.2"
    test_name: str = "Score Formula Correctness Test"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = None
    overall_pass: bool = False
    failure_reasons: List[str] = None
    evidence: Dict[str, Any] = None


def test_perfect_llm_score_gives_high_final():
    """
    Case 1: 全满分 case

    输入:
    - llm_scores = {correctness: 1.0, faithfulness: 1.0, ...}
    - hard_scores = {correctness: 0.5, ...} (中性默认值)
    - llm_judge_weight = 0.8

    预期:
    - final_score >= 0.9
    - 误差 < 0.05

    计算验证:
    final = 0.8 * 1.0 + 0.2 * 0.5 = 0.9 ✓
    """
    pass


def test_low_llm_score_gives_low_final():
    """
    Case 2: 全低分 case

    输入:
    - llm_scores = {correctness: 0.2, faithfulness: 0.3, ...}
    - hard_scores = {correctness: 0.5, ...}
    - llm_judge_weight = 0.8

    预期:
    - final_score < 0.3
    """
    pass


def test_mixed_scores():
    """
    Case 3: 混合 case

    输入:
    - llm_scores = {correctness: 0.8, faithfulness: 0.6, robustness: 0.9, ...}
    - 按公式计算预期值

    预期:
    - 实际值与预期值误差 < 0.05
    """
    pass


def test_hard_scores_neutral_defaults():
    """
    验证 hard_scores 使用中性默认值 (0.5)

    检查:
    - correctness: 0.5
    - faithfulness: 0.5
    - robustness: 0.5
    - consistency: 0.5
    - memory_retention: 0.5
    """
    pass


def test_llm_judge_weight_is_0_8():
    """
    验证 LLM Judge 权重为 0.8

    检查:
    - evaluator.llm_judge_weight == 0.8
    """
    pass


def test_score_calculation_logging():
    """
    验证评分计算日志正确输出

    检查日志包含:
    - [Score Calculation] LLM Judge weight: 0.80
    - [Score Calculation] Hard scores: {...}
    - [Score Calculation] LLM scores: {...}
    - [Score Calculation] {dim}: hard=X, llm=Y, final=Z
    """
    pass


def test_level_threshold_check():
    """
    验证 level 通过阈值检查

    Case 1: score = 0.8 >= 0.7 → level_passed = True
    Case 2: score = 0.6 < 0.7 → level_passed = False
    """
    pass


def reproduce_anomaly_cases():
    """
    重现 Phase 1 发现的异常案例，验证已修复

    原异常案例:
    - abr_example_001: LLM 10/10, old_score=0.664, new_score=?
    - ac_mscoco_001: LLM 9-10/10, old_score=0.680, new_score=?

    预期:
    - 所有原异常案例现在得到合理分数 (>= 0.8 for high LLM scores)
    """
    pass
```

### 3.4 计算公式验证

**当前配置验证**:
```
LLM Judge Weight (w) = 0.8
Hard Scores Default = 0.5 (中性)

公式: final[dim] = w * llm[dim] + (1-w) * hard[dim]
     = 0.8 * llm[dim] + 0.2 * hard[dim]

验证点:
┌─────────────┬──────────┬────────────┬─────────────┐
│ LLM Score   │ Hard     │ Final      │ Pass (>=0.7)│
├─────────────┼──────────┼────────────┼─────────────┤
│ 10/10 (1.0) │ 0.5      │ 0.9        │ ✓           │
│ 9/10 (0.9)  │ 0.5      │ 0.82       │ ✓           │
│ 8/10 (0.8)  │ 0.5      │ 0.74       │ ✓           │
│ 7/10 (0.7)  │ 0.5      │ 0.66       │ ✗           │
│ 5/10 (0.5)  │ 0.5      │ 0.50       │ ✗           │
│ 3/10 (0.3)  │ 0.5      │ 0.34       │ ✗           │
└─────────────┴──────────┴────────────┴─────────────┘
```

### 3.5 预期输出

```json
{
  "test_id": "3.2",
  "test_name": "Score Formula Correctness Test",
  "status": "PASS",
  "metrics": {
    "perfect_score_threshold": {
      "value": 0.9,
      "threshold": 0.9,
      "pass": true,
      "detail": "LLM 10/10 → final 0.9"
    },
    "low_score_threshold": {
      "value": 0.28,
      "threshold": 0.3,
      "pass": true,
      "detail": "LLM 2/10 → final 0.28"
    },
    "calculation_error_rate": {
      "value": 0.02,
      "threshold": 0.05,
      "pass": true,
      "detail": "Max error: 2%"
    }
  },
  "overall_pass": true,
  "failure_reasons": [],
  "evidence": {
    "anomaly_cases_fixed": [
      {
        "case_id": "abr_example_001",
        "llm_score": "10/10",
        "old_final": 0.664,
        "new_final": 0.9,
        "status": "FIXED"
      }
    ],
    "formula_config": {
      "llm_judge_weight": 0.8,
      "hard_scores_default": 0.5
    }
  }
}
```

---

## 四、变量与接口定义

### 4.1 共享数据结构

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

class TestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class ValidationMetric:
    """单个验证指标"""
    name: str
    value: float
    threshold: float
    pass_: bool
    detail: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.pass_


@dataclass
class Phase3TestResult:
    """Phase 3 测试结果标准格式"""
    test_id: str
    test_name: str
    status: TestStatus
    metrics: Dict[str, ValidationMetric] = field(default_factory=dict)
    overall_pass: bool = False
    failure_reasons: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "status": self.status.value,
            "metrics": {
                k: {
                    "value": v.value,
                    "threshold": v.threshold,
                    "pass": v.pass_,
                    "detail": v.detail
                }
                for k, v in self.metrics.items()
            },
            "overall_pass": self.overall_pass,
            "failure_reasons": self.failure_reasons,
            "evidence": self.evidence
        }
```

### 4.2 测试接口

```python
# 标准测试接口
def run_test_3_1(log_dir: str, output_dir: str) -> Phase3TestResult:
    """
    运行 Task 3.1 图像完整性测试

    Args:
        log_dir: 运行日志目录
        output_dir: 报告输出目录

    Returns:
        Phase3TestResult
    """
    pass


def run_test_3_2(evaluator_code: str, output_dir: str) -> Phase3TestResult:
    """
    运行 Task 3.2 评分公式测试

    Args:
        evaluator_code: evaluator.py 文件路径
        output_dir: 报告输出目录

    Returns:
        Phase3TestResult
    """
    pass
```

---

## 五、协作要求

### 5.1 与其他任务的依赖关系

```
Task 3.1 (图像完整性)
  ├── 依赖: Phase 2 Task 2.1 修复
  ├── 无前置 Phase 3 依赖
  └── 可与 3.2, 3.3, 3.4, 3.5, 3.6 并行

Task 3.2 (评分公式)
  ├── 依赖: Phase 2 Task 2.3 修复
  ├── 无前置 Phase 3 依赖
  └── 可与 3.1, 3.3, 3.4, 3.5, 3.6 并行
```

### 5.2 输出文件约定

| 文件 | 路径 | 格式 |
|------|------|------|
| Task 3.1 JSON 报告 | `report/stage3/phase3_3.1_image_completeness.json` | JSON |
| Task 3.1 文本报告 | `report/stage3/phase3_3.1_validation_report.txt` | TXT |
| Task 3.2 JSON 报告 | `report/stage3/phase3_3.2_score_formula.json` | JSON |
| Task 3.2 文本报告 | `report/stage3/phase3_3.2_validation_report.txt` | TXT |

### 5.3 失败处理流程

```
如果 Task 3.1 FAIL:
1. 检查 failure_reasons 中的具体失败原因
2. 检查 evidence.failed_cases 中的失败案例
3. 返回 Phase 2 Task 2.1 进行修复
4. 重新运行 Task 3.1
5. 直到 100% PASS

如果 Task 3.2 FAIL:
1. 检查 failure_reasons 中的具体失败原因
2. 检查 evidence.anomaly_cases 中的异常案例
3. 返回 Phase 2 Task 2.3 进行修复
4. 重新运行 Task 3.2
5. 直到 100% PASS
```

---

## 六、执行指南

### 6.1 运行命令

```bash
# 进入项目目录
cd E:\Code\M3Bench\M3Bench_new

# 运行 Task 3.1
python -m pytest tests/phase3/test_3_1_image_completeness.py -v \
    --log-dir=generated_tasks_v2 \
    --output-dir=docs/task/round3/report/stage3

# 运行 Task 3.2
python -m pytest tests/phase3/test_3_2_score_formula.py -v \
    --output-dir=docs/task/round3/report/stage3

# 或者运行组合测试脚本
python docs/task/round3/run_phase3_group_H.py
```

### 6.2 环境要求

- Python 3.8+
- pytest
- 已完成 Phase 2 修复的代码库
- 至少一个有效的运行日志目录

---

## 七、成功标准总结

### Task 3.1 成功标准

- [ ] `images_sent_rate` = 100% (所有应发送图像的 turn 都有图像)
- [ ] `image_exists_rate` = 100% (所有路径对应的文件都存在)
- [ ] `api_payload_correct_rate` = 100% (API payload 格式正确)
- [ ] 无任何失败案例

### Task 3.2 成功标准

- [ ] LLM Judge 10/10 → final_score >= 0.9
- [ ] LLM Judge <= 3/10 → final_score <= 0.3
- [ ] 计算误差 < 5%
- [ ] 所有 Phase 1 异常案例已修复

---

**文档作者**: Claude Code
**审核状态**: 待审核
**下一步**: 等待 Task 3.1 和 3.2 的实施和执行
