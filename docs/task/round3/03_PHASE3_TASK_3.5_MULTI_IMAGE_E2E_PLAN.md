# Phase 3 Task 3.5: 多图任务端到端测试计划

**文档版本**: 1.0
**创建日期**: 2026-02-04
**并行组**: J (可与H、I组并行执行)
**预估时间**: 2小时

---

## 一、任务背景

### 1.1 Phase 2 修复总结

| Task ID | 修复内容 | Phase 2 报告 | 测试状态 |
|---------|---------|-------------|----------|
| **2.5** | Multi-Image Strategy Unification | [PHASE2_TASK2.5_MULTI_IMAGE_STRATEGY_REPORT.md](report/stage2/PHASE2_TASK2.5_MULTI_IMAGE_STRATEGY_REPORT.md) | 全部测试通过 |

### 1.2 Phase 1 发现的问题

#### Task 1.5: 多图策略不一致问题 (P1 - HIGH)

**问题描述**:
- **54% 的 turns 发送 0 张图像**
- **43% 的 turns 发送所有图像**
- StrategicSimulator 使用 "send all" 策略
- LLMUserSimulator 使用 "progressive" 策略
- Evaluator 不知道实际发送了哪些图像

**Phase 1 统计**:
```
图像发送分布:
- 0 images: 54% (严重问题)
- 1 image: 2%
- 2 images: 1%
- 3+ images: 43%
```

**根因**:
1. 两个 Simulator 使用不同的图像注入策略
2. 无统一的策略管理器
3. Evaluator 无法感知 `images_sent`

**Phase 2 修复方案**:
- 新增 `ImageInjectionPolicy` 枚举 (4种策略)
- 新增 `ImagePolicyManager` 类
- 两个 Simulator 统一使用 ImagePolicyManager
- `images_sent` 传递到 evaluator context

---

## 二、Task 3.5: 多图任务端到端测试

### 2.1 测试目标

验证 Phase 2 Task 2.5 的修复效果，确保多图任务的完整端到端流程正确。

### 2.2 验证指标与阈值

| 指标 | 描述 | 阈值 | 失败条件 |
|------|------|------|----------|
| `ac_task_consistency` | AC 任务定义一致性 | **100%** | < 100% → FAIL |
| `images_question_alignment` | images_sent 与 question target 对齐 | **100%** | < 100% → FAIL |
| `evaluator_image_awareness` | Evaluator 知道实际发送的图像 | **100%** | < 100% → FAIL |

### 2.3 测试脚本设计

