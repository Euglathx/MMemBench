# Phase 2 并行组 E: Tasks 2.2 & 2.3

**组别**: E (可并行执行)
**预估总时间**: 5-7小时 (并行) | 6-8小时 (串行)
**依赖**: Phase 1 Tasks 1.2, 1.3
**优先级**: P1 (高优先级)

---

## 组概述

本组包含两个可以并行执行的任务,它们分别修复Phase 1中发现的关键评估问题:

- **Task 2.2**: Turn-Level Ground Truth 设计与实现
- **Task 2.3**: 评分公式重构

这两个任务逻辑相关但可以独立实现,建议分配给不同的开发人员并行完成。

---

# Task 2.2: Turn-Level Ground Truth 设计与实现

## 任务背景

### Phase 1 发现的问题 (Task 1.3)

**严重程度**: P1 HIGH

**核心问题**: 所有 turn (100%) 使用 task-level expected_answer 进行评估,包括应该有独立子目标的中间 turns。

**统计数据**:
- 总分析 turns: 264
- 使用 task-level expected: 264 (100%)
- 应该使用 turn-level: 71 (26.9%)
- 确认误判案例: 6

**影响**:
- 违反 Information Decoupling 原则
- 无法评估中间推理步骤
- 创造错误的模型激励(鼓励提前泄露最终答案)
- 71个turns的评估结果不可靠

### 具体误判示例

**Case 1: Entity Grounding 完美答案失败**
```
Task: "找到人。找到人左边的物体。它是什么?"
Expected (task-level): "最终物体是刀"

Turn 1 (entity_grounding):
  问题: "你能定位图中的人并描述他们的位置吗?"
  模型回答: "人在右侧,面朝左。穿红色衬衫..."
  LLM Judge 正确性: 10/10 (完美)
  Expected Answer Used: "最终物体是刀" ❌
  Should Be: "模型应识别/描述人" ✓
  评估结果: FAIL (score=0.66)
```

**Case 2: Chain Navigation 正确对象失败**
```
Turn 2 (chain_navigation):
  问题: "看人的正左边。你看到什么明显的物体?"
  模型回答: "紧邻人左边是一个大的矩形蛋糕..."
  LLM Judge 正确性: 7/10
  Expected Answer Used: "最终物体是刀" ❌
  Should Be: "人左边的物体" (蛋糕, NOT 刀) ✓
  评估结果: FAIL (score=0.61)
```

## 任务需求

### 设计目标

1. **支持 turn-level expected answers**: 每个 turn 有独立的预期答案
2. **Phase-aware evaluation**: 评估器知道当前 phase 的子目标
3. **向后兼容**: 不破坏现有的 task-level evaluation
4. **可测试**: 清晰的验证标准

### 核心交付物

1. **新数据结构**: `TurnGroundTruth` 类
2. **TaskState 更新**: 添加 `turn_ground_truths` 字段
3. **Simulator 增强**: 生成 turn-level expected answers
4. **Evaluator 接口更新**: 接收 turn-level context
5. **单元测试**: 验证 turn-level evaluation

## 当前情况

### 当前架构问题

**1. TaskState 只存储 task-level expected_answer**

```python
# 当前 TaskState (strategic_simulator.py:55-79)
@dataclass
class TaskState:
    task_id: str
    task_type: str
    question: str
    expected_answer: str  # ❌ 只有 task-level
    images: List[str]
    # ... 其他字段
```

**2. Evaluator 调用总是传递 task-level expected**

```python
# strategic_simulator.py:818-827
eval_result = self.evaluator.evaluate_response(
    response=model_content,
    expected_answer=self.task_state.expected_answer,  # ❌ 总是 task-level
    action_type=action,
    question_asked=message,
    context={...}
)
```

**3. TASK_STRATEGIES 定义 phase goals 但没有 turn expectations**

```python
# action_space.py:528-684
TASK_STRATEGIES = {
    "attribute_bridge_reasoning": TaskStrategy(
        phases=[
            {
                "name": "entity_grounding",
                "goal": "Model accurately describes entity"
                # ❌ MISSING: expected_answer or sub_goal
            }
        ]
    )
}
```

### 代码位置

