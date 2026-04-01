# 05. 正式评分与报告协议清理

> 本文档是一个**可维护的单问题文档**，默认交给单独窗口推进。
>
> 本文档负责：
> - 移除默认满分/N/A 进主报告的路径
> - 定义 applicable-only aggregation 与 report schema 分层
> - 规定 aggregate、support、invalid summary 的正式输出要求
>
> 本文档不负责：
> - state schema 注册本身
> - evaluator/simulator turn protocol 的完整重写
> - pilot/main batch 的最终规模
>
> 上游依赖：04 提供 turn-level protocol，02 提供 validity policy。
>
> 主要输出：供 06 消费的 official report schema 与 aggregate contract。

## 与其他窗口的耦合

### 本文档向外提供
- applicable-only aggregation 规则
- runtime schema / report schema 的分层原则
- invalid sample summary 应如何进入正式报告

### 本文档依赖外部确认
- 04 提供 evaluator 输出字段与 turn context
- 02 提供 validity 标签与过滤规则
- 01 提供 state-related summary 是否已可稳定输出

---

## 关键检查点

### Checkpoint 1：默认满分路径切断
- 已明确哪些 N/A 逻辑必须从正式报告中移除
- 已明确 runtime/debug 与 paper/report 的边界

### Checkpoint 2：aggregate contract 成型
- 每个维度同时有 mean 与 support
- overall 不再混入未测维度

### Checkpoint 3：validity 过滤接入
- invalid task/turn 不再混进主 aggregate
- invalid sample summary 有统一出口

### Checkpoint 4：下游实验可消费
- 06 可以直接基于本文档设计 validation / pilot 的报告检查项
- reviewer 风险点已能被报告结构正面回答

---

## 任务背景

当前系统中存在一个不适合正式论文报告的问题：

- 某些维度在“不适用”时会默认给满分
- 一些日志和聚合逻辑还停留在 debug-friendly 而不是 paper-ready 的状态
- aggregate score 虽然有接口，但当前 interleaved 结果里仍出现空字典

你已经明确要求：

> 默认分数任何时候都不应该出现在最后的报告中。

这是对的。正式 benchmark 的主结果里不能包含“因为没测所以给 10 分”这种设计。

---

## 当前问题

