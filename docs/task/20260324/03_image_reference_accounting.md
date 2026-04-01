# 03. 图片引用与 `images_sent_count` 字段重定义

> 本文档是一个**可维护的单问题文档**，默认交给单独窗口推进。
>
> 本文档负责：
> - 重定义 `images_sent_count` 相关语义
> - 明确 turn 级图片输入/历史暴露字段
> - 为 04/05 提供可消费的 logging contract
>
> 本文档不负责：
> - image delivery validity 的判定策略
> - evaluator prompt 的完整重写
> - batch 实验设计
>
> 上游依赖：当前 simulator result/tracking log 的图片字段现状。
>
> 主要输出：`visible_image_refs` / `memory_image_refs` / `turn_input_mode` 等字段语义。

## 与其他窗口的耦合

### 本文档向外提供
- `new_images_sent_count` / `visible_image_refs` / `memory_image_refs` 的字段语义
- `turn_input_mode` 的输入定义基础
- legacy `images_sent_count` 的去留建议

### 本文档依赖外部确认
- 04 对 evaluator 输入上下文的最小字段需求
- 05 对正式 report 层是否保留哪些图片字段的要求
- 02 对 delivery metadata 与图片引用字段的拼接方式

---

## 关键检查点

### Checkpoint 1：legacy 字段定位完成
- 已明确 `images_sent_count` 当前到底记录什么
- 已区分 debug 用途与正式协议用途

### Checkpoint 2：新字段语义闭合
- 能清楚区分 request payload、当前可见图片、历史可引用图片
- 不再用一个 count 承担多重含义

### Checkpoint 3：对 evaluator 可消费
- 04 可以直接基于本文档字段定义 protocol
- evaluator 不再需要从 `images_sent_count == 0` 反推协议

### Checkpoint 4：报告层边界清楚
- 已明确哪些字段只保留在 debug 层
- 已明确正式报告不再暴露哪些模糊字段

---

## 任务背景

当前日志中的 `images_sent_count` 存在明显语义混乱。

