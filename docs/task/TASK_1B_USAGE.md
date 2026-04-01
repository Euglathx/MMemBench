# Task 1B: 文本提示最小化 - 使用指南

## 功能概述

Task 1B 实现了文本提示的自动清洗功能，减少 user simulator 在测试多模态模型时提供的视觉描述，确保真正测试模型的视觉理解能力而非文本理解能力。

## 实现的功能

### 1. 在 StrategicSimulator 中添加了两个新参数

- `minimize_text_hints` (bool): 是否启用文本提示最小化，默认 `True`
- `hint_level` (str): 提示级别，可选值：
  - `"minimal"`: 最小化提示，只保留图像引用（如"Image 1"）
  - `"moderate"`: 中等提示，保留基本结构但移除具体属性
  - `"full"`: 完整提示，保留所有视觉描述（用于基线测试）

### 2. 核心方法

`_sanitize_message_for_target(message, images, action_type)`: 清洗消息中的视觉描述

**清洗规则：**

- 移除详细的视觉描述（如 "showing", "wearing", "positioned"）
- 移除颜色和属性（如 "red helmet" → "helmet"）
- 移除空间位置描述（如 "on the left" → "on one side"）
- **特殊情况**: guidance 动作保留空间术语（因为需要引导注意力）

### 3. 效果验证

使用真实场景测试：
- **原始消息**: 243 字符, 43 单词, 9 个视觉词汇
- **清洗后消息** (minimal): 97 字符, 18 单词, 1 个视觉词汇
- **减少率**:
  - 字符减少 60.1%
  - 视觉词汇减少 88.9%

## 使用方法

### 基本用法

```python
from src.simulator.strategic_simulator import StrategicSimulator

# 创建启用文本提示最小化的 simulator (推荐用于测试多模态模型)
simulator = StrategicSimulator(
    minimize_text_hints=True,
    hint_level="minimal",  # 最小化提示
    verbose=True
)

# 运行任务
task = {
    "task_id": "test_001",
    "task_type": "attribute_comparison",
    "question": "Which image shows more people?",
    "answer": "Image 0",
    "images": ["path/to/image1.jpg", "path/to/image2.jpg"]
}

result = simulator.run_task(task)
```

### 不同场景的配置

#### 1. 测试多模态模型（默认推荐）

```python
simulator = StrategicSimulator(
    minimize_text_hints=True,
    hint_level="minimal"
)
```

这是最严格的设置，确保模型无法通过文本提示回答问题，必须依赖视觉信息。

#### 2. 测试时保留部分提示

```python
simulator = StrategicSimulator(
    minimize_text_hints=True,
    hint_level="moderate"
)
```

保留基本结构但移除具体属性（颜色、尺寸等），适用于需要一些上下文的任务。

#### 3. 基线测试（文本模型）

```python
simulator = StrategicSimulator(
    minimize_text_hints=True,
    hint_level="full"
)
# 或者
simulator = StrategicSimulator(
    minimize_text_hints=False  # 完全不清洗
)
```

保留所有文本描述，用于测试纯文本模型的基线性能。

## 验证工具

### 1. 测试 Sanitization 功能

```bash
python tools/test_sanitization.py
```

这会运行一系列测试用例，验证：
- 不同 hint level 的清洗效果
- Guidance 动作的特殊处理
- 视觉词汇的减少率

### 2. 检查日志中的文本提示

```bash
# 检查单个日志文件
python tools/check_text_hints.py test_output/run_log_20240101.json

# 对比多个日志文件
python tools/check_text_hints.py test_output/minimal/*.json test_output/full/*.json
```

**输出示例：**
```
======================================================================
Log: run_log_20240101_120000.json
======================================================================
Total user turns: 15
Total visual words: 12
Total words: 245
Avg visual words/turn: 0.80
Avg words/turn: 16.33
Visual word ratio: 4.90%

Category Breakdown:
  spatial_terms       :   5
  colors              :   4
  descriptive_verbs   :   3

======================================================================
Target: <2 visual words/turn
Status: ✓ PASS
======================================================================
```

