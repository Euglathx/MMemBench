是、d# 状态测试改进：从表面一致性检查到状态维护正确性评测

> **安全性原则**: 本文档所有改动均为 **扩展而非覆盖**。现有 `Evaluator` 类不做任何修改，新增 `StateAwareEvaluator(Evaluator)` 子类来承载状态评测逻辑。现有 `EvaluatorStateSnapshot` 保持不变，新增 `StateEnrichedSnapshot` 子类扩展其字段。当 task 中不包含 `state_schema` 字段时，`StateAwareEvaluator` 的所有新增方法自动退化为 no-op，行为与原始 `Evaluator` 完全一致。

---

## 0. 跨文档接口契约

本文档是三份改进文档的 **评测层**，它消费数据标注改进产出的 `state_schema`，并为对话和测试改进提供评测能力：

```
┌─────────────────────────────────────────────────────────────────┐
│  数据标注改进                                                    │
│  产出: state_schema 字段, state_schema_types.py                  │
├──────────────────────────┬──────────────────────────────────────┤
│            ▼ 本文档消费   │                                      │
│  本文档: 状态测试改进                                            │
│  消费: StateSchema, StateVariable (from state_schema_types.py)   │
│  产出: StateAwareEvaluator (extends Evaluator)                   │
│  产出: StateEvolutionTracker (独立新类)                           │
│  产出: StateEnrichedSnapshot (extends EvaluatorStateSnapshot)    │
├──────────────────────────┬──────────────────────────────────────┤
│            ▼ 下游消费     │                                      │
│  对话和测试改进                                                  │
│  消费: StateAwareEvaluator (注入到 StatefulStrategicSimulator)   │
│  消费: StateEvolutionTracker (在 step() 扩展中驱动)              │
└─────────────────────────────────────────────────────────────────┘
```

**依赖的共享类型**: `src/simulator/state_schema_types.py`（定义于数据标注改进文档）

---

## 1. 任务背景

### 1.1 论文目标

论文的评测对象是：

> "模型能不能把不断到来的信息流压缩成一个足以支撑任务的动态状态，并在之后只基于这个状态做决策"

这意味着评测系统需要能够：
1. 在每一轮对话后，判断模型的内部状态是否正确
2. 区分"状态被正确维护"和"模型恰好答对了"
3. 追踪状态变量在对话过程中的演化轨迹
4. 识别状态维护的具体失败模式（遗忘、混淆、被误导篡改等）

### 1.2 为什么需要改进

当前的评测系统虽然有 7 个维度和 turn-level ground truth，但它本质上还是在做 **回答质量评估**，而非 **状态维护正确性评估**。它不知道"在第 N 轮时，模型的状态应该是什么样的"，因此无法判断"状态维护是否正确"。

---

## 2. 涉及的文件和接口

### 2.1 现有文件（只读参考，不修改）

| 文件 | 行数 | 关键接口 | 为什么不改 |
|------|------|----------|------------|
| `src/simulator/evaluator.py` | ~2230 | `Evaluator`, `evaluate_response()`, `EvaluatorStateSnapshot` | 核心评测逻辑完整，通过子类扩展 |
| `src/simulator/strategic_simulator.py` | ~2249 | `StrategicSimulator`, `step()` | 核心 simulator 逻辑完整，在对话改进文档中通过子类扩展 |
| `src/simulator/memory_store.py` | ~200 | `MemoryStore`, `TurnRecord` | 记忆存储不变，通过组合扩展 |
| `src/simulator/simulator_state.py` | ~228 | `SimulatorState`, `ResponseEvaluation` | 状态机不变，通过独立的 tracker 扩展 |

### 2.2 新增文件

| 文件 | 作用 | 被谁消费 |
|------|------|----------|
| **`src/simulator/state_aware_evaluator.py`** | `StateAwareEvaluator(Evaluator)` 子类 | 对话改进的 `StatefulStrategicSimulator` |
| **`src/simulator/state_evolution.py`** | `StateEvolutionTracker` 独立类 | `StateAwareEvaluator`, `StatefulStrategicSimulator` |