```python
# tests/phase3/test_3_5_multi_image_e2e.py

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class ImageInjectionPolicy(str, Enum):
    """图像注入策略枚举"""
    SEND_ALL_EVERY_TURN = "send_all_every_turn"
    PROGRESSIVE = "progressive"
    SEND_ALL_FIRST_TURN = "send_all_first_turn"
    ACTION_DEPENDENT = "action_dependent"


@dataclass
class MultiImageE2EResult:
    test_id: str = "3.5"
    test_name: str = "Multi-Image Task End-to-End Test"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = None
    overall_pass: bool = False
    failure_reasons: List[str] = None
    evidence: Dict[str, Any] = None


# ====================
# 测试用例: 单图任务
# ====================

def test_single_image_task():
    """
    测试单图任务的图像发送

    任务类型: 单图任务 (ABR single, AC single-image)

    验证:
    - 每个 turn 只发送 1 张图像
    - images_sent 长度 = 1
    - evaluator context 包含正确的 images_sent
    """
    pass


def test_single_image_all_turns_consistent():
    """
    验证单图任务所有 turns 的图像一致性

    使用 SEND_ALL_EVERY_TURN 策略:
    - Turn 1: [img1]
    - Turn 2: [img1]
    - Turn 3: [img1]
    - ...

    断言:
    - 所有 turns 的 images_sent 相同
    """
    pass


# ====================
# 测试用例: 3图任务
# ====================

def test_three_image_task_send_all():
    """
    测试 3 图任务 (SEND_ALL_EVERY_TURN 策略)

    任务类型: AC 任务 (3 images)

    验证:
    - 每个 turn 发送 3 张图像
    - images_sent 长度 = 3
    - 图像顺序一致
    """
    pass


def test_three_image_task_progressive():
    """
    测试 3 图任务 (PROGRESSIVE 策略)

    任务类型: AC 任务 (3 images)

    验证:
    - Turn 1 (guidance): [img1]
    - Turn 2 (guidance): [img2]
    - Turn 3 (guidance): [img3]
    - Turn 4 (guidance): [] (所有图像已显示)
    - Turn 5 (follow_up): [] (非 guidance)
    """
    pass


def test_three_image_task_first_turn_only():
    """
    测试 3 图任务 (SEND_ALL_FIRST_TURN 策略)

    验证:
    - Turn 1: [img1, img2, img3]
    - Turn 2: []
    - Turn 3: []
    """
    pass


# ====================
# 测试用例: 渐进式任务
# ====================

def test_progressive_task_image_reveal():
    """
    测试渐进式任务的图像逐步展示

    任务设计:
    - 初始: 隐藏所有图像
    - Turn 1: 展示 img1
    - Turn 2: 展示 img2
    - Turn 3: 展示 img3

    验证:
    - 每个 turn 正确增加展示的图像
    - 模型只能看到已展示的图像
    """
    pass


def test_progressive_task_memory_retention():
    """
    测试渐进式任务的记忆保留

    验证:
    - 模型能记住之前展示的图像内容
    - 后续 turns 可以引用之前的图像
    """
    pass


# ====================
# 测试用例: AC 任务一致性
# ====================

def test_ac_task_expected_answer_consistency():
    """
    验证 AC 任务的 expected_answer 与图像定义一致

    AC 任务类型:
    - attribute_comparison: 比较多图属性
    - counting_comparison: 比较数量

    验证:
    - expected_answer 正确引用图像
    - 图像顺序与答案对应
    """
    pass


def test_ac_task_question_image_alignment():
    """
    验证 AC 任务的 question 与 images_sent 对齐

    示例:
    - Question: "Which image has more red objects, Image 1 or Image 2?"
    - images_sent: [img1, img2]
    - 验证: img1 对应 "Image 1", img2 对应 "Image 2"
    """
    pass


# ====================
# 测试用例: Evaluator 集成
# ====================

def test_evaluator_receives_images_sent():
    """
    验证 Evaluator 收到 images_sent 参数

    检查:
    - context["images_sent"] 存在
    - context["images_sent"] 是列表
    - context["total_task_images"] 存在
    """
    pass


def test_evaluator_uses_images_for_evaluation():
    """
    验证 Evaluator 使用 images_sent 进行评估

    检查:
    - 当 images_sent = [] 且模型有视觉描述 → 检测为幻觉
    - 当 images_sent != [] 且模型有视觉描述 → 正常评估
    """
    pass


def test_evaluator_detects_partial_image_errors():
    """
    验证 Evaluator 检测部分图像错误

    场景:
    - 任务有 3 张图像
    - 只发送了 2 张 (progressive 策略)
    - 模型描述了第 3 张图像的内容

    预期:
    - Evaluator 应该检测到模型描述了未发送的图像
    """
    pass


# ====================
# 测试用例: 策略一致性
# ====================

def test_strategic_simulator_uses_policy():
    """
    验证 StrategicSimulator 使用 ImagePolicyManager

    检查:
    - simulator.image_policy 存在
    - simulator.image_policy 是 ImagePolicyManager 实例
    - 策略正确应用
    """
    pass


def test_llm_user_simulator_uses_policy():
    """
    验证 LLMUserSimulator 使用 ImagePolicyManager

    检查:
    - simulator.image_policy 存在
    - simulator.image_policy 是 ImagePolicyManager 实例
    - 策略正确应用
    """
    pass


def test_both_simulators_same_behavior():
    """
    验证两个 Simulator 使用相同策略时行为一致

    测试:
    - 相同任务
    - 相同策略
    - 相同 turn 序列

    断言:
    - images_sent 序列相同
    """
    pass


# ====================
# 端到端测试
# ====================

def test_e2e_single_image_flow():
    """
    端到端测试: 单图任务完整流程

    流程:
    1. 创建单图任务
    2. Simulator 发送图像
    3. 模型响应
    4. Evaluator 评估
    5. 验证所有步骤正确
    """
    pass


def test_e2e_multi_image_flow():
    """
    端到端测试: 多图任务完整流程

    流程:
    1. 创建 3 图 AC 任务
    2. Simulator 使用 SEND_ALL_EVERY_TURN 发送图像
    3. 模型响应
    4. Evaluator 评估 (知道发送了哪些图像)
    5. 验证所有步骤正确
    """
    pass


def test_e2e_progressive_flow():
    """
    端到端测试: 渐进式任务完整流程

    流程:
    1. 创建 3 图任务
    2. Simulator 使用 PROGRESSIVE 策略
    3. Turn 1: 发送 img1
    4. Turn 2: 发送 img2
    5. Turn 3: 发送 img3
    6. 验证每个 turn 的 images_sent 正确
    """
    pass


def run_comprehensive_test(log_dir: str) -> MultiImageE2EResult:
    """运行完整测试套件"""
    result = MultiImageE2EResult()
    result.metrics = {}
    result.failure_reasons = []
    result.evidence = {
        "single_image_tests": [],
        "multi_image_tests": [],
        "progressive_tests": [],
        "e2e_tests": []
    }

    # ... 实现测试逻辑 ...

    result.overall_pass = all(
        m["pass"] for m in result.metrics.values()
    )
    result.status = "PASS" if result.overall_pass else "FAIL"

    return result
```

