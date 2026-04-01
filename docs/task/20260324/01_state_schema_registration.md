# 01. State Schema 注册问题

> 本文档是一个**可维护的单问题文档**，默认交给单独窗口推进。
>
> 本文档负责：
> - 定位 `state_schema` 主链路断点
> - 明确 schema 注册的 runtime contract
> - 定义最小可运行 fixture、测试策略与 fail-fast 原则
>
> 本文档不负责：
> - evaluator/simulator 全协议重写
> - 正式 aggregate/report schema 设计
> - batch 主实验规模规划
>
> 上游依赖：任务数据或最小 fixture 能提供 `state_schema`。
>
> 主要输出：供 04/05/06 消费的 state-level runtime contract。

## 任务背景

`state_schema` 是当前论文叙事的中轴。没有它，系统只能做回答质量评估，而不能做真正的状态维护评估。

从最近的 interleaved 日志看，当前运行结果中普遍出现：

- `evaluator_state.status = "no_schema_registered"`
- `has_state_schema = false`
- `n_tracked_variables = 0`
- `variable_coverage = 0`

这说明 2026-03-09 的设计文档虽然方向对，但在正式运行链路里没有真正跑通。当前问题不是“还没做得够完整”，而是 **主链路没有成功接入**。

---

## 与其他窗口的耦合

### 本文档向外提供
- `require_state_schema` 的运行语义
- schema registration 成功/失败的日志约定
- 最小 fixture 与 smoke test 标准

### 本文档依赖外部确认
- 数据/任务生成侧是否真的写出 `state_schema`
- 04 是否需要额外的 turn-level state context
- 05 是否需要在正式报告层暴露哪些 state summary 字段

---

## 关键检查点

### Checkpoint 1：断点定位完成
- 已明确断在上游数据、runtime 注册、还是 evaluator 消费
- 不再只停留在“可能没接上”的模糊判断

### Checkpoint 2：最小闭环跑通
- 最小 task fixture 能注册 schema
- evaluator 与 task_progress 都能看到非空 state 信息

### Checkpoint 3：fail-fast 规则明确
- 已定义 `require_state_schema=True` 时的失效处理
- 已明确哪些结果应直接视为 invalid

### Checkpoint 4：测试交付可复用
- 单元、集成、日志审计三层测试点都已写清
- 下一窗口可以直接据此落测试与实现

---

## 当前现象与初步定位

### 已有设计

2026-03-09 的三份文档已经提出了一条很清晰的链路：

```text
data annotation
  -> task['state_schema']
  -> StatefulStrategicSimulator._extract_ground_truths()
  -> StateAwareEvaluator.register_state_schema()
  -> TaskProgress.from_state_schema()
  -> StateEvolutionTracker / state-level evaluation
```

而当前代码中：

