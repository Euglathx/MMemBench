# Phase 2 Window 1: 评估框架重构（Turn Purpose vs Expected Answer）

**任务编号**: ROUND4-P2-W1
**预计时间**: 4-6 小时
**依赖**: Phase 1 Window 2 完成
**优先级**: P0 - CRITICAL - 最高优先级
**可并行**: 可与 Window 2, 3, 4 并行（代码模块独立）

---

## 任务目标

重新设计评估框架，解决 Round 3 Task 2.2 的**概念框架错误**。

**核心问题**（用户反馈）:
> "对于很多 turn 来说不一定有 expected answer。我们至少要让 simulator 的 core model 知道，它现在在做什么。可以通过修改名字，从 expected answer 变成 **task_ground_truth**，然后让它明白很多动作（turn）只是为了增加可靠性。"

**本质**:
- 中间 turn 不应该有 "expected answer" 来判断对错
- 应该有 "turn_purpose" 来判断是否完成了该 turn 的功能
- 很多 turn 是**可靠性检查**，不是"答对某个答案"

---

## 背景信息

### Round 3 Task 2.2 的问题

**Round 3 做了什么**:
- 实现了 `TurnGroundTruth` 数据类
- 为每个 turn 生成 turn-level `expected_answer`

**为什么还是失败**:
- **概念框架错了**：不是每个 turn 都需要"正确答案"
- Evaluator 仍然在用 "correctness" 维度判断中间 turn
- LLM Judge prompt 仍然在比较"模型回答"和"task ground truth"

### 用户期望的正确框架

**Task-level**:
- `task_ground_truth`: 整个任务的最终真值（例如："The final object is a knife"）
- 用于 final_answer turn 的评估

**Turn-level**:
- `turn_purpose`: 这个 turn 的目的（例如："entity_grounding", "spatial_reasoning"）
- `is_reliability_check`: 是否是可靠性检查 turn（true/false）
- `evaluation_focus`: 评估重点（例如：["entity_identification", "visual_grounding"]）
- **不包括** "final_answer_match" 这样的 focus

**LLM Judge 需要知道**:
- 这个 turn 是在做什么
- 不要按最终答案扣分（对于 reliability check turns）
- 重点评估能力，不是正确性

---

## 任务详细要求

### 第一步：数据结构重构

#### 1.1 新增 TurnEvaluationContext 数据类

**文件**: `src/simulator/strategic_simulator.py`

**位置**: 在现有 `TurnGroundTruth` 附近添加

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class TurnEvaluationContext:
    """
    Turn 评估上下文（概念框架修正）

    这个数据类明确区分：
    - Task-level ground truth（整个任务的最终答案）
    - Turn-level purpose（这个 turn 的目的）

    关键原则：
    - 中间 turn 不是为了"答对"，而是为了展示能力或增加可靠性
    - 评估应该基于 purpose，不是基于 expected answer
    """
    turn_id: int
    phase: str  # "entity_grounding", "chain_navigation", "final_answer", etc.

    # Turn 目的（不是"期望答案"）
    turn_purpose: str  # "entity_grounding", "spatial_reasoning", "reliability_check", "final_answer"
    is_reliability_check: bool = False  # True 表示这个 turn 只是为了验证一致性

    # Task-level ground truth（供参考，不直接用于中间 turn 的正误判断）
    task_ground_truth: str = ""  # 重命名自 expected_answer，强调这是 task 层面的

    # Turn-level 评估重点（不是"expected answer"）
    evaluation_focus: List[str] = field(default_factory=list)
    # 可能的值：["entity_identification", "spatial_awareness", "visual_grounding",
    #           "consistency", "visual_evidence"]
    # 不包括 "final_answer_match"

    # 评估提示
    evaluation_hints: Dict[str, Any] = field(default_factory=dict)
    # 例如：{"ignore_final_answer": True, "focus_on_capability": True}

    # 可选：这个 turn 如果有 expected sub-goal answer，也可以记录
    turn_target: Optional[str] = None  # 例如："Model should identify the person location"
    acceptable_variations: List[str] = field(default_factory=list)