| 组件 | 文件 | 行号 | 问题 |
|------|------|------|------|
| Evaluator 调用 | strategic_simulator.py | 818-827 | 传递 task_state.expected_answer |
| TaskState 定义 | strategic_simulator.py | 55-79 | 无 turn_ground_truths 字段 |
| Evaluate 响应 | evaluator.py | 852-874 | expected_answer 参数是 task-level |
| Task Strategies | action_space.py | 528-684 | Phases 有 goals 但无 turn expectations |

## 实现设计

### 1. 新数据结构

#### TurnGroundTruth 类

```python
@dataclass
class TurnGroundTruth:
    """单个 turn 的 ground truth

    用于存储特定 turn 的评估标准,独立于 task-level expected answer。
    """
    turn_id: int
    phase: str  # e.g., "entity_grounding", "chain_navigation"
    action_type: str  # e.g., "guidance", "follow_up"

    # 这个 turn 测试的子目标
    sub_goal: str  # e.g., "identify_entity", "find_spatial_neighbor", "final_answer"

    # 这个 turn 的 expected answer (不是 task-level!)
    expected_answer: str

    # 可接受的替代答案
    acceptable_variations: List[str] = field(default_factory=list)

    # 应该可见的图像
    required_images: List[int] = field(default_factory=list)

    # 模型到目前为止应该学到的关键事实
    ground_truth_facts: List[Dict[str, Any]] = field(default_factory=list)

    # 可选: turn-specific evaluation hints
    evaluation_hints: Dict[str, Any] = field(default_factory=dict)
```

#### TaskState 更新

```python
@dataclass
class TaskState:
    """完整的任务执行状态"""
    task_id: str
    task_type: str
    question: str
    expected_answer: str  # 保留作为最终答案参考
    images: List[str]

    # === NEW: Turn-level ground truths ===
    turn_ground_truths: Dict[int, TurnGroundTruth] = field(default_factory=dict)
    current_turn_ground_truth: Optional[TurnGroundTruth] = None

    # Phase tracking
    current_phase: PhaseState = None
    phases_completed: List[str] = field(default_factory=list)

    # ... 其他现有字段保持不变
```

### 2. Simulator 实现

#### 生成 Turn Ground Truth

```python
class StrategicSimulator:

    def _generate_turn_ground_truth(
        self,
        phase_name: str,
        action: str,
        turn_num: int
    ) -> TurnGroundTruth:
        """为当前 turn 生成 expected answer

        根据 phase 和任务类型生成 turn-specific ground truth。
        """
        strategy = self._get_strategy(self.task_state.task_type)

        if phase_name == "entity_grounding":
            # Expected: 模型识别目标实体
            entity = self._extract_target_entity(self.task_state.question)
            return TurnGroundTruth(
                turn_id=turn_num,
                phase=phase_name,
                action_type=action,
                sub_goal="identify_entity",
                expected_answer=f"Model should identify/describe the {entity}",
                acceptable_variations=[
                    f"The {entity} is visible",
                    f"I can see the {entity}",
                    f"Located the {entity}"
                ],
                evaluation_hints={
                    "focus_on": "entity_identification",
                    "ignore_final_answer": True
                }
            )

        elif phase_name == "chain_navigation":
            # Expected: 模型找到中间对象
            relation = self._get_current_spatial_relation(turn_num)
            return TurnGroundTruth(
                turn_id=turn_num,
                phase=phase_name,
                action_type=action,
                sub_goal="spatial_relation",
                expected_answer=self._extract_intermediate_object(relation),
                acceptable_variations=[...],
                evaluation_hints={
                    "focus_on": "spatial_reasoning",
                    "check_relation": relation
                }
            )

        elif phase_name == "grounding":
            # Expected: 模型建立基础理解
            return TurnGroundTruth(
                turn_id=turn_num,
                phase=phase_name,
                action_type=action,
                sub_goal="baseline_understanding",
                expected_answer=self._extract_grounding_expectation(),
                evaluation_hints={
                    "focus_on": "visual_grounding"
                }
            )

        elif phase_name in ["final_answer", "final_evaluation"]:
            # Expected: 使用 task-level expected answer
            return TurnGroundTruth(
                turn_id=turn_num,
                phase=phase_name,
                action_type=action,
                sub_goal="final_answer",
                expected_answer=self.task_state.expected_answer,  # 使用 task-level
                evaluation_hints={
                    "is_final_answer": True
                }
            )

        else:
            # Default: 对其他 phases 使用 task-level
            return TurnGroundTruth(
                turn_id=turn_num,
                phase=phase_name,
                action_type=action,
                sub_goal="general",
                expected_answer=self.task_state.expected_answer,
                evaluation_hints={}
            )

    def _extract_target_entity(self, question: str) -> str:
        """从任务问题中提取目标实体"""
        # 简单实现: 查找常见实体词
        entities = ["person", "object", "人", "物体"]
        for entity in entities:
            if entity in question.lower():
                return entity
        return "target"

    def _extract_intermediate_object(self, relation: str) -> str:
        """提取中间对象 (不是最终答案)"""
        # 这需要解析任务的推理链
        # 简化版: 返回描述性答案
        return f"The object matching the relation '{relation}'"
```

