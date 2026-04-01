# Phase 2 Window 3: Evaluator 视觉判断一致性修复

**任务编号**: ROUND4-P2-W3
**预计时间**: 2-3 小时
**依赖**: Phase 1 完成
**优先级**: P1 - HIGH
**可并行**: 与 Window 1, 2, 4 完全并行

---

## 任务目标

修复评审报告 4.1 问题：Evaluator 对同一张图中对象的视觉判断前后矛盾。

**问题**: LLM Judge 每次都独立判断，没有记忆。同一张图在不同 turn 可能给出不同的空间关系判断（例如 knife 位置）。

---

## 背景信息

### 评审发现
同一任务中，对同一对象（如 knife）的位置判断前后矛盾：
- Turn 1: "knife 在右侧"
- Turn 3: "knife 在左侧"（矛盾！）

### Round 3 遗漏的问题
Task 2.6 只检测**模型响应**的矛盾，没有检测**Evaluator自己判断**的矛盾。

---

## 任务详细要求

### 1. 实现视觉事实缓存

**文件**: `src/simulator/evaluator.py`

**在 Evaluator.__init__() 中添加**:
```python
class Evaluator:
    def __init__(self, ...):
        # ... 现有代码 ...

        # NEW: 视觉事实缓存
        self.visual_fact_cache: Dict[Tuple[str, str, str], Any] = {}
        # Key: (task_id, object_name, attribute)
        # Value: 缓存的判断值
        # 例如: ("task_123", "knife", "position") -> "right side"
```

### 2. 实现缓存和一致性检查方法

```python
def _cache_visual_fact(
    self,
    task_id: str,
    object_name: str,
    attribute: str,
    value: Any,
    turn_id: int
) -> Any:
    """
    缓存视觉事实判断，并检测矛盾

    Args:
        task_id: 任务 ID
        object_name: 对象名称（例如 "knife", "person"）
        attribute: 属性名称（例如 "position", "color"）
        value: 判断值
        turn_id: 当前 turn ID

    Returns:
        应该使用的值（缓存的或新的）
    """
    key = (task_id, object_name, attribute)

    if key in self.visual_fact_cache:
        cached_value = self.visual_fact_cache[key]

        # 检测冲突
        if cached_value != value and not self._are_values_compatible(cached_value, value):
            logger.warning(
                f"[Evaluator Consistency Warning] Visual fact conflict detected!\n"
                f"  Task: {task_id}, Turn: {turn_id}\n"
                f"  Object: {object_name}, Attribute: {attribute}\n"
                f"  Cached: {cached_value} (from previous turn)\n"
                f"  New: {value} (current turn)\n"
                f"  → Using cached value to maintain consistency."
            )

            # 记录到 inconsistencies
            self.detected_inconsistencies.append({
                "task_id": task_id,
                "turn_id": turn_id,
                "object": object_name,
                "attribute": attribute,
                "cached": cached_value,
                "new": value,
                "resolution": "used_cached"
            })

            # 返回缓存的值，保持一致性
            return cached_value
        else:
            # 值相同或兼容，更新缓存
            self.visual_fact_cache[key] = value
            return value
    else:
        # 第一次判断，直接缓存
        self.visual_fact_cache[key] = value
        logger.debug(f"[Evaluator] Cached visual fact: {object_name}.{attribute} = {value}")
        return value

def _are_values_compatible(self, value1: Any, value2: Any) -> bool:
    """
    判断两个值是否兼容（语义上相似）

    例如：
    - "right side" 和 "on the right" 是兼容的
    - "left" 和 "right" 是不兼容的
    """
    # 简单实现：字符串相似度
    if isinstance(value1, str) and isinstance(value2, str):
        v1 = value1.lower().strip()
        v2 = value2.lower().strip()

        # 完全相同
        if v1 == v2:
            return True

        # 包含关系
        if v1 in v2 or v2 in v1:
            return True

        # 对立词检查
        opposites = [
            ("left", "right"),
            ("top", "bottom"),
            ("above", "below"),
            ("front", "back"),
            ("near", "far")
        ]
        for word1, word2 in opposites:
            if (word1 in v1 and word2 in v2) or (word2 in v1 and word1 in v2):
                return False  # 对立，不兼容

        # 默认认为兼容
        return True

    return value1 == value2
```

### 3. 集成到评估流程

**在 evaluate_response() 或 LLM Judge 相关方法中**:

如果 LLM Judge 返回了视觉判断（例如在 reasoning 中提到对象位置），提取并缓存：

```python
def evaluate_response(self, ...):
    # ... 现有逻辑 ...

    # 调用 LLM Judge
    llm_result = self._call_llm_judge(...)

    # 提取视觉判断（如果有）
    if "reasoning" in llm_result:
        visual_facts = self._extract_visual_facts_from_reasoning(
            llm_result["reasoning"],
            context.get("task_id"),
            context.get("turn_id")
        )

        # 缓存并检查一致性
        for fact in visual_facts:
            cached_value = self._cache_visual_fact(
                task_id=context["task_id"],
                object_name=fact["object"],
                attribute=fact["attribute"],
                value=fact["value"],
                turn_id=context["turn_id"]
            )

            # 如果值被修改（因为不一致），更新评估结果
            if cached_value != fact["value"]:
                logger.info(
                    f"[Evaluator] Adjusted visual fact to maintain consistency: "
                    f"{fact['object']}.{fact['attribute']} = {cached_value}"
                )

    # ... 返回结果 ...
```

### 4. 实现视觉事实提取（简单版）

```python
def _extract_visual_facts_from_reasoning(
    self,
    reasoning: str,
    task_id: str,
    turn_id: int
) -> List[Dict[str, Any]]:
    """
    从 LLM Judge 的 reasoning 中提取视觉判断

    简单实现：正则表达式匹配常见模式

    Returns:
        List of {"object": str, "attribute": str, "value": str}
    """
    facts = []

    # 模式 1: "the <object> is <position>"
    pattern1 = r'the\s+(\w+)\s+is\s+(on\s+the\s+\w+|at\s+the\s+\w+|\w+\s+side)'
    matches = re.finditer(pattern1, reasoning, re.IGNORECASE)
    for match in matches:
        facts.append({
            "object": match.group(1),
            "attribute": "position",
            "value": match.group(2)
        })

    # 模式 2: "knife on the right" / "person on the left"
    pattern2 = r'(\w+)\s+on\s+the\s+(\w+)'
    matches = re.finditer(pattern2, reasoning, re.IGNORECASE)
    for match in matches:
        facts.append({
            "object": match.group(1),
            "attribute": "position",
            "value": f"on the {match.group(2)}"
        })

    return facts
```

---

## 接口定义

### 输入
- Phase 1 验证报告
- 当前代码库

### 输出

#### 修改的文件
- `src/simulator/evaluator.py` - 添加缓存和一致性检查

#### 文档
- `docs/task/round4/phase2_fix2.2_report.md`

---

## 协作要求

**独立性**: 高
- 只修改 Evaluator 内部逻辑

**潜在冲突**: 与 Window 1（如果也修改 Evaluator）
- 建议先沟通，避免同时修改同一方法

---

## 验证标准

### Must Have
1. ✅ 运行包含多个 turn 的任务
2. ✅ 检查 evaluator 日志，有 consistency warning
3. ✅ 检查 `detected_inconsistencies` 列表非空（如果有矛盾）

### Nice to Have
1. 更智能的视觉事实提取（使用 LLM）
2. 可视化不一致性报告

---

## 测试方法

**集成测试脚本**: `scripts/round4_test_fix2.2.py`

```python
# 构造一个会导致 evaluator 矛盾的任务
# （例如，重复问同一对象位置）

simulator = StrategicSimulator()
simulator.start_task(test_task)

# 运行多个 turn
for _ in range(5):
    simulator.step()

# 检查 evaluator 的不一致性检测
inconsistencies = simulator.evaluator.detected_inconsistencies

if inconsistencies:
    print(f"✅ 检测到 {len(inconsistencies)} 个不一致性")
    for inc in inconsistencies:
        print(f"  - Turn {inc['turn_id']}: {inc['object']}.{inc['attribute']} "
              f"(cached={inc['cached']}, new={inc['new']})")
else:
    print("⚠️ 未检测到不一致性（可能是好事，或测试数据不足）")
```

---

## 交付物清单

- [ ] 修改后的 `src/simulator/evaluator.py`
- [ ] 测试脚本 `scripts/round4_test_fix2.2.py`
- [ ] 修复报告 `docs/task/round4/phase2_fix2.2_report.md`

---

**任务开始时间**: _____________
**任务完成时间**: _____________
**执行人**: _____________