### 2.4 测试矩阵

```
┌─────────────────────┬─────────────────┬──────────────────┬────────────────┐
│ 任务类型            │ 图像数量        │ 策略             │ 预期行为       │
├─────────────────────┼─────────────────┼──────────────────┼────────────────┤
│ ABR single          │ 1               │ SEND_ALL         │ [1] 每 turn    │
│ AC 2-image          │ 2               │ SEND_ALL         │ [1,2] 每 turn  │
│ AC 3-image          │ 3               │ SEND_ALL         │ [1,2,3] 每turn │
│ Progressive         │ 3               │ PROGRESSIVE      │ [1],[2],[3]... │
│ Front-load          │ 3               │ FIRST_TURN       │ [1,2,3],[],[]  │
└─────────────────────┴─────────────────┴──────────────────┴────────────────┘
```

### 2.5 预期输出

```json
{
  "test_id": "3.5",
  "test_name": "Multi-Image Task End-to-End Test",
  "status": "PASS",
  "metrics": {
    "ac_task_consistency": {
      "value": 1.0,
      "threshold": 1.0,
      "pass": true,
      "detail": "All AC tasks have consistent definitions"
    },
    "images_question_alignment": {
      "value": 1.0,
      "threshold": 1.0,
      "pass": true,
      "detail": "All images_sent align with question targets"
    },
    "evaluator_image_awareness": {
      "value": 1.0,
      "threshold": 1.0,
      "pass": true,
      "detail": "Evaluator knows which images were sent in 100% cases"
    }
  },
  "overall_pass": true,
  "failure_reasons": [],
  "evidence": {
    "single_image_tasks_tested": 20,
    "multi_image_tasks_tested": 30,
    "progressive_tasks_tested": 10,
    "strategy_usage": {
      "SEND_ALL_EVERY_TURN": 45,
      "PROGRESSIVE": 10,
      "SEND_ALL_FIRST_TURN": 5,
      "ACTION_DEPENDENT": 0
    },
    "policy_consistency": {
      "strategic_simulator": "SEND_ALL_EVERY_TURN",
      "llm_user_simulator": "SEND_ALL_EVERY_TURN",
      "consistent": true
    },
    "e2e_test_results": [
      {
        "test": "single_image_flow",
        "status": "PASS",
        "turns": 5,
        "all_images_sent_correct": true
      },
      {
        "test": "multi_image_flow",
        "status": "PASS",
        "turns": 4,
        "all_images_sent_correct": true
      },
      {
        "test": "progressive_flow",
        "status": "PASS",
        "turns": 6,
        "image_reveal_sequence": [[1], [2], [3], [], [], []]
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
from enum import Enum


class ImageInjectionPolicy(str, Enum):
    """图像注入策略 (来自 Phase 2 Task 2.5)"""
    SEND_ALL_EVERY_TURN = "send_all_every_turn"
    PROGRESSIVE = "progressive"
    SEND_ALL_FIRST_TURN = "send_all_first_turn"
    ACTION_DEPENDENT = "action_dependent"


@dataclass
class ImagePolicyTestCase:
    """图像策略测试用例"""
    task_id: str
    task_type: str
    total_images: int
    policy: ImageInjectionPolicy
    expected_images_per_turn: List[List[int]]
    actual_images_per_turn: List[List[int]] = field(default_factory=list)
    passed: bool = False
    error_message: Optional[str] = None


@dataclass
class E2ETestResult:
    """端到端测试结果"""
    test_name: str
    task_id: str
    total_turns: int
    images_sent_sequence: List[List[str]]
    evaluator_received_images: List[bool]
    all_correct: bool
    error_details: Optional[str] = None
```

