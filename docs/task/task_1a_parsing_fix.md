# Task 1A: 修复Core Model响应解析问题

## 任务优先级
**P0 - Week 1 Day 1-2**

## 可以并行
✅ 可以与 Task 1B (提示质量), 1C (截断), 1D (Batch) 同时进行
✅ 独立任务，无依赖

## 任务目标
修复核心模型（o1-preview等）返回reasoning tokens导致的JSON解析失败，消除"Please continue"和"Failed to parse response"错误。

---

## 问题现状

### 当前错误示例
从 `simulator_test_log/run_log_20260119_094231.json`:
```json
{
  "event": "core_model_decision",
  "turn": 0,
  "action": "follow_up",
  "message_to_model": "Please continue.",
  "reasoning": "Failed to parse response"
}
```

### 根本原因
1. o1-preview模型返回 `reasoning_content` 但 `content` 为空
2. 解析器期待在 `content` 中找到JSON
3. 找不到JSON时fallback返回 `{"action": "follow_up", "message": "Please continue."}`

### 量化指标
- **当前**: "Please continue" 1次, "Failed to parse" 1次
- **目标**: 0次

---

## 需要修改的文件

### 文件: `src/simulator/strategic_simulator.py`

#### 修改1: Lines 558-567 - `_parse_core_response()`

**NEW签名**:
```python
def _parse_core_response(self, content: str, reasoning_content: str = "") -> Dict[str, Any]:
```

**NEW实现要点**:
1. 如果content为空,尝试从reasoning_content解析
2. 支持markdown code block中的JSON
3. 增强的fallback logging
4. 添加parse_error标记

#### 修改2: Lines 439-487 - `_call_core_model_for_action()`

**NEW调用方式**:
```python
parsed = self._parse_core_response(
    content=response.get('content', ''),
    reasoning_content=response.get('reasoning_content', '')
)

# 添加重试逻辑
if parsed.get('parse_error') and attempt < max_retries:
    # Retry with explicit JSON instruction
```

### 文件: `src/simulator/llm_user_simulator.py`

#### 修改: Lines 129-140

类似修复,处理reasoning tokens

---

## 验证

创建 `task/verify_task_1a.py`,检查:
- "Please continue" count = 0
- "Failed to parse" count = 0

运行:
```bash
python run_experiment.py --model o1-preview ... --output-dir test_output/task_1a
python task/verify_task_1a.py test_output/task_1a/run_log_*.json
```

---

## 协作

**提供给**: Task 1B, 1C, 2A - 稳定的解析
**需要**: ❌ 无依赖
**冲突**: ❌ 无冲突,完全独立