### 2.3 扩展关系图

```
现有类（不修改）              新增类（扩展）
─────────────────          ──────────────────────────
Evaluator                  StateAwareEvaluator(Evaluator)
  ├─ evaluate_response()     ├─ evaluate_response()  # override: 在原有逻辑后追加状态比对
  ├─ _compute_*_score()      ├─ _compute_state_maintenance_score()  # 新增维度
  ├─ register_key_fact()     ├─ register_state_schema()  # 新增: 注册 state_schema
  └─ enable_snapshots        └─ state_tracker: StateEvolutionTracker  # 新增: 组合

EvaluatorStateSnapshot     StateEnrichedSnapshot(EvaluatorStateSnapshot)
  ├─ turn, response          ├─ (继承所有原有字段)
  ├─ hard/dynamic/llm_scores ├─ expected_state: Dict    # 新增
  └─ overall_score           ├─ actual_state: Dict      # 新增
                             └─ state_comparison: Dict   # 新增

(无)                       StateEvolutionTracker (独立新类)
                             ├─ __init__(state_schema)
                             ├─ record_event()
                             ├─ get_expected_state_at_turn()
                             ├─ extract_actual_state()
                             ├─ compare_states()
                             └─ diagnose_failure()
```

---

## 3. 当前进度和缺陷

### 3.1 已有的基础

1. **Turn-Level Ground Truth**: 每个 turn 有独立的 sub_goal 和 expected_answer，中间 turn 不用最终答案评分 —— 这是正确的方向
2. **Multi-Dimensional Scoring**: 7 个维度覆盖了多个方面
3. **EvaluatorStateSnapshot**: 已有状态快照基础设施，但只记录评分，不记录状态
4. **Injected Falsehoods Tracking**: 追踪误导注入，检查模型抵抗情况
5. **Claim Validation**: 提取并验证模型的事实声明
6. **Consistency Check（回马枪）**: 对话末尾重新问原始问题
7. **Cross-Image Object Mapping**: 跨图物体追踪机制已存在

### 3.2 核心缺陷

**缺陷 1: TurnGroundTruth 是描述性文本，不是可校验的状态**

当前的 `expected_answer` 是 `"Model should identify/describe the person"` 这样的文本，不是 `{"v1_dog_count": 3, "v2_person_exists": true}` 这样的结构化状态。

**缺陷 2: 没有"预期状态 vs 实际状态"的对比**

评估器在每一轮只做了"回答 vs 期望回答"的文本比较。它不会维护一个 `expected_state_at_turn_N` 和 `actual_state_at_turn_N` 来做结构化对比。

**缺陷 3: 无法区分不同的状态失败模式**

当模型在 Final Question 阶段答错时，当前评估系统只知道"答错了"，但不知道是因为：
- (a) 模型在 Observation 阶段就没观察到相关信息（**采集失败**）
- (b) 模型观察到了但在 Probing 阶段遗忘了（**状态衰减**）
- (c) 模型记住了但在 Stress Test 中被误导改变了（**鲁棒性失败**）
- (d) 模型的信息都正确但推理出了错误结论（**推理失败**）

**缺陷 4: 最终评分丢失了状态演化信息**

`per_turn` scores 是一个扁平列表，丢失了"在关键状态转移点（如误导注入后）模型做了什么"这样的关键信息。

**缺陷 5: Dynamic Scoring 基于文本匹配，不基于状态变量**

`_compute_consistency_score()` 通过比较当前回答和之前回答的文本来检测矛盾。但它不知道矛盾的性质（哪一方是正确的）。

---

## 4. 最终要求

### 4.1 StateEvolutionTracker — 状态演化追踪器（独立新类）

