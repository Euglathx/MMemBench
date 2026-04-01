# 对话和测试改进 - 更新版计划

> **安全性原则**: 本文档所有改动均为 **子类扩展或独立新模块**。现有 `StrategicSimulator`、`BatchTaskSimulator`、`action_space.py`、`task_config.py` 均不做破坏性修改。新增 `StatefulStrategicSimulator(StrategicSimulator)` 子类承载状态感知对话逻辑，新增 `InterleavedBatchSimulator(BatchTaskSimulator)` 子类承载任务交叉逻辑。对 `action_space.py` 和 `task_config.py` 的修改仅为 **追加式**（在已有字典中新增 key），不修改任何已有 key 的值。

---

## 0. 跨文档接口契约

本文档是三份改进文档的 **对话协调层**，它同时消费另外两份文档的产出：

```
┌──────────────────────────────────────────────────────────────────────┐
│  数据标注改进（上游）                                                 │
│  产出: state_schema_types.py — StateSchema, StateVariable 等         │
│  产出: StateSchemaConverter — 从 evidence 生成 state_schema           │
├──────────────────────────────────────────────────────────────────────┤
│  状态测试改进（同级）                                                 │
│  产出: StateAwareEvaluator(Evaluator) — 状态感知评估器                │
│  产出: StateEvolutionTracker — 状态演化追踪器                         │
├──────────────────────────────────────────────────────────────────────┤
│                    ▼ 本文档消费以上产出                                │
│  本文档: 对话和测试改进                                               │
│                                                                       │
│  产出: StatefulStrategicSimulator(StrategicSimulator)                 │
│        └─ 组合 StateAwareEvaluator + StateEvolutionTracker            │
│        └─ override step() 追加状态事件记录                            │
│        └─ override _extract_ground_truths() 加载 state_schema         │
│                                                                       │
│  产出: InterleavedBatchSimulator(BatchTaskSimulator)                  │
│        └─ override run_batch() 支持阶段级交叉调度                     │
│        └─ 组合 SharedConversationWindow + InterleavedScheduler        │
│                                                                       │
│  产出: PromptRouter (独立新类，不继承)                                │
│        └─ 替代 _build_core_system_prompt() 的内联逻辑                 │
│                                                                       │
│  追加: action_space.py TASK_STRATEGIES 新增 RC/LNF 条目               │
│  追加: task_config.py TASK_CONFIGS 新增 LNF 条目                      │
└──────────────────────────────────────────────────────────────────────┘
```

**共享类型**: `src/simulator/state_schema_types.py`（定义于数据标注改进文档）
**共享评估器**: `src/simulator/state_aware_evaluator.py`（定义于状态测试改进文档）

---

## Context

基于 2026-03-09 的初步诊断和 2026-03-11 的进一步需求，本文档整合了五个核心改进方向：
1. 考官任务完成状态追踪能力分析
2. 新增缺失任务类型支持（LNF、RC 的策略补全）
3. Prompt 路由与拼接机制（减轻核心模型上下文压力）
4. 批处理中的任务交叉测试
5. 现有数据标注转化（而非完全重建）

---

## 一、考官能否追踪任务完成状态？

### 1.1 当前实现

**可以，但追踪粒度较粗，且不足以支撑任务交叉调度。** 具体机制如下：

#### 层级 1：Phase-Level 追踪（`strategic_simulator.py`）

```python
# TaskState 中的阶段追踪
@dataclass
class TaskState:
    current_phase: PhaseState       # 当前阶段
    phases_completed: List[str]     # 已完成阶段列表
    difficulty_level: int           # 当前难度
    recent_scores: List[float]      # 最近分数
    actions_used: List[str]         # 已用动作
```

通过 `_advance_phase()` 方法（`strategic_simulator.py:248-283`）：
- 每个 phase 有 `min_turns`，只有达到最小轮数才允许前进
- 前进条件是纯数量触发，**不是基于子目标完成状态**

#### 层级 2：Turn-Level 追踪（`TurnGroundTruth`）

每一轮有 `sub_goal`（如 `"identify_entity"`, `"spatial_relation"`, `"final_answer"`），但：
- `sub_goal` 只是一个字符串标签，**没有结构化的完成判定**
- 评估器对 turn 打分，但分数不直接影响"子目标是否完成"的判定
- **没有** "子目标 A 完成后才能进入子目标 B" 的门控逻辑

#### 层级 3：Batch-Level 追踪（`batch_task_simulator.py`）

