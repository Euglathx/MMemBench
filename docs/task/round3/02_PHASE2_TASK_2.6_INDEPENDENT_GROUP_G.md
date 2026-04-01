# Phase 2 独立组 G: Task 2.6

**组别**: G (独立执行)
**预估时间**: 3-4小时
**依赖**: Phase 1 Task 1.6
**优先级**: P2 (中等优先级)

---

# Task 2.6: Evaluator 状态管理重构

## 任务背景

### Phase 1 发现的问题 (Task 1.6)

**严重程度**: P2 MEDIUM

**核心问题**: 评估器的多个维度分数表现得像常量,大部分时间保持默认值不变。

**统计数据**:

| 维度 | 默认值 | 保留率 | 唯一值数量 | 状态 |
|------|--------|--------|------------|------|
| `correctness` | - | - | 37 | ✓ 正常 |
| `memory_retention` | 0.3 | 3.4% | 5 | ✓ 正常 |
| **`robustness`** | 0.3 | **78.8%** | 2 | ❌ 可疑 |
| **`consistency`** | 0.3 | **76.1%** | 7 | ❌ 可疑 |
| **`faithfulness`** | 0.2 | **78.8%** | 6 | ❌ 可疑 |
| **`cross_image_confusion`** | 0.3 | **78.8%** | 3 | ❌ 可疑 |
| **`disambiguation`** | 0.3 | **78.8%** | 2 | ❌ 可疑 |

**关键发现**:
- **5 个维度** 在 76-79% 的 turns 中保持默认值
- **Robustness** 和 **disambiguation** 只有 2 个唯一值
- 某些任务中分数完全不变 (所有 turns 相同分数)

### 具体示例

**Task ac_mscoco_0** (7 turns):

| Turn | Phase | Robustness | Consistency | 观察 |
|------|-------|-----------|-------------|------|
| 1 | grounding | **0.72** | **0.72** | 初始值 |
| 2 | grounding | **0.72** | **0.72** | 未变化 |
| 3 | noise_injection | **0.72** | **0.72** | 未变化 |
| 4-7 | noise_injection | **0.72** | **0.72** | 完全相同! |

**问题**: 即使在 `noise_injection` phase (应该测试 robustness),robustness 分数也保持不变。

### 根本原因

