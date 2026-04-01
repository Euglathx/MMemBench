# Phase 3 Task 3.3 & 3.4: Turn-Level 验证测试计划

**文档版本**: 1.0
**创建日期**: 2026-02-04
**并行组**: I (可与H、J组并行执行)
**预估时间**: 1.5小时 (并行)

---

## 一、任务背景

### 1.1 Phase 2 修复总结

| Task ID | 修复内容 | Phase 2 报告 | 测试状态 |
|---------|---------|-------------|----------|
| **2.2** | Turn-Level Ground Truth 设计与实现 | [PHASE2_TASKS_2.2_2.3_COMPLETION_REPORT.md](report/stage2/PHASE2_TASKS_2.2_2.3_COMPLETION_REPORT.md) | 12/12 单元测试通过 |
| **2.4** | Simulator Truth Validation 机制 | [PHASE2_TASK2.4_TRUTH_VALIDATION_REPORT.md](report/stage2/PHASE2_TASK2.4_TRUTH_VALIDATION_REPORT.md) | 全部测试通过 |

### 1.2 Phase 1 发现的问题

#### Task 1.3: Expected Answer 跟踪问题 (P1 - HIGH)

**问题描述**:
- **100% 的 turns 使用 task-level expected_answer**
- **71 个 turns (26.9%)** 应该使用 turn-level expected answer
- **6 个确认误判案例**

**影响的 Phases**:
| Phase | 数量 | 应使用 Turn-Level | 状态 |
|-------|------|------------------|------|
| `entity_grounding` | 5 | 100% | ⚠️ CRITICAL |
| `chain_navigation` | 10 | 100% | ⚠️ CRITICAL |
| `grounding` | 56 | 100% | ⚠️ CRITICAL |
| `final_evaluation` | 56 | 0% | ✓ OK |
| `final_answer` | 5 | 0% | ✓ OK |

**根因** (代码位置: `strategic_simulator.py:818-827`):
```python
# 问题代码:
eval_result = self.evaluator.evaluate_response(
    response=model_content,
    expected_answer=self.task_state.expected_answer,  # ❌ Always task-level!
    ...
)
```

**误判案例示例**:
```
Task: "Find person. Find object left of person. What is it?"
Task Expected: "The final object is a knife"

Turn 1 (entity_grounding):
  Question: "Can you locate the person in the image?"
  Model: "The person is on the right side, wearing a red shirt"
  LLM Correctness: 10/10 (PERFECT)
  Expected Answer Used: "The final object is a knife" ❌
  Should Be: "Model should identify/describe the person" ✓
  Result: FAIL (score=0.66)
```

**Phase 2 修复方案**:
- 新增 `TurnGroundTruth` dataclass
- 实现 `_generate_turn_ground_truth()` 方法
- 更新 `TaskState` 包含 `turn_ground_truths` 字段
- 评估时使用 turn-level expected answer

#### Task 1.4: Simulator 真值验证问题 (P1 - HIGH)

**问题描述**:
- **Error propagation rate: 28.57%**
- Simulator 存储所有模型响应，无验证机制
- 无法区分正确和错误的声明
- Consistency checks 可能验证模型错误与自身一致

**Phase 2 修复方案**:
- 实现 `_validate_model_claims()` 方法
- 添加 `is_correct` 和 `claim_validation` 字段到 `TurnRecord`
- 实现 `get_conversation_history(filter_incorrect=True)` 过滤机制
- Consistency check 基于 ground truth 生成问题

---

## 二、Task 3.3: Turn-Level Ground Truth 覆盖测试

### 2.1 测试目标

验证 Phase 2 Task 2.2 的修复效果，确保所有中间 turns 使用正确的 turn-level expected answer。

### 2.2 验证指标与阈值 (零容忍)

| 指标 | 描述 | 阈值 | 失败条件 |
|------|------|------|----------|
| `turn_level_coverage` | 中间 phase turns 有独立 expected_answer 的比率 | **100%** | < 100% → FAIL |
| `expected_answer_alignment` | expected_answer 与 turn question 对齐的比率 | **100%** | < 100% → FAIL |
| `task_level_misuse_rate` | 中间 turns 使用 task-level answer 的比率 | **0%** | > 0% → FAIL |

### 2.3 测试脚本设计