```python
# 任务完成追踪
if task_report.get('completed', False):
    result.tasks_completed += 1
    self.completed_tasks.append({'task': task, 'report': task_report})
```

- 追踪已完成任务数量
- 全局 `total_turns` 计数器
- 跨任务记忆测试（但目前是 mock 实现，返回随机分数）

#### 层级 4：Ground Truth 提取（`_extract_ground_truths()`）

```python
# strategic_simulator.py:354-372
def _extract_ground_truths(self, task):
    self.task_state.ground_truths["expected_answer"] = task.get("answer", "")
    self.evaluator.register_key_fact("expected_answer", task.get("answer", ""), source="task")

    if "reasoning_path" in task:
        for i, step in enumerate(task["reasoning_path"]):
            self.task_state.ground_truths[f"reasoning_step_{i}"] = step
```

只提取了 `answer` 和 `reasoning_path`，**没有**从 evidence 文件中加载结构化的变量级信息。这意味着考官对"应该追踪哪些具体变量"一无所知。

### 1.2 缺陷总结

| 能力 | 当前状态 | 问题 | 交叉调度是否需要 |
|------|----------|------|:---:|
| Phase 完成判定 | 基于轮数 | 不是基于子目标完成 | **需要** — 交叉调度必须知道某阶段何时可安全暂停 |
| Sub-goal 完成 | 有标签无判定 | 没有结构化的完成条件 | **需要** — 必须知道 observation 是否收集到了足够变量 |
| 跨 Phase 门控 | 无 | Phase 前进不依赖上一阶段的输出 | **需要** — probing 阶段只有在 observation 有产出后才有意义 |
| Batch 任务完成 | 简单布尔值 | 缺乏部分完成的概念 | **需要** — 交叉模式下每个任务可能只完成了部分阶段 |
| 跨任务记忆测试 | Mock 实现 | 返回随机分数 | **需要** — 交叉调度的核心价值就在于测试跨任务记忆 |
| 变量级追踪 | 不存在 | ground_truths 只有 answer 和 reasoning_path | **需要** — 状态维护评测的基础 |

### 1.3 改进方案：TaskProgress 追踪（独立新模块）

要支撑后续的任务交叉测试，引入独立的 **TaskProgress** 追踪模块（不修改 `StrategicSimulator` 的原有 `TaskState`）：

```python
# src/simulator/task_progress.py — 独立新文件

from src.simulator.state_schema_types import StateSchema


@dataclass
class PhaseCompletion:
    """一个阶段的完成状态"""
    phase_name: str
    status: str  # 'not_started' | 'in_progress' | 'paused' | 'completed'
    min_turns: int
    turns_used: int
    variables_observed: List[str]     # 在此阶段被观察到的变量
    variables_probed: List[str]       # 在此阶段被 probe 过的变量
    probe_results: Dict[str, bool]    # variable_name -> 模型是否答对
    can_pause: bool                   # 是否已满足暂停条件

    def check_pausable(self) -> bool:
        """min_turns 已达且关键变量已覆盖"""
        return self.turns_used >= self.min_turns and len(self.variables_observed) > 0


@dataclass
class TaskProgress:
    """单个任务的完整进度 — 组合到 StatefulStrategicSimulator 中"""
    task_id: str
    task_type: str
    phases: List[PhaseCompletion]
    current_phase_index: int
    overall_status: str  # 'not_started' | 'in_progress' | 'paused' | 'completed' | 'failed'

    # 从 state_schema 加载的变量追踪
    tracked_variables: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state_schema(cls, task_id: str, task_type: str,
                          schema: StateSchema, phase_configs: List[Dict]) -> "TaskProgress":
        """从 state_schema 初始化（依赖数据标注改进的产出）"""
        phases = [PhaseCompletion(
            phase_name=pc['name'], status='not_started',
            min_turns=pc.get('min_turns', 2), turns_used=0,
            variables_observed=[], variables_probed=[],
            probe_results={}, can_pause=False,
        ) for pc in phase_configs]
        tracked = {name: var.value for name, var in schema.variables.items()} if schema else {}
        return cls(task_id=task_id, task_type=task_type, phases=phases,
                   current_phase_index=0, overall_status='not_started',
                   tracked_variables=tracked)

    def is_phase_pausable(self) -> bool:
        """当前阶段是否可以安全暂停（用于交叉调度）"""
        if self.current_phase_index >= len(self.phases):
            return False
        return self.phases[self.current_phase_index].check_pausable()

    def get_variable_coverage(self) -> float:
        """返回变量覆盖率（已观察/总数）"""
        if not self.tracked_variables:
            return 0
        current = self.phases[self.current_phase_index] if self.current_phase_index < len(self.phases) else None
        if not current:
            return 0
        observed = len(current.variables_observed)
        return observed / len(self.tracked_variables) if self.tracked_variables else 0
```

