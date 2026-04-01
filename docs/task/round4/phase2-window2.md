# Phase 2 Window 2: Prompt 与图像数量匹配修复

**任务编号**: ROUND4-P2-W2
**预计时间**: 2 小时
**依赖**: Phase 1 完成
**优先级**: P1 - HIGH
**可并行**: 与 Window 1, 3, 4 完全并行

---

## 任务目标

修复评审报告 3.1 问题：发送 3 张图但 prompt 说 "both images"。

**问题**: Round 3 Task 2.5 统一了图像发送策略，但 prompt 生成逻辑没有根据实际发送数量调整用词。

---

## 背景信息

### 评审发现
- 每轮都发 3 张图
- 但 prompt 写 "both images"（both 表示 2 张，不匹配）

### Round 3 Task 2.5 做了什么
- 统一了图像注入策略（`ImageInjectionPolicy.SEND_ALL_EVERY_TURN`）
- 确保每个 turn 发送的图像数量一致
- **但遗漏了**：prompt 生成逻辑没有根据实际图像数量调整用词

### 正确行为
- 1 张图 → "the image"
- 2 张图 → "both images"
- 3+ 张图 → "all 3 images" / "all {count} images"

---

## 任务详细要求

### 1. 找到 Prompt 生成位置

**可能的位置**:
- `src/simulator/strategic_simulator.py` - `_generate_next_question()` 方法
- `src/simulator/query_generator.py` - 如果有独立的 query generator
- `src/simulator/llm_user_simulator.py` - 如果使用 LLM 生成问题

**操作**:
使用 Grep 搜索关键词：
```bash
pattern: "both images"
pattern: "the image"
pattern: "generate.*question"
```

### 2. 实现图像引用词生成函数

**新增辅助函数**:

**文件**: `src/simulator/strategic_simulator.py` 或 `src/simulator/utils.py`

```python
def get_image_reference_phrase(image_count: int) -> str:
    """
    根据图像数量返回合适的引用词

    Args:
        image_count: 发送的图像数量

    Returns:
        合适的引用词

    Examples:
        >>> get_image_reference_phrase(1)
        'the image'
        >>> get_image_reference_phrase(2)
        'both images'
        >>> get_image_reference_phrase(3)
        'all 3 images'
    """
    if image_count == 0:
        logger.warning("[Image Reference] No images, but trying to generate image reference phrase")
        return "the visual content"  # Fallback

    elif image_count == 1:
        return "the image"

    elif image_count == 2:
        return "both images"

    else:
        return f"all {image_count} images"
```

### 3. 修改 Prompt 生成逻辑

#### 3.1 找到所有硬编码"both images"的地方

**操作**: Grep 搜索 `"both images"` 或 `"the image"`

**替换**:
```python
# Before (硬编码)
question = f"Looking at both images, which person is taller?"

# After (动态生成)
images_sent_count = len(images_to_send)
image_ref = get_image_reference_phrase(images_sent_count)
question = f"Looking at {image_ref}, which person is taller?"
```

#### 3.2 如果使用模板字符串

**Before**:
```python
prompt_template = "Looking at both images, can you identify {target}?"
```

**After**:
```python
# 添加 image_reference 作为模板变量
prompt_template = "Looking at {image_reference}, can you identify {target}?"

# 生成时填充
images_sent_count = len(images_to_send)
prompt = prompt_template.format(
    image_reference=get_image_reference_phrase(images_sent_count),
    target="the person"
)
```

#### 3.3 如果使用 LLM 生成问题

如果问题是由 LLM 动态生成的，需要在生成时提供正确的图像数量信息：

```python
def _generate_question_with_llm(self, images_to_send: List[str], ...):
    """使用 LLM 生成问题"""
    images_sent_count = len(images_to_send)
    image_ref = get_image_reference_phrase(images_sent_count)

    llm_prompt = f"""
Generate a question for the model.

Context:
- There are {images_sent_count} images.
- Use the phrase "{image_ref}" when referring to the images.

Example:
"Looking at {image_ref}, can you identify..."

Generate the question:
"""

    return self.llm_client.generate(llm_prompt)
```

### 4. 修改 AC 任务特定逻辑

**文件**: `src/data/task_generators.py` 或类似的任务生成器

Attribute Comparison 任务通常涉及多图，需要特别检查：

```python
def generate_ac_task_question(images: List[str], ...):
    """生成 AC 任务的问题"""
    image_count = len(images)
    image_ref = get_image_reference_phrase(image_count)

    # 生成比较问题
    question = f"Looking at {image_ref}, which image shows a larger {attribute}?"

    return question
```

---

## 接口定义

### 输入
- Phase 1 的验证报告（确认问题存在）
- 当前代码库

### 输出

#### 修改的文件
1. `src/simulator/strategic_simulator.py` 或 `src/simulator/utils.py` - 新增 `get_image_reference_phrase()`
2. 所有包含硬编码 "both images" / "the image" 的文件 - 修改为动态生成

#### 文档
- `docs/task/round4/phase2_fix2.1_report.md`

---

## 协作要求

### 与其他 Window 的关系

**独立性**: 高度独立
- 只修改 prompt 生成逻辑，不影响其他模块

