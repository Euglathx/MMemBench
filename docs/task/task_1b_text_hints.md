# Task 1B: 减少User Simulator的文本提示

## 任务优先级
**P0 - Week 1 Day 2-3**

## 可以并行
✅ 可以与 Task 1A (解析修复) 同时进行
✅ 可以与 Task 1C (截断修复) 同时进行

## 任务目标
减少user simulator在测试多模态模型时提供的文本描述，避免非多模态模型仅靠文本就能回答问题，确保真正测试视觉理解能力。

---

## 问题现状

### 当前问题示例
查看 `simulator_test_log/run_log_*.json` 中的对话：

**User simulator发送**:
```
"Here is an image showing a person on a motorcycle wearing a red helmet,
with another person standing near a bicycle in the background.
The motorcycle rider is in the foreground..."
```

**问题**: 非多模态模型看到这段文字就能回答"What color is the helmet?"，无需看图。

### 根本原因
1. `llm_user_simulator.py` 在构建prompt时会添加详细的图像描述
2. 这些描述作为"context"帮助user simulator理解任务
3. 但同时也泄露给了target model太多信息

### 量化指标
- **当前**: User messages平均包含 50-100 words的图像描述
- **目标**: User messages只包含 <10 words的图像引用（如"Image 1", "这张图片"）

---

## 需要修改的文件

### 文件1: `src/simulator/llm_user_simulator.py`

#### 位置: Line 311 附近
**需要查找的代码模式**:
```python
# 构建user prompt时添加图像描述的部分
raw_query = parsed.get("query", parsed.get("message_to_model", "请继续。"))
```

**需要添加的功能**:

```python
class LLMUserSimulator:
    def __init__(
        self,
        llm_client: LLMClient,
        minimize_text_hints: bool = True,  # NEW parameter
        hint_level: str = "minimal",       # NEW: "minimal" | "moderate" | "full"
    ):
        """
        Args:
            minimize_text_hints: If True, reduce image descriptions in messages
            hint_level:
                - "minimal": Only image IDs (e.g., "Image 1")
                - "moderate": Brief mentions (e.g., "the first image")
                - "full": Detailed descriptions (for text-only model testing)
        """
        self.minimize_text_hints = minimize_text_hints
        self.hint_level = hint_level
        # ... existing code

    def _sanitize_message_for_target(self, message: str, images: List[str]) -> str:
        """
        Remove or reduce visual descriptions from user message.

        Args:
            message: Original message from core model
            images: List of image paths being sent

        Returns:
            Sanitized message with minimal text hints
        """
        if not self.minimize_text_hints:
            return message  # Full descriptions allowed

        # Patterns to remove/replace
        visual_description_patterns = [
            # Detailed descriptions
            r"showing [\w\s,]+",
            r"wearing [\w\s,]+",
            r"with [\w\s,]+ in the background",
            r"in the foreground",
            r"positioned [\w\s,]+",
            # Color/attribute mentions
            r"red helmet", r"blue shirt", r"green car",
            # Spatial descriptions
            r"on the left", r"on the right", r"in the center",
        ]

        sanitized = message

        if self.hint_level == "minimal":
            # Remove all visual descriptions
            for pattern in visual_description_patterns:
                sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

            # Replace detailed references with generic ones
            sanitized = re.sub(
                r"(the|this|that) (image|picture|photo) (showing|of|with) [^.]+",
                r"\1 \2",
                sanitized,
                flags=re.IGNORECASE
            )

        elif self.hint_level == "moderate":
            # Keep basic structure, remove specific attributes
            for pattern in visual_description_patterns[4:]:  # Only remove colors/spatial
                sanitized = re.sub(pattern, "something", sanitized, flags=re.IGNORECASE)

        # Clean up multiple spaces
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        return sanitized
```

