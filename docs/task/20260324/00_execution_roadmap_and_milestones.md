# 00. 执行路线图与里程碑总表

> 本文档是 `docs/task/20260324/` 目录的总入口，专门用于**多窗口并行执行**。
>
> 使用原则：
> - 每个窗口只负责一个主文档，不跨文档随意扩 scope。
> - 每个窗口在推进前，先确认自己的上游依赖是否满足。
> - 每个窗口完成后，必须按本文档中的“检查点”和“交付物”回报结果，便于后续窗口继续接手。

---

## 1. 当前总目标

在不直接启动大规模 batch 的前提下，先把 MMemBench 的正式评测主链路修成一个可以支撑论文的方法系统。

本轮总目标分为三层：

### Layer A：主链路可运行
1. `state_schema` 能真正注册并进入 runtime
2. simulator 与 evaluator 协议一致
3. 图片引用/曝光历史可被清晰记录

### Layer B：正式报告可信
4. 默认满分从正式报告中移除
5. aggregate score 与 validity filtering 成立
6. 图片发送不稳定不会被伪装成模型 failure

### Layer C：为 batch 做准备
7. validation batch 的前置条件明确
8. baseline ablation 的最小设计就绪
9. future work 与当前主线解耦

---

## 2. 文档与职责总览

| 编号 | 文档 | 主职责 | 优先级 | 建议窗口 |
|------|------|--------|--------|---------|
| 00 | `00_execution_roadmap_and_milestones.md` | 总协调、里程碑、依赖、交接规范 | P0 | 主控窗口 |
| 01 | `01_state_schema_registration.md` | 打通 state schema 主链路与测试 | P0 | Window A |
| 02 | `02_image_delivery_reliability.md` | 处理传图不稳定与 validity 策略 | P1 | Window D |
| 03 | `03_image_reference_accounting.md` | 重定义图片相关日志与引用语义 | P0 | Window C |
| 04 | `04_evaluator_simulator_protocol_alignment.md` | 对齐 evaluator / simulator 正式协议 | P0 | Window B |
| 05 | `05_scoring_and_reporting_cleanup.md` | 清理默认分数与正式报告结构 | P1 | Window E |
| 06 | `06_batch_experiment_plan_and_future_directions.md` | 批量实验与 future work 规划 | P2 | Window F |

> 说明：
> - P0 = 主链路阻塞项，优先处理
> - P1 = 依赖 P0 结果进入正式报告层
> - P2 = 依赖前述结果，先不落实现，只保留方案

---

## 3. 推荐执行顺序

## Phase 0：协调与冻结范围
由主控窗口完成：
- 以本目录文档为唯一任务来源
- 明确每个窗口只改自己负责的主文档和直接相关代码
- 暂时不把 cross-task memory test 纳入本阶段实现

## Phase 1：三条主链并行
可并行启动三个窗口：

### Window A
负责：`01_state_schema_registration.md`

目标：
- 确认 schema 生成、加载、注册、日志链路是否闭合
- 给出最小可运行 fixture 和测试方案

### Window B
负责：`04_evaluator_simulator_protocol_alignment.md`

目标：
- 明确 current protocol 的断裂点
- 产出 turn-level evaluation context 合同
- 定义 image exposure store 方向

### Window C
负责：`03_image_reference_accounting.md`

目标：
- 清理 `images_sent_count` 的语义
- 设计正式替代字段
- 给 Window B 提供 turn input / image ref 的基础字段定义

> Phase 1 是最关键阶段。A/B/C 任何一条不清楚，后面都不该进入正式实现。

## Phase 2：正式评分与有效性层
建议在 Phase 1 结果稳定后再并行：

### Window D
负责：`02_image_delivery_reliability.md`

固定采用：**B + D** 组合方案。

目标：
- task 级 invalid 过滤
- turn/task/batch validity 标签
- 不把 delivery failure 混进正式模型评分

### Window E
负责：`05_scoring_and_reporting_cleanup.md`

目标：
- applicable-only aggregation
- runtime schema / report schema 分离
- aggregate 与 validity summary 对齐

