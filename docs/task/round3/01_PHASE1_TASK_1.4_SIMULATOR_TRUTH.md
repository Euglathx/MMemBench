# Phase 1 Task 1.4: Simulator提示词真值校验检查

## 任务目标

验证评审意见中的**P1级问题**：Simulator是否将模型输出当成事实写入下一轮提示。

## 问题描述（来自评审意见2.1和2.2）

评审意见指出：
- **ABR Turn 3**: 模型被判错（"右边没有物体"）
- **ABR Turn 4**: Simulator却说 "You correctly noted that ... is holding a knife"
- **AC Turn 2**: 模型"完全hallucinate了另一张图"
- **AC Turn 3**: 提问却说 "You've identified 3 people in the first image"

这说明：
- **Simulator将模型的错误输出当成"已确认事实"**
- 造成"错误自我强化"
- 污染"回马枪验证"机制

## 验证目标

1. **检测"伪确认"模式**: Simulator是否在说"You correctly..."而模型其实错了
2. **追踪truth propagation**: 模型的错误声明如何传播到后续turn
3. **验证真值校验机制**: Simulator是否有基于ground truth校验模型输出的逻辑
4. **量化污染影响**: 有多少turn被错误的"事实"污染

## 验证脚本设计

### 脚本名称
`debug_simulator_truth_validation.py`

### 验证步骤

#### Step 1: "伪确认"模式检测
```python
# 对于每个turn:
# 1. 读取turn N的evaluation结果
#    - 如果score < 0.5 或 level_passed=false → 模型答错
# 2. 读取turn N+1的simulator message
#    - 检查是否包含肯定词: "correctly", "you noted", "you identified", "you mentioned"
# 3. 如果出现"模型答错 + 下一轮被肯定" → 标记为伪确认

# 肯定词列表:
confirmation_phrases = [
    "you correctly", "you've correctly", "you identified",
    "you mentioned", "you noted", "as you said",
    "you've established", "you confirmed", "correct"
]
```

**成功标准**:
- 找出所有"模型错误+被肯定"的case pairs
- 统计发生率

#### Step 2: 真值传播追踪
```python
# 追踪"错误事实"如何在对话中传播:
# Turn 1: Model说 "There are 3 people"
# Turn 2: Sim说 "You identified 3 people, now..."
# Turn 3: Sim说 "Given the 3 people you saw..."

# 对于每个model claim:
# 1. 判断是否正确（对比ground truth）
# 2. 追踪后续turn的message中是否引用这个claim
# 3. 标记错误propagation链
```

**成功标准**:
- 构建错误传播图（哪些claim被传播了多少次）
- 量化污染深度（错误claim影响了多少轮）

#### Step 3: 真值校验机制检查
```python
# 检查simulator代码:
# 1. StrategicSimulator._generate_question()
#    - 生成下一轮message时是否校验上一轮response?
# 2. TaskState.model_claims
#    - 是否记录模型的claims?
#    - 是否与ground_truths对比?
# 3. Memory injection机制
#    - injected_falsehoods是否被追踪?
#    - 是否检测模型是否接受了falsehood?
```

**成功标准**:
- 明确指出代码中是否有真值校验逻辑
- 找到缺失的校验点

#### Step 4: "回马枪验证"污染分析
```python
# 检查consistency_check (回马枪):
# 1. 读取final turn的consistency check
# 2. 检查问题是否基于模型自己之前的回答
# 3. 对比ground truth

# 例如:
# Turn 1-5: Model一直错误地说"有3个人"
# Consistency check: "你之前说有3个人，确认一下"
# 正确做法: "图里到底有多少人？"（基于ground truth，不是模型声明）
```

**成功标准**:
- 明确consistency check是否被污染
- 给出正确的回马枪设计

### 输出格式

```json
{
  "validation_id": "1.4_simulator_truth_validation",
  "timestamp": "2026-02-03T...",
  "status": "FAIL" | "PASS",
  "false_confirmation_cases": [
    {
      "task_id": "abr_example_001",
      "turn_n": 3,
      "turn_n_evaluation": {"score": 0.3, "level_passed": false},
      "turn_n_plus_1_message": "You correctly noted that the knife is on the right...",
      "confirmation_phrase": "correctly noted",
      "severity": "HIGH"
    }
  ],
  "statistics": {
    "total_turn_pairs": 700,
    "false_confirmation_count": 85,
    "false_confirmation_rate": 12.14
  },
  "error_propagation": {
    "total_false_claims": 120,
    "propagated_claims": 90,
    "propagation_rate": 75.0,
    "max_propagation_depth": 5,
    "average_depth": 2.3
  },
  "code_analysis": {
    "has_truth_validation": false,
    "model_claims_tracked": true,
    "claims_validated_against_ground_truth": false,
    "consistency_check_polluted": true
  },
  "root_cause": {
    "primary_issue": "Simulator trusts model output without ground truth validation",
    "code_location": "strategic_simulator.py:_generate_question(), no validation step",
    "missing_mechanism": "Ground truth comparison before incorporating model claims"
  },
  "severity": "P1_HIGH",
  "recommended_fix": "Add truth validation layer between model response and next turn generation"
}
```