#### 在发送消息处调用
```python
def generate_query(...):
    # ... existing code to get message from core model ...

    # Sanitize message before sending to target
    if hasattr(self, 'minimize_text_hints') and self.minimize_text_hints:
        raw_query = self._sanitize_message_for_target(raw_query, images)

    return raw_query
```

---

## 接口定义

### 新增初始化参数
```python
LLMUserSimulator(
    llm_client=client,
    minimize_text_hints=True,   # NEW: Enable sanitization
    hint_level="minimal"         # NEW: Control level
)
```

### 新增方法签名
```python
def _sanitize_message_for_target(
    self,
    message: str,
    images: List[str]
) -> str:
    """Remove visual descriptions from user message."""
    pass
```

### 配置文件更新
需要在配置文件中添加（如 `config/multimodal.yaml` 或 `run_experiment.py` 参数）:

```yaml
# config/simulator.yaml (新建或更新)
user_simulator:
  minimize_text_hints: true
  hint_level: "minimal"  # minimal | moderate | full

  # For different test scenarios
  test_multimodal_model:
    hint_level: "minimal"   # Force visual understanding

  test_text_only_baseline:
    hint_level: "full"      # Allow text descriptions for baseline
```

---

## 测试验证

### 验证脚本 A: 文本长度检查
```python
# tools/check_text_hints.py
import json
import re
from pathlib import Path

def count_visual_words(message: str) -> int:
    """Count words that describe visual content."""
    visual_patterns = [
        r'\b(wearing|showing|positioned|colored|located)\b',
        r'\b(left|right|center|top|bottom|foreground|background)\b',
        r'\b(red|blue|green|yellow|black|white)\b',
    ]
    count = 0
    for pattern in visual_patterns:
        count += len(re.findall(pattern, message, re.IGNORECASE))
    return count

def analyze_log(log_path: Path):
    with open(log_path) as f:
        events = json.load(f)

    user_messages = [
        e for e in events
        if e.get('event') == 'core_model_decision'
    ]

    total_visual_words = 0
    for msg in user_messages:
        text = msg.get('message_to_model', '')
        total_visual_words += count_visual_words(text)

    avg_per_turn = total_visual_words / len(user_messages) if user_messages else 0

    print(f"Log: {log_path.name}")
    print(f"  Total user turns: {len(user_messages)}")
    print(f"  Total visual words: {total_visual_words}")
    print(f"  Avg visual words/turn: {avg_per_turn:.2f}")
    print(f"  Target: <2 words/turn")
    print(f"  Status: {'✓ PASS' if avg_per_turn < 2 else '✗ FAIL'}")

if __name__ == "__main__":
    import sys
    analyze_log(Path(sys.argv[1]))
```

运行:
```bash
python tools/check_text_hints.py test_output/task_1b/run_log_*.json
```

### 验证脚本 B: 对比测试
```bash
# Test with minimized hints
python run_experiment.py \
  --model gpt-4o \
  --task-file generated_tasks_v2/run_18/tasks/attribute_comparison_mscoco14.jsonl \
  --num-tasks 3 \
  --minimize-text-hints \
  --hint-level minimal \
  --output-dir test_output/task_1b_minimal

# Test with full hints (baseline)
python run_experiment.py \
  --model gpt-4o \
  --task-file generated_tasks_v2/run_18/tasks/attribute_comparison_mscoco14.jsonl \
  --num-tasks 3 \
  --hint-level full \
  --output-dir test_output/task_1b_full

# Compare logs
diff test_output/task_1b_minimal/run_log_*.json \
     test_output/task_1b_full/run_log_*.json
```

### 成功标准
- [ ] User messages中平均视觉描述词 <2个/turn
- [ ] 对比日志显示minimal版本明显减少描述性文本
- [ ] 多模态模型仍能正常回答（说明图像信息充足）
- [ ] 非多模态模型得分显著下降（<0.3，说明无法靠文本作弊）

---

## 协作要求