### 1.4 涉及文件

| 文件 | 改动方式 | 原有接口变化 |
|------|----------|:------------:|
| **新增** `src/simulator/task_progress.py` | `TaskProgress`, `PhaseCompletion` | N/A |
| `src/simulator/strategic_simulator.py` | 不修改。`StatefulStrategicSimulator` 子类在 `step()` 中驱动 `TaskProgress` | 无 |
| `src/simulator/batch_task_simulator.py` | 不修改。`InterleavedBatchSimulator` 子类使用 `TaskProgress` | 无 |

---

## 二、新增缺失任务类型支持

### 2.1 当前任务支持检测结果

| 任务类型 | `TASK_CONFIGS` (task_config.py) | `TASK_STRATEGIES` (action_space.py) | 数据生成 | 状态 |
|----------|:---:|:---:|:---:|------|
| attribute_comparison (AC) | 有 | 有 | 有 | 完整 |
| visual_noise_filtering (VNF) | 有 | 有 | 有 | 完整 |
| attribute_bridge_reasoning (ABR) | 有 | 有 | 有 | 完整 |
| relation_comparison (RC) | 有 | **无** | 有 | 缺 Strategy |
| logical_noise_filtering (LNF) | **无** | **无** | 有(VG) | 缺 Config + Strategy |

### 2.2 需要补全的内容（追加式，不修改已有条目）

#### RC: 追加 `TASK_STRATEGIES` 条目

`action_space.py` 的 `TASK_STRATEGIES` 字典中新增一个 key，**不修改任何已有 key**：

```python
# action_space.py — 在 TASK_STRATEGIES 字典末尾追加
"relation_comparison": TaskStrategy(
    task_type="relation_comparison",
    name="Relation Comparison",
    description="Compare relationships between objects across images",
    phases=[
        {"name": "grounding", "actions": ["guidance", "follow_up", "fine_grained"], "min_turns": 2},
        {"name": "relationship_probing", "actions": ["follow_up", "fine_grained", "guidance"], "min_turns": 2},
        {"name": "noise_injection", "actions": ["mislead", "distraction", "cross_image_confusion"], "min_turns": 2},
        {"name": "final_evaluation", "actions": ["fine_grained", "consistency_check"], "min_turns": 1}
    ],
    difficulty_progression={...},
    final_question_templates=[...],
    ground_truth_extraction="evidence"
)
```

#### LNF: 追加 `TASK_CONFIGS` 条目 + `TASK_STRATEGIES` 条目

```python
# task_config.py — 在 TASK_CONFIGS 字典末尾追加
"logical_noise_filtering": {
    "name": "Logical Noise Filtering",
    "description": "Select correct descriptions of images, filtering logical distractors",
    "goal": "Identify which description correctly matches the image content",
    "evaluation_criteria": [...],
    "multi_turn_strategy": {
        "phase_1": "Present image and have model describe",
        "phase_2": "Present options for model to choose",
        "phase_3": "Inject distractor options, test robustness"
    },
    "action_weights": {
        "guidance": 0.2, "follow_up": 0.2, "mislead": 0.25,
        "distraction": 0.15, "fine_grained": 0.2
    }
}

# action_space.py — 在 TASK_STRATEGIES 字典末尾追加
"logical_noise_filtering": TaskStrategy(...)
```

### 2.3 涉及文件

| 文件 | 改动方式 | 原有接口变化 |
|------|----------|:------------:|
| `src/simulator/action_space.py` | 在 `TASK_STRATEGIES` 字典中追加 2 个新 key | 无（已有 key 不变） |
| `src/simulator/task_config.py` | 在 `TASK_CONFIGS` 字典中追加 1 个新 key | 无（已有 key 不变） |

---

## 三、Prompt 路由与拼接机制

### 3.1 问题分析

当前 `_build_core_system_prompt()` 每次都把**所有信息**塞给核心模型。当任务类型增多（5种+）、动作增多（15+）时，system prompt 会非常长，且大部分信息与当前 turn 无关。

### 3.2 设计方案：独立 PromptRouter 类

`PromptRouter` 是一个 **独立新类**，不继承任何现有类。它被 `StatefulStrategicSimulator` 组合使用，**不修改原始 `StrategicSimulator` 的 `_build_core_system_prompt()`**。