## Phase 3：实验规划层
### Window F
负责：`06_batch_experiment_plan_and_future_directions.md`

前提：
- 至少拿到 A/B/C/D/E 的阶段性结果

目标：
- 整理 validation batch / pilot batch
- 定义最小 ablation
- 把 future directions 与当前主线切开

---

## 4. 里程碑表

| 里程碑 | 名称 | 进入条件 | 完成标准 |
|--------|------|----------|----------|
| M0 | 文档冻结 | 本目录文档写清楚职责和边界 | 各窗口知道自己做什么/不做什么 |
| M1 | Schema 主链路定位完成 | Window A 启动 | 能明确 schema 断在数据、runtime、还是 evaluator |
| M2 | Protocol 合同成型 | Window B + C 启动 | 有统一的 `turn_input_mode` / image refs / exposure 语义 |
| M3 | 正式评测 validity 层成型 | M1 + M2 完成 | 传图失败样本不会进入正式 aggregate |
| M4 | 正式报告协议成型 | M2 + M3 完成 | 默认满分移除，applicable-only aggregate 生效 |
| M5 | Validation batch ready | M1-M4 完成 | 单条任务、日志、聚合、validity 都可跑通 |
| M6 | Pilot experiment planning ready | M5 完成 | 批量实验方案与 baseline ablation 可执行 |

---

## 5. 跨文档依赖

```text
Window A / 01_state_schema_registration
    -> 提供 state-level runtime contract

Window C / 03_image_reference_accounting
    -> 提供 image ref / turn input 字段语义

Window B / 04_protocol_alignment
    -> 消费 A + C，产出 evaluator/simulator protocol

Window D / 02_image_delivery_reliability
    -> 消费 B + C，产出 validity policy (固定按 B + D 方案)

Window E / 05_scoring_and_reporting_cleanup
    -> 消费 B + D，产出正式报告协议

Window F / 06_batch_experiment_plan_and_future_directions
    -> 消费 A/B/C/D/E，产出 validation / pilot / ablation 规划
```

---

## 6. 每个窗口必须回报的检查点

为保证可维护、可交接，每个窗口在结束当前轮工作时必须回报以下内容：

### Checkpoint 1：边界确认
- 本窗口负责了什么
- 明确没有处理什么
- 是否发现需要主控窗口重新分配的耦合问题

### Checkpoint 2：接口确认
- 新增/修改了哪些输入输出字段
- 哪些字段是对其他窗口的 contract
- 哪些字段仍待定

### Checkpoint 3：风险确认
- 当前方案最大的风险点
- 如果直接实现，最可能踩坑的地方
- 是否存在 reviewer 风险

### Checkpoint 4：交付物确认
- 产出了什么文档/代码/测试
- 下一窗口拿什么继续干

---

## 7. 多窗口维护规则

1. **不要跨窗口修改别人的主文档结构**，除非主控窗口统一协调。
2. **每个文档都要先解决“接口是否明确”再谈实现细节**。
3. **涉及正式报告/论文 claims 的地方，优先考虑 reviewer 可能的质疑路径。**
4. **本轮允许先给方向性方案，不要求一次性写成终版实现计划。**
5. **如果某个窗口发现主前提不成立，应立刻回报，不要在错误前提上继续扩展。**

---

## 8. 当前固定决策

### 已固定
- `02_image_delivery_reliability.md` 按 **B + D** 组合方案推进
- cross-task memory test 暂不进入当前实现主线
- failure taxonomy 暂时只保留简单方案，不进入当前主任务
- 主要实验形态以 interleaved 为主，single-task 尽量作为其特例统一协议

### 暂未固定
- state score 的最终公式
- image exposure store 的最终结构细节
- batch/pilot 的最终规模

---

## 9. 主控窗口建议动作

主控窗口接下来最适合做的事：

1. 盯紧 Window A / B / C 三条主链是否真正闭合
2. 等三条主链结果出来后，再统一协调 D / E
3. 最后再让 F 整理实验路线

换句话说：

**先把“能不能正确评”这件事解决，再去做“评多少、跑多大”。**
