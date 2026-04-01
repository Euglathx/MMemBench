# Task 2B: 动作空间扩展

## 任务优先级
**P1 - Week 2 Day 5-6** (在Task 1A完成后)

## 可以并行
✅ 可以与Task 2A并行
⚠️ 需要Task 1A完成(稳定的解析)

## 任务目标
扩展动作使用,从当前的4种增加到8+种,启用memory_injection, cross_image_confusion等高级动作。

---

## 问题现状

### 当前动作分布
从 `run_log_20251231`:
- guidance: 6次 (43%)
- fine_grained: 4次
- mislead: 2次
- next_task: 2次
- **总共只有4种**

### 目标分布
- 至少8种不同动作
- 每种动作至少出现1次(10任务内)
- 没有单一动作>40%

---

## 需要修改的文件

### 文件1: `src/simulator/action_selector.py`

#### Lines 148-194 - 放宽rule-based选择

**OLD** (turns 0-2只用2种动作):
```python
if turn < 3:
    candidates = ["follow_up", "guidance"]
```

**NEW** (早期就引入多样性):
```python
if turn < 3:
    candidates = ["follow_up", "guidance", "fine_grained", "logic_skip"]
elif turn < 6:
    candidates = [..., "memory_injection", "consistency_check"]
```

### 文件2: `src/simulator/action_space.py`

#### Lines 43-509 - 降低难度门槛

找到这些动作,降低difficulty_level:
- memory_injection: 从3降到2
- cross_image_confusion: 从3降到2
- consistency_check: 从3降到1

### 文件3: `src/simulator/strategic_simulator.py`

#### Lines 307-346 - 强制动作多样性

**添加recent-action tracking**:

```python
def _select_action(self):
    # Track last 3 actions
    recent_actions = [
        h.get('action')
        for h in self.conversation_history[-3:]
    ]

    # Get candidates
    candidates = self.action_selector.get_candidates(...)

    # Prioritize unused actions
    diverse_candidates = [
        a for a in candidates
        if a not in recent_actions
    ]

    if diverse_candidates:
        return random.choice(diverse_candidates)
    else:
        return random.choice(candidates)
```

---

## 验证

### `task/verify_task_2b.py`

```python
import json
import sys
from collections import Counter

def verify_action_diversity(log_file):
    with open(log_file) as f:
        events = json.load(f)

    actions = [
        e.get('action')
        for e in events
        if e.get('event') == 'core_model_decision'
    ]

    action_counts = Counter(actions)
    unique_count = len(action_counts)
    total_count = len(actions)

    print(f"=== Action Diversity ===")
    print(f"Total actions: {total_count}")
    print(f"Unique actions: {unique_count}")
    print(f"Target: >= 8")

    for action, count in action_counts.most_common():
        pct = count / total_count * 100
        print(f"  {action}: {count} ({pct:.1f}%)")

    # Check criteria
    passed = True
    if unique_count < 8:
        print(f"❌ FAIL: Only {unique_count} unique actions")
        passed = False

    max_action_pct = max(c/total_count for c in action_counts.values()) * 100
    if max_action_pct > 40:
        print(f"❌ FAIL: Single action >40% ({max_action_pct:.1f}%)")
        passed = False

    if passed:
        print("✅ PASS: Action diversity achieved")

    return passed
```

运行:
```bash
python run_experiment.py --num-tasks 10 --output-dir test_output/task_2b
python task/verify_task_2b.py test_output/task_2b/run_log_*.json
```

---

## 协作

**需要**: Task 1A完成
**提供给**: Task 3验证
**冲突**: ❌ 无

---

## 预期工作量
- **代码修改**: ~150 lines
- **验证**: ~40 lines
- **测试**: 4 hours
- **总时间**: 2 days