```

#### 1.2 更新 TaskState（如果需要）

**文件**: `src/simulator/strategic_simulator.py`

**检查**: TaskState 是否已有 `current_turn_ground_truth` 字段

如果没有，添加：
```python
@dataclass
class TaskState:
    # ... 现有字段 ...

    # NEW: Turn evaluation context
    current_turn_evaluation_context: Optional[TurnEvaluationContext] = None
    turn_evaluation_contexts: Dict[int, TurnEvaluationContext] = field(default_factory=dict)
```

---

### 第二步：LLM Judge Prompt 重构

#### 2.1 新增 prompt 生成方法

**文件**: `src/simulator/evaluator.py`

**位置**: 在 `_call_llm_judge()` 方法附近

```python
def _build_llm_judge_prompt_v2(
    self,
    response: str,
    question: str,
    turn_context: TurnEvaluationContext,
    images_info: Dict[str, Any]
) -> str:
    """
    根据 turn purpose 动态生成 LLM Judge prompt

    Args:
        response: 模型响应
        question: 提问内容
        turn_context: Turn 评估上下文
        images_info: 图像信息

    Returns:
        为 LLM Judge 定制的 prompt
    """
    if turn_context.is_reliability_check:
        # 可靠性检查 turn：重点是一致性和能力展示，不是正确性
        prompt = f"""
You are evaluating a model's response during a RELIABILITY CHECK turn.

**Turn Information**:
- Turn ID: {turn_context.turn_id}
- Phase: {turn_context.phase}
- Purpose: {turn_context.turn_purpose}

**Evaluation Focus**: {', '.join(turn_context.evaluation_focus)}

**IMPORTANT INSTRUCTIONS**:
1. This turn is NOT asking for the final answer to the task.
2. Do NOT judge correctness against the task ground truth.
3. Focus ONLY on: {', '.join(turn_context.evaluation_focus)}

**Question Asked**:
{question}

**Model Response**:
{response}

**Task Ground Truth (for reference ONLY, do NOT use for scoring)**:
{turn_context.task_ground_truth}

Note: The model should NOT reveal this final answer in the current turn.
If the model mentions the final answer, it's PREMATURE, not encouraged.

**Evaluation Criteria**:

1. **Capability Demonstration** (Weight: HIGH):
   - Did the model demonstrate the required capability?
   - For entity_grounding: Can it identify/locate entities?
   - For spatial_reasoning: Can it understand spatial relations?

2. **Visual Grounding** (Weight: HIGH):
   - Is the response based on visual evidence from the image(s)?
   - Are specific visual details mentioned?

3. **Consistency** (Weight: MEDIUM):
   - Is the response consistent with previous turns (if any)?

4. **Avoiding Premature Answer** (Weight: LOW):
   - Did the model avoid revealing the final task answer?
   - This is a BONUS criterion, not a penalty.

**Output Format**:
{{
  "capability_demonstration": <score 0-10>,
  "visual_grounding": <score 0-10>,
  "consistency": <score 0-10>,
  "avoiding_premature_answer": <score 0-10>,
  "reasoning": "<brief explanation>"
}}
"""
    else:
        # 最终答案 turn：这时才比较 task ground truth
        prompt = f"""
You are evaluating the FINAL ANSWER turn.

**Question**: {question}
**Model Response**: {response}
**Expected Answer**: {turn_context.task_ground_truth}

**Evaluation Criteria**:

1. **Correctness** (Weight: HIGHEST):
   - Does the response match the expected answer?
   - Consider semantic equivalence, not just exact wording.

2. **Visual Evidence**:
   - Is the answer grounded in visual observation?

3. **Clarity**:
   - Is the answer clear and unambiguous?

**Output Format**:
{{
  "correctness": <score 0-10>,
  "visual_evidence": <score 0-10>,
  "clarity": <score 0-10>,
  "reasoning": "<explanation>"
}}
"""

    return prompt