#### 在 step() 中使用 Turn Ground Truth

```python
def step(self) -> Dict[str, Any]:
    """执行一个 turn 的模拟"""
    if not self.task_state:
        raise RuntimeError("No task started. Call start_task() first.")

    self.turn_count += 1
    phase = self.task_state.current_phase

    # 1. 决定 action
    action, message, core_parsed = self._call_core_model_for_action()

    # === NEW: 生成 turn-level ground truth ===
    turn_ground_truth = self._generate_turn_ground_truth(
        phase_name=phase.phase_name,
        action=action,
        turn_num=self.turn_count
    )
    self.task_state.turn_ground_truths[self.turn_count] = turn_ground_truth
    self.task_state.current_turn_ground_truth = turn_ground_truth

    # 2-5. 图像、消息、模型调用 (保持不变)
    images_to_send = self._get_images_for_turn(action)
    # ...

    # 6. 评估响应 - 使用 turn-level expected answer
    eval_result = self.evaluator.evaluate_response(
        response=model_content,
        expected_answer=turn_ground_truth.expected_answer,  # ✓ Turn-level!
        action_type=action,
        question_asked=message,
        context={
            "previous_responses": [c["claim"] for c in self.task_state.model_claims[-5:]],
            "phase": phase.phase_name,
            # === NEW: Turn-level context ===
            "sub_goal": turn_ground_truth.sub_goal,
            "turn_ground_truth": turn_ground_truth,
            "evaluation_hints": turn_ground_truth.evaluation_hints
        }
    )

    # ... 其余逻辑保持不变
```

### 3. Evaluator 更新

```python
class Evaluator:

    def evaluate_response(
        self,
        response: str,
        expected_answer: str,  # 现在是 turn-level!
        action_type: str,
        question_asked: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        task: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """评估响应 - 现在支持 turn-level context"""

        # === NEW: 提取 turn-level context ===
        sub_goal = context.get("sub_goal", "unknown") if context else "unknown"
        turn_ground_truth = context.get("turn_ground_truth") if context else None
        evaluation_hints = context.get("evaluation_hints", {}) if context else {}

        # === NEW: Phase-aware evaluation ===
        if sub_goal == "identify_entity":
            # Entity grounding: 关注实体识别,不关注最终答案
            return self._evaluate_entity_identification(
                response, expected_answer, evaluation_hints
            )

        elif sub_goal == "spatial_relation":
            # Chain navigation: 关注空间关系,不关注最终对象
            return self._evaluate_spatial_reasoning(
                response, expected_answer, evaluation_hints
            )

        elif sub_goal == "final_answer":
            # Final answer: 使用完整评估
            return self._evaluate_final_answer(
                response, expected_answer, evaluation_hints
            )

        else:
            # Default: 标准评估
            return self._evaluate_standard(
                response, expected_answer, action_type, question_asked, context
            )

    def _evaluate_entity_identification(
        self,
        response: str,
        expected_answer: str,
        hints: Dict[str, Any]
    ) -> EvaluationResult:
        """评估实体识别 turn"""

        # 重点: 模型是否识别和描述了实体
        # 不关心: 模型是否提到最终答案

        prompt = f"""
        Question type: Entity Identification
        Expected: {expected_answer}
        Model response: {response}

        Evaluate ONLY:
        1. Did the model identify the target entity?
        2. Did the model provide a description of its location?

        DO NOT penalize if the model doesn't mention the final answer.

        Score 0-10 for entity identification accuracy.
        """

        # 调用 LLM Judge
        llm_result = self._call_llm_judge(prompt)

        # 构建评估结果
        return EvaluationResult(
            score=llm_result.get("correctness", 0.5),
            level_passed=llm_result.get("correctness", 0.5) >= 0.7,
            # ... 其他字段
        )
```