从 [src/simulator/evaluator.py:203-240](../../../src/simulator/evaluator.py#L203-L240) 可以看到，当前多个维度在 N/A 时默认按 10 处理：

- robustness
- consistency（首轮）
- cross-image disambiguation
- ambiguity recognition

这种设计对在线调试友好，但对正式论文有两个问题：

1. 会抬高模型平均分
2. 会模糊“这个能力到底有没有被测到”

---

## 核心原则

## 原则 1：不适用不等于高分
N/A 应当是：
- 不进入正式 aggregate
- 单独记录适用次数

## 原则 2：正式报告与样品/调试协议解耦
如果某些任务需要：
- 先给样例图
- 做 warm-up
- 做 capability probing

那应当在实验协议层单走，不应通过“默认满分”塞进正式分数体系。

## 原则 3：每个维度都要同时报告 score 与 support
也就是：
- 平均分是多少
- 在多少个 applicable turns / tasks 上测得

---

## 推荐方案

## 一、引入 Applicable-Only Aggregation

对于每个维度，不再把 N/A turn 当作 10，而是：

- turn 级：`score = null`, `applicable = false`
- aggregate 级：只对 `applicable = true` 的 turn 求平均

### 例子

```json
{
  "robustness": {
    "mean": 0.42,
    "applicable_turns": 128,
    "total_turns": 640
  }
}
```

这样 reviewer 才知道 robustness 不是在所有 turn 上都被测了。

---

## 二、报告层分成两套 schema

## 1. Runtime/debug schema
保留较完整信息，便于开发：
- 原始 turn scores
- N/A 标记
- delivery validity
- phase info

## 2. Paper/report schema
只保留正式可报告内容：
- valid tasks only
- applicable-only aggregates
- 关键 phase / 关键 task type breakdown

不要直接把 runtime 的字段搬进论文表格。

---

## 三、aggregate score 需要补齐的内容

当前 [src/simulator/batch_task_simulator.py:545-592](../../../src/simulator/batch_task_simulator.py#L545-L592) 已经有聚合函数，但：
- 维度不全
- 不区分 applicable / non-applicable
- 当前 interleaved 结果里 aggregate 可能为空

建议新一版 aggregate 最少包含：

```json
{
  "overall": 0.61,
  "task_count_valid": 96,
  "turn_count_valid": 1820,
  "per_dimension": {
    "correctness": {"mean": 0.48, "applicable_turns": 1820},
    "faithfulness": {"mean": 0.67, "applicable_turns": 1820},
    "robustness": {"mean": 0.31, "applicable_turns": 420},
    "consistency": {"mean": 0.52, "applicable_turns": 1710},
    "memory_retention": {"mean": 0.44, "applicable_turns": 890},
    "cross_image_disambiguation": {"mean": 0.55, "applicable_turns": 260},
    "ambiguity_recognition": {"mean": 0.49, "applicable_turns": 180},
    "state_maintenance": {"mean": 0.41, "applicable_tasks": 96}
  },
  "per_phase": {...},
  "per_task_type": {...},
  "invalid_sample_summary": {...}
}
```

---

## 四、image policy 是否要加入 evaluator？

### 结论：要，但不要让 evaluator 自己推断。

image policy 是协议的一部分，应当由 simulator 提供给 evaluator。

### evaluator 需要知道的不是“策略名字本身”，而是策略结果
例如：
- 当前轮是否有 fresh 图
- 当前轮是否应该按 memory-only 评
- 当前轮是否允许 mixed evidence

### 可以保留 `image_policy` 字段的原因
1. 便于日志分析
2. 便于做 ablation
3. 便于 reviewer 理解 benchmark 的输入控制方式

### 推荐做法
- simulator 在 context 中传 `image_policy`
- evaluator 主要消费 `turn_input_mode`
- `image_policy` 更多用于 report / audit，不直接用于打分规则判断

---

## 五、正式报告中不应再出现的东西

1. 默认满分
2. 语义模糊的 legacy 字段
3. invalid 样本混入 aggregate
4. debug-only 解释直接作为论文主表输入

---

## 六、如果有“样品图”需求怎么办

你的判断是对的：

- 如果某类任务必须先给样例图
- 或先做 demonstration / warm-up

这必须和正式评测协议解耦。

### 建议做法
单独定义：
- `warmup_turns`
- `calibration_turns`

并规定：
- 不计入正式评分
- 不进入 aggregate
- 仅用于建立 interaction state 或验证模型是否能进入任务模式

不要通过默认分数把它们塞进主报告。

---

## Reviewer 可能会问什么

### Q1. 你们的 robustness 为什么这么高？
你需要能回答：
- 我们报告的是 applicable-only mean
- 并同时给出 applicable turn 数

### Q2. N/A turn 怎么处理？
回答：
- 不计分，只计 support

### Q3. 你们的 overall score 是否被某些未测维度虚高？
回答：
- 不会，因为 overall 只在明确的 report schema 上聚合

---

## 任务拆分

### 子任务 A：定义 runtime schema 与 report schema
### 子任务 B：让每个维度显式输出 applicable 标记
### 子任务 C：重写 aggregate 逻辑为 applicable-only
### 子任务 D：补充 per-phase / per-task-type aggregate
### 子任务 E：把 invalid sample summary 合入最终报告

---

## 阶段性验收标准

1. 正式报告中不再出现默认满分。
2. 每个维度都能看到 support 数量。
3. aggregate 不再为空。
4. image policy 与 turn input mode 能进入结果上下文。

---

## 暂不展开的内容

- 最终论文表格长什么样
- overall score 的最终权重是否要调整
- 是否需要额外的 calibration appendix

这些等正式实现后再定。
