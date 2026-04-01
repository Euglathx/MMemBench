# Round 2: 创建 PromptRouter

## 目标

创建 `src/simulator/prompt_router.py`:
- `PromptRouter` 类 + `SYSTEM_BASE` / `TASK_PROMPTS` / `PHASE_PROMPTS` 模板常量
- `assemble_prompt()` 返回 `(system_prompt, user_prompt)`
- `_compress_response()`, `_compress_history()`, `_get_phase_actions()`, `_get_phase_context()`
- 需要从 `action_space.py` 的 `TASK_STRATEGIES` 读取 phase→actions 映射

## 安全性

- 独立新文件，不继承任何类
- 不修改任何已有文件

## 适配

- `_get_phase_actions()` 需要正确处理实际 `TASK_STRATEGIES` 的 phase 结构
- `TASK_PROMPTS` 需覆盖全部 5 种任务类型（AC, VNF, ABR, RC, LNF）
- `PHASE_PROMPTS` 的 format keys 需要安全处理（使用 `.format_map()` with defaultdict 避免 KeyError）

# Round 3: 创建 StatefulStrategicSimulator

## 目标

创建 `src/simulator/stateful_simulator.py`:
- `StatefulStrategicSimulator(StrategicSimulator)` 子类
- Override `__init__`: 追加 `TaskProgress` + `PromptRouter`
- Override `_extract_ground_truths(task)`: super() + 加载 state_schema
- Override `step()`: super() + 状态事件记录（注意实际签名是 `step(self)` 无参）
- Override `_build_core_system_prompt(allowed_actions)`: 有 state_schema 时委托给 PromptRouter, 否则 super()
- Override `_build_core_user_prompt()`: 同上

## 适配

- `step()` 实际无参数（内部调用目标模型），不是文档里的 `step(self, vlm_response)`
- `_build_core_system_prompt` 接受 `allowed_actions: List[str]`
- 使用 `self._get_strategy()` 而非文档中的 `self._get_task_strategy()`
- `self.task_state` 而非 `self.state`
- state_schema 缺失时所有新增逻辑跳过，调用 super()

# Round 4: 创建 InterleavedBatchSimulator

## 目标

创建 `src/simulator/interleaved_batch.py`:
- `SharedConversationWindow` — 独立新类
- `InterleavedScheduler` — 独立新类
- `InterleavedBatchSimulator(BatchTaskSimulator)` 子类
- 更新 `src/simulator/__init__.py` 导出新模块

## 安全性

- `BatchTaskSimulator` 不被修改
- `interleave_mode=False` 退回 `super().run_batch()`

## 适配

- `BatchTaskSimulator.__init__` 接受 `(llm_client, evaluator, config, verbose)` 四个参数
- `run_batch` 接受 `tasks: List[Dict]` 返回 `BatchResult`
- 需要处理 `self.config.max_turns_per_session` 等属性