## 实际效果对比

### 示例 1: 详细视觉描述

**原始消息：**
```
Here is an image showing a person on a motorcycle wearing a red helmet,
with another person standing near a bicycle in the background.
```

**Minimal 清洗后：**
```
Here is an image.
```

**Moderate 清洗后：**
```
Here is an image showing a person on a motorcycle wearing a helmet,
with another person standing near a bicycle in the background.
```

### 示例 2: 空间和颜色描述

**原始消息：**
```
Look at the red car on the left and the blue bike on the right.
```

**Minimal 清洗后：**
```
Look at the car on one side and the bike on one side.
```

**Moderate 清洗后：**
```
Look at the car on one side and the bike on one side.
```

### 示例 3: Guidance 动作（特殊处理）

**原始消息：**
```
Please focus on the left side of the image.
```

**Minimal 清洗后 (action_type="guidance")：**
```
Please focus on the left side of the image.
```
*保留了空间术语，因为 guidance 需要引导注意力*

**Minimal 清洗后 (action_type="follow_up")：**
```
Please focus on one side of the image.
```

## 集成到实验流程

在实验脚本中使用：

```python
# 实验配置
experiment_config = {
    "multimodal_model_test": {
        "minimize_text_hints": True,
        "hint_level": "minimal"
    },
    "text_baseline_test": {
        "minimize_text_hints": False,
        "hint_level": "full"
    }
}

# 运行多模态模型测试
simulator_mm = StrategicSimulator(**experiment_config["multimodal_model_test"])
mm_results = simulator_mm.run_task(task)

# 运行文本基线测试
simulator_text = StrategicSimulator(**experiment_config["text_baseline_test"])
text_results = simulator_text.run_task(task)

# 对比结果
print(f"Multimodal score: {mm_results['scores']['aggregate']}")
print(f"Text baseline score: {text_results['scores']['aggregate']}")
print(f"Visual dependency: {mm_results['scores']['aggregate'] - text_results['scores']['aggregate']}")
```

## 预期效果

- **多模态模型**: 分数应保持稳定（因为有图像）
- **文本模型**: 分数应显著下降（无法靠文本作弊）
- **分数差异**: 可以衡量任务对视觉信息的依赖程度

## 故障排除

### 问题 1: Sanitization 后消息太短

**现象**: 消息被过度清洗，模型无法理解问题

**解决方案**: 使用 `hint_level="moderate"` 或针对特定任务类型调整

### 问题 2: 某些任务类型需要空间描述

**现象**: 某些推理任务需要空间关系提示

**解决方案**:
```python
# 为特定任务类型使用不同的 hint level
if task_type in ["spatial_reasoning", "position_comparison"]:
    hint_level = "moderate"
else:
    hint_level = "minimal"
```

### 问题 3: Guidance 动作不起作用

**现象**: Guidance 消息中的空间术语被移除

**解决方案**: 确保 `action_type="guidance"` 被正确传递给 `_sanitize_message_for_target()`

## 相关文件

- **核心实现**: [src/simulator/strategic_simulator.py](../src/simulator/strategic_simulator.py)
  - `_sanitize_message_for_target()` 方法（第1540行左右）
  - `step()` 方法集成（第738行左右）

- **测试工具**:
  - [tools/test_sanitization.py](../tools/test_sanitization.py): 功能测试
  - [tools/check_text_hints.py](../tools/check_text_hints.py): 日志分析

- **任务说明**: [task/task_1b_text_hints.md](./task_1b_text_hints.md)

## 下一步

完成 Task 1B 后，建议：

1. ✓ 运行 `python tools/test_sanitization.py` 验证功能
2. ✓ 使用 `hint_level="minimal"` 进行实验
3. ⏭ 使用 `tools/check_text_hints.py` 分析实验日志
4. ⏭ 对比多模态模型和文本基线的分数差异
5. ⏭ 根据结果调整 sanitization 规则（如有需要）

---

**实现完成日期**: 2026-02-01
**任务状态**: ✅ 已完成