### 诊断输出

```
=== Simulator Truth Validation Report ===

Status: FAIL ❌

Problem Summary:
- 12.14% of turn pairs show false confirmation
- 75% of model's false claims are propagated to later turns
- Consistency check is polluted by model's own errors

Evidence of False Confirmation:
Case 1: abr_example_001, Turns 3→4
  Turn 3 evaluation: FAIL (score=0.3)
  Turn 3 model said: "The knife is on the right"
  Turn 4 simulator says: "You correctly noted that... is holding a knife"
  Problem: Simulator affirmed an incorrect statement

Case 2: ac_mscoco_001, Turns 2→3
  Turn 2 evaluation: FAIL (cross-image confusion)
  Turn 2 model said: "3 people in first image, 2 in second"
  Turn 3 simulator says: "You've identified 3 people..."
  Problem: Simulator treated hallucination as fact

Error Propagation Analysis:
- 90 false claims were propagated (out of 120 total)
- Average propagation depth: 2.3 turns
- Worst case: A false claim propagated for 5 turns
- Impact: Later evaluations are based on polluted context

Example Propagation Chain:
Turn 1: Model says "There are 3 people" (WRONG, actually 2)
Turn 2: Sim says "You identified 3 people, now count cars"
Turn 3: Sim says "Given the 3 people you saw, which car is closest?"
Turn 4: Sim says "You mentioned 3 people and 2 cars..."
Turn 5: Consistency check: "You said 3 people, confirm?"
        (Should ask: "How many people are there?" based on ground truth)

Code Analysis:
```python
# Current (WRONG):
def _generate_question(self, action: str) -> str:
    # Uses model's previous response directly
    prev_response = self.turn_count > 0 and conversation_history[-1]
    # No validation against ground truth!

    prompt = f"User previously said: {prev_response}. Generate next question..."

# What's Missing:
def _validate_model_claims(self, response: str) -> Dict:
    """Validate model's claims against ground truth"""
    claims = self._extract_claims(response)
    validated = {
        claim: self._check_against_ground_truth(claim)
        for claim in claims
    }
    return validated
```

Impact on Design Goals:
❌ Error self-reinforcement: Happening
❌ "回马枪" validation: Polluted
❌ Information decoupling: Broken (simulator leaks model's misconceptions)
✓ Multi-turn testing: Still works mechanically

Why This Is Serious:
1. Creates feedback loop of errors
2. Makes it impossible to test "recovery from error"
3. Pollutes the very mechanism (consistency check) meant to catch errors
4. Violates the "independent evaluator" design principle

Recommended Architecture:
```python
@dataclass
class ModelClaim:
    turn: int
    claim: str
    is_correct: bool  # Validated against ground truth
    propagated_to_turns: List[int]

class StrategicSimulator:
    def _generate_question(self, action: str) -> str:
        # NEW: Validate before using
        if self.task_state.model_claims:
            validated_claims = self._validate_claims()
            # Only use correct claims in context
            # OR explicitly test model's error recovery
```

Severity: P1 HIGH
This creates systematic bias in evaluation results.
```

## 变量和接口定义

### 输入
- `log_dir`: Run logs目录
- `simulator_code_path`: strategic_simulator.py路径

### 输出
- `validation_report.json`
- `validation_report.txt`
- `false_confirmation_cases.csv`
- `error_propagation_graph.json`

### 接口

```python
class SimulatorTruthValidator:
    """验证simulator的真值校验机制"""

    def __init__(self, log_dir: str, simulator_path: str):
        pass

    def detect_false_confirmations(self) -> List[Dict]:
        """检测伪确认cases"""
        pass

    def trace_error_propagation(self) -> Dict:
        """追踪错误传播"""
        pass

    def check_truth_validation_mechanism(self) -> Dict:
        """检查代码中的真值校验逻辑"""
        pass

    def analyze_consistency_check_pollution(self) -> Dict:
        """分析回马枪是否被污染"""
        pass

    def generate_report(self) -> Tuple[Dict, str]:
        pass
```

## 协作要求

### 依赖
- **可并行**: 与Task 1.3并行（组B）
- **被依赖**: Task 2.4（Simulator真值校验机制）需要这个

### 数据共享
- 报告: `round3/results/phase1_1.4_simulator_truth.json`
- Cases: `round3/results/phase1_1.4_false_confirmations.csv`

## 成功标准

- [ ] 找到至少10个伪确认cases
- [ ] 构建错误传播图
- [ ] 明确指出代码缺失的校验逻辑
- [ ] 分析consistency check污染情况
- [ ] 提供修复建议

## 时间估算

- 脚本开发: 2小时
- 日志分析: 1小时
- 代码检查: 1小时
- 报告撰写: 1小时
- **总计: 约5小时**

---

**并行组**: B (与Task 1.3并行)
**优先级**: P1
**预估难度**: Medium-Hard