```
原始 StrategicSimulator:
  └─ _build_core_system_prompt()   ← 不修改
  └─ _build_core_user_prompt()     ← 不修改

StatefulStrategicSimulator(StrategicSimulator):
  └─ prompt_router: PromptRouter   ← 组合新模块
  └─ override _build_core_system_prompt() → 委托给 prompt_router
  └─ override _build_core_user_prompt()   → 委托给 prompt_router
```

```python
# src/simulator/prompt_router.py — 独立新文件

class PromptRouter:
    """
    Prompt 路由与组装。
    独立新类，被 StatefulStrategicSimulator 组合使用。
    """

    def __init__(self):
        self._task_prompts = TASK_PROMPTS    # 每种任务类型一个模板
        self._phase_prompts = PHASE_PROMPTS  # 每阶段一个模板

    def assemble_prompt(self, task_type: str, phase: str,
                        difficulty: int, turn_count: int,
                        vlm_response: str, history: List,
                        state_context: Dict = None) -> Tuple[str, str]:
        """
        返回 (system_prompt, user_prompt)

        state_context: 可选的状态上下文（来自 TaskProgress）
        """
        # 1. 系统提示 = 固定基底 + 任务模板 + 阶段指令
        system = SYSTEM_BASE
        system += self._task_prompts.get(task_type, "")
        system += self._phase_prompts.get(phase, "").format(
            allowed_actions=self._get_phase_actions(task_type, phase, difficulty),
            **self._get_phase_context(phase, state_context)
        )

        # 2. 用户提示 = 压缩历史 + 压缩回复 + 状态信息
        user = ""
        if vlm_response:
            user += f"## Target model's latest response\n{self._compress_response(vlm_response)}\n\n"
        user += f"## Dialogue summary (last {min(3, len(history))} turns)\n{self._compress_history(history)}\n\n"
        user += f"## Status\n- Turn: {turn_count}\n- Difficulty: {difficulty}/4\n"

        return system, user

    def _compress_response(self, response: str, max_length: int = 200) -> str:
        if len(response) <= max_length:
            return response
        return response[:max_length] + "..."

    def _compress_history(self, history: List, max_turns: int = 3) -> str:
        recent = history[-max_turns:] if history else []
        return "\n".join(str(h) for h in recent)

    def _get_phase_actions(self, task_type, phase, difficulty) -> str:
        # 从 TASK_STRATEGIES 中获取当前阶段可用的动作
        ...

    def _get_phase_context(self, phase, state_context=None) -> Dict:
        ctx = {}
        if state_context:
            ctx['probing_variables'] = state_context.get('probing_variables', [])
        return ctx


# === Prompt 模板 ===

SYSTEM_BASE = """You are a VLM capability examiner. Your task is to test the target model through strategic multi-turn dialogue.

## Output Format
Please output in JSON format:
{"action": "...", "message": "...", "reasoning": "..."}
"""

TASK_PROMPTS = {
    "attribute_comparison": """## Current Task: Attribute Comparison
Goal: Compare attribute differences of target objects across images
Focus: Cross-image observation accuracy, attribute extraction precision, comparative reasoning
""",
    "logical_noise_filtering": """## Current Task: Logical Noise Filtering
Goal: Identify correct description matching the image from multiple options
Focus: Visual evidence verification, logical distractor resistance
""",
    # ... other task types
}

PHASE_PROMPTS = {
    "observation": """## Current Phase: Observation
You do NOT know the final question. Guide the model to observe the images with generic questions.
Available actions: {allowed_actions}
""",
    "probing": """## Current Phase: Probing
Check whether the model remembers previous observations.
Probeable variables: {probing_variables}
Available actions: {allowed_actions}
""",
    "final_question": """## Current Phase: Final Question
Question: {question}
Expected answer: {expected_answer}
Available actions: {allowed_actions}
""",
}
```

### 3.3 涉及文件

| 文件 | 改动方式 | 原有接口变化 |
|------|----------|:------------:|
| **新增** `src/simulator/prompt_router.py` | PromptRouter 类 + 模板 | N/A |
| `src/simulator/strategic_simulator.py` | 不修改。`StatefulStrategicSimulator` 子类覆盖 prompt 构建方法 | 无 |

---

## 四、StatefulStrategicSimulator — 核心子类

### 4.1 扩展策略

`StatefulStrategicSimulator` 继承 `StrategicSimulator`，通过 `super()` 保留全部原有逻辑，仅扩展三个方面：