```python
# tests/phase3/test_3_3_turn_level_ground_truth.py

import os
import json
import random
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TurnLevelGTResult:
    test_id: str = "3.3"
    test_name: str = "Turn-Level Ground Truth Coverage Test"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = None
    overall_pass: bool = False
    failure_reasons: List[str] = None
    evidence: Dict[str, Any] = None


def test_all_intermediate_turns_have_turn_level_expected():
    """
    验证所有中间 phase 的 turn 有独立的 expected_answer

    中间 phases:
    - entity_grounding
    - chain_navigation
    - grounding
    - follow_up
    - consistency_check
    - mislead

    非中间 phases (使用 task-level):
    - final_answer
    - final_evaluation

    断言:
    - turn_ground_truth.expected_answer != task_state.expected_answer
      for all intermediate turns
    """
    pass


def test_expected_answer_matches_turn_question():
    """
    验证 expected_answer 与 turn 的 question 语义对齐

    检查:
    - entity_grounding: expected 应该关于实体识别/定位
    - chain_navigation: expected 应该关于中间对象（非最终答案）
    - grounding: expected 应该关于基础理解建立
    """
    pass


def test_no_task_level_answer_in_intermediate_turns():
    """
    验证中间 turns 不再使用 task-level answer 进行评估

    检查:
    - 评估调用时传入的 expected_answer 不是 task.expected_answer
    """
    pass


def test_random_sample_abr_tasks():
    """
    随机抽查 ABR 任务验证

    方法:
    - 随机抽取 50 个 ABR 任务的 turn 2 (chain_navigation)
    - 验证 expected_answer != task final answer

    断言:
    - 所有 50 个样本都使用 turn-level expected answer
    """
    pass


def test_turn_ground_truth_data_structure():
    """
    验证 TurnGroundTruth 数据结构完整性

    必需字段:
    - turn_id: int
    - phase: str
    - action_type: str
    - sub_goal: str
    - expected_answer: str
    - acceptable_variations: List[str]
    - required_images: List[int]
    - ground_truth_facts: List[Dict]
    - evaluation_hints: Dict

    断言:
    - 所有必需字段都存在且类型正确
    """
    pass


def test_evaluation_hints_propagation():
    """
    验证 evaluation_hints 正确传递到 evaluator

    检查:
    - evaluator 收到 context["evaluation_hints"]
    - evaluation_hints 包含 "focus_on" 和 "ignore_final_answer" 字段
    """
    pass


def reproduce_misjudged_cases():
    """
    重现 Phase 1 发现的 6 个误判案例

    原误判案例:
    1. Entity grounding: perfect answer fails
    2. Chain navigation: immediate vs final object
    3. ... (共 6 个)

    预期:
    - 所有 6 个案例现在评估正确
    """
    pass


def run_comprehensive_test(log_dir: str) -> TurnLevelGTResult:
    """运行完整测试套件"""
    result = TurnLevelGTResult()
    result.metrics = {}
    result.failure_reasons = []
    result.evidence = {"failed_cases": [], "sample_logs": []}

    # ... 实现测试逻辑 ...

    result.overall_pass = all(
        m["pass"] for m in result.metrics.values()
    )
    result.status = "PASS" if result.overall_pass else "FAIL"

    return result
```

### 2.4 Sub-goal 类型验证矩阵

```
Phase → Sub-goal → Expected Answer Pattern
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

entity_grounding → identify_entity
  Expected: "Model should identify/describe the [entity]"
  NOT: "The final answer is [X]"

chain_navigation → find_spatial_neighbor
  Expected: "The object [relation] of [entity] is [intermediate]"
  NOT: "The final object is [final_answer]"

grounding → establish_understanding
  Expected: "Model should understand the visual context"
  NOT: "The final answer is [X]"

follow_up → clarify_detail
  Expected: "Model should provide additional detail about [topic]"
  NOT: "The final answer is [X]"

final_answer → provide_final_answer
  Expected: task.expected_answer (正确使用 task-level)
  ✓ OK to use task-level

final_evaluation → verify_final_answer
  Expected: task.expected_answer (正确使用 task-level)
  ✓ OK to use task-level
```

### 2.5 预期输出