## 期望输出

### 1. 代码文件

#### 新增文件
- **无需新文件**: 所有更改在现有文件中

#### 修改文件
1. **src/simulator/strategic_simulator.py**
   - 添加 `TurnGroundTruth` dataclass
   - 更新 `TaskState` dataclass
   - 添加 `_generate_turn_ground_truth()` 方法
   - 更新 `step()` 方法使用 turn-level expected

2. **src/simulator/evaluator.py**
   - 更新 `evaluate_response()` 处理 turn-level context
   - 添加 phase-aware evaluation 方法:
     - `_evaluate_entity_identification()`
     - `_evaluate_spatial_reasoning()`
     - `_evaluate_final_answer()`

3. **src/simulator/action_space.py** (可选)
   - 为 TASK_STRATEGIES 添加 turn expectation generators

### 2. 单元测试

**tests/test_turn_ground_truth.py**

```python
class TestTurnGroundTruth(unittest.TestCase):
    """测试 turn-level ground truth 功能"""

    def test_entity_grounding_turn(self):
        """测试 entity grounding turn 应该通过"""
        task = {
            "question": "Find person. Find object left of person.",
            "expected_answer": "The knife"
        }

        simulator = StrategicSimulator()
        simulator.start_task(task)

        # Turn 1: Entity grounding
        turn_gt = simulator._generate_turn_ground_truth(
            "entity_grounding", "guidance", 1
        )

        # 模型识别人但未提到刀
        response = "The person is on the right side"
        eval_result = simulator.evaluator.evaluate_response(
            response=response,
            expected_answer=turn_gt.expected_answer,
            action_type="guidance",
            context={"sub_goal": "identify_entity"}
        )

        # 应该通过 (识别了实体)
        self.assertTrue(eval_result.level_passed)
        self.assertGreater(eval_result.score, 0.7)

    def test_chain_navigation_intermediate_object(self):
        """测试 chain navigation 识别中间对象应该通过"""
        # ... 类似测试

    def test_final_answer_requires_final_object(self):
        """测试 final answer turn 需要最终答案"""
        # ...
```

### 3. 验证报告

**docs/task/round3/report/stage2/PHASE2_TASK2.2_TURN_GROUND_TRUTH_REPORT.md**

包含:
- 实现摘要
- 代码变更详情
- 测试结果 (71+ affected turns 验证)
- Before/After 对比
- 误判案例修复验证

## 接口定义

### 输入接口

```python
# TaskState 接口 (strategic_simulator.py)
@dataclass
class TaskState:
    # 现有字段保持不变
    task_id: str
    expected_answer: str  # Task-level (保留)

    # 新增字段
    turn_ground_truths: Dict[int, TurnGroundTruth]
    current_turn_ground_truth: Optional[TurnGroundTruth]
```

### 输出接口

```python
# Evaluator.evaluate_response() 接口
def evaluate_response(
    self,
    response: str,
    expected_answer: str,  # 现在可以是 turn-level
    action_type: str,
    question_asked: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,  # 包含 turn-level hints
    task: Optional[Dict[str, Any]] = None
) -> EvaluationResult
```

### 内部接口

```python
# TurnGroundTruth 生成接口
def _generate_turn_ground_truth(
    self,
    phase_name: str,
    action: str,
    turn_num: int
) -> TurnGroundTruth
```

## 协作要求

### 与 Task 2.3 的并行协作

| 方面 | Task 2.2 | Task 2.3 | 协作点 |
|------|---------|---------|--------|
| **修改文件** | strategic_simulator.py, evaluator.py | evaluator.py | evaluator.py 需要协调 |
| **接口影响** | `evaluate_response()` context | `evaluate_response()` 评分逻辑 | 确保 context 字段一致 |
| **测试数据** | 71+ affected turns | 10+ anomaly cases | 可共享测试 log |
| **完成顺序** | 可同时开始 | 可同时开始 | 最后合并 evaluator 变更 |

