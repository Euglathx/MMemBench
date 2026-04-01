# Phase 2 并行组 F: Tasks 2.4 & 2.5

**组别**: F (可并行执行)
**预估总时间**: 5-6小时 (并行) | 7-9小时 (串行)
**依赖**: Phase 1 Tasks 1.4, 1.5
**优先级**: P1 (高优先级)

---

## 组概述

本组包含两个可以并行执行的任务,都专注于 Simulator 模块的修复:

- **Task 2.4**: Simulator 真值校验机制
- **Task 2.5**: 多图策略统一

这两个任务修改不同的 Simulator 功能模块,可以完全独立开发并行执行。

---

# Task 2.4: Simulator 真值校验机制

## 任��背景

### Phase 1 发现的问题 (Task 1.4)

**严重程度**: P1 HIGH (结构性风险)

**核心问题**: Simulator 将模型的错误输出当作事实存储和传播,没有任何真值校验机制。

**统计数据**:
- 虚假确认案例: 0 (当前样本 0%)
- 错误传播率: 28.57% (2/7 false claims)
- 最大传播深度: 3 turns
- **代码分析**: ❌ 无任何验证机制

**影响**:
- 模型错误会通过对话上下文自我强化
- "回马枪"一致性检查可能验证模型自己的错误而非真值
- 无法测试模型的错误恢复能力
- 评估器失去客观性

### 错误传播示例

**错误链 1: ac_mscoco_2**
```
Turn 5 (模型错误):
"I apologize, but as a text-based AI, I cannot 'look closely' at images..."
评估: Score 0.2/5 - 模型错误地声称是纯文本AI

Turn 6 (Simulator):
消息引用了关于看不到图像的先前声明...
→ 传播深度: +1

Turn 7, 8:
错误声明持续存在于对话历史中
→ 传播深度: +2, +3
```

**影响**: 错误存活了3轮,污染了所有后续交互。

### 代码架构缺陷