```json
{
  "test_id": "3.3",
  "test_name": "Turn-Level Ground Truth Coverage Test",
  "status": "PASS",
  "metrics": {
    "turn_level_coverage": {
      "value": 1.0,
      "threshold": 1.0,
      "pass": true,
      "detail": "71/71 intermediate turns have turn-level expected"
    },
    "expected_answer_alignment": {
      "value": 1.0,
      "threshold": 1.0,
      "pass": true,
      "detail": "All expected answers align with turn questions"
    },
    "task_level_misuse_rate": {
      "value": 0.0,
      "threshold": 0.0,
      "pass": true,
      "detail": "0 intermediate turns use task-level answer"
    }
  },
  "overall_pass": true,
  "failure_reasons": [],
  "evidence": {
    "total_turns_analyzed": 264,
    "intermediate_turns": 71,
    "final_turns": 193,
    "misjudged_cases_fixed": 6,
    "random_sample_results": {
      "sample_size": 50,
      "all_correct": true
    },
    "sub_goal_distribution": {
      "identify_entity": 5,
      "find_spatial_neighbor": 10,
      "establish_understanding": 56
    }
  }
}
```

---

## 三、Task 3.4: Simulator 真值一致性测试

### 3.1 测试目标

验证 Phase 2 Task 2.4 的修复效果，确保 Simulator 不会"确认"模型的错误。

### 3.2 验证指标与阈值

| 指标 | 描述 | 阈值 | 失败条件 |
|------|------|------|----------|
| `false_confirmation_rate` | "伪确认"率（模型错误被肯定的比率） | **0%** | > 0% → FAIL |
| `error_propagation_rate` | 错误传播率 | **< 5%** | >= 5% → FAIL |
| `ground_truth_consistency_check` | Consistency check 基于 ground truth 的比率 | **100%** | < 100% → FAIL |

### 3.3 测试脚本设计

```python
# tests/phase3/test_3_4_simulator_truth_validation.py

import os
import json
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class SimulatorTruthResult:
    test_id: str = "3.4"
    test_name: str = "Simulator Truth Consistency Test"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = None
    overall_pass: bool = False
    failure_reasons: List[str] = None
    evidence: Dict[str, Any] = None


def test_no_false_confirmations():
    """
    验证 Simulator 不会确认模型的错误

    测试方法:
    - 创建 10 个故意错误的模型 responses
    - 验证 simulator 不会说 "you correctly..." 或类似确认语

    错误示例:
    - Question: "What color is the car?"
    - Ground truth: "red"
    - Model response: "The car is blue"
    - Simulator should NOT say: "Yes, you correctly identified the blue car"

    断言:
    - 所有 10 个错误响应都不会被 simulator 确认
    """
    pass


def test_error_propagation_controlled():
    """
    验证错误不会传播到后续 turns

    测试方法:
    - Turn 1: 模型给出错误答案 (score < 0.5)
    - Turn 2+: 验证错误信息是否被过滤

    检查:
    - get_conversation_history(filter_incorrect=True) 排除错误 turn
    - 后续 turn 的 context 不包含错误信息
    """
    pass


def test_consistency_check_uses_ground_truth():
    """
    验证 consistency check 基于 ground truth 而非模型声明

    之前的问题:
    ```python
    message = f"You mentioned {model_claims[-1]}. Can you confirm?"
    # 问题: 引用了可能错误的模型声明
    ```

    修复后:
    ```python
    message = self._generate_consistency_check_from_ground_truth()
    # 返回: "Let's verify: {original_question}" 或类似重述
    ```

    断言:
    - consistency check 问题不引用 model_claims
    - consistency check 问题基于 task 原始问题或 ground truth
    """
    pass


def test_claim_validation_logic():
    """
    验证 _validate_model_claims() 方法正确性

    验证策略:
    - Score >= 0.7: 高置信度，假设正确
    - Score < 0.4: 低置信度，假设错误
    - Score 0.4-0.7: 中等，启发式比较

    测试:
    - 高分响应 → is_correct = True
    - 低分响应 → is_correct = False
    - 中等分数 → 根据内容判断
    """
    pass


def test_memory_filtering():
    """
    验证内存过滤功能

    检查:
    - filter_incorrect=True 时排除 is_correct=False 的 turns
    - score_threshold 正确应用
    - is_correct 优先于 score 检查
    """
    pass


def test_false_claim_injection_resistance():
    """
    验证 Simulator 对虚假信息注入的抵抗

    测试方法:
    - 注入虚假声明到模型响应
    - 验证 Simulator 不会将其视为事实
    - 验证后续 consistency check 不会基于虚假声明
    """
    pass


def create_deliberately_wrong_responses() -> List[Dict]:
    """
    创建 10 个故意错误的模型响应

    返回:
    [
        {
            "question": "What color is the car?",
            "ground_truth": "red",
            "wrong_response": "The car is blue",
            "expected_validation": {"is_correct": False}
        },
        ...
    ]
    """
    return [
        {
            "question": "What color is the car in the image?",
            "ground_truth": "The car is red",
            "wrong_response": "I can see a blue car in the image.",
            "expected_is_correct": False
        },
        {
            "question": "How many people are in the image?",
            "ground_truth": "There are 3 people",
            "wrong_response": "There is only 1 person in the image.",
            "expected_is_correct": False
        },
        {
            "question": "What is the person holding?",
            "ground_truth": "A book",
            "wrong_response": "The person is holding a phone.",
            "expected_is_correct": False
        },
        {
            "question": "Is the cat sitting or standing?",
            "ground_truth": "sitting",
            "wrong_response": "The cat is standing on the floor.",
            "expected_is_correct": False
        },
        {
            "question": "What is on the left side of the table?",
            "ground_truth": "A lamp",
            "wrong_response": "There is a vase on the left side of the table.",
            "expected_is_correct": False
        },
        {
            "question": "What time is shown on the clock?",
            "ground_truth": "3:30",
            "wrong_response": "The clock shows 7:45.",
            "expected_is_correct": False
        },
        {
            "question": "Is the door open or closed?",
            "ground_truth": "open",
            "wrong_response": "The door appears to be closed.",
            "expected_is_correct": False
        },
        {
            "question": "What breed is the dog?",
            "ground_truth": "Golden Retriever",
            "wrong_response": "This is a German Shepherd.",
            "expected_is_correct": False
        },
        {
            "question": "What is the weather like in the image?",
            "ground_truth": "sunny",
            "wrong_response": "It looks like a rainy day with dark clouds.",
            "expected_is_correct": False
        },
        {
            "question": "Where is the ball located?",
            "ground_truth": "under the chair",
            "wrong_response": "The ball is on top of the table.",
            "expected_is_correct": False
        }
    ]


def run_comprehensive_test(log_dir: str) -> SimulatorTruthResult:
    """运行完整测试套件"""
    result = SimulatorTruthResult()
    result.metrics = {}
    result.failure_reasons = []
    result.evidence = {
        "false_confirmation_cases": [],
        "error_propagation_cases": [],
        "sample_logs": []
    }

    # ... 实现测试逻辑 ...

    result.overall_pass = all(
        m["pass"] for m in result.metrics.values()
    )
    result.status = "PASS" if result.overall_pass else "FAIL"

    return result
```

