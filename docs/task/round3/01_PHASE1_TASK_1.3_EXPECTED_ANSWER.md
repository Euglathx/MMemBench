# Phase 1 Task 1.3: Expected Answer追踪验证

## 任务目标

验证评审意见中的**P1级问题**：每个turn是否使用了正确的turn-level expected_answer。

## 问题描述（来自评审意见1.2）

评审意见指出：
- **ABR Turn 2的问题是**: "看person左边紧挨着是什么"，模型回答"cake"
- **评语承认**: "按'immediately'这个词，cake是对的"
- **但评估说**: "expected answer是knife（更左边）"
- **最终**: `level_passed = false`

这说明：
- Evaluator在用**task-level expected_answer**（最终答案是knife）
- 而不是用**turn-level expected_answer**（这个turn应该回答cake）
- 这会破坏Information Decoupling设计原则

## 验证目标

1. **追踪expected_answer的来源**: 每个turn的expected_answer是从哪里来的？
2. **验证turn-level vs task-level**: 是否所有turn都在用task_start的expected_answer？
3. **检测误判cases**: 找出"模型答对但被判错"的情况
4. **评估影响范围**: 有多少turn受此问题影响？

## 验证脚本设计

### 脚本名称
`debug_expected_answer_tracking.py`

### 验证步骤

#### Step 1: Expected Answer来源追踪
```python
# 对于每个turn的evaluation:
# 1. 读取task_start的expected_answer
# 2. 读取turn的evaluation中使用的expected_answer
# 3. 对比两者是否相同
# 4. 检查是否应该使用不同的expected_answer

# 重点关注:
# - Phase = "entity_grounding" / "chain_navigation"的turn
# - 这些turn应该有独立的子目标
```

**成功标准**:
- 明确每个turn使用的expected_answer来源
- 统计有多少turn使用了task-level answer

#### Step 2: 子目标vs最终目标对比
```python
# 分析任务策略（TASK_STRATEGIES）:
# - 对于ABR任务，每个phase的目标是什么？
# - Phase 1 (entity_grounding): 找到person → expected: "person"
# - Phase 2 (chain_navigation): 找person左边 → expected: "cake" (or "knife"?)
# - Phase 3 (final_answer): 最终答案 → expected: "knife"

# 检查simulator/evaluator是否维护了turn-level expected_answer
```

**成功标准**:
- 清楚列出每个phase应该有的子目标
- 指出当前实现是否支持turn-level expected_answer

#### Step 3: 误判Cases分析
```python
# 找出"模型答对但被判错"的cases:
# 1. 读取turn的question
# 2. 读取model response
# 3. 人工/LLM判断response是否合理
# 4. 对比actual evaluation结果
# 5. 找出不一致的cases
```

**成功标准**:
- 找到至少5个明确的误判cases
- 每个case都有清晰的evidence

#### Step 4: 代码架构检查
```python
# 检查以下代码:
# 1. StrategicSimulator._generate_question()
#    - 是否为每个turn设置了turn_expected_answer?
# 2. Evaluator.evaluate_response()
#    - 使用的expected_answer参数从哪来?
# 3. TaskState数据结构
#    - 是否有turn-level ground truth字段?
```

**成功标准**:
- 明确指出代码是否支持turn-level expected_answer
- 找到需要修改的具体位置

### 输出格式

```json
{
  "validation_id": "1.3_expected_answer_tracking",
  "timestamp": "2026-02-03T...",
  "status": "FAIL" | "PASS",
  "expected_answer_sources": {
    "total_turns": 800,
    "using_task_level": 750,
    "using_turn_level": 50,
    "task_level_percentage": 93.75
  },
  "misjudged_cases": [
    {
      "task_id": "abr_example_001",
      "turn": 2,
      "phase": "chain_navigation",
      "question": "What is immediately to the left of the person?",
      "model_response": "A cake",
      "expected_answer_used": "knife",
      "should_be": "cake",
      "evaluation_result": "FAIL (score=0.4)",
      "should_be_result": "PASS",
      "evidence": "Question asks for 'immediately left', cake is correct"
    }
  ],
  "code_analysis": {
    "supports_turn_level_expected": false,
    "TaskState_has_turn_ground_truth": false,
    "evaluator_uses": "task-level expected_answer",
    "simulator_generates_turn_expected": false
  },
  "root_cause": {
    "primary_issue": "No turn-level expected_answer mechanism",
    "code_location": "evaluator.py:evaluate_response(), uses task.expected_answer for all turns",
    "design_gap": "TASK_STRATEGIES defines phases but not turn-level ground truth"
  },
  "severity": "P1_HIGH",
  "recommended_fix": "Implement TurnGroundTruth data structure and update evaluation flow"
}
```

### 诊断输出