- [src/simulator/stateful_simulator.py:111-118](../../../src/simulator/stateful_simulator.py#L111-L118) 确实尝试在 task 中读取 `state_schema`
- [src/simulator/state_aware_evaluator.py:44-51](../../../src/simulator/state_aware_evaluator.py#L44-L51) 确实提供了 `register_state_schema()`

但是：

- 当前 `StateAwareEvaluator` 仍然只是一个 **stub**，[src/simulator/state_aware_evaluator.py:1-105](../../../src/simulator/state_aware_evaluator.py#L1-L105)
- 当前运行日志表明实际 task 中大概率没有可用的 `state_schema`
- 即使注册成功，现有 evaluator 也还没有把 `state_schema` 用进正式评分主流程

### 为什么 2026-03-09 方案看起来“失败了”

初步反思，失败不是单点失败，而是三段链路同时没有闭合：

#### 1. 上游数据没有稳定提供 `state_schema`
之前文档重点在“定义 schema 结构”，但没有先用一个最小批次验证：
- 生成器是否真的把 `state_schema` 写入 JSONL
- 读取 task 时是否能读到
- 格式是否和 `StateSchema.from_dict()` 匹配

结果就是运行期很可能拿到的是“没有 schema 的旧 task”。

#### 2. runtime 虽有注册入口，但缺少强约束
当前 [src/simulator/stateful_simulator.py:111-130](../../../src/simulator/stateful_simulator.py#L111-L130) 的逻辑属于“有就注册、没有就降级”。这对兼容旧任务是安全的，但对论文实验阶段不够强。

因为它会让：
- 运行正常结束
- 日志里 quietly degrade
- 结果文件生成成功

但实际上主功能没生效。

#### 3. evaluator 主流程还没真正消费 schema
当前 `StateAwareEvaluator` 只记录 `_state_schema` 和 `_state_events`，并没有覆盖 `evaluate_response()` 来生成正式的 state-level scoring/reporting。

所以即使注册成功，目前也只是“有了一个 schema handle”，不是“做了 state evaluation”。

---

## 当前任务目标

本任务要完成三件事：

1. **确认 `state_schema` 的主链路到底断在哪里**。
2. **把 schema 注册变成实验前置条件，而不是可选降级项**。
3. **设计一套详细测试方案，确保它真正能跑起来。**

这份文档只定方向和接口，不展开最终实现细节。

---

## 初步方案

## 方案 1：把 state schema 分成两个阶段落地

### Stage 1: 先打通“可注册、可见、可验证”
目标不是立刻做完整 state evaluation，而是先保证：

- 任务 JSON 中存在 `state_schema`
- `StatefulStrategicSimulator` 能读到
- `StateAwareEvaluator` 能注册到
- `TaskProgress` 能看到 tracked variables
- 日志能显式写出 schema 摘要

如果这一层没通，后面谈状态评测都没有意义。

### Stage 2: 再做“参与正式评分”
在 Stage 1 通过后，再实现：

- expected state vs actual state comparison
- state maintenance score
- failure diagnosis
- final state report

---

## 接口与耦合关系

## 上游输入

### 必须输入
- `task['state_schema']`
- `state_schema` 与 `StateSchema.from_dict()` 兼容

### 上游来源
- 数据标注/转化侧
- 或最小人工构造 task fixture

## runtime 消费者

### `StatefulStrategicSimulator`
职责：
- 从 task 读取 schema
- 在 task 初始化时进行 schema 注册
- 初始化 `TaskProgress`
- 把 schema 是否成功加载写入 tracking log

### `StateAwareEvaluator`
职责：
- 接收 schema
- 在每轮评估中可访问当前 schema
- 输出 state-aware report

### `TaskProgress`
职责：
- 从 schema 初始化 tracked variables
- 让 phase completion 不再完全依赖 turn 数

---

## 强约束建议

为了避免之后继续 silently degrade，建议引入一个新的运行模式开关：

- `require_state_schema: bool`

语义：
- `False`：兼容旧任务，允许降级
- `True`：如果 task 没有 schema，直接把该 task 标记为 invalid，不进入正式实验结果

论文实验、正式 benchmark、批量化主实验，建议一律使用 `require_state_schema=True`。

---

## 详细测试方案（必须做）

这是当前所有任务里测试要求最高的一项。原因很简单：只要 state schema 没跑通，整篇论文的核心技术点都会被 reviewer 质疑。

## A. 单元测试

### A1. 类型与序列化测试
目标：确保 `StateSchema` 类型本身可靠。

覆盖点：
- `StateVariable.to_dict()/from_dict()` round-trip
- `Dependency.to_dict()/from_dict()` round-trip
- `StateSchema.to_dict()/from_dict()` round-trip
- 空 schema 的降级行为
- 缺字段/非法字段的报错行为

通过标准：
- round-trip 后对象语义一致
- 空 schema 不崩溃
- 非法 schema 不 silent pass

### A2. task fixture 注册测试
人工写 3 个最小 task fixture：
- VNF fixture
- AC fixture
- RC 或 ABR fixture

每个 fixture 都带一个极简但完整的 `state_schema`。

验证：
- `StatefulStrategicSimulator._extract_ground_truths()` 后，`self._state_schema is not None`
- evaluator 里 `_state_schema is not None`
- `task_progress.tracked_variables` 非空
- tracking log 中 `has_state_schema = true`

### A3. 断链测试
人工构造三种坏情况：
- task 中没有 `state_schema`
- schema 格式错误
- schema 中变量名和 probing phase 不匹配

验证：
- 在 `require_state_schema=False` 时优雅降级
- 在 `require_state_schema=True` 时正确 fail fast

---

## B. 集成测试

### B1. 生成器到 runtime 的端到端测试
从 dataprovider 真实生成一批最小任务：
- 1 个 VNF
- 1 个 AC
- 1 个 RC/ABR

检查：
1. 生成出的 JSONL 中是否真的写入 `state_schema`
2. runtime 读到 task 后是否真的完成注册
3. result log 中是否保留 schema 摘要

### B2. state-aware evaluator smoke test
即使 state scoring 还未完整实现，也必须有一个 smoke test：

- 注册 schema
- 记录至少 2 个 state events
- 调一次 `evaluate_response()`
- 最终 `get_state_report()` 返回非空结构

### B3. interleaved 模式兼容测试
因为正式实验主要是 interleaved：
- 多 task 连续执行后，schema 不应串任务污染
- 新 task 开始时 evaluator 必须 reset 并重注册 schema
- 上一个 task 的 tracked variables 不应留在下一个 task 里

---

## C. 日志与结果测试

### C1. 结果文件中必须出现的字段
正式实验的 task 结果里，至少要能看到：

```json
{
  "state_report": {
    "evaluator_state": {
      "status": "registered",
      "variables_total": 6
    },
    "task_progress": {
      "variable_coverage": 0.66
    }
  }
}
```

当前出现 `no_schema_registered` 就应视为失败样本，而不是正常结果。

### C2. 一致性检查
写一个离线检查脚本，自动扫结果文件并报错：
- `require_state_schema=True` 但 task 结果仍为 `no_schema_registered`
- `has_state_schema=true` 但 `n_tracked_variables=0`
- `state_schema` 存在但 `TaskProgress` 为空

---

## 缺陷排查顺序

建议严格按以下顺序排查：

1. **task 文件里到底有没有 `state_schema`**
2. `StateSchema.from_dict()` 是否能 parse
3. `StatefulStrategicSimulator` 是否真的被使用，而不是退回旧 simulator
4. evaluator 是否真的是 `StateAwareEvaluator`
5. `reset_for_task()` 是否把 schema 清掉后没有重新注册
6. interleaved 模式是否在 task 切换时丢失 schema
7. evaluator report 是否只是 stub 输出

这个顺序不要跳。否则很容易在 runtime 里乱修，最后发现根因只是上游任务没带 schema。

---

## Reviewer 可能会问什么

### Q1. 你们所谓的 state evaluation 是否真的在运行？
必须能用日志与测试回答：
- 是，task-level schema 已注册
- 是，runtime 中有 tracked variables
- 是，最终报告里能看到 state-level output

### Q2. 如果没有 schema 的 task 是否也进入主实验？
正式实验建议回答：
- 不进入
- 或单独列为 legacy mode，不和正式 benchmark 混算

### Q3. state schema 是否只是 final answer 的另一种写法？
后续需要靠内容设计回答：
- schema 包含 final-question variables 之外的 probing variables / auxiliary variables
- 不只是 answer serialization

---

## 本文档的阶段性验收标准

完成本任务后，至少应满足：

1. 能构造 3 个最小 schema task 并通过端到端测试。
2. 正式运行时，task result 中不再出现 `no_schema_registered`（在正式模式下）。
3. 能明确区分“schema 没有提供”与“schema 提供了但评测尚未完全实现”。
4. 为下一步 state-level scoring 留出稳定接口。

---

## 暂不展开的内容

本轮不在这里细化：
- state variable extraction 的 NLP 细节
- failure mode taxonomy 的正式算法
- state maintenance score 的最终公式

这些等 state schema 主链路跑通后再进入详细计划。