**位置**: [evaluator.py:663-671](../../src/simulator/evaluator.py#L663-L671)

```python
# Hard scores 设置为默认值
scores = {
    "correctness": 0.1,
    "faithfulness": 0.2,      # ← 78.8% turns 保留此值
    "robustness": 0.3,         # ← 78.8% turns 保留此值
    "consistency": 0.3,        # ← 76.1% turns 保留此值
    "memory_retention": 0.3    # ← 仅 3.4% turns 保留 (正常更新)
}
```

**为什么发生**:
1. **Memory retention** 被主动计算 (基于 ground truths vs claims) → 低保留率
2. **其他维度** 仅在特定 action types 时才更新 → 高保留率
3. 对于大多数 actions (`follow_up`, `guidance`), 默认值被保留

## 任务需求

### 修复目标

1. **所有维度动态更新**: 在每个 turn 都计算,不依赖默认值
2. **LLM Judge 正确映射**: 确保 LLM Judge 输出正确覆盖 hard scores
3. **添加状态快照**: 用于调试的 `EvaluatorStateSnapshot`
4. **一致性检查**: 验证判断的内部一致性
5. **详细日志**: 记录每个维度的更新原因

### 核心交付物

1. **动态 faithfulness 评分**: 总是评估视觉声明的真实性
2. **动态 robustness 评分**: 总是评估对误导的抵抗力
3. **动态 consistency 评分**: 总是与前序响应比较
4. **EvaluatorStateSnapshot 类**: 调试和验证工具
5. **单元测试**: 验证所有维度都动态更新

## 当前情况

### 当前评分逻辑

```python
# evaluator.py: hard_rule_evaluation()
def hard_rule_evaluation(self, response, expected, context):
    # 设置默认值
    scores = {
        "correctness": 0.1,
        "faithfulness": 0.2,
        "robustness": 0.3,
        "consistency": 0.3,
        "memory_retention": 0.3
    }

    # Memory retention 被计算 ← 这就是为什么它的保留率低
    scores["memory_retention"] = self._compute_memory_retention(...)

    # 其他维度: 仅在特定条件下更新
    if action_type == "mislead":
        scores["robustness"] = ...  # 只有 mislead actions 更新 robustness

    # 否则: 保持默认值!
    return scores
```

### 问题模式

| 维度 | 何时更新 | 何时使用默认值 | 结果 |
|------|---------|---------------|------|
| `memory_retention` | 每个 turn | 从不 | ✓ 正常 (3.4% 默认) |
| `robustness` | `mislead` action | 所有其他 actions | ❌ 78.8% 默认 |
| `faithfulness` | LLM Judge 检测幻觉时 | 大多数 turns | ❌ 78.8% 默认 |
| `consistency` | 特定检查 | 大多数 turns | ❌ 76.1% 默认 |
| `cross_image_confusion` | 多图任务特定检查 | 大多数 turns | ❌ 78.8% 默认 |

## 实现设计

### 1. 动态维度评分

#### Faithfulness - 总是评估

```python
class Evaluator:

    def _compute_faithfulness_score(
        self,
        response: str,
        images_sent: List[str],
        expected_answer: str,
        context: Dict[str, Any]
    ) -> float:
        """动态计算 faithfulness (总是执行)

        Faithfulness: 模型的声明是否基于实际视觉证据,而非幻觉。
        """
        # 如果没有发送图像但模型描述视觉内容 → 严重幻觉
        if len(images_sent) == 0:
            if self._contains_visual_descriptions(response):
                logger.warning("[Faithfulness] Visual descriptions without images → hallucination")
                return 0.0  # 严重幻觉

        # 使用 LLM Judge 评估 faithfulness
        if self.use_llm_judge:
            prompt = f"""
            Response: {response}
            Expected: {expected_answer}

            Does the response make claims that are not grounded in visual evidence?
            Rate faithfulness 0-10 (10 = completely grounded, 0 = pure hallucination).
            """
            llm_result = self._call_llm_judge(prompt)
            return llm_result.get("faithfulness", 0.5) / 10.0

        # Fallback: 基于响应与期望的对齐
        # (非最优但比固定默认值好)
        similarity = self._semantic_similarity(response, expected_answer)
        return max(0.2, similarity)  # 至少 0.2 (而非固定 0.2)

    def _contains_visual_descriptions(self, response: str) -> bool:
        """检查响应是否包含视觉描述"""
        visual_keywords = [
            "see", "看到", "visible", "显示", "image shows", "图中",
            "in the image", "在图片", "picture", "photo"
        ]
        response_lower = response.lower()
        return any(keyword in response_lower for keyword in visual_keywords)
```

#### Robustness - 总是评估

```python
def _compute_robustness_score(
    self,
    response: str,
    action_type: str,
    previous_responses: List[str],
    context: Dict[str, Any]
) -> float:
    """动态计算 robustness (总是执行)

    Robustness: 模型对误导、压力和不确定性的抵抗力。
    """
    # 如果是 mislead/stress action: 检查模型是否抵抗
    if action_type in ["mislead", "mislead_subtle", "distraction", "noise_injection"]:
        # 使用 LLM Judge 评估抵抗力
        if self.use_llm_judge:
            prompt = f"""
            This was a misleading/stress test action.
            Response: {response}

            Did the model resist misinformation and maintain accuracy?
            Rate robustness 0-10 (10 = perfect resistance, 0 = completely misled).
            """
            llm_result = self._call_llm_judge(prompt)
            return llm_result.get("robustness", 0.5) / 10.0

    # 即使不是 stress action: 检查模型是否改变了先前的正确答案
    if previous_responses:
        last_response = previous_responses[-1]
        # 如果模型保持一致的正确信息 → 高 robustness
        if self._maintains_correctness(response, last_response):
            return 0.8
        # 如果模型改变了答案 → 低 robustness
        elif self._contradicts_previous(response, last_response):
            return 0.4

    # Default: 中性 (但基于实际检查)
    return 0.6  # 中性但合理的基线
```

#### Consistency - 总是评估

```python
def _compute_consistency_score(
    self,
    response: str,
    previous_responses: List[str],
    context: Dict[str, Any]
) -> float:
    """动态计算 consistency (总是执行)

    Consistency: 模型在多个 turns 中是否保持一致的信息。
    """
    if not previous_responses:
        # 第一个 turn: 无法比较一致性
        return 0.7  # 中性起点

    # 检查与所有先前响应的一致性
    consistency_scores = []

    for prev_response in previous_responses[-3:]:  # 检查最近 3 个
        # 提取关键声明
        current_claims = self._extract_key_claims(response)
        prev_claims = self._extract_key_claims(prev_response)

        # 检查是否有矛盾
        contradictions = self._find_contradictions(current_claims, prev_claims)

        if contradictions:
            consistency_scores.append(0.3)  # 发现矛盾
        else:
            consistency_scores.append(0.9)  # 一致

    # 返回平均一致性
    return sum(consistency_scores) / len(consistency_scores)

def _find_contradictions(
    self,
    claims1: List[str],
    claims2: List[str]
) -> List[Tuple[str, str]]:
    """查找两组声明之间的矛盾"""
    contradictions = []

    # 简化实现: 检查明显的矛盾关键词
    opposite_pairs = [
        ("left", "right"),
        ("top", "bottom"),
        ("more", "less"),
        ("larger", "smaller"),
        # ...
    ]

    for claim1 in claims1:
        for claim2 in claims2:
            for word1, word2 in opposite_pairs:
                if word1 in claim1.lower() and word2 in claim2.lower():
                    # 可能的矛盾
                    contradictions.append((claim1, claim2))

    return contradictions
```

#### Cross-Image Confusion - 动态评估

```python
def _compute_cross_image_confusion_score(
    self,
    response: str,
    images_sent: List[str],
    task_type: str,
    context: Dict[str, Any]
) -> float:
    """动态计算 cross_image_confusion (对多图任务)"""

    # 单图任务: 不适用
    if len(images_sent) <= 1:
        return 1.0  # N/A → 满分

    # 多图任务: 检查是否混淆图像
    if task_type in ["attribute_comparison", "attribute_bridge_reasoning"]:
        # 使用 LLM Judge
        if self.use_llm_judge:
            prompt = f"""
            Task type: Multi-image comparison
            Response: {response}

            Does the model correctly distinguish between images?
            Or does it confuse attributes/objects across images?

            Rate 0-10 (10 = perfect distinction, 0 = severe confusion).
            """
            llm_result = self._call_llm_judge(prompt)
            return llm_result.get("cross_image_confusion", 0.5) / 10.0

    # Default: 假设没有混淆
    return 0.7
```

### 2. 更新 evaluate_response()

```python
def evaluate_response(
    self,
    response: str,
    expected_answer: str,
    action_type: str,
    question_asked: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    task: Optional[Dict[str, Any]] = None
) -> EvaluationResult:
    """评估响应 - 所有维度动态计算"""

    # 提取 context 信息
    previous_responses = context.get("previous_responses", []) if context else []
    images_sent = context.get("images_sent", []) if context else []
    task_type = task.get("task_type") if task else "unknown"

    # === 1. Hard rule evaluation (作为基线) ===
    hard_scores = self.hard_rule_evaluation(response, expected_answer, context or {})

    # === 2. 动态计算所有维度 (覆盖 hard scores) ===
    dynamic_scores = {}

    # Faithfulness - 总是计算
    dynamic_scores["faithfulness"] = self._compute_faithfulness_score(
        response, images_sent, expected_answer, context or {}
    )

    # Robustness - 总是计算
    dynamic_scores["robustness"] = self._compute_robustness_score(
        response, action_type, previous_responses, context or {}
    )

    # Consistency - 总是计算
    dynamic_scores["consistency"] = self._compute_consistency_score(
        response, previous_responses, context or {}
    )

    # Cross-image confusion - 对多图任务计算
    dynamic_scores["cross_image_confusion"] = self._compute_cross_image_confusion_score(
        response, images_sent, task_type, context or {}
    )

    # Disambiguation - 类似逻辑
    dynamic_scores["disambiguation"] = self._compute_disambiguation_score(
        response, context or {}
    )

    # === 3. 使用动态分数覆盖 hard scores ===
    for dim, score in dynamic_scores.items():
        hard_scores[dim] = score
        logger.debug(f"[Dynamic Score] {dim} = {score:.3f}")

    # === 4. LLM Judge (如果可用) ===
    llm_scores = None
    if self.use_llm_judge:
        llm_scores = self._evaluate_with_llm_judge(...)

    # === 5. 合并分数 ===
    final_scores = self._compute_final_scores(hard_scores, llm_scores)

    # === 6. 计算 overall score ===
    overall_score = self._compute_overall_score(final_scores)

    # === 7. 创建评估结果 ===
    result = EvaluationResult(
        score=overall_score,
        level_passed=overall_score >= self.level_thresholds[self.current_level],
        # ... 其他字段
    )

    return result
```

### 3. EvaluatorStateSnapshot

```python
@dataclass
class EvaluatorStateSnapshot:
    """评估器状态快照 - 用于调试和验证

    捕获评估过程中的所有中间状态,便于诊断问题。
    """
    turn: int
    timestamp: str

    # 输入
    response: str
    expected_answer: str
    action_type: str
    context: Dict[str, Any]

    # Hard scores (基线)
    hard_scores: Dict[str, float]

    # Dynamic scores (计算后)
    dynamic_scores: Dict[str, float]

    # LLM Judge scores (如果有)
    llm_scores: Optional[Dict[str, float]]

    # Final scores (合并后)
    final_scores: Dict[str, float]

    # Overall score
    overall_score: float

    # 维度更新日志
    dimension_updates: Dict[str, str]  # dimension -> update_reason

    # 判断一致性检查
    consistency_checks: Dict[str, Any]


class Evaluator:

    def __init__(self, ...):
        # ...
        self.enable_snapshots = False  # 默认关闭
        self.snapshots: List[EvaluatorStateSnapshot] = []

    def evaluate_response(self, ...) -> EvaluationResult:
        # ... 评估逻辑 ...

        # === 创建快照 ===
        if self.enable_snapshots:
            snapshot = EvaluatorStateSnapshot(
                turn=context.get("turn", 0) if context else 0,
                timestamp=datetime.now().isoformat(),
                response=response,
                expected_answer=expected_answer,
                action_type=action_type,
                context=context or {},
                hard_scores=hard_scores.copy(),
                dynamic_scores=dynamic_scores.copy(),
                llm_scores=llm_scores.copy() if llm_scores else None,
                final_scores=final_scores.copy(),
                overall_score=overall_score,
                dimension_updates=self._get_dimension_updates(),
                consistency_checks=self._run_consistency_checks(result)
            )
            self.snapshots.append(snapshot)

        return result

    def get_snapshots(self) -> List[EvaluatorStateSnapshot]:
        """获取所有状态快照"""
        return self.snapshots

    def export_snapshots(self, filepath: str):
        """导出快照到文件用于分析"""
        import json
        data = [asdict(s) for s in self.snapshots]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
```

### 4. 一致性检查

```python
def _run_consistency_checks(self, eval_result: EvaluationResult) -> Dict[str, Any]:
    """运行内部一致性检查

    验证评估结果的逻辑一致性。
    """
    checks = {}

    # Check 1: 如果 LLM correctness 高但 overall score 低 → 可能问题
    if eval_result.llm_judge_scores:
        llm_correctness = eval_result.llm_judge_scores.get("correctness", 0)
        if llm_correctness >= 0.9 and eval_result.score < 0.7:
            checks["high_llm_low_overall"] = {
                "status": "WARNING",
                "llm_correctness": llm_correctness,
                "overall_score": eval_result.score,
                "message": "LLM Judge gave high score but overall is low"
            }

    # Check 2: 如果 faithfulness 低但 correctness 高 → 矛盾
    if eval_result.faithfulness_score < 0.4 and eval_result.score > 0.8:
        checks["low_faith_high_correct"] = {
            "status": "INCONSISTENT",
            "faithfulness": eval_result.faithfulness_score,
            "correctness": eval_result.score,
            "message": "Low faithfulness but high correctness is contradictory"
        }

    # Check 3: 所有维度都是默认值 → 可能未正确更新
    default_values = {
        "faithfulness": 0.2,
        "robustness": 0.3,
        "consistency": 0.3
    }

    all_defaults = all(
        abs(eval_result.__dict__.get(f"{dim}_score", 0) - default_values[dim]) < 0.01
        for dim in default_values
    )

    if all_defaults:
        checks["all_defaults"] = {
            "status": "ERROR",
            "message": "All dimensions retained default values - not updated?"
        }

    return checks
```

## 期望输出

### 1. 代码文件

#### 修改文件

1. **src/simulator/evaluator.py**
   - 添加 `_compute_faithfulness_score()` 方法
   - 添加 `_compute_robustness_score()` 方法
   - 添加 `_compute_consistency_score()` 方法
   - 添加 `_compute_cross_image_confusion_score()` 方法
   - 添加 `_compute_disambiguation_score()` 方法
   - 添加 `EvaluatorStateSnapshot` dataclass
   - 更新 `evaluate_response()` 使用动态计算
   - 添加 `_run_consistency_checks()` 方法
   - 添加 snapshot 功能

### 2. 单元测试

**tests/test_evaluator_dynamics.py**

```python
class TestEvaluatorDynamics(unittest.TestCase):
    """测试评估器动态评分"""

    def test_faithfulness_always_computed(self):
        """Faithfulness 应该在每个 turn 计算"""
        evaluator = Evaluator()

        # Turn 1
        result1 = evaluator.evaluate_response(
            response="I see a person",
            expected_answer="person",
            action_type="follow_up",
            context={"images_sent": ["img1.jpg"]}
        )

        # Turn 2
        result2 = evaluator.evaluate_response(
            response="I see a cat",
            expected_answer="cat",
            action_type="follow_up",
            context={"images_sent": ["img2.jpg"]}
        )

        # 两个 faithfulness 分数应该不同 (不是默认值)
        self.assertNotEqual(result1.faithfulness_score, 0.2)
        self.assertNotEqual(result2.faithfulness_score, 0.2)
        self.assertNotEqual(result1.faithfulness_score, result2.faithfulness_score)

    def test_robustness_updates_every_turn(self):
        """Robustness 应该在每个 turn 更新"""
        evaluator = Evaluator()

        # 多个 turns
        results = []
        for i in range(5):
            result = evaluator.evaluate_response(
                response=f"Response {i}",
                expected_answer="answer",
                action_type="follow_up",
                context={"previous_responses": [f"Response {j}" for j in range(i)]}
            )
            results.append(result)

        # Robustness 分数应该有变化
        robustness_scores = [r.robustness_score for r in results]
        unique_scores = set(robustness_scores)

        # 至少应该有 2 个不同的值
        self.assertGreater(len(unique_scores), 1)

        # 不应该全部是默认值 0.3
        default_count = sum(1 for s in robustness_scores if abs(s - 0.3) < 0.01)
        self.assertLess(default_count, len(robustness_scores))

    def test_consistency_computed(self):
        """Consistency 应该基于先前响应计算"""
        evaluator = Evaluator()

        # Turn 1
        result1 = evaluator.evaluate_response(
            response="The person is on the left",
            expected_answer="left",
            action_type="follow_up",
            context={"previous_responses": []}
        )

        # Turn 2 - 一致
        result2 = evaluator.evaluate_response(
            response="Yes, the person is on the left side",
            expected_answer="left",
            action_type="follow_up",
            context={"previous_responses": ["The person is on the left"]}
        )

        # Turn 3 - 矛盾
        result3 = evaluator.evaluate_response(
            response="Actually, the person is on the right",
            expected_answer="left",
            action_type="follow_up",
            context={"previous_responses": ["The person is on the left", "Yes, the person is on the left side"]}
        )

        # 一致的响应应该有高 consistency
        self.assertGreater(result2.consistency_score, 0.7)

        # 矛盾的响应应该有低 consistency
        self.assertLess(result3.consistency_score, 0.5)

    def test_snapshots_capture_state(self):
        """Snapshots 应该捕获评估状态"""
        evaluator = Evaluator()
        evaluator.enable_snapshots = True

        # 评估几个响应
        for i in range(3):
            evaluator.evaluate_response(
                response=f"Response {i}",
                expected_answer="answer",
                action_type="follow_up"
            )

        # 应该有 3 个快照
        snapshots = evaluator.get_snapshots()
        self.assertEqual(len(snapshots), 3)

        # 每个快照应该包含所有必要信息
        snapshot = snapshots[0]
        self.assertIsNotNone(snapshot.hard_scores)
        self.assertIsNotNone(snapshot.dynamic_scores)
        self.assertIsNotNone(snapshot.final_scores)

    def test_consistency_checks_detect_issues(self):
        """一致性检查应该检测问题"""
        evaluator = Evaluator()

        # 模拟矛盾情况: 高 LLM score 但低 overall
        # (这应该被 consistency check 标记)

        # ... 实现测试
```

### 3. 验证报告

**docs/task/round3/report/stage2/PHASE2_TASK2.6_EVALUATOR_STATE_REPORT.md**

包含:
- 动态评分实现摘要
- Before/After 维度更新率对比
- EvaluatorStateSnapshot 使用示例
- 一致性检查结果
- 10+ 任务的状态演化验证

## 接口定义

### 新增内部方法

```python
# 动态评分方法
def _compute_faithfulness_score(self, ...) -> float
def _compute_robustness_score(self, ...) -> float
def _compute_consistency_score(self, ...) -> float
def _compute_cross_image_confusion_score(self, ...) -> float
def _compute_disambiguation_score(self, ...) -> float

# 一致性检查
def _run_consistency_checks(self, eval_result) -> Dict[str, Any]

# Snapshot 管理
def get_snapshots(self) -> List[EvaluatorStateSnapshot]
def export_snapshots(self, filepath: str)
```

### 新增数据类

```python
@dataclass
class EvaluatorStateSnapshot:
    turn: int
    timestamp: str
    response: str
    expected_answer: str
    hard_scores: Dict[str, float]
    dynamic_scores: Dict[str, float]
    final_scores: Dict[str, float]
    overall_score: float
    # ...
```

### 配置接口

```python
class Evaluator:
    def __init__(
        self,
        # ... 现有参数 ...
        enable_snapshots: bool = False  # NEW
    )
```

## 协作要求

### 与其他任务的关系

- **独立任务**: 不依赖其他 Phase 2 任务
- **可选依赖**: Task 2.2 的 turn-level context 可以提升评估质量
- **可选依赖**: Task 2.5 的 images_sent 可以提升 faithfulness 评估

**建议**: 在 Tasks 2.2-2.5 完成后执行,以充分利用新增的 context 信息。

### 依赖的 Phase 1 报告

- **Task 1.6 报告**: [PHASE1_TASK1.6_EVALUATOR_STATE_REPORT.md](../report/PHASE1_TASK1.6_EVALUATOR_STATE_REPORT.md)
  - 维度保留率统计
  - 常量分数案例
  - 状态演化分析

## 验证标准

### 成功标准

- [ ] 所有 5 个可疑维度都有动态计算方法
- [ ] `evaluate_response()` 使用动态分数
- [ ] 默认值保留率 < 20% (从 76-79% 降低)
- [ ] `EvaluatorStateSnapshot` 实现
- [ ] 一致性检查实现
- [ ] 单元测试验证动态更新
- [ ] 10+ 任务验证分数多样性
- [ ] 完整技术报告生成

### 测试用例

**Test Case 1: Faithfulness 不是常量**
```python
results = [evaluate(...) for _ in range(5)]
faithfulness_scores = [r.faithfulness_score for r in results]
assert len(set(faithfulness_scores)) > 1  # 至少 2 个不同值
```

**Test Case 2: Robustness 在 mislead action 时更新**
```python
result = evaluate(action_type="mislead", ...)
assert result.robustness_score != 0.3  # 不是默认值
```

**Test Case 3: Consistency 检测矛盾**
```python
result = evaluate(
    response="right",
    context={"previous_responses": ["left"]}
)
assert result.consistency_score < 0.5  # 矛盾 → 低分
```

---

## 总结: Task 2.6 执行计划

### 时间线

**Day 1 (实现动态评分)**:
- 上午: 实现 faithfulness, robustness, consistency 动态计算
- 下午: 实现 cross_image_confusion, disambiguation 动态计算
- 晚上: 更新 evaluate_response() 使用动态分数

**Day 2 (Snapshot 和测试)**:
- 上午: 实现 EvaluatorStateSnapshot
- 下午: 实现一致性检查
- 晚上: 单元测试

**Day 3 (验证和报告)**:
- 上午: 运行 10+ 任务验证
- 下午: 对比 Before/After 统计
- 晚上: 生成报告

### 最终交付物检查清单

- [ ] 5个动态评分方法实现
- [ ] evaluate_response() 更新
- [ ] EvaluatorStateSnapshot 类
- [ ] 一致性检查方法
- [ ] 单元测试 (5+ cases)
- [ ] 维度保留率 < 20%
- [ ] 状态快照导出功能
- [ ] 技术报告

---

**文档创建时间**: 2026-02-03
**预计完成时间**: 3-4小时
**优先级**: P2 (中等优先级,建议在 Tasks 2.2-2.5 后执行)