```
=== Expected Answer Tracking Validation Report ===

Status: FAIL ❌

Problem Summary:
- 93.75% of turns use task-level expected_answer
- This includes intermediate turns that should have sub-goals
- Result: Models are penalized for not revealing final answer early

Evidence of Misjudgment:
Case 1: abr_example_001, Turn 2
  Question: "What is immediately to the left of the person?"
  Model: "A cake"
  Expected (used): "knife" (task-level final answer)
  Should be: "cake" (turn-level correct answer)
  Evaluation: FAIL ❌
  Correct evaluation: PASS ✓
  Impact: Model is correct but marked wrong

Case 2: abr_example_005, Turn 1
  Question: "Locate the person in the image"
  Model: "There is a person in the center"
  Expected (used): "The final object is a knife"
  Should be: "person" or entity description
  Evaluation: FAIL ❌
  Correct evaluation: PASS ✓

Why This Is Serious:
1. Violates Information Decoupling principle
   - Models are expected to reveal final answer in turn 1
   - Creates "hindsight bias"
2. Encourages wrong behavior
   - Model that says "I see a person and a knife" passes
   - Model that focuses on asked entity fails
3. Makes evaluation meaningless
   - Can't test step-by-step reasoning
   - Can't isolate error sources

Code Analysis:
```python
# Current (WRONG):
def evaluate_response(self, response, expected_answer, ...):
    # expected_answer is always task.expected_answer
    hard_scores = self._hard_rule_evaluation(
        response, expected_answer, action_type
    )

# Evaluator receives:
evaluator.evaluate_response(
    response=model_response,
    expected_answer=self.task_state.expected_answer,  # ❌ Task-level
    ...
)
```

What's Missing:
1. TaskState does not track turn-level ground truth
2. Simulator does not generate turn-level expected answers
3. Evaluator has no concept of "sub-goal"
4. TASK_STRATEGIES defines phases but not per-turn expectations

Recommended Architecture:
```python
@dataclass
class TurnGroundTruth:
    turn_id: int
    phase: str
    sub_goal: str  # e.g., "identify_entity", "spatial_relation"
    expected_answer: str  # Turn-specific answer
    acceptable_variations: List[str]

@dataclass
class TaskState:
    ...
    turn_ground_truths: Dict[int, TurnGroundTruth]  # NEW
    current_turn_ground_truth: TurnGroundTruth  # NEW
```

Impact on Design Goals:
❌ Information Decoupling: Broken
❌ Step-by-step evaluation: Impossible
❌ Error source isolation: Unreliable
✓ Final answer check: Still works

Severity: P1 HIGH
This is a fundamental architecture gap, not just a bug.
```

## 变量和接口定义

### 输入
- `log_dir`: Run logs目录
- `strategy_config`: action_space.py路径（用于理解phase定义）

### 输出
- `validation_report.json`: 机器可读报告
- `validation_report.txt`: 人类可读详细报告
- `misjudged_cases.csv`: 所有误判cases

### 接口

```python
class ExpectedAnswerTracker:
    """追踪expected_answer使用情况"""

    def __init__(self, log_dir: str, strategy_path: str):
        pass

    def trace_expected_answer_source(self) -> Dict:
        """追踪每个turn的expected_answer来源"""
        pass

    def analyze_sub_goals(self) -> Dict:
        """分析任务策略中的子目标定义"""
        pass

    def find_misjudged_cases(self) -> List[Dict]:
        """找出误判cases"""
        pass

    def check_code_architecture(self) -> Dict:
        """检查代码是否支持turn-level expected_answer"""
        pass

    def generate_report(self) -> Tuple[Dict, str]:
        pass
```

## 协作要求

### 与其他任务的依赖
- **独立任务**: 不依赖其他Phase 1任务
- **可并行**: 可以与Task 1.4并行（组B）
- **被依赖**: Task 2.2（Turn-level Ground Truth设计）需要这个

### 与Phase 2的接口
- 必须明确列出需要turn-level expected_answer的phase
- 必须提供设计gap的清晰描述
- 必须给出数据结构建议

### 数据共享
- 验证报告: `round3/results/phase1_1.3_expected_answer.json`
- 误判cases: `round3/results/phase1_1.3_misjudged_cases.csv`

## 成功标准

- [ ] 统计覆盖至少200个turns
- [ ] 找到至少5个明确的误判cases
- [ ] 清楚指出代码架构gap
- [ ] 提供TurnGroundTruth数据结构建议
- [ ] 报告有充分证据支持

## 时间估算

- 脚本开发: 2小时
- 日志分析: 1小时
- 代码检查: 1小时
- 报告撰写: 1小时
- **总计: 约5小时**

---

**并行组**: B (可以与Task 1.4并行)
**优先级**: P1 (高优先级)
**预估难度**: Hard (需要理解任务策略和phase设计)