```

#### 2.2 更新 _call_llm_judge() 方法

**文件**: `src/simulator/evaluator.py`

**修改**: 添加对 `turn_evaluation_context` 的支持

```python
def _call_llm_judge(
    self,
    response: str,
    expected_answer: str,  # 保留向后兼容
    action_type: str,
    question_asked: str,
    context: Dict[str, Any]
) -> Optional[Dict[str, float]]:
    """
    调用 LLM Judge 进行评分

    NEW: 支持 turn_evaluation_context
    """
    # 检查是否有新的 turn evaluation context
    turn_ctx = context.get("turn_evaluation_context")

    if turn_ctx:
        # 使用新的 prompt 生成逻辑
        prompt = self._build_llm_judge_prompt_v2(
            response=response,
            question=question_asked,
            turn_context=turn_ctx,
            images_info=context.get("images_info", {})
        )
    else:
        # Fallback to old prompt logic
        logger.warning(
            "[Evaluator] No turn_evaluation_context found, using legacy evaluation. "
            "This is expected for tasks before Round 4 fixes."
        )
        prompt = self._build_legacy_llm_judge_prompt(...)  # 旧逻辑

    # 调用 LLM
    llm_response = self.llm_client.generate(prompt)

    # 解析并返回 scores
    return self._parse_llm_judge_response(llm_response, turn_ctx)
```

---

### 第三步：Evaluator 评分策略调整

#### 3.1 动态调整维度权重

**文件**: `src/simulator/evaluator.py`

**修改**: `evaluate_response()` 方法

```python
def evaluate_response(
    self,
    response: str,
    expected_answer: str,
    action_type: str,
    question_asked: str,
    context: Dict[str, Any]
) -> EvaluationResult:
    """
    评估模型响应

    NEW: 根据 turn_evaluation_context 调整评估策略
    """
    # 提取 turn evaluation context
    turn_ctx = context.get("turn_evaluation_context")

    # 调用 LLM Judge（使用新 prompt）
    llm_scores = self._call_llm_judge(
        response=response,
        expected_answer=expected_answer,
        action_type=action_type,
        question_asked=question_asked,
        context=context
    )

    # 根据 turn purpose 调整维度权重
    if turn_ctx and turn_ctx.is_reliability_check:
        # 可靠性检查 turn：降低 correctness 权重
        dimension_weights = {
            "correctness": 0.1,      # 不重要
            "faithfulness": 0.3,     # 视觉基础很重要
            "consistency": 0.3,      # 一致性很重要
            "robustness": 0.2,       # 抵抗误导
            "capability": 0.1        # 能力展示
        }
        logger.info(
            f"[Evaluator] Turn {turn_ctx.turn_id} is a RELIABILITY CHECK. "
            f"Using adjusted weights: correctness=0.1 (low), "
            f"faithfulness=0.3, consistency=0.3"
        )
    else:
        # 最终答案 turn：correctness 是重点
        dimension_weights = {
            "correctness": 0.5,      # 最重要
            "faithfulness": 0.2,
            "consistency": 0.15,
            "robustness": 0.15
        }
        logger.info(
            f"[Evaluator] Turn {turn_ctx.turn_id if turn_ctx else '?'} is FINAL ANSWER. "
            f"Using standard weights: correctness=0.5 (high)"
        )

    # 计算最终分数
    final_scores = self._combine_scores(llm_scores, hard_scores, dimension_weights)

    # 返回结果
    return EvaluationResult(
        scores=final_scores,
        turn_evaluation_context=turn_ctx,  # 记录到结果中
        ...
    )
