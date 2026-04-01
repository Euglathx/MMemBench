# 02. 图片发送稳定性与实验有效性

> 本文档是一个**可维护的单问题文档**，默认交给单独窗口推进。
>
> 本文档负责：
> - 传图不稳定时，正式实验如何定义 validity
> - 哪些样本过滤、哪些样本保留日志但不入主表
> - 如何避免把系统层失败误当作模型 failure
>
> 本文档不负责：
> - state schema 的具体实现
> - evaluator/simulator 正式协议的完整重写
> - batch 主实验规模设计
>
> 当前固定决策：**按 B + D 组合方案推进**。

---

## 与其他窗口的接口前提（现已确认）

Window D 现在不再在真空里定义 validity。

上游窗口已经给出可消费的 turn-level protocol：

- Window C 已固定图片字段语义：
  - `new_images_sent_count`
  - `visible_image_refs`
  - `memory_image_refs`
  - `turn_input_mode`
- Window B 已固定 evaluator 按 explicit contract 而不是按 prompt 表面形式判断协议。

当前直接相关代码位置：

- [strategic_simulator.py:743-805](../../../src/simulator/strategic_simulator.py#L743-L805)
  - 生成 `turn_input_mode / visible_image_refs / memory_image_refs / new_images_sent_count`
- [evaluator.py:990-1066](../../../src/simulator/evaluator.py#L990-L1066)
  - evaluator 已把上述字段当 authoritative contract
- [stateful_simulator.py:182-204](../../../src/simulator/stateful_simulator.py#L182-L204)
  - tracking log 已记录新字段，旧字段已降级为 `images_sent_count_legacy`

因此 Window D 现在只需要补齐：**delivery validity metadata** 与 **formal filtering policy**。

---

## 任务背景

当前有一个关键现实问题：图片发送到 API 端点并不总是稳定成功。这个问题会直接污染动态评测，因为模型在不同 turn 看到的视觉输入可能并不符合协议设计。

用户已经指出一个重要事实：

- “inconsistent access belief” 未必是模型的内在行为问题
- 更可能是 API 端点不稳定，导致有时图片发上去、有时没发上去

这意味着我们不能轻易把“前面像看到了图，后面又说看不到图”全都解释为模型 failure。这里存在 **系统层噪声**。

---

## 核心判断

这个问题本质上不是模型问题，而是 **evaluation validity problem**。

因此方案设计原则固定为：

1. **不要把传图失败伪装成 model failure。**
2. **不要让 evaluator 在不知道图片是否真实送达的情况下继续按正式协议打分。**
3. **保留尽可能多的原始日志，但正式主表只保留 validity 可解释的样本。**
4. **heuristic 只能产出 `suspected_failed`，不能直接产出 confirmed failure。**
5. **invalid 样本必须保留日志，但不进入主表。**

---

## 与其他窗口的耦合

### 本文档向外提供
- turn/task/batch validity 的标记原则
- `image_delivery` / `evaluation_validity` / `task_validity` 的正式语义
- 正式统计时哪些样本过滤、哪些样本仅保留日志的规则

### 本文档依赖外部确认
- 03 提供 request payload 语义：`visible_image_refs` / `memory_image_refs` / `new_images_sent_count`
- 04 提供 evaluator/simulator 正式协议边界，避免 invalid turn 继续被正式评分
- 05 提供 aggregate/report 层如何消费 validity 标签与 invalid summary

---

## 关键检查点

### Checkpoint 1：validity 边界固定
- 已明确这是 system-level validity 问题，不是直接当作 model failure
- 已固定按 B + D 组合方案推进

### Checkpoint 2：证据层级清楚
- 已区分 system receipt、request payload、behavior heuristic 三层证据
- heuristic 只能标 `suspected_failed`，不能直接当 confirmed

### Checkpoint 3：过滤口径可执行
- 已明确 task 级 invalid / excluded 过滤规则
- 已明确 invalid 样本保留日志但不入主表

### Checkpoint 4：下游接口可消费
- 04/05 可以直接读取 validity metadata，而不是重复自行猜测
- 06 可以基于 invalid summary 设计 validation batch 检查项

---

## 推荐方向

推荐采用 **B + D 的组合**：

- 先做 turn/task/batch 级 validity 标记
- 正式实验按 **task 粒度** 过滤
- 不做“只丢这一轮、保留后面”的复杂恢复
- 所有被过滤样本都保留原始日志和过滤原因

这意味着：

- **不按 batch 全丢**
- **不做 turn 级局部修补后再继续入主表**
- **正式 aggregate 只统计 `task_validity.status = valid` 的任务**

---

## 先固定两个边界

### 边界 1：Window D 不重写 turn protocol
Window D 直接消费 Window B/C 已固定字段：

- `turn_input_mode`
- `visible_image_refs`
- `memory_image_refs`
- `new_images_sent_count`
- `current_question_scope.expected_source`

### 边界 2：Window D 只补“delivery 是否可信”
Window D 不再让 evaluator 自己猜：

- 这轮本来应不应该有图
- 当前无图是 protocol 设计还是 delivery failure
- 当前 refusal 是模型能力问题还是图片没送到

这些都必须转化成显式 metadata。

---

## 正式 validity taxonomy

为避免把“证据状态”和“是否进主表”混在一起，Window D 把标签拆成三层：

1. `image_delivery.status`：描述 delivery 证据结论
2. `evaluation_validity`：描述该 turn 是否可进入正式评分
3. `task_validity.status`：描述该 task 是否可进入正式 aggregate

### 一、Turn 级：`image_delivery.status`

固定枚举：

- `confirmed`
- `confirmed_failed`
- `suspected_failed`
- `not_applicable`
- `unverified`

固定含义：

#### 1. `confirmed`
表示按**当前可获得的最强客观证据**，没有发现本轮图片发送失败。

它可以来自：
- system receipt 明确确认成功
- 或 request payload 证据完整且与 intended send 一致

注意：
- 这里的 `confirmed` 是 **对当前 delivery chain 的 best-available objective confirmation**
- 它不是“模型一定真的理解了图片”，也不是“回答一定正确”

#### 2. `confirmed_failed`
表示有**客观证据**确认本轮 delivery 相对协议发生失败。

典型情况：
- system receipt 明确返回 attachment failure / missing image
- intended send 非空，但 request payload 实际没带上应带图片
- intended image refs 与实际 payload refs 明确不一致

#### 3. `suspected_failed`
表示只有**behavior heuristic** 指向失败，但没有一级/二级客观证据确认。

这是一个审计标签，不是 confirmed failure。

#### 4. `not_applicable`
表示这轮本来就不是 fresh image delivery turn。

典型情况：
- `turn_input_mode = memory_only`
- `turn_input_mode = text_only`
- 且本轮 `intended_image_refs = []`

#### 5. `unverified`
表示这轮理论上涉及图片发送，但当前日志链路缺少足够 metadata，既不能确认成功，也不能确认失败。

典型情况：
- 旧日志没有 intended / payload / receipt 记录
- 旁路入口未接入 delivery metadata

---

## 二、Turn 级：`evaluation_validity`

固定枚举：

- `valid`
- `invalid_due_to_delivery`
- `excluded_unverified_delivery`
- `legacy_unverified`

固定含义：

#### 1. `valid`
这轮可以进入正式评分。

适用情况：
- `image_delivery.status = confirmed`
- 或 `image_delivery.status = not_applicable`

#### 2. `invalid_due_to_delivery`
这轮因已确认的 delivery failure 不可进入正式评分。

适用情况：
- `image_delivery.status = confirmed_failed`

#### 3. `excluded_unverified_delivery`
这轮不进入正式评分，但原因不是 confirmed failure，而是 delivery 证据不足或只到 heuristic 层。

适用情况：
- `image_delivery.status = suspected_failed`
- `image_delivery.status = unverified`

#### 4. `legacy_unverified`
旧结果专用。表示该 turn 来自尚未接入 Window D validity metadata 的历史日志，不能作为正式结果使用。

---

## 三、Task 级：`task_validity.status`

固定枚举：

- `valid`
- `invalid_due_to_delivery`
- `excluded_unverified_delivery`
- `legacy_unverified`

### task 级 roll-up 规则（B + D 固定）

#### 规则 1：任意正式 turn 若出现 `invalid_due_to_delivery`，整个 task 失效
即：
- 只要 task 内任一需要正式评测的 turn 被确认 delivery failure
- 该 task 整体标为 `invalid_due_to_delivery`
- **不做局部恢复，不让后续 turn 回到主表**

这是方案 B 的核心：**按 task 丢弃，不按 batch 丢弃。**

#### 规则 2：若没有 confirmed failure，但出现 `excluded_unverified_delivery`，整个 task 不入主表
即：
- 只有 heuristic 怀疑
- 或 metadata 不足无法验证
- 这类 task 不算 confirmed invalid，但也**不进入正式 aggregate**

因此 task 级标签用：
- `excluded_unverified_delivery`

#### 规则 3：只有所有正式 score-bearing turns 都是 `valid`，task 才能标 `valid`

#### 规则 4：旧日志没有 validity metadata 时，task 标 `legacy_unverified`

---

## Batch 级：`batch_validity_summary`

batch 不做单一总标签，而做 summary。

建议至少输出：

```json
{
  "batch_validity_summary": {
    "task_count_total": 100,
    "task_count_valid": 91,
    "task_count_invalid_due_to_delivery": 4,
    "task_count_excluded_unverified_delivery": 3,
    "task_count_legacy_unverified": 2,
    "turn_count_invalid_due_to_delivery": 7,
    "turn_count_excluded_unverified_delivery": 11,
    "evidence_breakdown": {
      "system_receipt": 1,
      "request_payload": 5,
      "behavior_heuristic": 9,
      "legacy_or_missing_metadata": 4
    }
  }
}
```

batch summary 的用途是：
- 审计样本损失
- 说明系统层噪声规模
- 给 05 的 report schema 提供 invalid summary 输入

它**不替代** task 粒度过滤，也**不意味着整批作废**。

---

## 三层证据如何使用

这是 Window D 的核心。

### 一级证据：system receipt
最理想，也最强。

例子：
- endpoint 明确回传 attachment receipt
- response metadata 明确列出收到的图片数/图片 id
- 明确返回 image missing / attachment parse failure

### 二级证据：request payload
当 endpoint 不提供 receipt 时，这是主力证据层。

至少应记录：
- `intended_image_refs`
- `visible_image_refs`
- `payload_image_count`
- 请求 id / response id（如有）

这里要特别固定语义：
- `visible_image_refs` 来自 Window C/04 的正式协议，表示**本轮实际附带到 request payload 的图片 refs**
- `payload_image_count` 应等于 `len(visible_image_refs)`
- `intended_image_refs` 表示 simulator **本轮原本打算发送**的图片 refs

### 三级证据：behavior heuristic
只能辅助，不能直接确认。

典型信号：
- 首轮本应有图，但模型明确说看不到图
- 同类任务里突然从 grounded detail 切到 generic refusal
- 多个连续 turn 出现同一拒看模板

### 固定判定原则

#### 原则 1：高层证据优先，低层证据不能推翻高层证据
即：
- system receipt > request payload > behavior heuristic
- heuristic 只能在高层证据缺失时补位
- heuristic 不能覆盖已经存在的客观成功证据

#### 原则 2：heuristic 只能产出 `suspected_failed`
不能直接产出：
- `confirmed_failed`
- `invalid_due_to_delivery`

#### 原则 3：request payload mismatch 可以直接确认 failure
如果：
- `intended_image_refs != visible_image_refs`
- 或 `payload_image_count != len(visible_image_refs)`
- 或 intended 非空但 payload 实际为空

则可直接标：
- `image_delivery.status = confirmed_failed`
- `evaluation_validity = invalid_due_to_delivery`

#### 原则 4：request payload match 但缺 system receipt 时，可标 `confirmed`
这是当前阶段的**best-available objective policy**。

也就是说：
- 只要 payload 链路完整且自洽
- 即使 endpoint 没有回 receipt
- 也允许作为正式样本保留

否则在当前端点条件下，主实验几乎无法运行。

#### 原则 5：如果只有 heuristic，转为排除而不是确认失败
即：
- `image_delivery.status = suspected_failed`
- `evaluation_validity = excluded_unverified_delivery`

这样可以避免把 delivery failure 伪装成 model failure，也避免把 heuristic 误写成 confirmed system failure。

---

## 哪些样本过滤，哪些样本只保留日志

### 进入正式主表的样本
必须同时满足：

1. `task_validity.status = valid`
2. task 内用于 aggregate 的 turn 都满足 `evaluation_validity = valid`
3. 不属于 `legacy_unverified`

### 不进入正式主表、但保留日志的样本
包括：

#### A. `invalid_due_to_delivery`
- confirmed delivery failure
- 保留 run log / tracking log / task result
- 进入 invalid summary
- 不进入主 aggregate

#### B. `excluded_unverified_delivery`
- 只有 heuristic 怀疑
- 或 metadata 缺口过大无法验证
- 保留日志
- 进入 invalid summary
- 不进入主 aggregate

#### C. `legacy_unverified`
- 历史运行未接入新 metadata
- 可做 debug 对照
- 不进入正式主表

---

## 什么情况下一个 task 会被 delivery failure 污染

在 B + D 方案下，Window D 不做“局部恢复”。

因此一旦下面任一情况成立，task 整体不进入主表：

1. 任一 `fresh_visual` 或 `mixed` turn 出现 `confirmed_failed`
2. 任一需要 fresh visual grounding 的 turn（`fresh_visual_required = true`）出现 `confirmed_failed`
3. 任一 score-bearing visual turn 只有 heuristic / 缺 metadata，无法确认 delivery validity

原因很直接：
- 该轮 response 已不可信
- 后续 memory probing 可能建立在错误 exposure 前提上
- 在 interleaved 设置里继续保留后续正式分数会很难对 reviewer 自证

因此：
- **不做“坏一轮、保后面”的主方案**
- **一旦污染到正式视觉链路，就按 task 粒度剔除**

---

## 哪些 turn 是 `not_applicable`

为了避免把正常的 memory-only / text-only 轮误判为 delivery 问题，固定如下：

### `not_applicable` 的条件
同时满足：

1. 本轮 `intended_image_refs = []`
2. 且本轮协议允许无 fresh 图：
   - `turn_input_mode = memory_only`
   - 或 `turn_input_mode = text_only`
   - 或 `current_question_scope.expected_source != fresh_visual`

此时：
- `image_delivery.status = not_applicable`
- `evaluation_validity = valid`

关键点：
- **无图不等于失败**
- 在 Information Decoupling 任务里，很多无图轮是合法设计，不应被 Window D 错杀

---

## 建议的最小 metadata 合同

Window D 不改 B/C 的 turn protocol，只新增直接相关 validity metadata：

### Turn 级

```json
{
  "turn_input_mode": "mixed",
  "visible_image_refs": ["Image 4"],
  "memory_image_refs": ["Image 0", "Image 1"],
  "current_question_scope": {
    "expected_source": "fresh_visual"
  },
  "image_delivery": {
    "intended_image_refs": ["Image 4"],
    "payload_image_count": 1,
    "system_receipt_status": "not_available",
    "receipt_image_count": null,
    "evidence_source": "request_payload",
    "status": "confirmed",
    "status_reason": "payload_matches_intent"
  },
  "evaluation_validity": "valid"
}
```

### Task 级

```json
{
  "task_validity": {
    "status": "excluded_unverified_delivery",
    "invalid_turns": [3],
    "reason": "heuristic_only_delivery_suspicion",
    "evidence_sources": ["behavior_heuristic"]
  }
}
```

### Batch 级

```json
{
  "batch_validity_summary": {
    "task_count_total": 100,
    "task_count_valid": 91,
    "task_count_invalid_due_to_delivery": 4,
    "task_count_excluded_unverified_delivery": 3,
    "task_count_legacy_unverified": 2
  }
}
```

---

## `image_delivery` 子字段语义

建议最少保留：

### `intended_image_refs`
- simulator 本轮原本计划发送的图片 refs
- 用来和 `visible_image_refs` 做一致性核对

### `payload_image_count`
- 本轮 request payload 中实际附带的图片数
- 应与 `len(visible_image_refs)` 一致

### `system_receipt_status`
建议枚举：
- `confirmed`
- `failed`
- `not_available`
- `not_applicable`

### `receipt_image_count`
- 若 endpoint 提供 receipt，就记录 endpoint 声称收到的图片数
- 否则为 `null`

### `evidence_source`
建议枚举：
- `system_receipt`
- `request_payload`
- `behavior_heuristic`
- `legacy_or_missing_metadata`

### `status_reason`
建议记录一个简短、可聚合的 machine-readable 原因，例如：
- `payload_matches_intent`
- `payload_missing_intended_images`
- `receipt_reported_attachment_failure`
- `heuristic_visual_refusal_on_expected_visual_turn`
- `missing_delivery_metadata`

---

## 与 evaluator 的边界

### evaluator 负责
- 读取 `evaluation_validity`
- 对 `evaluation_validity = valid` 的 turn 做正式评分
- 对 invalid/excluded turns 可以保留 debug output，但**不得写入正式 aggregate**

### evaluator 不负责
- 不自己猜测传图是否成功
- 不从 refusal 文本直接推断 confirmed failure
- 不从 `images_sent_count_legacy` 反推 validity

### 特别说明
如果客观 metadata 已显示：
- `image_delivery.status = confirmed`

但模型仍表现出“像没看到图”的行为，默认解释应是：
- **模型行为异常 / 能力问题 / alignment 问题 / 其他协议问题**
- 而不是重新把它改判成 delivery failure

也就是说：
- **delivery validity 用 metadata 判**
- **model failure 用 evaluator 判**
- 两者不能互相替代

---

## 与 report / aggregation 的边界

05 需要直接消费以下规则：

### 主 aggregate 只吃 `task_validity.status = valid`

### invalid summary 必须单列
至少单列：
- `invalid_due_to_delivery`
- `excluded_unverified_delivery`
- `legacy_unverified`

### invalid 样本保留日志但不入主表
这是 formal reporting 的硬规则，不是 debug 偏好。

---

## 当前代码链路上的直接提醒

虽然 B/C 已把主 turn contract 打通，但仍有少数旁路入口还在用占位 context，例如：

- [strategic_simulator.py:1753-1765](../../../src/simulator/strategic_simulator.py#L1753-L1765)
- [strategic_simulator.py:2270-2282](../../../src/simulator/strategic_simulator.py#L2270-L2282)

这些 consistency-check / chain-final 路径当前会塞入：
- `turn_input_mode = memory_only`
- 但 `memory_image_refs = []`

这类旁路如果暂时没有接上完整 delivery metadata，Window D 的处理原则应是：

- 先视为 **debug / legacy-like path**
- 不要把它们自动当作正式 visual delivery evidence
- 如果这些路径未来进入正式主实验，必须补齐 `image_delivery` metadata

---

## Reviewer 视角

如果 Window D 不修，reviewer 很容易问：

> 你们所谓的 dynamic failure，怎么证明不是 image transport instability？

Window D 修完后，回答路径应是：

1. 我们把 delivery validity 和 model scoring 分开了。
2. 我们按 system receipt / request payload / behavior heuristic 分层取证。
3. heuristic 只会产生 `suspected_failed`，不会直接产生 confirmed failure。
4. invalid 或 unverified 的样本保留日志，但不进入正式主表。
5. 正式结果只在 `task_validity.status = valid` 的任务上聚合。

这条回答链是 reviewer-friendly 的。

---

## 任务拆分

### 子任务 A：补齐 delivery metadata
在 simulator result / tracking log 中补：
- `image_delivery.intended_image_refs`
- `image_delivery.payload_image_count`
- `image_delivery.system_receipt_status`
- `image_delivery.receipt_image_count`
- `image_delivery.evidence_source`
- `image_delivery.status`
- `image_delivery.status_reason`

### 子任务 B：接 evaluator gating
让 evaluator 在正式评分入口读取：
- `evaluation_validity`
- `task_validity.status`

### 子任务 C：接 report filtering
让 05 的 aggregate/report 层只统计：
- `task_validity.status = valid`

### 子任务 D：补 invalid summary
输出：
- invalid / excluded / legacy 的数量、比例、原因、证据来源

---

## 本任务阶段性验收标准

1. 能在日志里明确区分：
   - `confirmed`
   - `confirmed_failed`
   - `suspected_failed`
   - `not_applicable`
   - `unverified`
2. heuristic 只能落到 `suspected_failed`，不能直接落到 confirmed failure。
3. task 级能稳定区分：
   - `valid`
   - `invalid_due_to_delivery`
   - `excluded_unverified_delivery`
   - `legacy_unverified`
4. 正式 aggregate 只统计 `task_validity.status = valid` 的 task。
5. invalid 样本保留日志但不进入主表。

---

## 暂不展开的内容

- endpoint 层自动重试策略
- 多 endpoint fallback
- 传图失败后的自动 rerun 机制
- 细粒度 failure taxonomy
- “可恢复 turn” 的复杂局部恢复方案

这些后续如果要做，再单独细化，不纳入本轮主方案。