### 对其他任务的影响
**Task 2 (评估系统)**:
- ⚠️ 本任务完成后，需要重新测试评估基准
- 预期非多模态模型得分会下降（这是好事）

**Task 1A (解析修复)**: 无影响，完全独立

### 需要其他任务提供
✅ **Task 1A**: 如果同时进行，建议等1A完成后再测试，避免parse error干扰

### 提供给其他任务
✅ **所有后续任务**: 更清洁的测试环境，真正测试视觉能力

---

## 实现建议

### 开发步骤
1. **Day 2 上午**:
   - 添加 `minimize_text_hints` 和 `hint_level` 参数
   - 实现 `_sanitize_message_for_target()` 基础版本

2. **Day 2 下午**:
   - 编写 `check_text_hints.py` 验证脚本
   - 测试sanitization效果

3. **Day 3 上午**:
   - 优化sanitization规则（根据实际日志调整正则）
   - 添加配置文件支持

4. **Day 3 下午**:
   - 运行对比测试（minimal vs full）
   - 验证多模态模型仍能正常工作

### 调试技巧

1. **保留原始消息对比**:
```python
def _sanitize_message_for_target(self, message: str, images: List[str]) -> str:
    sanitized = # ... sanitization logic ...

    # Debug logging
    logger.debug(f"Original: {message}")
    logger.debug(f"Sanitized: {sanitized}")
    logger.debug(f"Removed {len(message) - len(sanitized)} characters")

    return sanitized
```

2. **渐进式测试**:
- 先用 `hint_level="moderate"` 测试
- 确认模型仍能工作
- 再切换到 `hint_level="minimal"`

3. **不同任务类型测试**:
```bash
# Attribute comparison - should work with minimal hints
--task-file .../attribute_comparison_*.jsonl

# Reasoning tasks - might need moderate hints
--task-file .../attribute_bridge_reasoning_*.jsonl
```

---

## 边界情况处理

### 情况1: Guidance动作
**问题**: Guidance动作本来就是要引导注意力，可能需要一些描述

**解决方案**:
```python
def _sanitize_message_for_target(self, message: str, images: List[str], action_type: str = None) -> str:
    # Guidance actions允许简单的空间引用
    if action_type == "guidance":
        # 允许: "Look at the left side"
        # 移除: "Look at the person wearing red on the left"
        preserve_patterns = [r"left", r"right", r"top", r"bottom"]
        # ... 调整清理逻辑
```

### 情况2: 跨图像对比
**问题**: "Compare the colors in Image 1 and Image 2" - 这里的"colors"算不算hint?

**解决方案**:
```python
# 允许任务相关的抽象词汇
allowed_abstract_terms = ["color", "size", "position", "number", "shape"]
# 但移除具体值: "red", "large", "top", "three", "circular"
```

### 情况3: Follow-up问题
**问题**: "You mentioned the person on the motorcycle. What color is their helmet?"

**解决方案**:
```python
# 保留之前对话中模型自己说的内容
# 只移除user simulator新加的描述
if is_follow_up:
    # Extract what model said previously
    model_previous_claims = context.get('model_claims', [])
    # Allow references to model's own statements
```

---

## 预期工作量
- **代码修改**: ~150 lines
- **验证脚本**: ~50 lines
- **测试时间**: ~4 hours (多轮对比测试)
- **总时间**: 2 days
- **可并行**: 100%（与Task 1A, 1C独立）

---

## 风险与缓解

### 风险1: 过度清理导致问题不明确
**表现**: 模型无法理解问题

**缓解**:
- 使用 `hint_level="moderate"` 作为默认
- 只在明确测试视觉能力时用 `"minimal"`

### 风险2: 不同任务类型需要不同level
**缓解**:
```python
# 根据task_type自动调整
task_hint_levels = {
    "attribute_comparison": "minimal",
    "visual_noise_filtering": "minimal",
    "attribute_bridge_reasoning": "moderate",  # 需要一些结构提示
}
```
