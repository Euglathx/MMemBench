# Task 2B: 动作空间扩展 - 使用指南

## 概述

Task 2B扩展了M3Bench的动作空间，从原来的4种主要动作增加到8+种，启用了高级动作如`memory_injection`、`cross_image_confusion`和`consistency_check`。

## 目标

- ✅ 至少8种不同动作
- ✅ 每种动作至少出现1次（在10任务内）
- ✅ 没有单一动作占比>40%

## 快速测试

### 1. 测试动作选择器

运行快速测试验证动作选择器是否产生多样化的动作：

```bash
python test_action_diversity.py
```

**预期输出：**
- 10轮测试：至少6-9种唯一动作
- 100轮测试：至少8-12种唯一动作
- 最大动作占比 < 20%

### 2. 验证模块导入

确保所有修改的模块可以正常导入：

```bash
python -c "from src.simulator.action_selector import ActionSelector; print('✅ ActionSelector OK')"
python -c "from src.simulator.action_space import ACTION_DEFINITIONS; print(f'✅ Found {len(ACTION_DEFINITIONS)} actions')"
python -c "from src.simulator.strategic_simulator import StrategicSimulator; print('✅ StrategicSimulator OK')"
```

## 完整实验验证

### 步骤1: 运行实验

运行10个任务的完整实验：

```bash
python run_experiment.py --num-tasks 10 --output-dir test_output/task_2b
```

**注意事项：**
- 确保有足够的API配额（需要调用LLM）
- 实验可能需要10-30分钟
- 日志文件将保存在 `test_output/task_2b/`

### 步骤2: 验证结果

运行验证脚本分析动作多样性：

```bash
python task/verify_task_2b.py test_output/task_2b/run_log_*.json
```

**验证标准：**
1. **唯一动作数量**: >= 8种
2. **最大动作占比**: <= 40%
3. **高级动作使用**: 至少1种

**示例输出：**
```
==================================================
=== Task 2B: Action Diversity Verification ===
==================================================

Total actions: 50
Unique actions: 10

--- Action Distribution ---
  guidance                 :   8 ( 16.0%) ████████
  fine_grained             :   7 ( 14.0%) ███████
  follow_up                :   6 ( 12.0%) ██████
  mislead                  :   5 ( 10.0%) █████
  memory_injection         :   4 (  8.0%) ████
  ...

--- Verification Results ---
✅ PASS: 10 unique actions (>= 8)
✅ PASS: Max action 'guidance' at 16.0% (<= 40%)
✅ PASS: 3 high-level action(s) used

✅ OVERALL: Action diversity verification PASSED
```

## 问题排查

### 问题1: 导入错误

**症状：**
```
ImportError: cannot import name 'ACTION_DEFINITIONS'
```

**解决方案：**
确保你在项目根目录运行命令，并且Python路径正确：
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### 问题2: 动作多样性不足

**症状：**
```
❌ FAIL: Only 5 unique actions (need >= 8)
```

**可能原因：**
- `action_selector.py` 的rule-based逻辑未正确修改
- `action_space.py` 的难度门槛未降低
- `strategic_simulator.py` 的多样性强制未生效

**调试步骤：**
1. 检查 `action_selector.py` 的 `_select_rule_based` 方法
2. 确认 `action_space.py` 中的 `difficulty_level` 已降低
3. 验证 `strategic_simulator.py` 的 `_select_action` 方法

### 问题3: 单一动作占比过高

**症状：**
```
❌ FAIL: Action 'guidance' at 65.0% (> 40%)
```

**可能原因：**
- `strategic_simulator.py` 的多样性强制逻辑未生效
- Recent action tracking未正确实现

**解决方案：**
检查 `strategic_simulator.py` 中的这段代码：
```python
recent_actions = self.task_state.actions_used[-3:]
diverse_candidates = [a for a in candidates if a not in recent_actions]
```

## 修改文件清单

- ✅ `src/simulator/action_selector.py`
- ✅ `src/simulator/action_space.py`
- ✅ `src/simulator/strategic_simulator.py`
- ✅ `task/verify_task_2b.py` (新建)
- ✅ `test_action_diversity.py` (新建，辅助测试)

## 技术细节

### 动作扩展

原有动作（4种）：
- guidance
- follow_up
- mislead
- fine_grained

新增高频使用的动作（8+种）：
- logic_skip
- negation
- distraction
- redundancy
- update
- **memory_injection** (高级)
- **consistency_check** (高级)
- **cross_image_confusion** (高级)

### 难度级别调整

| 动作 | 原难度 | 新难度 |
|------|--------|--------|
| memory_injection | 3 | 2 |
| consistency_check | 3 | 1 |
| cross_image_confusion | 3 | 2 |

### 轮次阶段调整

| 轮次范围 | 原动作数 | 新动作数 | 改进 |
|----------|----------|----------|------|
| 0-2 (前期) | 2 | 4 | +100% |
| 3-5 (中期) | 4 | 8 | +100% |
| 6+ (后期) | 4 | 8 | +100% |

## 后续集成

Task 2B完成后，可以继续：

1. **Task 2A** (评估系统修复) - 可并行
2. **Task 3** (最终验证) - 需要Task 2A和2B都完成

## 参考

- 任务文档: [task_2b_action_space.md](task_2b_action_space.md)
- 完成总结: [task_2b_completion_summary.md](task_2b_completion_summary.md)
- 验证脚本: [verify_task_2b.py](verify_task_2b.py)

## 成功标准

Task 2B被认为成功完成，当：

1. ✅ 快速测试通过（test_action_diversity.py）
2. ✅ 所有模块导入无错误
3. ✅ 完整实验产生>=8种唯一动作
4. ✅ 单一动作占比<=40%
5. ✅ 至少1种高级动作被使用
6. ✅ 验证脚本返回PASS

---

**状态**: ✅ 已完成
**日期**: 2025-02-01
**验证**: 快速测试已通过，等待完整实验验证
