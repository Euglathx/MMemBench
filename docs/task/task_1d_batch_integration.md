# Task 1D: Batch数据集成

## 任务优先级
**P0 - Week 1 Day 4-5** (在Task 1A完成后)

## 可以并行
⚠️ 建议等Task 1A完成后开始(避免parse error干扰测试)
✅ 可以与Task 1B, 1C同时进行

## 任务目标
确保batch测试能捕获完整的turn-level对话细节,并能直接使用 `generated_tasks_v2/run_18` 数据进行测试。

---

## 问题现状

### 当前问题
1. `batch_test_results/*.json` 只有聚合分数,没有turn details
2. 转换工具 `convert_batch_results_to_runlog.py` 生成placeholder events
3. 无法用batch结果生成真实的test log

### 根本原因
`src/simulator/batch_task_simulator.py:365-385` 中 `_run_single_task_in_batch()` 没有捕获 `StrategicSimulator` 的conversation history

### 用户需求
✅ 必须能直接使用 `generated_tasks_v2/run_18/tasks/*.jsonl` 数据

---

## 需要修改的文件

### 文件1: `src/simulator/strategic_simulator.py`

#### 修改: 添加conversation history存储

```python
class StrategicSimulator:
    def __init__(self, ...):
        self.conversation_history = []  # NEW: Store all turns

    def step(self) -> Dict[str, Any]:
        # ... existing step logic ...

        # NEW: After each turn, record details
        self.conversation_history.append({
            'turn': self.turn_counter,
            'action': action,
            'query': message_to_send,
            'response': target_response,
            'images_sent': images_to_send,
            'evaluation': evaluation_result.to_dict(),
            'timestamp': datetime.now().isoformat()
        })

        return step_result
```

### 文件2: `src/simulator/batch_task_simulator.py`

#### 修改: Lines 337-385 - `_run_single_task_in_batch()`

```python
def _run_single_task_in_batch(self, task: Dict, ...) -> Dict:
    # Create simulator
    simulator = StrategicSimulator(...)

    # Run task
    result = simulator.run_task(task)

    # NEW: Capture conversation history
    turn_details = []
    if hasattr(simulator, 'conversation_history'):
        turn_details = simulator.conversation_history.copy()

    # Build result with turns
    return {
        **result,
        'turns': turn_details,  # NEW
        'conversation_history': turn_details,  # NEW (别名)
        'task_id': task.get('task_id'),
        'task_type': task.get('task_type'),
        'completed': result.get('completed', False),
        'turns_used': len(turn_details)
    }
```

### 文件3: `tools/convert_batch_results_to_runlog.py`

#### 修改: Lines 36-142 - 使用真实turn数据

```python
def convert_batch_result_to_events(batch_result: Dict) -> List[Dict]:
    events = []

    for task_result in batch_result.get('task_results', []):
        # Task start event
        events.append({
            "event": "task_start",
            "task_id": task_result.get('task_id'),
            "task_type": task_result.get('task_type'),
            "timestamp": "..."
        })

        # NEW: Use actual turns if available
        if 'turns' in task_result and task_result['turns']:
            for turn_data in task_result['turns']:
                # Core model decision
                events.append({
                    "event": "core_model_decision",
                    "turn": turn_data.get('turn'),
                    "action": turn_data.get('action'),
                    "message_to_model": turn_data.get('query'),
                    "timestamp": turn_data.get('timestamp')
                })

                # Target model response
                events.append({
                    "event": "target_model_response",
                    "turn": turn_data.get('turn'),
                    "target_response": turn_data.get('response'),
                    "images_sent": turn_data.get('images_sent', []),
                    "evaluation": turn_data.get('evaluation', {}),
                    "timestamp": turn_data.get('timestamp')
                })
        else:
            # Fallback to placeholder (old behavior)
            logger.warning(f"Task {task_result.get('task_id')}: No turn details, using placeholders")
            # ... existing placeholder logic ...

        # Task end event
        events.append({
            "event": "task_end",
            "task_id": task_result.get('task_id'),
            "completed": task_result.get('completed'),
            "timestamp": "..."
        })

    return events
```

---

## 兼容性要求: run_18数据