```python
# src/simulator/state_evolution.py
"""
状态演化追踪器 - 独立新类，不继承任何现有类。
消费 state_schema_types.py 中的共享类型。
"""

from src.simulator.state_schema_types import StateSchema, StateVariable, VariableRelevance


class VariableStatus(Enum):
    """变量在某一轮时的状态"""
    NOT_YET_OBSERVED = "not_yet_observed"
    OBSERVED = "observed"
    CHALLENGED_BUT_MAINTAINED = "challenged_but_maintained"
    MISLEAD_ACCEPTED = "mislead_accepted"
    UPDATED = "updated"
    FORGOTTEN = "forgotten"


@dataclass
class VariableStateAtTurn:
    """某个变量在某一轮时的预期状态"""
    name: str
    expected_value: Any
    status: VariableStatus
    last_event: str        # 'initial_observation', 'mislead_rejected', 'mislead_accepted', ...
    confidence: float      # 我们对"模型应该知道这个值"的信心 (0~1)


@dataclass
class ExpectedStateAtTurn:
    """某一轮时模型应该维护的完整状态快照"""
    turn: int
    variables: Dict[str, VariableStateAtTurn]


@dataclass
class ActualStateAtTurn:
    """从模型回答中提取的实际状态"""
    turn: int
    extracted_claims: Dict[str, Any]    # variable_name -> 模型声称的值
    extraction_confidence: float        # 整体提取置信度


@dataclass
class StateComparisonResult:
    """预期状态 vs 实际状态的比对结果"""
    turn: int
    matches: List[str]              # 正确维护的变量名
    mismatches: List[Dict]          # [{'variable': ..., 'expected': ..., 'actual': ..., 'reason': ...}]
    not_probed: List[str]           # 未被检查的变量名
    failure_mode: Optional[str]     # 主要失败模式


@dataclass
class StateEvent:
    """一次状态事件"""
    turn: int
    event_type: str     # 'observed', 'challenged', 'maintained', 'changed', 'forgotten', 'confused'
    variable: str
    details: Dict


class StateEvolutionTracker:
    """
    追踪状态变量在对话过程中的演化。

    独立新类，不继承任何现有类。
    通过 state_schema (from state_schema_types.py) 初始化。
    当 state_schema 为空时，所有方法返回空结果（优雅降级）。
    """

    def __init__(self, state_schema: Optional[StateSchema] = None):
        self.schema = state_schema
        self.evolution_log: List[StateEvent] = []
        self._variable_history: Dict[str, List[StateEvent]] = {}

        # 从 schema 初始化变量状态
        if self.schema:
            for name in self.schema.variables:
                self._variable_history[name] = []

    @property
    def is_active(self) -> bool:
        """是否有有效的 schema（用于下游判断是否启用状态评测）"""
        return self.schema is not None and len(self.schema.variables) > 0

    def record_event(self, turn: int, event_type: str, variable: str, details: Dict = None):
        """记录一次状态事件"""
        if not self.is_active:
            return
        event = StateEvent(turn=turn, event_type=event_type, variable=variable, details=details or {})
        self.evolution_log.append(event)
        if variable in self._variable_history:
            self._variable_history[variable].append(event)

    def get_expected_state_at_turn(self, turn: int) -> ExpectedStateAtTurn:
        """基于 schema 和已发生的事件，计算第 N 轮时的预期状态"""
        if not self.is_active:
            return ExpectedStateAtTurn(turn=turn, variables={})

        variables = {}
        for name, var in self.schema.variables.items():
            history = [e for e in self._variable_history.get(name, []) if e.turn <= turn]
            status, confidence = self._compute_variable_status(var, history)
            variables[name] = VariableStateAtTurn(
                name=name,
                expected_value=var.value,
                status=status,
                last_event=history[-1].event_type if history else 'none',
                confidence=confidence,
            )
        return ExpectedStateAtTurn(turn=turn, variables=variables)

    def _compute_variable_status(self, var: StateVariable,
                                  history: List[StateEvent]) -> Tuple[VariableStatus, float]:
        """根据事件历史推断变量的当前状态和置信度"""
        if not history:
            return VariableStatus.NOT_YET_OBSERVED, 0.0

        last_event = history[-1]
        status_map = {
            'observed': VariableStatus.OBSERVED,
            'maintained': VariableStatus.CHALLENGED_BUT_MAINTAINED,
            'changed': VariableStatus.MISLEAD_ACCEPTED,
            'forgotten': VariableStatus.FORGOTTEN,
        }
        status = status_map.get(last_event.event_type, VariableStatus.OBSERVED)

        # 置信度: 越近期被观察到，置信度越高
        confidence = 1.0 if last_event.event_type in ('observed', 'maintained') else 0.3
        return status, confidence

    def compare_states(self, turn: int,
                       actual: ActualStateAtTurn) -> StateComparisonResult:
        """比对预期状态和实际状态"""
        if not self.is_active:
            return StateComparisonResult(turn=turn, matches=[], mismatches=[], not_probed=[], failure_mode=None)

        expected = self.get_expected_state_at_turn(turn)
        matches, mismatches, not_probed = [], [], []

        for name, expected_var in expected.variables.items():
            if name in actual.extracted_claims:
                if self._values_match(expected_var.expected_value, actual.extracted_claims[name]):
                    matches.append(name)
                else:
                    mismatches.append({
                        'variable': name,
                        'expected': expected_var.expected_value,
                        'actual': actual.extracted_claims[name],
                        'status_before': expected_var.status.value,
                    })
            else:
                not_probed.append(name)

        failure_mode = self._diagnose_failure(mismatches, expected) if mismatches else None
        return StateComparisonResult(
            turn=turn, matches=matches, mismatches=mismatches,
            not_probed=not_probed, failure_mode=failure_mode,
        )

    def _values_match(self, expected: Any, actual: Any) -> bool:
        """比较两个值是否匹配（支持模糊匹配）"""
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            return abs(expected - actual) < 0.01
        return str(expected).lower().strip() == str(actual).lower().strip()

    def _diagnose_failure(self, mismatches: List[Dict],
                           expected: ExpectedStateAtTurn) -> str:
        """诊断主要失败模式"""
        for mm in mismatches:
            var_name = mm['variable']
            status = mm.get('status_before', '')
            if status == VariableStatus.NOT_YET_OBSERVED.value:
                return 'observation_miss'
            elif status == VariableStatus.OBSERVED.value:
                return 'state_decay'
            elif status == VariableStatus.CHALLENGED_BUT_MAINTAINED.value:
                return 'state_decay'  # 曾经抵抗了但后来还是忘了
            elif status == VariableStatus.MISLEAD_ACCEPTED.value:
                return 'mislead_acceptance'
        return 'unknown'

    def get_evolution_summary(self) -> List[Dict]:
        """获取所有变量的演化轨迹摘要"""
        if not self.is_active:
            return []

        summaries = []
        for name, history in self._variable_history.items():
            trajectory = " -> ".join([e.event_type for e in history]) if history else "not_observed"
            final_status = history[-1].event_type if history else "not_observed"
            correct = final_status in ('observed', 'maintained')
            summaries.append({
                'variable': name,
                'trajectory': trajectory,
                'final_status': final_status,
                'correct': correct,
            })
        return summaries
```

