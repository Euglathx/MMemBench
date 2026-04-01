# 06. 批量化实验方案与未来方向

> 本文档是一个**可维护的单问题文档**，默认交给单独窗口推进。
>
> 本文档负责：
> - 定义 validation batch / pilot batch 的进入条件与最小方案
> - 整理 baseline ablation 的初步设计
> - 把 cross-task memory、failure taxonomy 等方向明确留在 future work
>
> 本文档不负责：
> - 先行修复 schema/protocol/reporting 主链路
> - 直接启动 main batch
> - 在本轮落地复杂 future-work 实现
>
> 上游依赖：01-05 的阶段性结果，尤其是 schema、protocol、validity、report schema 已稳定。
>
> 主要输出：实验规划、批量化进入条件与未来方向边界。

## 与其他窗口的耦合

### 本文档向外提供
- validation batch / pilot batch 的进入条件
- baseline ablation 的最小设计框架
- future work 与当前主线的边界

### 本文档依赖外部确认
- 01 是否已解决 schema 主链路
- 04 是否已形成稳定 protocol
- 02/05 是否已完成 validity filtering 与 report schema 清理

---

## 关键检查点

### Checkpoint 1：前置条件冻结
- 已明确哪些能力不完成就不能启动 batch
- 不再在批量实验中边跑边修主协议

### Checkpoint 2：validation batch 可执行
- 已给出最小规模、检查重点、输出形式
- 能作为 internal validation report 而不是论文主表

### Checkpoint 3：ablation 边界清楚
- 四组 baseline 的价值与差异已写清
- 能回答 reviewer 关于“到底是哪一部分起作用”的质疑

### Checkpoint 4：future work 解耦
- cross-task memory 与 failure taxonomy 已保留但不挤进当前主里程碑
- 下一窗口知道哪些方向现在不要开工

---

## 任务背景

批量化测试、baseline ablation、cross-task memory test、failure taxonomy 等都是重要方向，但当前不应在主链路还没跑通时直接展开。

当前优先级应当是：

1. 单条任务协议跑通
2. evaluator 与 simulator 对齐
3. state schema 真正生效
4. 正式报告协议清理完成

在此基础上，才进入大规模实验。

---

## 一、batch 启动前置条件（Go / No-Go）

批量实验启动前，必须全部满足；任一项未满足时，只允许继续修主链路或跑极小人工检查，不推进大规模 batch。

### P0. state schema 已跑通
- 正式 task 带 `state_schema`
- 运行中不再出现 `no_schema_registered`
- tracked variables 非空
- `require_state_schema=True` 的 task 不会静默降级进正式结果

### P1. protocol alignment 已完成
- evaluator 知道当前轮是 fresh visual、memory-only 还是 mixed
- image exposure store / refs 已工作
- 合法 recalled state 不再被系统性误罚
- single-task 与 interleaved 使用同一套 turn-level contract

### P2. scoring / reporting 已清理
- 无默认满分
- aggregate 可生成且非空
- applicable-only aggregation 生效
- invalid 样本不会混入主 aggregate

### P3. 图片发送有效性机制已就位
- 至少有 task-level validity filtering
- `confirmed` / `suspected_failed` / `not_applicable` 语义已固定
- invalid reason 可进入 batch summary

### P4. 日志与审计出口已就位
- turn context 中能看到 `turn_input_mode`、image refs、validity metadata
- task / batch 输出中能看到 support、invalid summary、必要的 schema summary
- 可以抽样人工复核，不需要靠猜测解释结果

### Go / No-Go 结论
- **Go（仅允许 validation batch）**：P0-P4 全满足。
- **No-Go**：任一项未满足；尤其不能在 validation/pilot 里边跑边修 schema/protocol/reporting 主链路。

---

## 二、批量化实验的最小方案

建议先做一个 **small-scale validation batch**，不是正式主实验，也不是论文主表来源。

## 阶段 1：Validation Batch

### 定位
- 这是 **internal validation report**。
- 目标是验证协议、日志、聚合、validity filtering 是否可信。
- 不追求模型覆盖面，也不用于宣称最终 benchmark 结论。

### 最小方案
- task types：VNF / AC / RC 各 10 条 valid task 为目标
- models：2 个
- 预计原始投放量：每类 task 每模型可多准备 2-4 条缓冲样本，用于吸收 delivery invalid 或 schema invalid
- 结果口径：只对 `evaluation_validity=valid` / `task_validity.status=valid` 的样本做正式聚合

### 检查重点
- schema 注册成功率是否达到可接受水平
- invalid sample 比例与原因是否清楚
- aggregate 输出是否完整且 support 正确
- phase breakdown / task-type breakdown 是否合理
- evaluator reasoning 是否与 `turn_input_mode` / exposure history 一致
- audit sample 是否能人工解释