**无冲突**:
- 与 Window 1（评估框架）、Window 3（Evaluator 一致性）、Window 4（Consistency check）无代码冲突

---

## 当前进度

- [ ] 搜索所有 "both images" 位置
- [ ] 搜索所有 "the image" 位置
- [ ] 实现 `get_image_reference_phrase()` 函数
- [ ] 修改 strategic_simulator.py
- [ ] 修改 task_generators.py（如果有）
- [ ] 修改 query_generator.py（如果有）
- [ ] 修改 llm_user_simulator.py（如果有）
- [ ] 添加单元测试
- [ ] 集成测试（运行 AC 任务验证）
- [ ] 生成修复报告
- [ ] 完成

---

## 验证标准

### Must Have
1. ✅ 所有硬编码的 "both images" 都被替换
2. ✅ 运行 AC 任务（3 张图），检查 prompt 包含 "all 3 images"
3. ✅ 运行单图任务，检查 prompt 包含 "the image"
4. ✅ 运行双图任务，检查 prompt 包含 "both images"

### Nice to Have
1. 单元测试覆盖 0, 1, 2, 3, 10 张图的情况
2. 支持中文（"这张图" / "这两张图" / "这 3 张图"）

---

## 测试方法

### 单元测试

**文件**: `tests/test_image_reference_phrase.py`

```python
def test_get_image_reference_phrase():
    """测试图像引用词生成"""
    assert get_image_reference_phrase(0) == "the visual content"  # Fallback
    assert get_image_reference_phrase(1) == "the image"
    assert get_image_reference_phrase(2) == "both images"
    assert get_image_reference_phrase(3) == "all 3 images"
    assert get_image_reference_phrase(10) == "all 10 images"

def test_prompt_generation_with_dynamic_image_ref():
    """测试 prompt 生成使用动态图像引用"""
    simulator = StrategicSimulator()

    # 3 张图的任务
    task = {
        "images": ["img1.jpg", "img2.jpg", "img3.jpg"],
        # ...
    }

    simulator.start_task(task)
    question = simulator._generate_next_question(...)

    # 验证 prompt
    assert "all 3 images" in question.lower()
    assert "both images" not in question.lower()  # 不应该出现
```

### 集成测试

**脚本**: `scripts/round4_test_fix2.1.py`

```python
# 运行 AC 任务（3 张图）
ac_task = {
    "task_id": "test_ac_3_images",
    "images": ["img1.jpg", "img2.jpg", "img3.jpg"],
    # ...
}

simulator = StrategicSimulator()
simulator.start_task(ac_task)
simulator.step()

# 检查第一个 turn 的问题
run_log = simulator.get_run_log()
turn_1 = run_log["turns"][0]

print(f"Turn 1 question: {turn_1['question']}")
assert "all 3 images" in turn_1["question"].lower(), "❌ Prompt 应该包含 'all 3 images'"
print("✅ Prompt 正确使用 'all 3 images'")
```

---

## 交付物清单

- [ ] 修改后的 `src/simulator/strategic_simulator.py` 或 `src/simulator/utils.py`
- [ ] 修改后的其他 prompt 生成文件
- [ ] 单元测试文件 `tests/test_image_reference_phrase.py`
- [ ] 集成测试脚本 `scripts/round4_test_fix2.1.py`
- [ ] 修复报告 `docs/task/round4/phase2_fix2.1_report.md`

---

## 修复报告模板

**文件**: `docs/task/round4/phase2_fix2.1_report.md`

```markdown
# Phase 2 修复 2.1: Prompt 与图像数量匹配

## 问题描述
评审报告 3.1：发送 3 张图但 prompt 说 "both images"

## 修复内容

### 1. 新增函数
- `get_image_reference_phrase(image_count)` - 根据图像数量生成引用词

### 2. 修改文件
| 文件 | 修改位置 | 修改内容 |
|-----|---------|---------|
| src/simulator/strategic_simulator.py | 行 X | 硬编码 "both images" → 动态生成 |
| src/data/task_generators.py | 行 Y | AC 任务问题生成 |
| ... | ... | ... |

### 3. 测试结果
- ✅ 单图任务: "the image"
- ✅ 双图任务: "both images"
- ✅ 三图任务: "all 3 images"

## 示例对比

### 修复前
```
Question: "Looking at both images, which person is taller?"
Images sent: [img1, img2, img3]  # ❌ 3 张图但说"both"
```

### 修复后
```
Question: "Looking at all 3 images, which person is taller?"
Images sent: [img1, img2, img3]  # ✓ 匹配
```

## 影响评估
- 破坏性: 无（只改 prompt 内容，不改逻辑）
- 向后兼容: 是（旧任务重新运行时会自动使用新逻辑）
```

---

## 注意事项

1. **全面搜索**: 不只是 "both images"，也要搜索 "the image"
2. **模板字符串**: 检查是否有模板文件（.txt, .yaml）也包含硬编码
3. **多语言**: 如果支持中文，也要修改中文版本
4. **日志输出**: 修改后添加日志，方便调试

---

**任务开始时间**: _____________
**任务完成时间**: _____________
**执行人**: _____________