### 3.2 测试接口

```python
def run_test_3_5(log_dir: str, output_dir: str) -> Phase3TestResult:
    """
    运行 Task 3.5 多图任务端到端测试

    Args:
        log_dir: 运行日志目录
        output_dir: 报告输出目录

    Returns:
        Phase3TestResult
    """
    pass


def test_policy_behavior(
    policy: ImageInjectionPolicy,
    total_images: int,
    num_turns: int,
    actions: List[str]
) -> List[List[int]]:
    """
    测试特定策略的行为

    Args:
        policy: 图像注入策略
        total_images: 总图像数量
        num_turns: 总 turn 数量
        actions: 每个 turn 的 action 类型

    Returns:
        每个 turn 应该发送的图像索引列表
    """
    pass
```

---

## 四、协作要求

### 4.1 与其他任务的依赖关系

```
Task 3.5 (Multi-Image E2E)
  ├── 依赖: Phase 2 Task 2.5 修复
  ├── 弱依赖: Task 3.1 (图像发送完整性)
  │   └── 建议先通过 3.1 确保基础图像发送正常
  ├── 无强前置 Phase 3 依赖
  └── 可与 3.1, 3.2, 3.3, 3.4, 3.6 并行

与其他任务的关系:
- Task 3.1: 基础图像发送
- Task 3.5: 多图策略一致性 (本任务)
- 两者互补: 3.1 验证"能发送"，3.5 验证"正确发送"
```

### 4.2 输出文件约定

| 文件 | 路径 | 格式 |
|------|------|------|
| Task 3.5 JSON 报告 | `report/stage3/phase3_3.5_multi_image_e2e.json` | JSON |
| Task 3.5 文本报告 | `report/stage3/phase3_3.5_validation_report.txt` | TXT |
| E2E 测试详情 | `report/stage3/phase3_3.5_e2e_details.json` | JSON |

### 4.3 失败处理流程

```
如果 Task 3.5 FAIL:
1. 检查 failure_reasons 中的具体失败原因
2. 分析失败类型:
   a. AC 任务一致性失败 → 检查任务定义
   b. images_sent 对齐失败 → 检查 ImagePolicyManager
   c. Evaluator 感知失败 → 检查 context 传递
3. 返回 Phase 2 Task 2.5 进行修复
4. 重新运行 Task 3.5
5. 直到 100% PASS
```

---

## 五、执行指南

### 5.1 运行命令

```bash
# 进入项目目录
cd E:\Code\M3Bench\M3Bench_new

# 运行 Task 3.5
python -m pytest tests/phase3/test_3_5_multi_image_e2e.py -v \
    --log-dir=generated_tasks_v2 \
    --output-dir=docs/task/round3/report/stage3

# 运行特定策略测试
python -m pytest tests/phase3/test_3_5_multi_image_e2e.py::test_three_image_task_progressive -v

# 运行端到端测试
python -m pytest tests/phase3/test_3_5_multi_image_e2e.py::test_e2e_multi_image_flow -v

# 或者运行组合测试脚本
python docs/task/round3/run_phase3_group_J.py
```

### 5.2 环境要求

- Python 3.8+
- pytest
- 已完成 Phase 2 修复的代码库
- 包含多图任务的运行日志

---

## 六、成功标准总结

### Task 3.5 成功标准

- [ ] `ac_task_consistency` = 100% (AC 任务定义一致)
- [ ] `images_question_alignment` = 100% (images_sent 与 question 对齐)
- [ ] `evaluator_image_awareness` = 100% (Evaluator 知道发送了哪些图像)

### 详细检查项

- [ ] 单图任务: 每个 turn 只发送 1 张图像
- [ ] 3图任务 (SEND_ALL): 每个 turn 发送 3 张图像
- [ ] 渐进式任务: 按正确顺序逐张发送
- [ ] 两个 Simulator 使用相同策略时行为一致
- [ ] Evaluator context 包含 images_sent
- [ ] Evaluator 能检测部分图像错误
- [ ] 所有 E2E 测试通过

---

**文档作者**: Claude Code
**审核状态**: 待审核
**下一步**: 等待 Task 3.5 的实施和执行