### 检查run_18数据格式

```bash
# 检查run_18的task格式
head -n 1 generated_tasks_v2/run_18/tasks/attribute_comparison_mscoco14.jsonl | jq .
```

预期字段:
```json
{
  "task_id": "ac_mscoco_...",
  "task_type": "attribute_comparison",
  "images": ["images/COCO_...jpg", ...],
  "question": "...",
  "answer": "...",
  "metadata": {...}
}
```

### 确保加载器兼容

在 `run_batch_test.py` 中:

```python
def load_tasks_from_jsonl(file_path: str) -> List[Dict]:
    """Load tasks from JSONL, compatible with run_18 format."""
    tasks = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                task = json.loads(line)

                # Validate required fields
                required = ['task_id', 'task_type', 'images', 'question']
                missing = [f for f in required if f not in task]
                if missing:
                    logger.warning(f"Line {line_num}: Missing fields {missing}, skipping")
                    continue

                # Ensure images are accessible
                # run_18 uses relative paths like "images/COCO_..."
                # Convert to absolute if needed
                base_dir = Path(file_path).parent.parent  # Go up to run_18/
                task['images'] = [
                    str(base_dir / img) if not Path(img).is_absolute() else img
                    for img in task['images']
                ]

                tasks.append(task)
            except json.JSONDecodeError as e:
                logger.error(f"Line {line_num}: Invalid JSON - {e}")

    return tasks
```

---

## 验证

### 创建 `task/verify_task_1d.py`

```python
#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def verify_batch_integration(batch_result_file: Path):
    with open(batch_result_file) as f:
        data = json.load(f)

    print("=== Task 1D Verification ===")

    total_tasks = 0
    tasks_with_turns = 0
    total_turns_captured = 0

    for batch in data.get('results', []):
        for task_result in batch.get('task_results', []):
            total_tasks += 1

            if 'turns' in task_result:
                tasks_with_turns += 1
                turns = task_result['turns']
                total_turns_captured += len(turns)

                # Verify turn structure
                if turns:
                    first_turn = turns[0]
                    required_keys = ['turn', 'action', 'query', 'response']
                    missing = [k for k in required_keys if k not in first_turn]
                    if missing:
                        print(f"❌ Task {task_result.get('task_id')}: Missing keys {missing}")
                    else:
                        print(f"✅ Task {task_result.get('task_id')}: {len(turns)} turns captured")

    print(f"\nTotal tasks: {total_tasks}")
    print(f"Tasks with turn details: {tasks_with_turns}")
    print(f"Total turns captured: {total_turns_captured}")

    if tasks_with_turns == total_tasks and total_turns_captured > 0:
        print("✅ PASS: All tasks have turn-level details")
        return True
    else:
        print(f"❌ FAIL: {total_tasks - tasks_with_turns} tasks missing turn details")
        return False

if __name__ == "__main__":
    result_file = Path(sys.argv[1])
    passed = verify_batch_integration(result_file)
    sys.exit(0 if passed else 1)
```

### 运行验证

```bash
# Run batch test with run_18 data
python run_batch_test.py \
  --task-files "generated_tasks_v2/run_18/tasks/attribute_comparison_*.jsonl" \
  --tasks-per-batch 2 \
  --num-batches 1 \
  --output-dir test_output/task_1d

# Verify batch results have turn details
python task/verify_task_1d.py test_output/task_1d/batch_results_*.json

# Convert to runlog and verify no placeholders
python tools/convert_batch_results_to_runlog.py \
  test_output/task_1d/batch_results_*.json \
  test_output/task_1d/converted_runlog.json

# Check for placeholders
grep -c "detailed log not available" test_output/task_1d/converted_runlog.json
# Should output: 0
```

---

## 协作

**提供给**:
- Task 3 (验证): 完整的batch流程数据

**需要**:
- ⚠️ Task 1A (建议): 避免parse error干扰
- ✅ run_18数据: 确认已生成且格式正确

**冲突**:
- ❌ 与Task 1A, 1B, 1C无代码冲突

---

## 预期工作量
- **代码修改**: ~200 lines
- **验证脚本**: ~60 lines
- **测试时间**: 4 hours
- **总时间**: 2 days