**位置 1: 无条件内存存储** ([strategic_simulator.py:835-841](../../src/simulator/strategic_simulator.py#L835-L841))
```python
# 8. Store in memory
self.memory.add_turn(
    action=action,
    user_message=message,
    model_response=model_content,  # ← 无论正确与否都存储
    evaluation=eval_result.to_dict(),
    key_info=[f"Turn {self.turn_count}: {action}"]
)
```

**位置 2: 无过滤的历史检索** ([memory_store.py:176-190](../../src/simulator/memory_store.py#L176-L190))
```python
def get_conversation_history(self, n_turns: Optional[int] = None) -> List[Dict[str, str]]:
    history = []
    for turn in turns:
        history.append({"role": "user", "content": turn.user_message})
        history.append({"role": "assistant", "content": turn.model_response})  # ← 无过滤
    return history
```

**位置 3: Claims 跟踪但不验证** ([strategic_simulator.py:810-815](../../src/simulator/strategic_simulator.py#L810-L815))
```python
# 6. Track model claims
self.task_state.model_claims.append({
    "turn": self.turn_count,
    "claim": model_content,
    "action_context": action
    # ← Missing: "is_correct": self._validate_claim(model_content)
})
```

## 任务需求

### 修复目标

1. **添加真值验证层**: 将模型 claims 与 ground truth 对比
2. **标记错误 claims**: 区分 validated_claims vs unvalidated_claims
3. **过滤对话历史**: 可选地从上下文中排除错误 turns
4. **修复一致性检查**: 基于 ground truth 而非模型声明

### 核心交付物

1. **`_validate_model_claims()` 方法**: 验证模型声明的真实性
2. **`is_correct` 标记**: 为 model_claims 添加验证标记
3. **历史过滤**: `get_conversation_history(filter_incorrect=True)`
4. **一致性检查修复**: 基于 ground truth 生成问题
5. **单元测试**: 验证错误检测和过滤功能

## 当前情况

### 缺失的机制

| 机制 | 当前状态 | 需要添加 |
|------|---------|---------|
| Model claims 跟踪 | ✓ 存在 | - |
| Ground truth 存储 | ✓ 存在 | - |
| **Claim 验证** | ❌ **缺失** | ✓ 添加 _validate_model_claims() |
| **内存过滤** | ❌ **缺失** | ✓ 添加 filter_incorrect 参数 |
| **一致性检查 grounding** | ❌ **缺失** | ✓ 基于 ground truth |

### 当前流程 (有问题)

```
Model Response (可能错误)
    ↓
Evaluation (评分)
    ↓
Memory Storage (存储所有内容)  ← 无过滤
    ↓
Conversation History (包含错误)  ← 无过滤
    ↓
Context for Next Turn (被污染)
    ↓
Simulator 引用模型声明 (错误传播)
```

### 期望流程 (修复后)

```
Model Response
    ↓
Evaluation (评分)
    ↓
Claim Validation (验证真实性)  ← NEW!
    ↓
Memory Storage (带 is_correct 标记)  ← NEW!
    ↓
Filtered History (可选排除错误)  ← NEW!
    ↓
Clean Context for Next Turn
    ↓
Simulator 仅引用验证过的声明  ← NEW!
```

## 实现设计

### 1. Claim 验证层

#### `_validate_model_claims()` 方法

```python
class StrategicSimulator:

    def _validate_model_claims(
        self,
        response: str,
        turn_number: int,
        evaluation: EvaluationResult
    ) -> Dict[str, Any]:
        """验证模型声明与 ground truth 的对齐

        Args:
            response: 模型的响应
            turn_number: Turn 编号
            evaluation: 评估结果

        Returns:
            {
                "claims": List[Dict],  # 提取的声明及验证状态
                "has_false_claims": bool,
                "validation_summary": str
            }
        """
        # 1. 提取可验证的声明
        claims = self._extract_factual_claims(response)

        validated_claims = []
        false_claim_count = 0

        # 2. 对每个声明进行验证
        for claim in claims:
            is_correct = self._check_claim_against_ground_truth(
                claim=claim,
                ground_truths=self.task_state.ground_truths,
                expected_answer=self.task_state.expected_answer,
                evaluation_score=evaluation.score
            )

            validated_claims.append({
                "claim": claim,
                "is_correct": is_correct,
                "turn": turn_number,
                "confidence": "high" if evaluation.score > 0.7 else "low"
            })

            if not is_correct:
                false_claim_count += 1

        return {
            "claims": validated_claims,
            "has_false_claims": false_claim_count > 0,
            "false_claim_count": false_claim_count,
            "validation_summary": f"{len(validated_claims) - false_claim_count}/{len(validated_claims)} claims validated"
        }

    def _extract_factual_claims(self, response: str) -> List[str]:
        """从响应中提取可验证的事实性声明

        简化实现: 按句子分割并过滤
        完整实现: 使用 NLP 或 LLM 提取声明
        """
        # 简单实现: 按句子分割
        sentences = re.split(r'[.!?]+', response)
        claims = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # 跳过太短的
                continue

            # 过滤掉非事实性语句
            non_factual_patterns = [
                r'^I think',
                r'^I believe',
                r'^Maybe',
                r'^Perhaps',
                r'^It seems',
                r'^I apologize'
            ]

            is_non_factual = any(
                re.match(pattern, sentence, re.IGNORECASE)
                for pattern in non_factual_patterns
            )

            if not is_non_factual:
                claims.append(sentence)

        return claims

    def _check_claim_against_ground_truth(
        self,
        claim: str,
        ground_truths: Dict[str, Any],
        expected_answer: str,
        evaluation_score: float
    ) -> bool:
        """检查声明是否与 ground truth 对齐

        策略:
        1. 如果评估分数高 (>0.7), 假设正确
        2. 如果评估分数低 (<0.4), 假设错误
        3. 中等分数: 使用 LLM 进行语义比较
        """
        # Strategy 1: Use evaluation score as proxy
        if evaluation_score >= 0.7:
            return True  # High score → likely correct

        if evaluation_score < 0.4:
            return False  # Low score → likely incorrect

        # Strategy 2: Semantic comparison (optional, for medium scores)
        # 可以使用 LLM Judge 进行更精细的验证
        # 这里简化为基于分数的判断
        return evaluation_score >= 0.5
```

#### 更新 `step()` 使用验证

```python
def step(self) -> Dict[str, Any]:
    """执行一个 turn 的模拟 - 添加 claim 验证"""

    # ... 前面的代码保持不变 ...

    # 7. 评估响应
    eval_result = self.evaluator.evaluate_response(...)

    # === NEW: 验证模型声明 ===
    claim_validation = self._validate_model_claims(
        response=model_content,
        turn_number=self.turn_count,
        evaluation=eval_result
    )

    if self.verbose and claim_validation["has_false_claims"]:
        print(f"[Claim Validation] ⚠️  {claim_validation['false_claim_count']} false claims detected")
        print(f"[Claim Validation] {claim_validation['validation_summary']}")

    # 6. Track model claims - 添加验证信息
    self.task_state.model_claims.append({
        "turn": self.turn_count,
        "claim": model_content,
        "action_context": action,
        # === NEW: Validation info ===
        "is_correct": not claim_validation["has_false_claims"],
        "validation": claim_validation,
        "evaluation_score": eval_result.score
    })

    # 8. Store in memory - 传递验证信息
    self.memory.add_turn(
        action=action,
        user_message=message,
        model_response=model_content,
        evaluation=eval_result.to_dict(),
        key_info=[f"Turn {self.turn_count}: {action}"],
        # === NEW: Validation flag ===
        is_correct=not claim_validation["has_false_claims"],
        claim_validation=claim_validation
    )

    # ... 后面的代码保持不变 ...
```

### 2. 内存过滤

#### 更新 MemoryStore

```python
# memory_store.py
class MemoryStore:

    def get_conversation_history(
        self,
        n_turns: Optional[int] = None,
        filter_incorrect: bool = False,  # NEW
        score_threshold: float = 0.5  # NEW
    ) -> List[Dict[str, str]]:
        """获取对话历史 - 支持过滤错误 turns

        Args:
            n_turns: 返回最近 N 个 turns
            filter_incorrect: 是否过滤错误的 turns
            score_threshold: 过滤阈值 (低于此分数的 turns 被排除)

        Returns:
            对话历史消息列表
        """
        if self.current_task is None:
            return []

        turns = self.current_task.turns
        if n_turns:
            turns = turns[-n_turns:]

        history = []
        filtered_count = 0

        for turn in turns:
            # === NEW: 过滤逻辑 ===
            if filter_incorrect:
                # 检查评估分数
                eval_score = turn.evaluation.get("score", 1.0)

                # 或检查 is_correct 标记 (如果存在)
                is_correct = getattr(turn, 'is_correct', None)
                if is_correct is not None:
                    should_include = is_correct
                else:
                    should_include = eval_score >= score_threshold

                if not should_include:
                    filtered_count += 1
                    if hasattr(self, 'verbose') and self.verbose:
                        logger.debug(f"[Memory Filter] Skipping turn {turn.turn_id} (score={eval_score:.2f})")
                    continue

            # 添加到历史
            history.append({"role": "user", "content": turn.user_message})
            history.append({"role": "assistant", "content": turn.model_response})

        if filter_incorrect and filtered_count > 0:
            logger.info(f"[Memory Filter] Filtered out {filtered_count} incorrect turns")

        return history
```

#### 更新 Turn 数据类

```python
# memory_store.py
@dataclass
class Turn:
    """单个对话 turn"""
    turn_id: int
    action: str
    user_message: str
    model_response: str
    evaluation: Dict[str, Any]
    key_info: List[str] = field(default_factory=list)
    timestamp: str = ""

    # === NEW: Validation fields ===
    is_correct: Optional[bool] = None  # 验证标记
    claim_validation: Optional[Dict[str, Any]] = None  # 详细验证结果
```

#### 在 Simulator 中使用过滤

```python
class StrategicSimulator:

    def __init__(
        self,
        # ... 其他参数 ...
        filter_incorrect_turns: bool = True,  # NEW: 是否过滤错误 turns
        error_filter_threshold: float = 0.5  # NEW: 过滤阈值
    ):
        # ...
        self.filter_incorrect_turns = filter_incorrect_turns
        self.error_filter_threshold = error_filter_threshold

    def step(self) -> Dict[str, Any]:
        # ...

        # 4. Build conversation for target model
        target_messages = self.memory.get_conversation_history(
            filter_incorrect=self.filter_incorrect_turns,  # NEW
            score_threshold=self.error_filter_threshold  # NEW
        )
        target_messages.append({"role": "user", "content": message})

        # ...
```

### 3. 一致性检查修复

#### 当前问题

```python
# CURRENT (WRONG) - 引用模型声明:
def run_consistency_check(self):
    prev_claim = self.task_state.model_claims[-1]["claim"]
    message = f"You mentioned {prev_claim}. Can you confirm?"
    # ← 如果 prev_claim 是错误的,这会强化错误!
```

#### 修复实现

```python
def run_consistency_check(self) -> Dict[str, Any]:
    """运行最终一致性检查 ("回马枪") - 基于 ground truth"""
    if not self.task_state or not self.enable_consistency_check:
        return {}

    if self.verbose:
        print(f"\n--- Consistency Check (回马枪) ---")

    # === OLD: 引用模型声明 (错误!) ===
    # message = f"让我们回到最初的问题。{self.task_state.question}"

    # === NEW: 基于 ground truth 重新提问 ===
    message = self._generate_consistency_check_from_ground_truth()

    target_messages = self.memory.get_conversation_history(
        filter_incorrect=True  # NEW: 只包含正确的 turns
    )
    target_messages.append({"role": "user", "content": message})

    response = self.llm_client.call_target_model(
        messages=target_messages,
        max_tokens=2048
    )

    model_content = response.get("content", "") if response.get("success") else ""

    # Compare with expected (ground truth)
    eval_result = self.evaluator.evaluate_response(
        response=model_content,
        expected_answer=self.task_state.expected_answer,
        action_type="consistency_check",
        question_asked=message
    )

    if self.verbose:
        print(f"Final Answer: {model_content[:150]}...")
        print(f"Consistency Score: {eval_result.score:.2f}")

    self._log_event("consistency_check", {
        "question": message,
        "response": model_content,
        "score": eval_result.score,
        "expected": self.task_state.expected_answer,
        "grounded_in_truth": True  # NEW: 标记这是基于真值的
    })

    return {
        "passed": eval_result.score > 0.7,
        "score": eval_result.score,
        "response": model_content,
        "grounded_check": True  # NEW
    }

def _generate_consistency_check_from_ground_truth(self) -> str:
    """基于 ground truth 生成一致性检查问题

    不引用模型的先前声明,而是要求模型重新回答原始问题。
    """
    # Strategy 1: 重新表述原始问题
    original_q = self.task_state.question

    reformulations = [
        f"让我们再确认一次: {original_q}",
        f"回到最初的问题: {original_q}",
        f"请再次回答: {original_q}",
        f"Let's verify: {original_q}",
        f"To confirm, {original_q.lower()}"
    ]

    return random.choice(reformulations)
```

## 期望输出

### 1. 代码文件

#### 修改文件

1. **src/simulator/strategic_simulator.py**
   - 添加 `_validate_model_claims()` 方法
   - 添加 `_extract_factual_claims()` 方法
   - 添加 `_check_claim_against_ground_truth()` 方法
   - 更新 `step()` 使用验证
   - 更新 `run_consistency_check()` 基于 ground truth
   - 添加 `_generate_consistency_check_from_ground_truth()` 方法
   - 添加配置参数: `filter_incorrect_turns`, `error_filter_threshold`

2. **src/simulator/memory_store.py**
   - 更新 `Turn` dataclass 添加 `is_correct` 和 `claim_validation` 字段
   - 更新 `get_conversation_history()` 添加过滤功能
   - 添加 `filter_incorrect` 和 `score_threshold` 参数

### 2. 单元测试

**tests/test_truth_validation.py**

```python
class TestTruthValidation(unittest.TestCase):
    """测试真值验证机制"""

    def test_validate_correct_claims(self):
        """正确的声明应该被标记为 correct"""
        simulator = StrategicSimulator()
        task = {
            "task_id": "test",
            "question": "What is in the image?",
            "answer": "A person",
            "images": []
        }
        simulator.start_task(task)

        # 模拟高分评估
        eval_result = EvaluationResult(score=0.9, level_passed=True)

        validation = simulator._validate_model_claims(
            response="I see a person in the image",
            turn_number=1,
            evaluation=eval_result
        )

        self.assertFalse(validation["has_false_claims"])

    def test_validate_incorrect_claims(self):
        """错误的声明应该被标记为 incorrect"""
        simulator = StrategicSimulator()
        task = {
            "task_id": "test",
            "question": "What is in the image?",
            "answer": "A person",
            "images": []
        }
        simulator.start_task(task)

        # 模拟低分评估
        eval_result = EvaluationResult(score=0.2, level_passed=False)

        validation = simulator._validate_model_claims(
            response="I cannot see images, I am text-only",
            turn_number=1,
            evaluation=eval_result
        )

        self.assertTrue(validation["has_false_claims"])

    def test_memory_filtering(self):
        """内存过滤应该排除错误 turns"""
        memory = MemoryStore()
        memory.start_task("test_task", "test_type", "test_answer")

        # 添加正确 turn
        memory.add_turn(
            action="follow_up",
            user_message="Question 1",
            model_response="Correct answer",
            evaluation={"score": 0.9},
            key_info=[],
            is_correct=True
        )

        # 添加错误 turn
        memory.add_turn(
            action="follow_up",
            user_message="Question 2",
            model_response="Wrong answer",
            evaluation={"score": 0.2},
            key_info=[],
            is_correct=False
        )

        # 不过滤: 应该有 4 条消息 (2 turns * 2 messages/turn)
        history_all = memory.get_conversation_history(filter_incorrect=False)
        self.assertEqual(len(history_all), 4)

        # 过滤: 应该只有 2 条消息 (1 correct turn * 2)
        history_filtered = memory.get_conversation_history(filter_incorrect=True)
        self.assertEqual(len(history_filtered), 2)

    def test_consistency_check_grounded(self):
        """一致性检查应该基于 ground truth"""
        simulator = StrategicSimulator()
        task = {
            "task_id": "test",
            "question": "What object is visible?",
            "answer": "A knife",
            "images": []
        }
        simulator.start_task(task)

        # 生成一致性检查消息
        message = simulator._generate_consistency_check_from_ground_truth()

        # 验证: 应该包含原始问题,不应该引用模型声明
        self.assertIn("What object is visible?", message)
        self.assertNotIn("You said", message)
        self.assertNotIn("You mentioned", message)
```

### 3. 集成测试

**tests/test_error_propagation.py**

```python
class TestErrorPropagation(unittest.TestCase):
    """测试错误传播防止"""

    def test_error_does_not_propagate(self):
        """错误不应该传播到后续 turns"""
        simulator = StrategicSimulator(filter_incorrect_turns=True)
        # ... 模拟一个错误响应
        # 验证后续 turns 的 context 中不包含错误
```

### 4. 验证报告

**docs/task/round3/report/stage2/PHASE2_TASK2.4_TRUTH_VALIDATION_REPORT.md**

包含:
- 实现摘要
- 验证机制设计
- 错误传播测试结果
- Before/After 对比
- 一致性检查修复验证

## 接口定义

### 新增内部接口

```python
# Claim 验证接口
def _validate_model_claims(
    self,
    response: str,
    turn_number: int,
    evaluation: EvaluationResult
) -> Dict[str, Any]:
    """返回: {claims, has_false_claims, validation_summary}"""
    pass

# Ground truth 检查接口
def _check_claim_against_ground_truth(
    self,
    claim: str,
    ground_truths: Dict[str, Any],
    expected_answer: str,
    evaluation_score: float
) -> bool:
    """返回: claim 是否正确"""
    pass
```

### 更新的接口

```python
# MemoryStore.get_conversation_history() 新增参数
def get_conversation_history(
    self,
    n_turns: Optional[int] = None,
    filter_incorrect: bool = False,  # NEW
    score_threshold: float = 0.5  # NEW
) -> List[Dict[str, str]]
```

### 配置接口

```python
# StrategicSimulator 新增初始化参数
class StrategicSimulator:
    def __init__(
        self,
        # ... 现有参数 ...
        filter_incorrect_turns: bool = True,  # NEW
        error_filter_threshold: float = 0.5  # NEW
    )
```

## 协作要求

### 与 Task 2.5 的并行协作

| 方面 | Task 2.4 | Task 2.5 | 协作策略 |
|------|---------|---------|---------|
| **修改文件** | strategic_simulator.py (claim validation), memory_store.py | strategic_simulator.py (image sending), llm_user_simulator.py | 不同代码区域 |
| **代码行号** | ~810-850, memory_store.py 全部 | ~890-920, llm_user_simulator.py | 行号不重叠 |
| **测试** | truth_validation 测试 | image_strategy 测试 | 独立测试文件 |
| **冲突风险** | 低 (不同方法) | 低 | 可完全并行 |

**建议流程**:
- Day 1-2: 完全独立开发
- Day 3: 合并到同一分支并测试

### 依赖的 Phase 1 报告

- **Task 1.4 报告**: [PHASE1_TASK1.4_SIMULATOR_TRUTH_VALIDATION_REPORT.md](../report/PHASE1_TASK1.4_SIMULATOR_TRUTH_VALIDATION_REPORT.md)
  - 错误传播链详情
  - 代码架构gap分析
  - 修复建议

## 验证标准

### 成功标准

- [ ] `_validate_model_claims()` 方法实现
- [ ] `is_correct` 标记添加到 model_claims
- [ ] `get_conversation_history()` 支持过滤
- [ ] 一致性检查基于 ground truth
- [ ] 单元测试覆盖验证和过滤
- [ ] 错误传播率降至 0%
- [ ] 完整技术报告生成

### 测试用例

**Test Case 1: 高分响应标记为正确**
```python
eval_score = 0.9
validation = _validate_model_claims(response, 1, eval_result)
assert validation["has_false_claims"] == False
```

**Test Case 2: 低分响应标记为错误**
```python
eval_score = 0.2
validation = _validate_model_claims(response, 1, eval_result)
assert validation["has_false_claims"] == True
```

**Test Case 3: 错误 turns 被过滤**
```python
history = memory.get_conversation_history(filter_incorrect=True)
# 应该不包含 score < 0.5 的 turns
```

---

# Task 2.5: 多图策略统一

## 任务背景

### Phase 1 发现的问题 (Task 1.5)

**严重程度**: P1 HIGH

**核心问题**:
1. 图像发送不一致 - 54% turns 发送 0 图像
2. 两个 simulators 使用不同的图像注入策略
3. AC 任务定义与 expected_answer 不对齐

**统计数据**:
- AC turns 分析: 224
- 发送所有图像: 96 (42.9%)
- 发送部分图像: 7 (3.1%)
- **未发送图像**: 121 (54.0%) ❌
- 任务定义不对齐: ~200 (100%) ❌

### Simulator 策略不一致

| Simulator | 策略 | 实现 |
|-----------|------|------|
| **StrategicSimulator** | `send_all_every_turn` | 每个 turn 发送所有图像 |
| **LLMUserSimulator** | `progressive` | 逐个发送图像 |

**代码证据**:

**StrategicSimulator** (strategic_simulator.py:890-919):
```python
def _get_images_for_turn(self, action: str) -> List[str]:
    """For multimodal testing, we need to send ALL images on EVERY turn"""
    # Send all images for all actions
    ...
```

**LLMUserSimulator** (llm_user_simulator.py:517-537):
```python
def _get_images_to_send(self, action: str) -> List[str]:
    """确定要发送给待测 VLM 的图片"""
    if action == "guidance" and task_images:
        # For guidance, show next image if not all shown
        if len(self.images_shown) < len(task_images):
            next_img_idx = len(self.images_shown)
            ...
```

### AC 任务定义不对齐

**Pattern 1: 比较问题但单图答案**
```
Question: "Count the person in each image. Which has more?"
Images: 3 images
Expected: "Image 0 has 3 person(s)"  ← 只提到一个图像!

应该是: "Image 0 has 3 persons, Image 1 has 2, Image 2 has 1. Image 0 has more."
```

**Pattern 2: 位置问题但不完整答案**
```
Question: "In which image is the person positioned bottommost?"
Images: 3 images
Expected: "Image 2 has the person bottommost"  ← 缺少比较上下文

应该是: "Image 2 has the person in the bottommost position compared to Images 0 and 1."
```

## 任务需求

### 修复目标

1. **统一图像发送策略**: 两个 simulators 使用相同策略
2. **修复 AC 任务定义**: Expected answers 与问题类型对齐
3. **传递 images_sent 给 evaluator**: 让评估器知道发送了哪些图像
4. **添加策略配置**: 允许选择不同的图像注入策略

### 核心交付物

1. **统一的 ImageInjectionPolicy**: 配置类定义策略
2. **LLMUserSimulator 更新**: 匹配 StrategicSimulator 策略
3. **AC 任务 expected_answer 修复**: 生成器或手动修复
4. **Evaluator 接口更新**: 接收 `images_sent` 参数
5. **单元测试**: 验证策略一致性

## 当前情况

### 图像发送策略对比

```python
# StrategicSimulator - 当前实现 (Task 2.1 已修复)
def _get_images_for_turn(self, action: str) -> List[str]:
    """Send ALL images on EVERY turn"""
    valid_images = []
    for img_rel_path in self.task_state.images:
        resolved_path = self._resolve_single_image_path(img_rel_path)
        if resolved_path:
            valid_images.append(resolved_path)
    return valid_images  # 返回所有图像

# LLMUserSimulator - 当前实现 (需要修复)
def _get_images_to_send(self, action: str) -> List[str]:
    """Progressive image sending"""
    if len(self.images_shown) < len(task_images):
        next_img_idx = len(self.images_shown)
        return [task_images[next_img_idx]]  # 返回一个图像
    return []
```

### Evaluator 不知道 images_sent

```python
# 当前 evaluator 调用 (strategic_simulator.py)
eval_result = self.evaluator.evaluate_response(
    response=model_content,
    expected_answer=...,
    action_type=action,
    question_asked=message,
    context={...}
    # ← Missing: images_sent parameter!
)
```

## 实现设计

### 1. 图像注入策略配置

#### ImageInjectionPolicy 枚举

```python
# action_space.py or new file: image_policy.py
from enum import Enum

class ImageInjectionPolicy(str, Enum):
    """图像注入策略"""

    # 每个 turn 发送所有图像 (推荐用于多模态测试)
    SEND_ALL_EVERY_TURN = "send_all_every_turn"

    # 逐个发送图像 (用于测试渐进式信息披露)
    PROGRESSIVE = "progressive"

    # 仅在第一个 turn 发送所有图像
    SEND_ALL_FIRST_TURN = "send_all_first_turn"

    # 根据 action 类型决定
    ACTION_DEPENDENT = "action_dependent"
```

#### ImagePolicyManager 类

```python
class ImagePolicyManager:
    """管理图像发送策略的决策"""

    def __init__(self, policy: ImageInjectionPolicy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN):
        self.policy = policy
        self.images_shown_indices: Set[int] = set()

    def get_images_to_send(
        self,
        all_images: List[str],
        turn: int,
        action: str
    ) -> List[str]:
        """根据策略决定发送哪些图像

        Args:
            all_images: 所有可用图像路径
            turn: 当前 turn 编号
            action: 当前 action 类型

        Returns:
            应该发送的图像路径列表
        """
        if self.policy == ImageInjectionPolicy.SEND_ALL_EVERY_TURN:
            return all_images

        elif self.policy == ImageInjectionPolicy.PROGRESSIVE:
            # 逐个发送
            if action == "guidance":
                # 发送下一个未显示的图像
                for idx, img in enumerate(all_images):
                    if idx not in self.images_shown_indices:
                        self.images_shown_indices.add(idx)
                        return [img]
            # 非 guidance action: 不发送新图像
            return []

        elif self.policy == ImageInjectionPolicy.SEND_ALL_FIRST_TURN:
            if turn == 1:
                return all_images
            else:
                return []

        elif self.policy == ImageInjectionPolicy.ACTION_DEPENDENT:
            # guidance 和 follow_up: 发送所有
            if action in ["guidance", "follow_up"]:
                return all_images
            # 其他: 不发送
            return []

        else:
            # Default
            return all_images
```

### 2. 统一 Simulators

#### 更新 StrategicSimulator

```python
class StrategicSimulator:

    def __init__(
        self,
        # ... 其他参数 ...
        image_injection_policy: ImageInjectionPolicy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN  # NEW
    ):
        # ...
        self.image_policy = ImagePolicyManager(image_injection_policy)

    def _get_images_for_turn(self, action: str) -> List[str]:
        """Determine which images to send - 使用策略管理器"""
        if not self.task_state or not self.task_state.images:
            return []

        # 首先解析所有图像路径 (使用 Task 2.1 的增强解析)
        all_resolved_images = []
        for img_rel_path in self.task_state.images:
            resolved_path = self._resolve_single_image_path(img_rel_path)
            if resolved_path:
                all_resolved_images.append(resolved_path)

        # 然后使用策略决定发送哪些
        images_to_send = self.image_policy.get_images_to_send(
            all_images=all_resolved_images,
            turn=self.turn_count,
            action=action
        )

        return images_to_send
```

#### 更新 LLMUserSimulator

```python
class LLMUserSimulator:

    def __init__(
        self,
        # ... 其他参数 ...
        image_injection_policy: ImageInjectionPolicy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN  # NEW
    ):
        # ...
        self.image_policy = ImagePolicyManager(image_injection_policy)
        # 移除 self.images_shown (由 ImagePolicyManager 管理)

    def _get_images_to_send(self, action: str) -> List[str]:
        """确定要发送的图片 - 使用统一策略"""
        if not self.task_state or not self.task_state.images:
            return []

        # 解析图像路径 (复用 StrategicSimulator 的逻辑或独立实现)
        all_images = self._resolve_task_images()

        # 使用策略管理器
        images_to_send = self.image_policy.get_images_to_send(
            all_images=all_images,
            turn=self.current_turn,
            action=action
        )

        return images_to_send
```

### 3. 传递 images_sent 给 Evaluator

#### 更新 Simulator

```python
# strategic_simulator.py step()
def step(self) -> Dict[str, Any]:
    # ...

    # 3. Determine images to send
    images_to_send = self._get_images_for_turn(action)

    # ...

    # 7. 评估响应 - 传递 images_sent
    eval_result = self.evaluator.evaluate_response(
        response=model_content,
        expected_answer=...,
        action_type=action,
        question_asked=message,
        context={
            "previous_responses": [...],
            "phase": phase.phase_name,
            # === NEW: Images sent ===
            "images_sent": images_to_send,
            "total_task_images": len(self.task_state.images)
        }
    )

    # ...
```

#### 更新 Evaluator

```python
# evaluator.py
class Evaluator:

    def evaluate_response(
        self,
        response: str,
        expected_answer: str,
        action_type: str,
        question_asked: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        task: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """评估响应 - 现在知道发送了哪些图像"""

        # === NEW: 提取 images_sent ===
        images_sent = context.get("images_sent", []) if context else []
        total_images = context.get("total_task_images", 0) if context else 0

        # 如果没有图像但模型描述视觉内容 → 幻觉
        if len(images_sent) == 0 and self._contains_visual_descriptions(response):
            logger.warning("[Evaluator] Model describes visuals but no images were sent!")
            # 降低 faithfulness 分数
            # ...

        # 如果只发送部分图像但模型引用所有图像 → 可能的幻觉
        if 0 < len(images_sent) < total_images:
            if self._references_unsent_images(response, images_sent, total_images):
                logger.warning("[Evaluator] Model may reference images that weren't sent!")
                # ...

        # 正常评估
        # ...
```

### 4. 修复 AC 任务定义 (可选)

#### 选项 A: 更新任务生成器

```python
# 在任务生成脚本中修复
def generate_ac_task_expected_answer(question: str, images: List, ground_truth: Dict) -> str:
    """生成与问题类型对齐的 expected answer"""

    if "which has more" in question.lower() or "count" in question.lower():
        # 比较问题: 给出所有图像的计数和比较结果
        counts = [ground_truth[img]["count"] for img in images]
        max_idx = counts.index(max(counts))
        return f"Image {max_idx} has {max(counts)} (more than others: {counts})"

    elif "bottommost" in question.lower() or "positioned" in question.lower():
        # 位置问题: 给出位置和比较
        positions = [ground_truth[img]["position"] for img in images]
        target_idx = find_bottommost(positions)
        return f"Image {target_idx} has the person in the bottommost position"

    # ... 其他类型
```

#### 选项 B: 手动修复现有任务 (如果数量不多)

创建修复脚本批量更新任务文件中的 `expected_answer` 字段。

## 期望输出

### 1. 代码文件

#### 新增文件
1. **src/simulator/image_policy.py** (可选,或添加到 action_space.py)
   - `ImageInjectionPolicy` 枚举
   - `ImagePolicyManager` 类

#### 修改文件
2. **src/simulator/strategic_simulator.py**
   - 添加 `image_injection_policy` 参数
   - 使用 `ImagePolicyManager`
   - 传递 `images_sent` 给 evaluator

3. **src/simulator/llm_user_simulator.py**
   - 添加 `image_injection_policy` 参数
   - 使用 `ImagePolicyManager`
   - 移除独立的 `images_shown` 逻辑

4. **src/simulator/evaluator.py**
   - 更新 `evaluate_response()` 使用 `images_sent`
   - 添加幻觉检测逻辑 (基于 images_sent)

5. **task_generators/...** (可选)
   - 修复 AC 任务 expected_answer 生成

### 2. 单元测试

**tests/test_image_strategy.py**

```python
class TestImageStrategy(unittest.TestCase):
    """测试图像策略统一"""

    def test_send_all_policy(self):
        """SEND_ALL_EVERY_TURN 策略应该每turn发送所有图像"""
        manager = ImagePolicyManager(ImageInjectionPolicy.SEND_ALL_EVERY_TURN)

        images = ["img1.jpg", "img2.jpg", "img3.jpg"]

        # Turn 1, 2, 3 都应该返回所有图像
        for turn in [1, 2, 3]:
            result = manager.get_images_to_send(images, turn, "follow_up")
            self.assertEqual(len(result), 3)

    def test_progressive_policy(self):
        """PROGRESSIVE 策略应该逐个发送"""
        manager = ImagePolicyManager(ImageInjectionPolicy.PROGRESSIVE)

        images = ["img1.jpg", "img2.jpg", "img3.jpg"]

        # Turn 1: 第一个图像
        result1 = manager.get_images_to_send(images, 1, "guidance")
        self.assertEqual(len(result1), 1)
        self.assertEqual(result1[0], "img1.jpg")

        # Turn 2: 第二个图像
        result2 = manager.get_images_to_send(images, 2, "guidance")
        self.assertEqual(len(result2), 1)
        self.assertEqual(result2[0], "img2.jpg")

    def test_simulators_use_same_policy(self):
        """两个 simulators 应该使用相同策略"""
        policy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN

        strategic = StrategicSimulator(image_injection_policy=policy)
        llm_user = LLMUserSimulator(image_injection_policy=policy)

        # 验证两者使用相同策略
        self.assertEqual(strategic.image_policy.policy, policy)
        self.assertEqual(llm_user.image_policy.policy, policy)

    def test_evaluator_receives_images_sent(self):
        """Evaluator 应该接收 images_sent 信息"""
        simulator = StrategicSimulator()
        task = {
            "task_id": "test",
            "question": "Test",
            "answer": "Test",
            "images": ["img1.jpg", "img2.jpg"]
        }
        simulator.start_task(task)

        # Mock evaluator to capture context
        original_evaluate = simulator.evaluator.evaluate_response

        received_context = {}
        def mock_evaluate(*args, **kwargs):
            received_context.update(kwargs.get("context", {}))
            return original_evaluate(*args, **kwargs)

        simulator.evaluator.evaluate_response = mock_evaluate

        # 运行一个 step
        simulator.step()

        # 验证 context 包含 images_sent
        self.assertIn("images_sent", received_context)
```

### 3. 集成测试

**tests/test_image_strategy_integration.py**

```python
class TestImageStrategyIntegration(unittest.TestCase):
    """集成测试图像策略"""

    def test_strategic_vs_llm_user_consistency(self):
        """两个 simulators 应该产生一致的图像发送行为"""
        # ... 使用相同任务运行两个 simulators
        # 验证 images_sent 一致
```

### 4. 验证报告

**docs/task/round3/report/stage2/PHASE2_TASK2.5_MULTI_IMAGE_STRATEGY_REPORT.md**

包含:
- 策略统一实现摘要
- 两个 simulators 的对比
- images_sent 传递验证
- AC 任务修复 (如果执行)
- Before/After 测试结果

## 接口定义

### 新增接口

```python
# ImageInjectionPolicy 枚举
class ImageInjectionPolicy(str, Enum):
    SEND_ALL_EVERY_TURN = "send_all_every_turn"
    PROGRESSIVE = "progressive"
    # ...

# ImagePolicyManager 类
class ImagePolicyManager:
    def get_images_to_send(
        self,
        all_images: List[str],
        turn: int,
        action: str
    ) -> List[str]
```

### 更新的接口

```python
# Simulator 初始化新增参数
class StrategicSimulator:
    def __init__(
        self,
        # ... 其他参数 ...
        image_injection_policy: ImageInjectionPolicy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN
    )

# Evaluator.evaluate_response() context 新增字段
context = {
    # ... 现有字段 ...
    "images_sent": List[str],  # NEW
    "total_task_images": int  # NEW
}
```

## 协作要求

### 与 Task 2.4 的并行协作

完全独立,无冲突风险。

### 依赖的 Phase 1 报告

- **Task 1.5 报告**: [PHASE1_TASK1.5_MULTI_IMAGE_STRATEGY_REPORT.md](../report/PHASE1_TASK1.5_MULTI_IMAGE_STRATEGY_REPORT.md)
  - 图像发送统计
  - Simulator 策略对比
  - AC 任务不对齐案例

### 与其他任务的依赖

- **依赖 Task 2.1**: 使用增强的图像路径解析
- **后续影响**: Task 2.6 可能使用 images_sent 信息

## 验证标准

### 成功标准

- [ ] `ImageInjectionPolicy` 枚举定义
- [ ] `ImagePolicyManager` 类实现
- [ ] 两个 simulators 使用统一策略
- [ ] `images_sent` 传递给 evaluator
- [ ] Evaluator 使用 images_sent 进行幻觉检测
- [ ] 单元测试验证策略一致性
- [ ] 集成测试验证行为一致
- [ ] 完整技术报告生成

### 测试用例

**Test Case 1: SEND_ALL 策略**
```python
policy = ImagePolicyManager(SEND_ALL_EVERY_TURN)
result = policy.get_images_to_send(3_images, turn=1, action="follow_up")
assert len(result) == 3
```

**Test Case 2: PROGRESSIVE 策略**
```python
policy = ImagePolicyManager(PROGRESSIVE)
result1 = policy.get_images_to_send(3_images, turn=1, action="guidance")
assert len(result1) == 1
```

**Test Case 3: Evaluator 接收 images_sent**
```python
context = {"images_sent": ["img1.jpg"], "total_task_images": 3}
# evaluator 应该检测到只发送了部分图像
```

---

## 总结: 并行组 F 执行计划

### 时间线 (并行执行)

**Day 1 (独立开发)**:
- Task 2.4: 实现 claim 验证, 内存过滤
- Task 2.5: 实现策略管理器, 更新 simulators

**Day 2 (独立测试)**:
- Task 2.4: 测试验证和过滤功能
- Task 2.5: 测试策略一致性

**Day 3 (合并和验证)**:
- 上午: 两个任务合并到同一分支
- 下午: 联合测试
- 晚上: 生成报告

### 最终交付物检查清单

**Task 2.4**:
- [ ] `_validate_model_claims()` 实现
- [ ] `is_correct` 标记添加
- [ ] `get_conversation_history()` 过滤功能
- [ ] 一致性检查基于 ground truth
- [ ] 单元测试 (3+ cases)
- [ ] 错误传播率降至 0%
- [ ] 技术报告

**Task 2.5**:
- [ ] `ImageInjectionPolicy` 和 `ImagePolicyManager`
- [ ] 两个 simulators 统一策略
- [ ] `images_sent` 传递给 evaluator
- [ ] Evaluator 幻觉检测
- [ ] 单元测试 (3+ cases)
- [ ] 策略一致性验证通过
- [ ] 技术报告

---

**文档创建时间**: 2026-02-03
**预计完成时间**: 5-6小时 (并行) | 7-9小时 (串行)
**优先级**: P1 (两个任务都是高优先级)
