# Phase 2 Task 2.6: Evaluator State Management Report

**完成日期**: 2026-02-04
**开发者**: Claude Code
**任务状态**: ✅ 已完成并通过所有测试

---

## 执行摘要

本次开发成功完成了 Phase 2 独立组 G 的任务：**Evaluator 状态管理重构**。

### 解决的问题

Phase 1 Task 1.6 发现的核心问题：

| 维度 | 修复前默认值保留率 | 唯一值数量 | 问题 |
|------|-------------------|-----------|------|
| `robustness` | **78.8%** | 2 | 几乎是常量 |
| `consistency` | **76.1%** | 7 | 高保留率 |
| `faithfulness` | **78.8%** | 6 | 高保留率 |
| `cross_image_confusion` | **78.8%** | 3 | 高保留率 |
| `disambiguation` | **78.8%** | 2 | 几乎是常量 |

**目标**：将默认值保留率降低到 **< 20%**

### 测试结果

**20/20 单元测试全部通过** ✅

---

## 实现内容

### 1. 动态评分方法 (5个)

**位置**: [src/simulator/evaluator.py:1002-1274](../../src/simulator/evaluator.py#L1002-L1274)

#### 1.1 `_compute_faithfulness_score()`

动态计算 faithfulness 分数，检测幻觉和视觉基础：

```python
def _compute_faithfulness_score(
    self,
    response: str,
    images_sent: List[str],
    expected_answer: str,
    context: Dict[str, Any]
) -> Tuple[float, str]:
    """
    评估模型声明是否基于视觉证据。

    检测场景:
    - 没有图像但有视觉描述 → 严重幻觉 (0.0)
    - 高幻觉指示词 → 低分 (0.4)
    - 接受注入的错误信息 → 低分 (0.3)
    - 强视觉基础 → 高分 (0.9)
    """
```

**关键改进**:
- 无图像但有视觉声明 → 自动评为 0 分（之前保持默认 0.5）
- 检测幻觉指示词（"i assume", "maybe", "probably" 等）
- 检测是否接受了注入的错误信息

#### 1.2 `_compute_robustness_score()`

动态计算 robustness 分数，检测抵抗误导能力：

```python
def _compute_robustness_score(
    self,
    response: str,
    action_type: str,
    previous_responses: List[str],
    context: Dict[str, Any]
) -> Tuple[float, str]:
    """
    评估模型对误导的抵抗力。

    检测场景:
    - mislead action + 带视觉证据抵抗 → 满分 (1.0)
    - mislead action + 无证据抵抗 → 部分分数 (0.7)
    - mislead action + 接受误导 → 低分 (0.2)
    - 非 stress action + 保持正确 → 高分 (0.8)
    - 非 stress action + 矛盾先前 → 中低分 (0.4)
    """
```

**关键改进**:
- 不仅在 mislead action 时评估，非 stress action 也评估
- 区分"有视觉证据抵抗"和"无证据抵抗"

#### 1.3 `_compute_consistency_score()`

动态计算 consistency 分数，检测跨 turn 一致性：

```python
def _compute_consistency_score(
    self,
    response: str,
    previous_responses: List[str],
    context: Dict[str, Any]
) -> Tuple[float, str]:
    """
    评估模型在多个 turns 中的一致性。

    检测场景:
    - 第一个 turn → 中性分数 (0.7)
    - 发现矛盾 → 低分 (0.3 per contradiction)
    - 保持一致 → 高分 (0.9)
    """
```

**关键改进**:
- 使用 `_extract_key_claims()` 提取关键声明
- 使用 `_find_contradictions()` 检测矛盾（基于对立词对）
- 检查最近 3 个响应

#### 1.4 `_compute_cross_image_confusion_score()`

动态计算跨图混淆分数：

```python
def _compute_cross_image_confusion_score(
    self,
    response: str,
    images_sent: List[str],
    task_type: str,
    context: Dict[str, Any]
) -> Tuple[float, str]:
    """
    评估模型是否正确区分多图中的对象。

    检测场景:
    - 单图任务 → N/A (1.0)
    - 属性错误归属到其他图像 → 低分
    - 正确区分 → 高分 (0.9)
    """
```

**关键改进**:
- 检测属性与图像的接近度
- 区分正确归属和错误归属

#### 1.5 `_compute_disambiguation_score()`

动态计算歧义识别分数：

```python
def _compute_disambiguation_score(
    self,
    response: str,
    context: Dict[str, Any]
) -> Tuple[float, str]:
    """
    评估模型是否识别歧义引用。

    检测场景:
    - 识别歧义或列举选项 → 满分 (1.0)
    - 有歧义引用但未识别 → 低分 (0.3)
    - 无歧义引用 → 中性 (0.8)
    """
```

---

### 2. EvaluatorStateSnapshot 数据类

**位置**: [src/simulator/evaluator.py:27-70](../../src/simulator/evaluator.py#L27-L70)

```python
@dataclass
class EvaluatorStateSnapshot:
    """评估器状态快照 - 用于调试和验证"""
    turn: int
    timestamp: str

    # 输入
    response: str
    expected_answer: str
    action_type: str
    context: Dict[str, Any]

    # 分数
    hard_scores: Dict[str, float]
    dynamic_scores: Dict[str, float]
    llm_scores: Optional[Dict[str, float]]
    final_scores: Dict[str, float]
    overall_score: float

    # 调试信息
    dimension_updates: Dict[str, str]  # dimension -> update_reason
    consistency_checks: Dict[str, Any]
```

**功能**:
- 捕获每个 turn 的完整评估状态
- 记录每个维度更新的原因
- 支持导出为 JSON 文件

---

### 3. 一致性检查方法

**位置**: [src/simulator/evaluator.py:1995-2065](../../src/simulator/evaluator.py#L1995-L2065)

```python
def _run_consistency_checks(self, eval_result: EvaluationResult) -> Dict[str, Any]:
    """
    检测评估结果的逻辑一致性。

    检查项:
    1. high_llm_low_overall: LLM 高分但 overall 低
    2. low_faith_high_correct: 低 faithfulness 高 correctness
    3. all_defaults: 所有维度保持默认值
    4. robustness_mislead_mismatch: 高 robustness 但被误导
    5. dual_low_scores: consistency 和 robustness 同时低
    """
```

---

### 4. Snapshot 管理功能

**位置**: [src/simulator/evaluator.py:2067-2172](../../src/simulator/evaluator.py#L2067-L2172)

| 方法 | 功能 |
|------|------|
| `get_snapshots()` | 获取所有状态快照 |
| `export_snapshots(filepath)` | 导出快照到 JSON 文件 |
| `get_dimension_statistics()` | 获取各维度统计信息 |
| `get_snapshot_summary()` | 获取快照摘要 |
| `validate_dynamic_scoring()` | 验证动态评分是否正常工作 |

---

### 5. evaluate_response() 更新

**修改位置**: [src/simulator/evaluator.py:1339-1394](../../src/simulator/evaluator.py#L1339-L1394)

关键变更：

```python
# 1. Hard rule evaluation (基线)
hard_scores = self._hard_rule_evaluation(response, expected_answer, action_type)

# === Task 2.6: 动态维度评分 (总是计算) ===
images_sent = context.get("images_sent", [])
previous_responses = self.previous_responses.copy()
task_type = self.task_type

dynamic_scores = {}

# Faithfulness - 总是计算
faith_score, faith_reason = self._compute_faithfulness_score(...)
dynamic_scores["faithfulness"] = faith_score

# Robustness - 总是计算
robust_score, robust_reason = self._compute_robustness_score(...)
dynamic_scores["robustness"] = robust_score

# ... 其他维度 ...

# 使用动态分数覆盖 hard scores
for dim, score in dynamic_scores.items():
    hard_scores[dim] = score
```

---

## 单元测试

**文件**: [tests/test_evaluator_dynamics.py](../../tests/test_evaluator_dynamics.py)

### 测试覆盖

| 测试类 | 测试数量 | 状态 |
|--------|---------|------|
| TestDynamicFaithfulness | 3 | ✅ PASS |
| TestDynamicRobustness | 4 | ✅ PASS |
| TestDynamicConsistency | 3 | ✅ PASS |
| TestSnapshotFunctionality | 3 | ✅ PASS |
| TestConsistencyChecks | 1 | ✅ PASS |
| TestDimensionStatistics | 2 | ✅ PASS |
| TestCrossImageConfusion | 2 | ✅ PASS |
| TestDisambiguation | 2 | ✅ PASS |
| **Total** | **20** | ✅ **ALL PASS** |

### 关键测试用例

```python
# Test 1: Faithfulness 无图像幻觉检测
def test_faithfulness_no_images_hallucination(self):
    result = self.evaluator.evaluate_response(
        response="In the image, I can see a beautiful sunset...",
        context={"images_sent": []}  # 没有图像!
    )
    self.assertEqual(result.faithfulness_score, 0.0)

# Test 2: Robustness 带视觉证据抵抗
def test_robustness_resisted_with_evidence(self):
    self.evaluator.register_injected_falsehood("blue", "red")
    result = self.evaluator.evaluate_response(
        response="Actually, looking at the image, I can see the person is wearing red, not blue.",
        action_type="mislead"
    )
    self.assertEqual(result.robustness_score, 1.0)

# Test 3: Consistency 矛盾检测
def test_consistency_contradictory_response(self):
    # First turn: "left"
    # Second turn: "right" (矛盾!)
    result2 = self.evaluator.evaluate_response(
        response="Actually, the person is on the right side of the image."
    )
    self.assertLess(result2.consistency_score, 0.5)
```

---

## 配置接口

### 新增参数

```python
class Evaluator:
    def __init__(
        self,
        # ... 现有参数 ...
        enable_snapshots: bool = False  # NEW: 启用状态快照
    )
```

### 使用示例

```python
# 启用快照进行调试
evaluator = Evaluator(enable_snapshots=True)

# 评估一些响应
for response in responses:
    evaluator.evaluate_response(response=response, ...)

# 获取快照
snapshots = evaluator.get_snapshots()

# 导出到文件
evaluator.export_snapshots("debug_snapshots.json")

# 验证动态评分是否正常
validation = evaluator.validate_dynamic_scoring()
print(validation)
# {"status": "PASS", "message": "All dimensions have default retention rate < 20%"}

# 获取维度统计
stats = evaluator.get_dimension_statistics()
print(stats["faithfulness"]["default_retention_rate"])  # 应该 < 0.2
```

---

## 预期影响

### 修复前 vs 修复后

| 维度 | 修复前保留率 | 预期修复后保留率 | 改进 |
|------|-------------|-----------------|------|
| `faithfulness` | 78.8% | < 20% | ✅ 大幅改进 |
| `robustness` | 78.8% | < 20% | ✅ 大幅改进 |
| `consistency` | 76.1% | < 20% | ✅ 大幅改进 |
| `cross_image_confusion` | 78.8% | < 20% | ✅ 大幅改进 |
| `disambiguation` | 78.8% | < 20% | ✅ 大幅改进 |

### 评估准确性

1. **Faithfulness**: 现在会检测无图像幻觉、视觉基础强度
2. **Robustness**: 现在会在每个 turn 评估，不仅是 mislead action
3. **Consistency**: 现在会检测跨 turn 矛盾
4. **Cross-image**: 现在会检测属性错误归属
5. **Disambiguation**: 现在会检测歧义识别能力

---

## 代码变更摘要

### 修改的文件

| 文件 | 变更类型 | 行数 |
|------|---------|------|
| `src/simulator/evaluator.py` | 修改 | +450 行 |
| `tests/test_evaluator_dynamics.py` | 新建 | 430 行 |

### 新增方法

| 方法 | 说明 |
|------|------|
| `_compute_faithfulness_score()` | 动态计算 faithfulness |
| `_compute_robustness_score()` | 动态计算 robustness |
| `_compute_consistency_score()` | 动态计算 consistency |
| `_compute_cross_image_confusion_score()` | 动态计算跨图混淆 |
| `_compute_disambiguation_score()` | 动态计算歧义识别 |
| `_contains_visual_descriptions()` | 检测视觉描述 |
| `_maintains_correctness()` | 检测保持正确性 |
| `_contradicts_previous()` | 检测矛盾 |
| `_extract_key_claims()` | 提取关键声明 |
| `_find_contradictions()` | 查找矛盾 |
| `_run_consistency_checks()` | 运行一致性检查 |
| `get_snapshots()` | 获取快照 |
| `export_snapshots()` | 导出快照 |
| `get_dimension_statistics()` | 获取维度统计 |
| `get_snapshot_summary()` | 获取快照摘要 |
| `validate_dynamic_scoring()` | 验证动态评分 |
| `_std()` | 计算标准差 |

### 新增数据类

| 类 | 说明 |
|---|------|
| `EvaluatorStateSnapshot` | 评估器状态快照 |

---

## 验证清单

### 成功标准

- [x] 所有 5 个可疑维度都有动态计算方法
- [x] `evaluate_response()` 使用动态分数
- [x] 预期默认值保留率 < 20%（通过动态评分实现）
- [x] `EvaluatorStateSnapshot` 实现
- [x] 一致性检查实现
- [x] 单元测试验证动态更新（20 个测试全部通过）
- [x] 完整技术报告生成

### Phase 3 验证准备

Task 3.6 将验证：
- 同一任务内对同一物体的判断一致性 >= 95%
- 所有维度分数的动态范围 > 0.3（不能是常数）
- 默认值保留率 < 20%（大部分应该被更新）

---

## 总结

Task 2.6 的实现成功解决了 Phase 1 中发现的评估器状态管理问题：

1. ✅ **动态评分**: 所有 5 个可疑维度现在都有专门的动态计算方法
2. ✅ **状态快照**: 实现了 `EvaluatorStateSnapshot` 用于调试和验证
3. ✅ **一致性检查**: 实现了 5 种一致性检查检测逻辑问题
4. ✅ **验证工具**: 实现了 `validate_dynamic_scoring()` 验证动态评分是否正常工作

所有代码已完成并通过 20 个单元测试，可以立即投入使用。

---

**报告生成时间**: 2026-02-04
**作者**: Claude Code
**状态**: ✅ 任务完成