```

---

### 第四步：Simulator 集成

#### 4.1 生成 TurnEvaluationContext

**文件**: `src/simulator/strategic_simulator.py`

**新增或修改方法**: `_generate_turn_evaluation_context()`

```python
def _generate_turn_evaluation_context(
    self,
    turn_num: int,
    phase_name: str,
    action: str
) -> TurnEvaluationContext:
    """
    为当前 turn 生成评估上下文

    根据 phase 和 action，确定：
    - turn_purpose
    - is_reliability_check
    - evaluation_focus
    """
    # 获取 task ground truth
    task_ground_truth = self.task_state.expected_answer

    # 根据 phase 确定 turn purpose
    if phase_name in ["entity_grounding", "grounding"]:
        return TurnEvaluationContext(
            turn_id=turn_num,
            phase=phase_name,
            turn_purpose="entity_grounding",
            is_reliability_check=True,  # 这是可靠性检查
            task_ground_truth=task_ground_truth,
            evaluation_focus=["entity_identification", "visual_grounding"],
            evaluation_hints={"ignore_final_answer": True, "focus_on_capability": True},
            turn_target=f"Model should identify and locate entities in the image"
        )

    elif phase_name == "chain_navigation":
        return TurnEvaluationContext(
            turn_id=turn_num,
            phase=phase_name,
            turn_purpose="spatial_reasoning",
            is_reliability_check=True,  # 这是可靠性检查
            task_ground_truth=task_ground_truth,
            evaluation_focus=["spatial_awareness", "intermediate_reasoning"],
            evaluation_hints={"ignore_final_answer": True},
            turn_target=f"Model should navigate spatial relations step by step"
        )

    elif phase_name in ["final_answer", "final_evaluation"]:
        return TurnEvaluationContext(
            turn_id=turn_num,
            phase=phase_name,
            turn_purpose="final_answer",
            is_reliability_check=False,  # 这不是可靠性检查
            task_ground_truth=task_ground_truth,
            evaluation_focus=["final_answer_correctness", "reasoning_completeness"],
            evaluation_hints={},
            turn_target=task_ground_truth  # 这里才用 task ground truth
        )

    else:
        # 默认：假设是可靠性检查
        logger.warning(f"[Simulator] Unknown phase {phase_name}, treating as reliability check")
        return TurnEvaluationContext(
            turn_id=turn_num,
            phase=phase_name,
            turn_purpose="unknown",
            is_reliability_check=True,
            task_ground_truth=task_ground_truth,
            evaluation_focus=["general_capability"],
            evaluation_hints={"ignore_final_answer": True}
        )
```

#### 4.2 在 step() 方法中调用

**文件**: `src/simulator/strategic_simulator.py`

**位置**: `step()` 方法中，调用 evaluator 之前

```python
def step(self):
    # ... 现有逻辑 ...

    # 生成 turn evaluation context
    turn_eval_ctx = self._generate_turn_evaluation_context(
        turn_num=self.turn_count,
        phase_name=phase.phase_name,
        action=action
    )

    # 保存到 task state
    self.task_state.current_turn_evaluation_context = turn_eval_ctx
    self.task_state.turn_evaluation_contexts[self.turn_count] = turn_eval_ctx

    logger.info(
        f"[Simulator] Turn {self.turn_count}: purpose={turn_eval_ctx.turn_purpose}, "
        f"is_reliability_check={turn_eval_ctx.is_reliability_check}, "
        f"evaluation_focus={turn_eval_ctx.evaluation_focus}"
    )

    # 调用 evaluator（传递 turn_evaluation_context）
    eval_result = self.evaluator.evaluate_response(
        response=model_content,
        expected_answer=self.task_state.expected_answer,  # 保留向后兼容
        action_type=action,
        question_asked=message,
        context={
            "turn_evaluation_context": turn_eval_ctx,  # NEW
            "images_sent": images_to_send,
            "turn_id": self.turn_count,
            # ... 其他 context ...
        }
    )

    # ... 现有逻辑 ...