### 3.4 验证配置

```python
# 默认配置验证
simulator_config = {
    "filter_incorrect_turns": True,  # 默认启用
    "error_filter_threshold": 0.5    # 分数阈值
}

# 验证点:
# 1. StrategicSimulator 使用默认配置
# 2. 过滤功能正常工作
# 3. 阈值正确应用
```

### 3.5 预期输出

```json
{
  "test_id": "3.4",
  "test_name": "Simulator Truth Consistency Test",
  "status": "PASS",
  "metrics": {
    "false_confirmation_rate": {
      "value": 0.0,
      "threshold": 0.0,
      "pass": true,
      "detail": "0/10 wrong responses were falsely confirmed"
    },
    "error_propagation_rate": {
      "value": 0.0,
      "threshold": 0.05,
      "pass": true,
      "detail": "0% errors propagated to subsequent turns"
    },
    "ground_truth_consistency_check": {
      "value": 1.0,
      "threshold": 1.0,
      "pass": true,
      "detail": "100% consistency checks based on ground truth"
    }
  },
  "overall_pass": true,
  "failure_reasons": [],
  "evidence": {
    "deliberately_wrong_responses_tested": 10,
    "false_confirmations_found": 0,
    "error_propagation_instances": 0,
    "consistency_check_samples": [
      {
        "type": "reformulated_question",
        "original": "What color is the car?",
        "consistency_question": "Let's verify: What color is the car in the image?"
      }
    ],
    "memory_filtering_tests": {
      "total_turns": 50,
      "filtered_out": 12,
      "filter_reason": "is_correct=False or score<0.5"
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


@dataclass
class TurnGroundTruth:
    """Turn-level ground truth (来自 Phase 2 Task 2.2)"""
    turn_id: int
    phase: str
    action_type: str
    sub_goal: str
    expected_answer: str
    acceptable_variations: List[str] = field(default_factory=list)
    required_images: List[int] = field(default_factory=list)
    ground_truth_facts: List[Dict[str, Any]] = field(default_factory=list)
    evaluation_hints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimValidation:
    """声明验证结果 (来自 Phase 2 Task 2.4)"""
    claims: List[str]
    has_false_claims: bool
    false_claim_count: int
    validation_summary: str
    is_correct: bool
```

