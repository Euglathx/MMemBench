# Round 1: 补全 RC/LNF 策略 + TaskProgress + 跨文档 Stub

## 目标

1. 在 `action_space.py` 的 `TASK_STRATEGIES` 字典末尾追加 `relation_comparison` 和 `logical_noise_filtering` 两个 key
2. 在 `task_config.py` 的 `TASK_CONFIGS` 字典末尾追加 `logical_noise_filtering` key
3. 创建 `src/simulator/task_progress.py` — `PhaseCompletion` + `TaskProgress` dataclass
4. 创建跨文档依赖的 stub 文件（防止导入失败）：
   - `src/simulator/state_schema_types.py` — 最小 `StateSchema` / `StateVariable` 定义
   - `src/simulator/state_aware_evaluator.py` — 继承 `Evaluator` 的空壳子类

## 安全性

- `action_space.py`: 仅追加新 key，已有 key 不变
- `task_config.py`: 仅追加新 key，已有 key 不变
- 所有新增文件均为独立模块，不修改已有文件的已有代码

## 代码要点

### action_space.py 追加差异（文档 vs 实际代码）

文档中 `TaskStrategy` phases 示例使用简化格式。实际代码中每个 phase 有 `name`, `description`, `actions`, `min_turns`, `goal` 五个字段。需按实际格式补全。

### step() 签名差异

文档写 `step(self, vlm_response)`, 实际是 `step(self)` — 在 Round 3 实现 `StatefulStrategicSimulator` 时需适配。

### _build_core_system_prompt 签名差异

文档写无参, 实际是 `_build_core_system_prompt(self, allowed_actions: List[str])` — Round 2/3 需适配。

### _get_strategy vs _get_task_strategy

文档写 `_get_task_strategy()`, 实际方法名是 `_get_strategy()` — Round 3 需适配。