### 最小交付物
- 一份 internal validation report
- 一份 batch validity summary（valid / invalid / invalid reasons）
- 一份 aggregate snapshot（per-dimension mean + support）
- 一组 audit samples（建议每个 task type 至少抽 2-3 条）

### 通过标准
- valid 样本中不应再出现 `no_schema_registered`
- aggregate / support / invalid summary 三者能对齐
- memory-only turn 不再被系统性当作“当前无图即 hallucination”
- invalid 样本能解释为 protocol / delivery / schema 问题，而不是混入正式得分

### 输出定位
- 不是论文主表
- 不做大规模模型比较
- 只用于判定是否进入 pilot batch

---

## 阶段 2：Pilot Batch

### 目标
验证 dynamic setting 是否真的显著拉开与 static baseline 的差距。

### 建议规模
- task types: 全部主任务类型
- models: 3-4 个
- 每种 task type 至少 50-100 条

### 输出
- 可以形成初步图表
- 用于写 methodology / experiment setup

---

## 阶段 3：Main Batch

### 目标
正式论文结果。

### 建议规模
之后再定，不在本轮细化。

---

## 三、baseline ablation 的初步方案

当前至少建议准备四种设置：

## A. Static single-turn baseline
- 一次性给图
- 一次性给最终问题
- 无动态 probing

### 价值
作为最传统 multimodal benchmark baseline。

## B. Multi-turn without decoupling
- 多轮，但最终问题提前可见
- 无严格 information decoupling

### 价值
区分“多轮”与“真正 decoupled dynamic evaluation”。

## C. Decoupled without perturbation
- 先观察，再问
- 但不加入 misleading / stress / conflict

### 价值
区分 Information Decoupling 的贡献与 adversarial probing 的贡献。

## D. Full MMemBench
- decoupling + perturbation + evidence-aware evaluation

### 价值
作为完整方法。

---

## Reviewer 视角下，这些 ablation 为什么重要

如果没有 ablation，reviewer 可能会问：

1. 性能下降是不是只是因为 prompt 变长了？
2. 是因为多轮，还是因为 decoupling？
3. 是因为 misleading，还是因为 evaluator 更严格？

这四组设置基本可以把这些问题拆开。

---

## 四、未来方向：cross-task memory test

你已经明确说暂时不要开这个坑。这里仅保留方向说明。

## 为什么值得保留
从论文价值上看，cross-task interference 很有吸引力，因为它直接对应：
- context contamination
- task switching under shared session history
- memory collision across multimodal tasks

## 为什么现在不做
因为当前还有更基础的问题没解决：
- state schema
- protocol alignment
- image validity

## 当前建议
- 在代码结构上保留接口
- 在文档中保留未来方向
- 不进入当前主里程碑

---

## 五、未来方向：failure mode taxonomy

你已经指出一个现实问题：
- 类别太多可能分析样本不够
- 自动归类也不简单

这个判断是合理的。

### 简化建议
不要一开始做很细 taxonomy。先做一个 4 类粗粒度版本：

1. `observation_failure`
2. `memory_decay_or_loss`
3. `misleading_or_instruction_drift`
4. `cross_image_or_index_confusion`

### 是否立即做？
建议：
- 先不作为当前主任务
- 只保留一个简单方案，等 pilot batch 后看样本量再决定

### 论文价值
如果后面样本够，这会非常适合 qualitative analysis 和 error breakdown 图。

---

## 六、批量实验代码的建议方向

## 目标
批量实验代码应建立在“单条任务跑通”的基础上，而不是边跑边调协议。

## 建议能力

### 1. preflight validation
批量开始前先检查：
- schema presence
- image validity policy enabled
- report schema version
- evaluator/simulator protocol version

### 2. validity-aware aggregation
批量结束后自动输出：
- valid tasks
- invalid tasks
- invalid reasons

### 3. ablation-ready config
通过配置切换：
- static
- multi-turn non-decoupled
- decoupled
- full

### 4. audit sampling
每个 batch 自动抽若干 task 供人工复核。

---

## 七、本阶段建议的文档结论

当前不进入：
- cross-task memory 主实验
- 复杂 failure taxonomy
- 大规模 main batch

当前应先完成：
- schema
- protocol
- scoring/reporting
- image validity

等这些都稳定后，再开启 pilot batch 与 baseline ablation。

---

## 阶段性验收标准

1. 已形成 validation batch 方案。
2. 已形成四组 baseline ablation 的最小设计。
3. 已把 cross-task memory 与 failure taxonomy 作为 future work 保留下来。
4. 明确大规模批量测试必须以单条任务协议跑通为前提。