**建议协作流程**:
1. **Day 1**: 各自实现自己的功能
2. **Day 2**: 协调 evaluator.py 的合并
3. **Day 3**: 联合测试和验证

### 依赖的 Phase 1 报告

- **Task 1.3 报告**: [PHASE1_TASK1.3_EXPECTED_ANSWER_REPORT.md](../report/PHASE1_TASK1.3_EXPECTED_ANSWER_REPORT.md)
  - 71个受影响的 turns 列表
  - 6个误判案例详情
  - Expected answer 来源统计

### 与其他任务的依赖

- **无前置依赖**: 可以立即开始
- **后续任务**: Task 2.6 (Evaluator State Management) 可能使用 turn-level context

## 验证标准

### 成功标准

- [ ] `TurnGroundTruth` 类实现且有文档
- [ ] `TaskState` 包含 `turn_ground_truths` 字段
- [ ] `_generate_turn_ground_truth()` 为所有 phases 实现
- [ ] `evaluate_response()` 接收并使用 turn-level context
- [ ] 单元测试覆盖 3+ sub_goal 类型
- [ ] 71+ affected turns 的评估结果改善
- [ ] 6个误判案例修复验证通过
- [ ] 完整的技术报告生成

### 测试用例

**Test Case 1: Entity Grounding 完美答案应该通过**
```python
turn = {"phase": "entity_grounding", "sub_goal": "identify_entity"}
response = "The person is on the right side, wearing red"
expected_turn = "Model should identify the person"
# 应该: level_passed = True, score >= 0.7
```

**Test Case 2: Chain Navigation 中间对象应该通过**
```python
turn = {"phase": "chain_navigation", "sub_goal": "spatial_relation"}
response = "Immediately left is a cake"
expected_turn = "The object left of person" (cake, not knife)
# 应该: level_passed = True (即使不提到最终对象 knife)
```

**Test Case 3: Final Answer 需要最终答案**
```python
turn = {"phase": "final_answer", "sub_goal": "final_answer"}
response = "The person is on the right"  # 只提到实体
expected_turn = "The knife"  # task-level expected
# 应该: level_passed = False (未给出最终答案)
```

---

# Task 2.3: 评分公式重构

## 任务背景

### Phase 1 发现的问题 (Task 1.2)

**严重程度**: P0 CRITICAL (when anomaly rate > 20%)

**核心问题**: LLM Judge 给出满分 (10/10) 但最终 score < 0.7,导致 `level_passed = false`。

**统计数据** (模拟数据):
- 异常 cases: 10+
- 异常率: 2.0% (当前样本)
- 问题: Hard scores 的低默认值 (0.1-0.3) 污染最终分数

**具体异常示例**:

| Task ID | Turn | LLM Judge | Final Score | Passed | Discrepancy |
|---------|------|-----------|-------------|--------|-------------|
| abr_example_001 | 1 | 10/10 (全满分) | 0.664 | ❌ | -3.5% |
| ac_mscoco_001 | 3 | 9-10/10 | 0.680 | ❌ | -1.9% |
| task_003 | 1 | 8-10/10 | 0.680 | ❌ | -4.8% |

### 根因