### 4.2 StateAwareEvaluator — 扩展评估器（Evaluator 子类）

```python
# src/simulator/state_aware_evaluator.py
"""
StateAwareEvaluator - Evaluator 的子类扩展。
在原有 7 维评分之上，新增状态维护正确性评测。
当 task 没有 state_schema 时，行为与原始 Evaluator 完全一致。
"""

from src.simulator.evaluator import Evaluator, EvaluatorStateSnapshot
from src.simulator.state_evolution import StateEvolutionTracker, ActualStateAtTurn
from src.simulator.state_schema_types import StateSchema


@dataclass
class StateEnrichedSnapshot(EvaluatorStateSnapshot):
    """
    扩展的快照，在原有字段基础上新增状态比对信息。
    继承 EvaluatorStateSnapshot 的所有字段。
    """
    expected_state: Optional[Dict] = None       # 本轮的预期状态
    actual_state: Optional[Dict] = None         # 本轮从回答中提取的状态
    state_comparison: Optional[Dict] = None     # 比对结果
    state_maintenance_score: Optional[float] = None


class StateAwareEvaluator(Evaluator):
    """
    Evaluator 的子类，新增状态维护正确性评测。

    扩展策略:
    1. __init__ 调用 super().__init__()，追加 state_tracker 属性
    2. evaluate_response() 调用 super().evaluate_response() 获得原有评分，
       然后在结果中追加 state_comparison 信息
    3. 当没有 state_schema 时，所有新增逻辑被跳过，行为等同原始 Evaluator

    注入方式:
    - 在 StatefulStrategicSimulator 中，用 StateAwareEvaluator 替代 Evaluator
    - 原始 StrategicSimulator 仍然使用原始 Evaluator，不受影响
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_tracker: Optional[StateEvolutionTracker] = None

    def register_state_schema(self, state_schema: StateSchema):
        """
        注册 state_schema，初始化状态追踪器。
        新增方法，不覆盖任何父类方法。
        """
        self.state_tracker = StateEvolutionTracker(state_schema)

    def evaluate_response(self, response: str, expected_answer: str,
                          action_type: str, question_asked: str,
                          context: Dict = None, **kwargs) -> Dict:
        """
        扩展的评测方法。

        流程:
        1. 调用 super().evaluate_response() 获得原有 7 维评分
        2. 如果 state_tracker 存在且活跃，追加状态比对
        3. 将状态比对结果附加到返回的 eval_result 中
        """
        # Step 1: 原有评测（完全不变）
        eval_result = super().evaluate_response(
            response=response,
            expected_answer=expected_answer,
            action_type=action_type,
            question_asked=question_asked,
            context=context,
            **kwargs
        )

        # Step 2: 状态评测（仅在 tracker 存在时）
        if self.state_tracker and self.state_tracker.is_active:
            turn = context.get('turn', 0) if context else 0
            state_eval = self._evaluate_state_maintenance(response, turn, context)
            eval_result['state_evaluation'] = state_eval
        # 否则 eval_result 与原始 Evaluator 完全一致

        return eval_result

    def _evaluate_state_maintenance(self, response: str, turn: int,
                                     context: Dict) -> Dict:
        """
        状态维护评测（全新逻辑，不覆盖任何父类方法）。

        1. 从回答中提取模型声称的状态
        2. 获取预期状态
        3. 比对并诊断
        """
        # 提取实际状态
        actual = self._extract_state_from_response(response, turn)

        # 比对
        comparison = self.state_tracker.compare_states(turn, actual)

        # 计算状态维护分数
        total_probed = len(comparison.matches) + len(comparison.mismatches)
        score = len(comparison.matches) / total_probed if total_probed > 0 else None

        return {
            'comparison': {
                'matches': comparison.matches,
                'mismatches': comparison.mismatches,
                'not_probed': comparison.not_probed,
                'failure_mode': comparison.failure_mode,
            },
            'state_maintenance_score': score,
        }

    def _extract_state_from_response(self, response: str,
                                      turn: int) -> ActualStateAtTurn:
        """
        从模型回答中提取结构化状态。
        利用父类已有的 _extract_factual_claims() 能力。

        策略:
        1. 使用规则匹配提取数值型声明 (count, boolean)
        2. 如果启用了 LLM judge，用 LLM 辅助提取复杂声明
        3. 将提取结果映射到 state_schema 的变量名
        """
        claims = {}
        confidence = 0.5

        # 利用 state_tracker.schema 知道要提取哪些变量
        if self.state_tracker and self.state_tracker.schema:
            for var_name, var in self.state_tracker.schema.variables.items():
                extracted = self._try_extract_variable(response, var)
                if extracted is not None:
                    claims[var_name] = extracted

            if claims:
                confidence = len(claims) / len(self.state_tracker.schema.variables)

        return ActualStateAtTurn(turn=turn, extracted_claims=claims,
                                 extraction_confidence=confidence)

    def _try_extract_variable(self, response: str, var) -> Optional[Any]:
        """尝试从回答中提取单个变量的值"""
        # 策略 1: 数值型 → 正则匹配
        # 策略 2: 布尔型 → 关键词检测
        # 策略 3: 复杂型 → LLM 辅助（如果启用）
        # 具体实现待定，这里给出框架
        ...

    def record_state_event(self, turn: int, event_type: str,
                            variable: str, details: Dict = None):
        """
        记录状态事件的便捷方法。
        代理到 state_tracker.record_event()。
        新增方法，不覆盖任何父类方法。
        """
        if self.state_tracker:
            self.state_tracker.record_event(turn, event_type, variable, details)

    def get_state_tracking_report(self) -> Dict:
        """
        生成最终的状态追踪报告。
        新增方法，不覆盖任何父类方法。
        """
        if not self.state_tracker or not self.state_tracker.is_active:
            return {}  # 降级: 没有 schema 就不产出报告

        evolution = self.state_tracker.get_evolution_summary()
        total = len(evolution)
        correct = sum(1 for e in evolution if e['correct'])

        # 失败模式统计
        failure_counts = {}
        for event in self.state_tracker.evolution_log:
            if event.event_type in ('forgotten', 'changed', 'confused'):
                mode = event.event_type
                failure_counts[mode] = failure_counts.get(mode, 0) + 1

        return {
            'total_variables': total,
            'correctly_maintained': correct,
            'state_maintenance_score': correct / total if total > 0 else 0,
            'failure_breakdown': failure_counts,
            'evolution_summary': evolution,
        }
```