```python
# src/simulator/stateful_simulator.py — 独立新文件

from src.simulator.strategic_simulator import StrategicSimulator
from src.simulator.state_aware_evaluator import StateAwareEvaluator  # 状态测试改进的产出
from src.simulator.state_schema_types import StateSchema              # 数据标注改进的产出
from src.simulator.task_progress import TaskProgress
from src.simulator.prompt_router import PromptRouter


class StatefulStrategicSimulator(StrategicSimulator):
    """
    StrategicSimulator 的子类扩展。

    扩展点:
    1. __init__: 追加 TaskProgress + PromptRouter 组合
    2. _extract_ground_truths(): override 加载 state_schema
    3. step(): override 在原有逻辑后追加状态事件记录
    4. _build_core_system_prompt(): override 委托给 PromptRouter
    5. _build_core_user_prompt(): override 委托给 PromptRouter

    安全性:
    - 所有 override 方法都先调用 super() 获得原有结果
    - state_schema 缺失时，自动降级为原始 StrategicSimulator 的行为
    - 原始 StrategicSimulator 的代码不被修改
    """

    def __init__(self, *args, **kwargs):
        # 如果调用方传了 evaluator，使用它；否则创建 StateAwareEvaluator
        if 'evaluator' not in kwargs or kwargs['evaluator'] is None:
            kwargs['evaluator'] = StateAwareEvaluator()
        super().__init__(*args, **kwargs)

        # 新增组合
        self.task_progress: Optional[TaskProgress] = None
        self.prompt_router: PromptRouter = PromptRouter()
        self._state_schema: Optional[StateSchema] = None

    def _extract_ground_truths(self, task):
        """
        Override: 在原有提取之上，额外加载 state_schema。

        流程:
        1. super()._extract_ground_truths(task)  — 原有逻辑不变
        2. 如果 task 中有 state_schema 字段，解析并注册
        """
        super()._extract_ground_truths(task)

        # 新增: 加载 state_schema
        schema_data = task.get('state_schema')
        if schema_data:
            self._state_schema = StateSchema.from_dict(schema_data)
            # 注册到 StateAwareEvaluator
            if isinstance(self.evaluator, StateAwareEvaluator):
                self.evaluator.register_state_schema(self._state_schema)
            # 初始化 TaskProgress
            strategy = self._get_task_strategy(task.get('task_type', ''))
            phase_configs = strategy.phases if strategy else []
            self.task_progress = TaskProgress.from_state_schema(
                task_id=task.get('task_id', ''),
                task_type=task.get('task_type', ''),
                schema=self._state_schema,
                phase_configs=phase_configs,
            )
        # 否则: state_schema 缺失，不初始化，后续所有新增逻辑被跳过

    def step(self, vlm_response: str):
        """
        Override: 在原有 step 逻辑后，追加状态事件记录。

        流程:
        1. result = super().step(vlm_response)  — 完整的原有 step 逻辑
        2. 如果 task_progress 存在，更新阶段进度
        3. 如果 evaluator 是 StateAwareEvaluator，记录状态事件
        4. 返回原有 result（不修改其格式）
        """
        result = super().step(vlm_response)

        # 新增: 状态事件记录
        if self.task_progress and self._state_schema:
            self._record_state_events(vlm_response, result)

        return result

    def _record_state_events(self, vlm_response: str, step_result):
        """记录本轮的状态事件（全新方法，不覆盖父类）"""
        turn = self.state.current_turn if hasattr(self, 'state') else 0
        action = step_result.get('action', '') if isinstance(step_result, dict) else ''

        if isinstance(self.evaluator, StateAwareEvaluator):
            # 根据 action 类型决定事件类型
            event_type = 'observed'  # 默认
            if action in ('mislead', 'cross_image_confusion'):
                event_type = 'challenged'
            elif action in ('follow_up', 'fine_grained'):
                event_type = 'observed'

            # 对 state_schema 中的每个变量判断是否被本轮涉及
            for var_name, var in self._state_schema.variables.items():
                if self._is_variable_mentioned(vlm_response, var):
                    self.evaluator.record_state_event(turn, event_type, var_name)

    def _is_variable_mentioned(self, response: str, var) -> bool:
        """检查模型回答中是否提到了某个变量"""
        # 简单实现: 检查变量的 description 或 value 的关键词
        # 可以在后续用更精确的方法替代
        ...

    def _build_core_system_prompt(self):
        """Override: 委托给 PromptRouter"""
        if self._state_schema:
            system, _ = self.prompt_router.assemble_prompt(
                task_type=self.task_state.task_type if hasattr(self, 'task_state') else '',
                phase=self.state.phase.value if hasattr(self, 'state') else '',
                difficulty=getattr(self.task_state, 'difficulty_level', 1),
                turn_count=self.state.current_turn if hasattr(self, 'state') else 0,
                vlm_response='',
                history=[],
                state_context={'probing_variables': self._state_schema.probing_variables},
            )
            return system
        # 降级: 没有 state_schema，使用原有逻辑
        return super()._build_core_system_prompt()

    def _build_core_user_prompt(self, vlm_response='', **kwargs):
        """Override: 委托给 PromptRouter"""
        if self._state_schema:
            _, user = self.prompt_router.assemble_prompt(
                task_type=self.task_state.task_type if hasattr(self, 'task_state') else '',
                phase=self.state.phase.value if hasattr(self, 'state') else '',
                difficulty=getattr(self.task_state, 'difficulty_level', 1),
                turn_count=self.state.current_turn if hasattr(self, 'state') else 0,
                vlm_response=vlm_response,
                history=getattr(self, 'conversation_history', []),
            )
            return user
        # 降级
        return super()._build_core_user_prompt(vlm_response=vlm_response, **kwargs)
```