```

---

## 接口定义

### 输入
- Phase 1 的验证报告（确认 Task 2.2 失败）
- 当前代码库

### 输出

#### 核心代码文件
1. `src/simulator/strategic_simulator.py` - 添加 `TurnEvaluationContext`，修改 `_generate_turn_evaluation_context()` 和 `step()`
2. `src/simulator/evaluator.py` - 添加 `_build_llm_judge_prompt_v2()`，修改 `_call_llm_judge()` 和 `evaluate_response()`

#### 文档
- `docs/task/round4/phase2_fix2.0_report.md` - 修复报告

---

## 协作要求

### 与其他 Window 的关系

**独立性**: 高度独立
- 修改的代码模块与其他修复（2.1, 2.2, 2.3, 2.4）不冲突

**可能的冲突点**:
- `evaluator.py`: 如果 Window 3 也在修改 evaluator，需要协调
- 建议：先完成此任务，其他 window 基于此修改

---

## 当前进度

- [ ] 设计 `TurnEvaluationContext` 数据类
- [ ] 实现 `_generate_turn_evaluation_context()` 方法
- [ ] 实现 `_build_llm_judge_prompt_v2()` 方法
- [ ] 修改 `_call_llm_judge()` 方法
- [ ] 修改 `evaluate_response()` 方法（动态权重）
- [ ] 集成到 `step()` 方法
- [ ] 添加日志输出
- [ ] 单元测试
- [ ] 集成测试（运行 1 个任务验证）
- [ ] 生成修复报告
- [ ] 完成

---

## 验证标准

### Must Have
1. ✅ `TurnEvaluationContext` 数据类正确定义
2. ✅ LLM Judge prompt 明确区分 reliability check 和 final answer
3. ✅ 运行测试任务，检查 run log 中：
   - Turn 1 的 `is_reliability_check = true`
   - LLM Judge prompt 包含"RELIABILITY CHECK"字样
   - Correctness 权重降低到 0.1
4. ✅ 向后兼容：旧任务（没有 turn_evaluation_context）仍能运行

### Nice to Have
1. 单元测试覆盖率 > 80%
2. 详细的代码注释
3. 示例 run log 对比（修复前 vs 修复后）

---

## 测试方法

### 单元测试

**文件**: `tests/test_turn_evaluation_context.py`

```python
def test_turn_evaluation_context_creation():
    """测试 TurnEvaluationContext 创建"""
    ctx = TurnEvaluationContext(
        turn_id=1,
        phase="entity_grounding",
        turn_purpose="entity_grounding",
        is_reliability_check=True,
        task_ground_truth="The final object is a knife",
        evaluation_focus=["entity_identification"],
        evaluation_hints={"ignore_final_answer": True}
    )
    assert ctx.is_reliability_check == True
    assert "entity_identification" in ctx.evaluation_focus

def test_llm_judge_prompt_reliability_check():
    """测试 LLM Judge prompt 生成（reliability check）"""
    evaluator = Evaluator()
    ctx = TurnEvaluationContext(
        turn_id=1,
        phase="entity_grounding",
        turn_purpose="entity_grounding",
        is_reliability_check=True,
        task_ground_truth="The final object is a knife",
        evaluation_focus=["entity_identification"]
    )

    prompt = evaluator._build_llm_judge_prompt_v2(
        response="The person is on the right side",
        question="Can you locate the person?",
        turn_context=ctx,
        images_info={}
    )

    # 验证 prompt 内容
    assert "RELIABILITY CHECK" in prompt
    assert "Do NOT judge correctness against the task ground truth" in prompt
    assert "entity_identification" in prompt
```

### 集成测试

运行 1 个完整任务，检查 run log：

```bash
python scripts/round4_test_fix2.0.py
```

检查输出的 run log 中：
- Turn 1: `is_reliability_check = true` ✓
- Turn 1: `evaluation_focus = ["entity_identification"]` ✓
- Turn 1 evaluation: `dimension_weights.correctness = 0.1` ✓

---

## 交付物清单

- [ ] 修改后的 `src/simulator/strategic_simulator.py`
- [ ] 修改后的 `src/simulator/evaluator.py`
- [ ] 单元测试文件 `tests/test_turn_evaluation_context.py`
- [ ] 集成测试脚本 `scripts/round4_test_fix2.0.py`
- [ ] 修复报告 `docs/task/round4/phase2_fix2.0_report.md`
- [ ] 示例 run log（修复后）

---

## 注意事项

1. **向后兼容**: 旧代码/旧任务应该仍能运行（fallback 到 legacy logic）
2. **日志详细**: 每个关键步骤都要有 logger.info()
3. **用户反馈对齐**: 确保实现符合用户的"task_ground_truth" vs "turn_purpose"概念

---

**任务开始时间**: _____________
**任务完成时间**: _____________
**执行人**: _____________