### 4.2 测试接口

```python
def run_test_3_3(log_dir: str, output_dir: str) -> Phase3TestResult:
    """
    运行 Task 3.3 Turn-Level Ground Truth 覆盖测试

    Args:
        log_dir: 运行日志目录
        output_dir: 报告输出目录

    Returns:
        Phase3TestResult
    """
    pass


def run_test_3_4(log_dir: str, output_dir: str) -> Phase3TestResult:
    """
    运行 Task 3.4 Simulator 真值一致性测试

    Args:
        log_dir: 运行日志目录
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
Task 3.3 (Turn-Level GT)
  ├── 依赖: Phase 2 Task 2.2 修复
  ├── 无前置 Phase 3 依赖
  └── 可与 3.1, 3.2, 3.4, 3.5, 3.6 并行

Task 3.4 (Simulator Truth)
  ├── 依赖: Phase 2 Task 2.4 修复
  ├── 无前置 Phase 3 依赖
  └── 可与 3.1, 3.2, 3.3, 3.5, 3.6 并行
```

### 5.2 输出文件约定

| 文件 | 路径 | 格式 |
|------|------|------|
| Task 3.3 JSON 报告 | `report/stage3/phase3_3.3_turn_level_gt.json` | JSON |
| Task 3.3 文本报告 | `report/stage3/phase3_3.3_validation_report.txt` | TXT |
| Task 3.4 JSON 报告 | `report/stage3/phase3_3.4_simulator_truth.json` | JSON |
| Task 3.4 文本报告 | `report/stage3/phase3_3.4_validation_report.txt` | TXT |

### 5.3 失败处理流程

```
如果 Task 3.3 FAIL:
1. 检查 failure_reasons 中的具体失败原因
2. 检查哪些 phases 仍在使用 task-level expected answer
3. 检查 TurnGroundTruth 生成逻辑
4. 返回 Phase 2 Task 2.2 进行修复
5. 重新运行 Task 3.3
6. 直到 100% PASS

如果 Task 3.4 FAIL:
1. 检查 failure_reasons 中的具体失败原因
2. 检查 false_confirmation_cases 和 error_propagation_cases
3. 检查 _validate_model_claims() 逻辑
4. 检查 memory filtering 逻辑
5. 返回 Phase 2 Task 2.4 进行修复
6. 重新运行 Task 3.4
7. 直到 100% PASS
```

---

## 六、执行指南

### 6.1 运行命令

```bash
# 进入项目目录
cd E:\Code\M3Bench\M3Bench_new

# 运行 Task 3.3
python -m pytest tests/phase3/test_3_3_turn_level_ground_truth.py -v \
    --log-dir=generated_tasks_v2 \
    --output-dir=docs/task/round3/report/stage3

# 运行 Task 3.4
python -m pytest tests/phase3/test_3_4_simulator_truth_validation.py -v \
    --log-dir=generated_tasks_v2 \
    --output-dir=docs/task/round3/report/stage3

# 或者运行组合测试脚本
python docs/task/round3/run_phase3_group_I.py
```

### 6.2 环境要求

- Python 3.8+
- pytest
- 已完成 Phase 2 修复的代码库
- 至少一个有效的运行日志目录

---

## 七、成功标准总结

### Task 3.3 成功标准

- [ ] `turn_level_coverage` = 100% (所有中间 turns 使用 turn-level expected)
- [ ] `expected_answer_alignment` = 100% (expected answer 与 turn question 对齐)
- [ ] `task_level_misuse_rate` = 0% (中间 turns 不使用 task-level answer)
- [ ] 所有 6 个 Phase 1 误判案例已修复
- [ ] 随机抽查 50 个 ABR 任务全部正确

### Task 3.4 成功标准

- [ ] `false_confirmation_rate` = 0% (模型错误不被 simulator 确认)
- [ ] `error_propagation_rate` < 5% (错误不传播到后续 turns)
- [ ] `ground_truth_consistency_check` = 100% (consistency check 基于 ground truth)
- [ ] 10 个故意错误的响应测试全部正确处理
- [ ] Memory filtering 功能正常工作

---

**文档作者**: Claude Code
**审核状态**: 待审核
**下一步**: 等待 Task 3.3 和 3.4 的实施和执行