### 4.2 涉及文件

| 文件 | 改动方式 | 原有接口变化 |
|------|----------|:------------:|
| **新增** `src/simulator/stateful_simulator.py` | `StatefulStrategicSimulator(StrategicSimulator)` 子类 | N/A |
| `src/simulator/strategic_simulator.py` | **不修改** | 无 |

---

## 五、批处理与任务交叉测试

### 5.1 当前批处理机制

`batch_task_simulator.py` 的核心限制：
- 每个 task 创建新的 `StrategicSimulator` 实例（完全独立）
- 任务之间是完全串行的
- 跨任务记忆测试是 mock 实现
- 对话历史不跨 task 共享

### 5.2 改进方案：InterleavedBatchSimulator（子类扩展）

```python
# src/simulator/interleaved_batch.py — 独立新文件

from src.simulator.batch_task_simulator import BatchTaskSimulator
from src.simulator.stateful_simulator import StatefulStrategicSimulator
from src.simulator.task_progress import TaskProgress


class SharedConversationWindow:
    """同一个 batch 内的共享对话窗口 — 独立新类"""

    def __init__(self, max_turns: int = 50):
        self.max_turns = max_turns
        self.full_history: List[Dict] = []
        self.current_turn: int = 0
        self.task_contexts: Dict[str, Dict] = {}

    def add_turn(self, task_id: str, turn_data: Dict):
        turn_data['_task_id'] = task_id
        self.full_history.append(turn_data)
        self.current_turn += 1

    def get_history_for_target_model(self, compress: bool = True) -> List[Dict]:
        """所有任务的对话都在同一个窗口中"""
        if compress and len(self.full_history) > 10:
            return self._compress_early_history() + self.full_history[-10:]
        return self.full_history

    def get_history_for_core_model(self, current_task_id: str) -> str:
        """聚焦当前任务，压缩其他任务的信息"""
        focused = [h for h in self.full_history if h.get('_task_id') == current_task_id]
        other = [h for h in self.full_history if h.get('_task_id') != current_task_id]
        return f"[Current task: {len(focused)} turns] [Other tasks: {len(other)} turns compressed]"

    def _compress_early_history(self) -> List[Dict]:
        """压缩早期历史"""
        ...


class InterleavedScheduler:
    """阶段级交叉调度器 — 独立新类"""

    def __init__(self, tasks: List[Dict], strategy: str = "round_robin"):
        self.tasks = tasks
        self.strategy = strategy
        self.task_progress: Dict[str, TaskProgress] = {}

    def next_segment(self) -> Optional[Tuple[str, str]]:
        """返回下一个要执行的 (task_id, phase)，或 None 表示全部完成"""
        if self.strategy == "round_robin":
            return self._round_robin_next()
        elif self.strategy == "interleaved":
            return self._interleaved_next()
        return None

    def _interleaved_next(self) -> Optional[Tuple[str, str]]:
        """
        交叉策略:
        T1.obs → T2.obs → T3.obs → T1.probe → T2.probe → T1.final → T3.probe → ...
        """
        # 找到所有还有未完成阶段的任务
        # 按策略选择下一个 (task, phase) 组合
        ...

    def _round_robin_next(self) -> Optional[Tuple[str, str]]:
        ...

    def report_phase_done(self, task_id: str, phase: str):
        """报告某个 task 的某个 phase 完成"""
        ...


class InterleavedBatchSimulator(BatchTaskSimulator):
    """
    BatchTaskSimulator 的子类扩展。

    扩展点:
    1. run_batch(): override 支持阶段级交叉调度
    2. 组合 SharedConversationWindow + InterleavedScheduler
    3. 使用 StatefulStrategicSimulator 替代 StrategicSimulator

    安全性:
    - 原始 BatchTaskSimulator 的代码不被修改
    - 可以通过 interleave_mode=False 退回到原始串行行为
    - 原始 run_batch() 仍然可以通过 super() 调用
    """

    def __init__(self, *args, interleave_mode: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.interleave_mode = interleave_mode
        self.shared_window: Optional[SharedConversationWindow] = None
        self.scheduler: Optional[InterleavedScheduler] = None

    def run_batch(self, tasks: List[Dict], **kwargs):
        """
        Override: 支持交叉模式和串行模式。

        interleave_mode=False → super().run_batch(tasks) 原有行为
        interleave_mode=True  → 阶段级交叉调度
        """
        if not self.interleave_mode:
            return super().run_batch(tasks, **kwargs)

        return self._run_interleaved_batch(tasks, **kwargs)

    def _run_interleaved_batch(self, tasks: List[Dict], **kwargs):
        """交叉模式的 batch 执行（全新逻辑，不覆盖父类方法）"""
        self.shared_window = SharedConversationWindow(max_turns=self.config.max_turns_per_session)
        self.scheduler = InterleavedScheduler(tasks, strategy="interleaved")

        # 为每个 task 创建 StatefulStrategicSimulator（而非原始 StrategicSimulator）
        simulators: Dict[str, StatefulStrategicSimulator] = {}
        for task in tasks:
            task_id = task.get('task_id', str(id(task)))
            sim = StatefulStrategicSimulator(
                llm_client=self.llm_client,
                evaluator=StateAwareEvaluator(),  # 每个 task 独立的状态评估器
            )
            simulators[task_id] = sim

        # 交叉调度主循环
        while self.shared_window.current_turn < self.shared_window.max_turns:
            next_segment = self.scheduler.next_segment()
            if next_segment is None:
                break  # 所有任务所有阶段已完成

            task_id, phase = next_segment
            sim = simulators[task_id]

            # 执行该任务的该阶段（若干轮）
            self._run_phase_segment(sim, task_id, phase)

            self.scheduler.report_phase_done(task_id, phase)

        # 汇总报告
        return self._compile_interleaved_report(simulators)

    def _run_phase_segment(self, sim, task_id, phase):
        """执行一个 task 的一个 phase"""
        ...

    def _compile_interleaved_report(self, simulators):
        """汇总所有 task 的报告"""
        ...
```