### 4.3 失败模式分类

| 失败模式 | 描述 | 诊断标准 |
|----------|------|----------|
| **Observation Miss** | 模型从未正确观察到某个变量 | Observation 阶段的 probe 就已经答错 |
| **State Decay** | 模型观察到了但后来遗忘了 | 早期 probe 正确，后期 probe 错误 |
| **Mislead Acceptance** | 模型被误导信息改变了正确状态 | 误导注入前正确，注入后错误 |
| **Cross-State Confusion** | 模型将不同图片/物体的属性混淆 | 回答了其他变量的值 |
| **Reasoning Failure** | 基础变量都正确但推理出了错误结论 | 所有 primary variables 正确但 derived variable 错误 |
| **Attention Drift** | 模型被干扰信息吸引，忽略了核心变量 | distraction 后核心变量回忆失败 |

### 4.4 改进后的评测报告结构

```python
{
    "task_id": "...",

    # ======= 原有报告字段（完全保留不变） =======
    "per_turn_scores": [...],
    "final_scores": {...},
    "overall_score": 0.72,

    # ======= 新增: 状态追踪报告（可选，仅当 state_schema 存在时） =======
    "state_tracking_report": {
        "total_variables": 6,
        "correctly_maintained": 4,
        "state_maintenance_score": 0.67,
        "failure_breakdown": {
            "observation_miss": 0,
            "state_decay": 1,
            "mislead_acceptance": 1,
            "confusion": 0,
            "reasoning_failure": 0
        },
        "evolution_summary": [
            {"variable": "v1_dog_count", "trajectory": "observed -> challenged -> maintained", "correct": true},
            {"variable": "v2_cat_count", "trajectory": "observed -> forgotten", "correct": false},
            {"variable": "v3_person_color", "trajectory": "observed -> changed", "correct": false},
        ],
        "per_phase_scores": {
            "observation_completeness": 0.83,
            "probing_accuracy": 0.80,
            "noise_resistance": 0.50,
            "final_answer_correctness": 0.0
        }
    }
}
```