**代码位置**: [evaluator.py:907-914](../../src/simulator/evaluator.py#L907-L914)

```python
# 当前实现 (有问题):
if llm_scores:
    w = self.llm_judge_weight  # w = 0.6
    final_scores = {
        k: w * llm_scores[k] + (1 - w) * hard_scores[k]
        for k in hard_scores
    }
```

**问题**:
1. `llm_scores['correctness'] = 10/10 = 1.0` (LLM Judge 满分)
2. `hard_scores['correctness'] = 0.1` (默认值,从未被更新!)
3. `final_scores['correctness'] = 0.6 * 1.0 + 0.4 * 0.1 = 0.64` (远低于期望的 1.0)

**Hard Scores 默认值**:
```python
# evaluator.py:663-671
scores = {
    "correctness": 0.1,     # 假设 90% 错误
    "faithfulness": 0.2,    # 假设 80% 幻觉
    "robustness": 0.3,
    "consistency": 0.3,
    "memory_retention": 0.3
}
```

这些是"惩罚性默认值",假设模型失败。即使 LLM Judge 给满分,这些低值仍参与计算。

## 任务需求

### 修复目标

1. **LLM Judge 满分时应该接近满分**: 10/10 → final score ≈ 1.0
2. **Hard scores 不应污染 LLM scores**: 当 LLM Judge 可用时,应以其为主
3. **保持 fallback 机制**: LLM Judge 不可用时仍可工作
4. **详细的评分日志**: 可追踪每个维度的计算过程

### 核心交付物

1. **调整 hard_scores 默认值** 或 **修改权重逻辑**
2. **添加评分计算日志**
3. **单元测试**: 验证 LLM Judge 满分 → final score ≈ 1.0
4. **回归测试**: 确保现有功能不受影响

## 当前情况

### 当前评分流程

```
LLM Judge Output (0-10)
    ↓ normalize (÷10)
LLM Scores (0-1)
    ↓
    ↓ weighted_average(llm_scores, hard_scores, w=0.6)
    ↓
Final Scores per dimension
    ↓ weighted_sum(dimension_weights)
    ↓
Overall Score (0-1)
    ↓ compare(threshold=0.7)
    ↓
Level Passed (boolean)
```

**问题所在**: `weighted_average` 步骤中,hard_scores 默认值污染结果。

### 代码位置

| 组件 | 文件 | 行号 | 当前值/逻辑 |
|------|------|------|------------|
| Hard scores 默认值 | evaluator.py | 663-671 | 0.1-0.3 (惩罚性) |
| LLM Judge 权重 | evaluator.py | 初始化 | 0.6 (60%) |
| 权重混合逻辑 | evaluator.py | 907-914 | `w*llm + (1-w)*hard` |
| Overall score 计算 | evaluator.py | 928-936 | 维度加权求和 |

## 实现设计

### 方案对比

| 方案 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **方案1: 调整默认值** | 简单,向后兼容 | 仍有混合污染 | ✓ 推荐 (短期) |
| **方案2: Hard scores 作为 fallback** | LLM Judge 权重100% | 破坏现有逻辑 | ⚠️ 需要测试 |
| **方案3: 提高 LLM weight** | 简单调整 | 默认值仍有影响 | ✓ 可选 (补充) |

**推荐组合**: **方案1 + 方案3** (调整默认值 + 提高权重)

### 方案1: 调整 Hard Scores 默认值 (推荐)

#### 实现

```python
# evaluator.py:663-671
# OLD (惩罚性默认):
scores = {
    "correctness": 0.1,
    "faithfulness": 0.2,
    "robustness": 0.3,
    "consistency": 0.3,
    "memory_retention": 0.3
}

# NEW (中性默认):
scores = {
    "correctness": 0.5,      # 中性 (50% 正确率假设)
    "faithfulness": 0.5,     # 中性
    "robustness": 0.5,       # 中性
    "consistency": 0.5,      # 中性
    "memory_retention": 0.5  # 中性
}
```

#### 效果

**Before**:
```
LLM Judge: 10/10 → llm_score = 1.0
Hard score: 0.1
Final = 0.6 * 1.0 + 0.4 * 0.1 = 0.64 ❌
```

**After**:
```
LLM Judge: 10/10 → llm_score = 1.0
Hard score: 0.5
Final = 0.6 * 1.0 + 0.4 * 0.5 = 0.80 ✓ (better!)
```

### 方案3: 提高 LLM Judge 权重 (补充)

#### 实现

```python
# evaluator.py 初始化
class Evaluator:
    def __init__(self, ...):
        # OLD:
        self.llm_judge_weight = 0.6

        # NEW:
        self.llm_judge_weight = 0.8  # 或 1.0 (完全依赖 LLM Judge)
```

#### 效果 (llm_weight = 0.8)

```
LLM Judge: 10/10 → llm_score = 1.0
Hard score: 0.5
Final = 0.8 * 1.0 + 0.2 * 0.5 = 0.90 ✓ (excellent!)
```

### 添加详细日志

```python
def _compute_final_scores(
    self,
    hard_scores: Dict[str, float],
    llm_scores: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """计算最终分数 - 添加详细日志"""

    if llm_scores:
        w = self.llm_judge_weight
        final_scores = {}

        logger.info(f"[Score Calculation] LLM Judge weight: {w}")
        logger.info(f"[Score Calculation] Hard scores: {hard_scores}")
        logger.info(f"[Score Calculation] LLM scores: {llm_scores}")

        for dim in hard_scores:
            hard = hard_scores[dim]
            llm = llm_scores.get(dim, hard)
            final = w * llm + (1 - w) * hard

            final_scores[dim] = final

            logger.debug(
                f"[Score Calculation] {dim}: "
                f"hard={hard:.3f}, llm={llm:.3f}, "
                f"final = {w}*{llm:.3f} + {1-w}*{hard:.3f} = {final:.3f}"
            )

        logger.info(f"[Score Calculation] Final scores: {final_scores}")
        return final_scores

    else:
        logger.warning("[Score Calculation] LLM Judge unavailable, using hard scores only")
        return hard_scores
```

## 期望输出

### 1. 代码文件

#### 修改文件
1. **src/simulator/evaluator.py**
   - 修改 `hard_rule_evaluation()` 中的默认值 (663-671行)
   - 修改 `__init__()` 中的 `llm_judge_weight` (可选)
   - 添加 `_compute_final_scores()` 的详细日志
   - 添加分数计算过程的 DEBUG 日志

### 2. 单元测试

**tests/test_score_calculation.py**

```python
class TestScoreCalculation(unittest.TestCase):
    """测试评分计算逻辑"""

    def test_llm_judge_perfect_score(self):
        """LLM Judge 满分应该得到高 final score"""
        evaluator = Evaluator(llm_judge_weight=0.8)

        # 模拟 LLM Judge 满分
        llm_scores = {
            "correctness": 1.0,
            "faithfulness": 1.0,
            "robustness": 1.0,
            "consistency": 1.0,
            "memory_retention": 1.0
        }

        hard_scores = {
            "correctness": 0.5,
            "faithfulness": 0.5,
            "robustness": 0.5,
            "consistency": 0.5,
            "memory_retention": 0.5
        }

        final_scores = evaluator._compute_final_scores(hard_scores, llm_scores)

        # 验证
        self.assertGreaterEqual(final_scores["correctness"], 0.80)
        self.assertGreaterEqual(final_scores["faithfulness"], 0.80)

    def test_llm_judge_unavailable_uses_hard_scores(self):
        """LLM Judge 不可用时应该使用 hard scores"""
        evaluator = Evaluator()

        hard_scores = {"correctness": 0.5}
        final_scores = evaluator._compute_final_scores(hard_scores, llm_scores=None)

        self.assertEqual(final_scores["correctness"], 0.5)

    def test_hard_scores_neutral_default(self):
        """Hard scores 应该使用中性默认值"""
        evaluator = Evaluator()

        # 调用 hard_rule_evaluation
        response = "Test response"
        expected = "Test expected"
        hard_scores = evaluator.hard_rule_evaluation(response, expected, {})

        # 验证默认值是中性的 (0.5)
        self.assertEqual(hard_scores.get("correctness", 0), 0.5)
```

### 3. 回归测试

**tests/test_evaluator_regression.py**

```python
class TestEvaluatorRegression(unittest.TestCase):
    """确保修复不破坏现有功能"""

    def test_low_llm_score_still_fails(self):
        """LLM Judge 低分仍应该失败"""
        # ...

    def test_medium_scores_still_work(self):
        """中等分数的行为保持一致"""
        # ...
```

### 4. 验证报告

**docs/task/round3/report/stage2/PHASE2_TASK2.3_SCORE_FORMULA_REPORT.md**

包含:
- 修复摘要
- Before/After 对比
- 10+ anomaly cases 重新评估结果
- 评分日志示例
- 回归测试结果

## 接口定义

### 内部接口 (无变化)

```python
# Evaluator 评分接口保持不变
def evaluate_response(
    self,
    response: str,
    expected_answer: str,
    action_type: str,
    question_asked: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    task: Optional[Dict[str, Any]] = None
) -> EvaluationResult
```

### 配置接口 (新增可选)

```python
# 可配置的评分参数
class Evaluator:
    def __init__(
        self,
        mode: EvaluationMode = EvaluationMode.STRESS_TEST,
        llm_judge_weight: float = 0.8,  # NEW: 可配置 (默认 0.8)
        hard_score_defaults: Optional[Dict[str, float]] = None,  # NEW: 可配置默认值
        verbose: bool = False
    ):
        # ...
        self.llm_judge_weight = llm_judge_weight

        if hard_score_defaults:
            self.hard_score_defaults = hard_score_defaults
        else:
            self.hard_score_defaults = {
                "correctness": 0.5,
                "faithfulness": 0.5,
                "robustness": 0.5,
                "consistency": 0.5,
                "memory_retention": 0.5
            }
```

## 协作要求

### 与 Task 2.2 的并行协作

| 方面 | Task 2.2 | Task 2.3 | 协作策略 |
|------|---------|---------|---------|
| **修改文件** | evaluator.py (evaluate_response) | evaluator.py (分数计算) | 分工明确,各自分支 |
| **代码区域** | Line 852-900+ | Line 663-671, 907-936 | 不重叠,易合并 |
| **测试** | Turn-level evaluation 测试 | Score calculation 测试 | 独立测试文件 |
| **合并策略** | Task 2.2 先合并 | Task 2.3 后合并,基于 2.2 | 或同时合并 |

**推荐流程**:
1. Day 1: 各自在独立分支开发
2. Day 2: Task 2.2 先合并到 main (评估逻辑优先)
3. Day 2: Task 2.3 rebase 到最新 main 并合并

### 依赖的 Phase 1 报告

- **Task 1.2 报告**: [phase1_1.2_score_calculation.json](../report/phase1_1.2_score_calculation.json)
  - 10+ anomaly cases 列表
  - 权重配置分析
  - 根因详细说明

### 与其他任务的依赖

- **无前置依赖**: 可立即开始
- **后续影响**: Task 2.6 可能依赖改进后的评分逻辑

## 验证标准

### 成功标准

- [ ] Hard scores 默认值更新为 0.5
- [ ] LLM Judge weight 调整 (0.8 或保持 0.6)
- [ ] 详细评分日志添加完成
- [ ] 10+ anomaly cases 重新评估通过
- [ ] LLM Judge 10/10 → final score >= 0.80
- [ ] 回归测试全部通过
- [ ] 完整的技术报告生成

### 测试用例

**Test Case 1: LLM Judge 满分**
```python
llm_scores = {"correctness": 1.0, "faithfulness": 1.0, ...}
hard_scores = {"correctness": 0.5, "faithfulness": 0.5, ...}
# 期望: final_scores["correctness"] >= 0.80
```

**Test Case 2: LLM Judge 低分**
```python
llm_scores = {"correctness": 0.2}
hard_scores = {"correctness": 0.5}
# 期望: final_scores["correctness"] ≈ 0.32 (仍然低)
```

**Test Case 3: LLM Judge 不可用**
```python
llm_scores = None
hard_scores = {"correctness": 0.5}
# 期望: final_scores["correctness"] = 0.5 (fallback)
```

---

## 总结: 并行组 E 执行计划

### 时间线 (并行执行)

**Day 1 (各自开发)**:
- Task 2.2: 实现 TurnGroundTruth, 更新 TaskState, 生成逻辑
- Task 2.3: 调整默认值, 添加日志, 单元测试

**Day 2 (协调合并)**:
- 上午: Task 2.2 完成并合并到 main
- 下午: Task 2.3 rebase 并合并

**Day 3 (联合验证)**:
- 上午: 运行 71+ affected turns 验证 Task 2.2
- 下午: 运行 10+ anomaly cases 验证 Task 2.3
- 晚上: 生成报告

### 最终交付物检查清单

**Task 2.2**:
- [ ] TurnGroundTruth 类实现
- [ ] TaskState 更新
- [ ] _generate_turn_ground_truth() 方法
- [ ] evaluate_response() 支持 turn-level
- [ ] 单元测试 (3+ cases)
- [ ] 71+ turns 验证通过
- [ ] 技术报告

**Task 2.3**:
- [ ] Hard scores 默认值更新
- [ ] LLM Judge weight 调整
- [ ] 评分日志添加
- [ ] 单元测试 (3+ cases)
- [ ] 10+ anomaly cases 重新评估
- [ ] 回归测试通过
- [ ] 技术报告

---

**文档创建时间**: 2026-02-03
**预计完成时间**: 5-7小时 (并行) | 6-8小时 (串行)
**优先级**: P1 (Task 2.2), P0 (Task 2.3)
