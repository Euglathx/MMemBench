# 2026-03-24 Follow-up Task Pack

> 本目录中的文档默认用于**多窗口并行执行**与**后续窗口交接**。
>
> 维护原则：
> - 每份文档都应只负责一个清晰问题域。
> - 每份文档都应能独立交给另一个窗口继续推进。
> - 每份文档都应明确：背景、范围、依赖、输出、关键检查点。
> - 当前目录中的方向性方案优先于实现细节；详细计划在后续窗口继续细化。

本目录用于承接 2026-03-24 之后的修复与重构工作，目标不是一次性写完详细实现计划，而是先把问题拆清楚、接口理顺、耦合关系说明白，并确定一批可维护、可分阶段推进的任务文档。

## 核心背景

当前 interleaved 日志已经暴露出一组不是“说法层面”而是“协议与实现层面”的问题：

1. `state_schema` 没有成功注册到正式运行链路，导致当前日志并没有真正进行状态级评测。
2. simulator 与 evaluator 对“图片是否可用于当前轮评测”的理解不一致。
3. 一些日志字段（如 `images_sent_count`）的语义不清，难以支撑论文中的 Information Decoupling 叙事。
4. 评测维度中仍存在 N/A 默认满分的设计，这不适合作为正式论文报告协议。
5. 批量化实验与 baseline ablation 需要建立在“单条任务跑通且日志可信”的前提上。

## 文档结构

### 0. [00_execution_roadmap_and_milestones.md](00_execution_roadmap_and_milestones.md)
**总控文档。建议主控窗口先读。**

用于多窗口并行执行时的总路线图、依赖关系、执行顺序、里程碑、检查点与交接规范。

### 1. [01_state_schema_registration.md](01_state_schema_registration.md)
**最高优先级。**

聚焦 `state_schema` 注册失败问题。说明为什么 2026-03-09 的方案虽然方向正确，但这次运行中仍然出现 `no_schema_registered`；明确排查顺序、接口契约、测试方案，以及必须达到的验收标准。

### 2. [02_image_delivery_reliability.md](02_image_delivery_reliability.md)
聚焦图片发送链路不稳定的问题。讨论它为什么会污染整批实验，除了“整批丢弃”之外还有哪些可接受的缓解方案，以及不同方案对论文价值、可解释性和 reviewer 质疑的影响。

### 3. [03_image_reference_accounting.md](03_image_reference_accounting.md)
聚焦 `images_sent_count` 等字段的定义和用途。目标是明确“这个字段到底记录什么、给谁用、能不能支撑论文叙事”，并给出保留/重命名/删除的方向性方案。

### 4. [04_evaluator_simulator_protocol_alignment.md](04_evaluator_simulator_protocol_alignment.md)
聚焦 simulator 与 evaluator 的协议同步问题。这份文档是本轮工作中除了 state schema 外最重要的一份：它直接关系到当前评测是否真的在评价 earlier observation / memory content，以及 interleaved 模式下 evaluator 是否应当获得缓存图片。

### 5. [05_scoring_and_reporting_cleanup.md](05_scoring_and_reporting_cleanup.md)
聚焦默认分数、aggregate score、image policy 等正式报告问题。目标是定义一套适合论文的正式评测输出协议，避免默认满分污染最终结果。

### 6. [06_batch_experiment_plan_and_future_directions.md](06_batch_experiment_plan_and_future_directions.md)
聚焦批量化测试、baseline ablation，以及暂时不立刻开工但值得保留的未来方向（如 cross-task memory test、failure taxonomy 等）。

## 推荐执行顺序

### Phase A: 先把单条任务协议跑通
1. `01_state_schema_registration.md`
2. `04_evaluator_simulator_protocol_alignment.md`
3. `03_image_reference_accounting.md`
4. `05_scoring_and_reporting_cleanup.md`

### Phase B: 再处理运行稳定性与批量化
5. `02_image_delivery_reliability.md`
6. `06_batch_experiment_plan_and_future_directions.md`

## 依赖关系总览

```text
01_state_schema_registration
    ├─ provides: state-level runtime contract
    └─ required by: 04, 05, 06

02_image_delivery_reliability
    ├─ provides: image delivery validity policy
    └─ required by: 05, 06

03_image_reference_accounting
    ├─ provides: logging semantics for image usage
    └─ required by: 04, 05, 06

04_evaluator_simulator_protocol_alignment
    ├─ consumes: 01, 03
    ├─ informed by: 02
    ├─ provides: formal evaluation protocol
    └─ required by: 05, 06

05_scoring_and_reporting_cleanup
    ├─ consumes: 02, 04
    ├─ provides: official report schema
    └─ required by: 06

06_batch_experiment_plan_and_future_directions
    └─ consumes: 01-05
```

## 当前结论

在进入大规模 batch 之前，必须先把下面三件事做实：

1. **state schema 真正注册并生效**。
2. **evaluator 能明确知道当前轮是在评 fresh visual evidence 还是 recalled state**。
3. **最终报告不再包含默认满分或语义模糊的日志字段**。

否则后续批量结果即使很多，也很难支撑论文主张。