### 5.3 涉及文件

| 文件 | 改动方式 | 原有接口变化 |
|------|----------|:------------:|
| **新增** `src/simulator/interleaved_batch.py` | `InterleavedBatchSimulator(BatchTaskSimulator)` 子类 | N/A |
| **新增** (同文件) | `SharedConversationWindow`, `InterleavedScheduler` 独立新类 | N/A |
| `src/simulator/batch_task_simulator.py` | **不修改** | 无 |

---

## 六、现有数据标注转化（而非完全重建）

> 此节是数据标注改进文档第 3.3 节和第 4.4 节的摘要。详细转化策略见数据标注改进文档。

### 6.1 转化可行性总结

| 任务类型 | 转化可行性 | primary variables | auxiliary variables | 需要额外操作 |
|----------|:---------:|:-----------------:|:-------------------:|:------------:|
| VNF | ★★★★★ | 完整 | 完整（`all_objects`） | 无 |
| RC | ★★★★☆ | 完整 | 部分（`co_occurring`） | 无 |
| ABR | ★★★★☆ | 完整 | 缺失 | 生成器 hook 补充 |
| AC | ★★★☆☆ | 完整 | 缺失 | 生成器 hook 补充 |
| LNF | ★★★☆☆ | 部分 | 部分 | 生成器 hook 补充 |

### 6.2 实施路径

1. **第一步（零成本）**: 用 `StateSchemaConverter` 转化 VNF + RC 的现有数据
2. **第二步（小幅修改）**: 在 `task_generators.py` 中通过后处理 hook 追加 `all_objects_in_image`
3. **第三步（批量转化）**: 运行 `tools/convert_annotations_to_schema.py`

详见: [数据标注改进文档](../数据标注改进/data_annotation_improvement.md) 第 4.4-4.5 节