从代码看：
- [src/simulator/stateful_simulator.py:189](../../../src/simulator/stateful_simulator.py#L189) 当前定义为 `len(result.get("images_sent", []) or [])`

这说明它目前记录的是：
- **当前轮次 result 中 `images_sent` 列表的长度**

而不是：
- 整个任务历史中已经暴露过多少张图
- 当前对话窗口中可被引用的图片总数
- 当前 evaluator 可用的图片总数

这也是为什么日志里会出现很多 `images_sent_count = 0`，但其实这个 task 在更早轮次已经见过图。

---

## 问题本质

`images_sent_count` 这个名字让人容易误解成：
- 当前任务总图数
- 目前为止累计送图数
- 当前窗口仍可用图数

但它实际上只是：
- 当前这一轮新附带的图片数量

如果继续保留这个名字，会带来三个问题：

1. 不利于论文表达 Information Decoupling
2. 不利于 evaluator 判断当前轮应当按什么协议打分
3. 不利于后期排查“这轮没图，但是否可以基于历史 state 作答”

---

## 先回答：这个字段目前主要有什么用？

结合当前代码和日志，这个字段主要用于：

1. **调试**：看当前 turn 有没有附带图片
2. **日志摘要**：在 `tracking_log` 里快速查看 turn 的输入形态

它目前 **并没有形成稳定的协议语义**，至少没有支撑：
- evaluator 的评测条件
- 正式 aggregate 分析
- batch validity filtering

所以，当前它更像是一个粗糙 debug 字段，而不是正式报告字段。

---

## 初步结论

### 结论 1
`images_sent_count` 不应继续作为正式结果字段直接使用。

### 结论 2
如果保留，应当把它重命名并拆成更明确的几个字段。

### 结论 3
如果最后发现没人真正依赖它，可以把旧字段从正式结果中移除，仅在 debug log 中保留。

---

## 推荐方向：拆成四个正式字段 + 一个 legacy/debug 字段

不要试图让一个 count 解决所有语义问题。建议正式协议固定为：

## 1. `new_images_sent_count`
含义：
- **当前轮 request payload 中新附带发送的图片数量**
- 它是 payload 计数，不是 exposure 增量计数
- 如果同一张图在后续 turn 又被重新附带发送，仍然计入本轮 `new_images_sent_count`

用途：
- 调试 API payload
- 配合 delivery metadata 判断当前轮是否真的尝试了 fresh visual grounding

## 2. `visible_image_refs`
含义：
- **当前轮 request 中实际附带的图片引用列表**
- 是本轮 fresh visual evidence 的引用集合
- 顺序应与本轮发送顺序一致
- 例如 `['Image 4', 'Image 5']`

用途：
- evaluator 直接知道当前轮 fresh evidence 来自哪些 image ids
- report 层可解释“这轮模型眼前实际有哪些图”

## 3. `memory_image_refs`
含义：
- **在当前 turn 开始之前，本 task 中已暴露过、因此允许模型通过 earlier observation / memory 合法引用的图片集合**
- 这是 prior exposure 集，不包含本轮刚新发的图
- 去重后记录，按首次暴露顺序或稳定 index 顺序输出

用途：
- 支撑 Information Decoupling
- 支撑“当前没图，但允许基于 earlier observation 回答”
- 避免把“当前可见图片”和“历史可引用图片”混在一起

## 4. `turn_input_mode`
含义：
- **当前轮评测协议模式标签**，由 simulator 显式给出，不由 evaluator 反推

固定枚举：
- `fresh_visual`: `visible_image_refs` 非空，`memory_image_refs` 为空
- `mixed`: `visible_image_refs` 非空，`memory_image_refs` 也非空
- `memory_only`: `visible_image_refs` 为空，`memory_image_refs` 非空
- `text_only`: 两者都为空

用途：
- evaluator 直接按协议评估，不再从 `images_sent_count == 0` 猜测
- Window B 可直接把它作为 turn-level evaluation context 的主开关

## 5. `images_sent_count_legacy`
含义：
- 兼容旧日志语义，等价于旧的 `images_sent_count`
- 即 `len(images_sent)` / `len(visible_image_refs)`

用途：
- 仅供 debug / compatibility
- 不进入正式协议和正式报告字段合同

---

## 关于“重复发送的图片不能算作新的 count”这个问题

这要区分两类概念：

### 如果你问的是 request 级 payload 计数
那重复发送也应计入当前轮发送数。因为本轮确实又发了一次。

### 如果你问的是历史暴露图像集合
那重复发送不应算作新的 exposure。应该去重。

所以最合理的办法不是在一个 count 上纠结，而是把两个概念拆开：

- `new_images_sent_count`：本轮 payload 数量
- `memory_image_refs`：历史唯一图像集合

---

## 建议删除还是保留旧字段？

## 推荐做法

### 正式结果层
删除 `images_sent_count`，改用：
- `new_images_sent_count`
- `visible_image_refs`
- `memory_image_refs`
- `turn_input_mode`

### debug / compatibility 层
短期保留一个明确降级的字段：

- `images_sent_count_legacy`
- deprecated
- 含义固定为当前轮 payload 数量
- 仅供旧日志兼容 / debug 摘要

不要再在任何正式协议里继续使用原名 `images_sent_count`。

---

## 这个字段应该服务谁？

## simulator
需要知道：
- 本轮 intended send 是什么
- 历史暴露过哪些图

## evaluator
需要知道：
- 当前轮是否有 fresh visual evidence
- 当前轮是否只能依据 recalled state
- 当前答案涉及哪些 image refs

## report / analysis
需要知道：
- 各 phase 中发图策略是什么
- 模型失败发生在有图阶段还是无图阶段

---

## 与 image policy 的关系

这份文档只处理字段定义，但它和 image policy 强耦合。

建议 evaluator 不再猜测“为什么没图”，而是直接读取：
- `turn_input_mode = fresh_visual | memory_only | mixed`

这个字段可由 simulator 根据：
- `visible_image_refs`
- `memory_image_refs`
- image policy
- 当前 turn 是否为首次曝光

来生成。

其中语义必须固定：
- `visible_image_refs` = 当前轮 payload 中真的附带发送的图片
- `memory_image_refs` = 当前轮开始前已暴露过、因此本轮允许引用的历史图片
- `new_images_sent_count` = `len(visible_image_refs)`，但它只表达 payload 数，不表达历史集合大小

这样 evaluator 就不用再从 `images_sent_count == 0` 推断任何事情。

---

## Reviewer 视角

如果正式论文里的日志或图表仍然使用语义模糊的 `images_sent_count`，reviewer 很容易问：

- 这是当前轮发图数还是任务总图数？
- 没发图是否意味着模型不能用之前见过的图？
- 你们的 decoupling 是怎么 operationalize 的？

所以这件事虽然看起来是个小字段，实际上非常影响论文表达。

---

## 任务拆分

### 子任务 A：梳理现有依赖
确认哪些模块真的在消费 `images_sent_count`。

### 子任务 B：定义新字段
在 simulator 的 result / tracking log 中统一引入：
- `new_images_sent_count`
- `visible_image_refs`
- `memory_image_refs`
- `turn_input_mode`

### 子任务 C：迁移 evaluator
让 evaluator 改读 `turn_input_mode`，而不是猜测当前轮是否该按 fresh visual grounding 评。

### 子任务 D：清理报告层
正式输出中不再展示 legacy `images_sent_count`。

## 给 Window B 的直接字段合同

Window B 在定义 evaluator / simulator protocol 时，可直接消费以下 turn-level contract：

```json
{
  "new_images_sent_count": 1,
  "visible_image_refs": ["Image 4"],
  "memory_image_refs": ["Image 0", "Image 1"],
  "turn_input_mode": "mixed"
}
```

固定解释：
- `new_images_sent_count`: 本轮 payload 中发送了几张图
- `visible_image_refs`: 本轮 target model 当前可见的图
- `memory_image_refs`: 本轮开始前该 task 已暴露过、因此允许 recalled-state 引用的图
- `turn_input_mode`: evaluator 的主协议开关，不再由 evaluator 自己猜

Window B 使用要求：
- 不要把 `new_images_sent_count` 当成历史累计暴露数
- 不要把 `visible_image_refs` 当成 memory store
- 不要把 `memory_image_refs` 理解为“包含本轮新图”的全集
- 如果后续需要“截至当前轮（含本轮）的累计暴露集合”，应显式单列，例如 `all_exposed_image_refs`，不要复用 `memory_image_refs`

---

## 给 Window B 的迁移点清单（evaluator 侧）

Window B 接下来需要重点清理的是：**不要再让 evaluator 的正式协议语义依赖 `images_sent` 这种 payload-path 字段**。

### A. 已经可直接复用的入口
- [evaluator.py:675-695](../../../src/simulator/evaluator.py#L675-L695)
  - LLM judge prompt 已能读取 `turn_input_mode / visible_image_refs / memory_image_refs`
- [evaluator.py:992-1013](../../../src/simulator/evaluator.py#L992-L1013)
  - `_get_turn_evidence_contract()` 已经把新字段当 authoritative contract
- [evaluator.py:1019-1066](../../../src/simulator/evaluator.py#L1019-L1066)
  - `_classify_evidence_usage()` 已经按 `turn_input_mode` 区分 `fresh_visual / mixed / memory_only / text_only`

### B. 仍然带有 legacy 影子的入口
- [evaluator.py:1478-1517](../../../src/simulator/evaluator.py#L1478-L1517)
  - `evaluate_response()` 仍先从 `context["images_sent"]` 取值，再把它传给：
    - `_compute_faithfulness_score(...)`
    - `_compute_cross_image_confusion_score(...)`
- [evaluator.py:1068-1130](../../../src/simulator/evaluator.py#L1068-L1130)
  - `_compute_faithfulness_score()` 还保留 `images_sent` 形参，但当前核心判断其实已经转到 `_classify_evidence_usage(context)`
  - 这说明 `images_sent` 在这里已基本可降为兼容参数，后续可删除
- [evaluator.py:1333-1399](../../../src/simulator/evaluator.py#L1333-L1399)
  - `_compute_cross_image_confusion_score()` 仍用 `len(images_sent)` 判断是否是多图 turn
  - 这里后续应改成基于协议字段判断，而不是基于 payload 路径列表长度

### C. Window B 推荐迁移顺序
1. 在 `evaluate_response()` 内部，把动态评分入口统一改成先读 `_get_turn_evidence_contract(context)`。
2. 让 `_compute_faithfulness_score()` 去掉对 `images_sent` 的语义依赖，仅保留 contract 驱动。
3. 让 `_compute_cross_image_confusion_score()` 改读：
   - `visible_image_refs`
   - `memory_image_refs`
   - 必要时 `all_exposed_image_refs`
   而不是 `len(images_sent)`。
4. 明确规定：
   - `images_sent` 仅保留为原始 payload/debug 数据
   - 正式协议判断一律走 `turn_input_mode + refs`
5. 对 consistency-check / chain-step / stress-test 这些旁路入口，补齐一致的 contract，避免出现 `turn_input_mode="memory_only"` 但 `memory_image_refs=[]` 这种占位状态长期存在。

### D. Window B 实现时的判断原则
- 是否“多图可混淆”不应只看本轮 payload 发了几张图。
- 是否“允许 memory-based answering”不应由 evaluator 猜测。
- 是否“当前轮必须 fresh visual”应由 `current_question_scope.expected_source` / `fresh_visual_required` 决定。

---

## 实现状态（Window C 本轮）

已在直接相关代码中补齐最小字段链路：
- [image_policy.py](../../../src/simulator/image_policy.py)
- [strategic_simulator.py](../../../src/simulator/strategic_simulator.py)
- [stateful_simulator.py](../../../src/simulator/stateful_simulator.py)

当前实现约定：
- `memory_image_refs` = prior exposure only（不含本轮新发）
- `visible_image_refs` = current payload only
- `turn_input_mode` 支持 `fresh_visual | mixed | memory_only | text_only`
- state tracking log 已改写为新字段，并将旧字段降级为 `images_sent_count_legacy`

---

## 验收标准

1. 任意 turn 都能清楚回答：当前轮有没有 fresh 图？
2. 任意 turn 都能清楚回答：模型是否可合法依赖 earlier observed images？
3. evaluator 不再依赖 `images_sent_count == 0` 做协议判断。
4. 正式报告不再暴露语义模糊字段。