---

## 5. 安全性保证清单

| 保证项 | 实现方式 |
|--------|----------|
| 原有 `Evaluator` 类不被修改 | `StateAwareEvaluator` 是子类，通过 `super()` 调用原有逻辑 |
| 原有 `EvaluatorStateSnapshot` 不被修改 | `StateEnrichedSnapshot` 是子类，继承所有原有字段 |
| 没有 `state_schema` 时行为不变 | `StateEvolutionTracker.is_active` 返回 `False`，所有新增逻辑被跳过 |
| 原有 `evaluate_response()` 返回格式兼容 | 新增的 `state_evaluation` 字段是附加的，不改变原有字段 |
| 原有 `StrategicSimulator` 不受影响 | 它仍然使用原始 `Evaluator`，只有 `StatefulStrategicSimulator` 使用新子类 |
| 可以随时回退 | 把 `StateAwareEvaluator` 替换为 `Evaluator` 即可回到原有行为 |

---

## 6. 下一步要审查的内容

### 6.1 需要深入检查的文件

| 文件 | 审查目标 |
|------|----------|
| `src/simulator/evaluator.py` 的 `evaluate_response()` 完整签名 | 确认 super() 调用的参数和返回格式 |
| `src/simulator/evaluator.py` 的 `EvaluatorStateSnapshot` | 确认所有字段，以便 `StateEnrichedSnapshot` 正确继承 |
| `src/simulator/evaluator.py` 的 `register_key_fact()` / `register_injected_falsehood()` | 现有的事实注册机制，看是否可复用于 `record_state_event()` |
| `src/simulator/strategic_simulator.py` 的 `_extract_factual_claims()` | 现有的声明提取方法，看能否复用 |
| `src/simulator/entity_extractor.py` 完整内容 | 现有实体提取能力，看如何为 `_try_extract_variable()` 服务 |