---

## 七、安全性保证清单

| 保证项 | 实现方式 |
|--------|----------|
| `StrategicSimulator` 不被修改 | `StatefulStrategicSimulator` 是子类，所有 override 都先调用 `super()` |
| `BatchTaskSimulator` 不被修改 | `InterleavedBatchSimulator` 是子类，`interleave_mode=False` 退回原有行为 |
| `Evaluator` 不被修改 | `StateAwareEvaluator` 是子类（定义于状态测试改进文档） |
| `action_space.py` 已有条目不变 | 只在 `TASK_STRATEGIES` 字典中追加新 key |
| `task_config.py` 已有条目不变 | 只在 `TASK_CONFIGS` 字典中追加新 key |
| `memory_store.py` 不被修改 | 通过 `SharedConversationWindow` 独立管理共享历史 |
| `simulator_state.py` 不被修改 | 通过独立的 `TaskProgress` 模块管理进度追踪 |
| 没有 `state_schema` 时全部降级 | 所有新增子类检测 `state_schema` 是否存在，缺失时调用 `super()` |
| 可以随时回退 | 用原始类替代子类即可恢复全部原有行为 |

---

## 八、实施优先级与依赖关系

```
依赖关系图（含跨文档依赖）:

  ┌──────────────────────────┐
  │ [数据] state_schema_types │ ← 最先实现，三份文档的基础
  └────────────┬─────────────┘
               │
  ┌────────────▼─────────────┐     ┌────────────────────────┐
  │ [对话] 补全 RC/LNF 策略   │     │ [数据] StateSchemaConv. │ ← 独立，可并行
  │ (追加 action_space/       │     │ + 转化脚本              │
  │  task_config)             │     └────────────┬───────────┘
  └────────────┬─────────────┘                   │
               │                                  │
  ┌────────────▼─────────────┐     ┌──────────────▼──────────┐
  │ [对话] PromptRouter       │     │ [评测] StateEvolution   │
  │ (独立新类)                │     │ Tracker (独立新类)       │
  └────────────┬─────────────┘     └──────────────┬──────────┘
               │                                  │
               │                   ┌──────────────▼──────────┐
               │                   │ [评测] StateAware       │
               │                   │ Evaluator(Evaluator)    │
               │                   └──────────────┬──────────┘
               │                                  │
  ┌────────────▼──────────────────────────────────▼──┐
  │ [对话] StatefulStrategicSimulator(Strategic...)    │
  │ 组合 PromptRouter + StateAwareEvaluator           │
  └────────────┬─────────────────────────────────────┘
               │
  ┌────────────▼──────────────────────────────────────┐
  │ [对话] InterleavedBatchSimulator(Batch...)          │
  │ + SharedConversationWindow + InterleavedScheduler   │
  │ + TaskProgress                                      │
  └────────────────────────────────────────────────────┘
```

**推荐执行顺序**:
1. **共享基础**: `state_schema_types.py`（数据标注改进文档）
2. **并行启动**: 补全 RC/LNF 策略 + `StateSchemaConverter` + 转化脚本
3. **然后并行**: `PromptRouter` + `StateEvolutionTracker` + `StateAwareEvaluator`
4. **然后**: `StatefulStrategicSimulator`
5. **最后**: `InterleavedBatchSimulator` + `SharedConversationWindow` + `TaskProgress`

---

## 九、新增文件总览（三份文档合计）

| 文件 | 来源文档 | 类型 |
|------|----------|------|
| `src/simulator/state_schema_types.py` | 数据标注改进 | 共享类型定义 |
| `dataprovider/state_schema_converter.py` | 数据标注改进 | 转化器 |
| `dataprovider/state_schema_hooks.py` | 数据标注改进 | 生成器 hook |
| `tools/convert_annotations_to_schema.py` | 数据标注改进 | 批量脚本 |
| `src/simulator/state_evolution.py` | 状态测试改进 | StateEvolutionTracker |
| `src/simulator/state_aware_evaluator.py` | 状态测试改进 | StateAwareEvaluator(Evaluator) |
| `src/simulator/task_progress.py` | 对话测试改进 | TaskProgress, PhaseCompletion |
| `src/simulator/prompt_router.py` | 对话测试改进 | PromptRouter + 模板 |
| `src/simulator/stateful_simulator.py` | 对话测试改进 | StatefulStrategicSimulator(StrategicSimulator) |
| `src/simulator/interleaved_batch.py` | 对话测试改进 | InterleavedBatchSimulator(BatchTaskSimulator) + 调度器 |