### 6.2 需要确认的设计决策

1. **状态提取精度**: `_try_extract_variable()` 用规则匹配还是 LLM-as-extractor？建议：count/boolean 用规则，其余用 LLM
2. **probing 粒度**: 一个问题 probe 一个变量 vs 多个变量？建议：由对话改进文档的 `StatefulStrategicSimulator` 决定
3. **与 LLM-as-Judge 的关系**: state comparison 纯基于规则，LLM 只用于提取阶段
4. **向后兼容**: 新增的 `state_tracking_report` 是附加字段，原有报告格式不变

---

## 7. 初步计划

### Phase 1: 共享类型依赖
- 前置条件: 数据标注改进的 `state_schema_types.py` 已完成
- 验证: `StateSchema.from_dict()` 和 `.to_dict()` 工作正常

### Phase 2: StateEvolutionTracker
1. 实现 `src/simulator/state_evolution.py` 中的所有数据类和 `StateEvolutionTracker`
2. 编写单元测试（事件记录、预期状态计算、状态比对、失败诊断）
3. **降级测试**: schema 为空时所有方法返回空结果

### Phase 3: StateAwareEvaluator
1. 实现 `src/simulator/state_aware_evaluator.py`
2. 验证 `super().evaluate_response()` 调用正确
3. 实现基本的 `_extract_state_from_response()`（先用规则匹配）
4. **降级测试**: 不注册 schema 时行为与原始 Evaluator 一致

### Phase 4: 集成测试
1. 用已转化的 VNF 数据（有 state_schema）运行 StateAwareEvaluator
2. 用没有 state_schema 的旧数据运行，确认降级行为正确
3. 检查评测报告的 `state_tracking_report` 内容是否合理

### Phase 5: 失败模式诊断精化
1. 细化 `_diagnose_failure()` 的规则
2. 在实际日志中验证各失败模式的识别准确性
3. 如果规则不够精确，引入 LLM 辅助诊断（作为可选 fallback）

### Phase 6: 对接对话改进
1. 与 `StatefulStrategicSimulator` 集成（由对话改进文档驱动）
2. 确认 `record_state_event()` 在每轮被正确调用
3. 端到端测试: task + state_schema → 多轮对话 → state_tracking_report
