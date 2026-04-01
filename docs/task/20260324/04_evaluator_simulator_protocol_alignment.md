# 04. Evaluator 与 Simulator 协议对齐

> 本文档是一个**可维护的单问题文档**，默认交给单独窗口推进。
>
> 本文档负责：
> - 对齐 simulator 与 evaluator 的 turn-level evaluation contract
> - 定义 `turn_input_mode`、image exposure store、evidence mode 的职责边界
> - 说明 single-task 与 interleaved 如何统一协议
>
> 本文档不负责：
> - state schema 上游生成细节
> - image delivery validity 的具体过滤实现
> - 正式 report schema 的最终表格形式
>
> 上游依赖：01 提供 state-level runtime contract，03 提供 image ref 字段语义。
>
> 主要输出：供 05/06 消费的 formal evaluation protocol。

## 与其他窗口的耦合

### 本文档向外提供
- simulator -> evaluator 的 turn-level contract
- image exposure store 与 `turn_input_mode` 的职责边界
- single-task / interleaved 统一协议的方向

### 本文档依赖外部确认
- 01 提供 schema 注册后的 state context 能力边界
- 03 提供 image refs 与 logging semantics
- 02 提供哪些 turn/task 会因 delivery failure 被标 invalid
- 05 提供正式报告需要保留哪些 evaluator 输出字段

---

## 关键检查点

### Checkpoint 1：断裂点描述清楚
- 已明确 simulator 与 evaluator 当前各自假设什么
- 已明确误判发生在何处

### Checkpoint 2：turn-level contract 成型
- `turn_input_mode` / `visible_image_refs` / `memory_image_refs` 已定义清楚
- evaluator 不再依赖 prompt 表面形式猜协议

### Checkpoint 3：统一协议方向固定
- 已明确 single-task 是 interleaved 的特例
- 不再维护两套彼此漂移的图片协议

### Checkpoint 4：输出接口可供下游消费
- 05 能基于本文档定义 report schema
- 06 能基于本文档设计 validation batch 检查项

---

## 任务背景

这是当前除 `state_schema` 之外最关键的问题。

你已经明确指出，这不是简单的“措辞问题”，而是：

1. evaluator 可能并没有真的评价 earlier observation / memory content
2. simulator 与 evaluator 对“这一轮有没有图、能否使用历史观察”理解不一致
3. 当前协议并不完全支撑论文中的动态 context management 叙事

这是对的。当前问题是 **协议层断裂**。

---

## 当前问题的核心

### evaluator 现在在做什么
从 [src/simulator/evaluator.py:181-185](../../../src/simulator/evaluator.py#L181-L185) 可以看到，当前 LLM judge prompt 强调：

- 必须核验“实际提供的图片”
- 没有图片还做视觉断言要被重罚

这个规则对普通 VQA 是合理的。

但你的 benchmark 不是普通 VQA。你的目标是：

- 先观察
- 再在后续 turn 中只基于已形成 state 回答

也就是说，**后续无图 turn 的某些视觉判断应该是合法的 recalled state usage，而不是天然 hallucination**。

### simulator 现在在做什么
当前 simulator 的 turn 里常常是：
- 首轮或少数轮发图
- 后续很多轮 `images_sent = []`
- 但问题仍在问 earlier observation 的内容

这本来正是 Information Decoupling 的设计目标。

### 断裂点
断裂在于：

- simulator 认为“当前轮无图，但可以基于 earlier observation 回答”
- evaluator 却经常按“当前轮无图，所以视觉判断不可信”来评分

这样就会把 benchmark 自己设计的核心能力测试，误判成 low faithfulness。

---

## 先回答一个关键问题

## 当前 evaluator 有没有真正评价 earlier observation / memory content？

### 初步结论：没有完整做到。

它当前做到了三件事：

1. 会把 previous responses 放进上下文
2. 会把 key facts / expected answer 放进 judge prompt
3. 会评 consistency / memory retention

但它没有真正做到：

### 1. 区分 recalled state 与新视觉主张
它没有明确知道：
- 当前 response 是在复述 earlier observation
- 还是在新增一个此前从未建立过的视觉 claim

### 2. 把 earlier observation 作为结构化评测对象
它没有 expected state at turn t，也没有 actual state at turn t。

### 3. 基于 image exposure history 决定 faithfulness 规则
它只知道当前 prompt 有没有图，而不知道：
- 这些图是否在 earlier turn 已经发过
- 当前轮是否属于 memory-only probing

所以现在它更接近：
- 用上下文辅助的回答质量评估
而不是：
- 对 earlier observation / memory content 的正式评测

---

## 我们需要的统一协议

推荐建立一个统一的 **Turn Evaluation Protocol**。

每一轮在进入 evaluator 前，simulator 必须显式给出：

```json
{
  "turn_input_mode": "fresh_visual | memory_only | mixed",
  "visible_image_refs": ["Image 0"],
  "memory_image_refs": ["Image 0", "Image 1"],
  "current_question_scope": {
    "expected_source": "fresh_visual | memory | either",
    "target_variables": ["img0_has_chair", "img1_has_chair"]
  }
}
```

有了这个，evaluator 才能按协议评，而不是猜。

---

## 推荐方向：统一使用“图像记忆缓存 + 当前可见图像”模型

你提出的方向非常合理：

- simulator 保存发送过的图片
- 后续 evaluator 在评估时可以拿到“当前轮可见图片 + 历史已观测图片”的关系
- interleaved 模式与单 task 模式尽量统一，不走两套图片库

### 推荐方案

采用统一的 image reference store：

## 核心思想

每个 task 维护一个 **Image Exposure Store**，不是两套图库，而是一个统一存储，带两种视图：

1. `visible_now`
2. `observed_before`

### 数据结构草案

```json
{
  "image_store": {
    "Image 0": {
      "path": "...",
      "first_exposed_turn": 1,
      "last_visible_turn": 1
    },
    "Image 1": {
      "path": "...",
      "first_exposed_turn": 1,
      "last_visible_turn": 1
    }
  },
  "turn_context": {
    "visible_now": ["Image 0"],
    "observed_before": ["Image 0", "Image 1"]
  }
}
```

### 好处

- interleaved 和 single-task 共用一套机制
- evaluator 可以根据 `turn_input_mode` 判断当前是否允许 memory-based answering
- 不需要维护“两套独立图片库”

---

## evaluator 应该如何用这些信息

## 新原则

### 原则 1：faithfulness 不再只看“当前轮有没有图”
而要看：
- claim 是否来自 `visible_now`
- 或是否合理来自 `observed_before`
- 或是否是完全新编的视觉细节

### 原则 2：memory-only turn 的合法回答不应天然被判为 hallucination
如果问题是：
- “前面那组图里哪张有 chair？”
且 `Image 0/1` 已在 earlier turn 曝光
那么回答 `Image 0` 应被视为合法 state recall。

### 原则 3：新增视觉细节要严格区分
如果当前轮没图，但模型突然说：
- “桌子上还有一个微波炉和购物袋”
而 earlier observation 中从未建立这些内容
这应判为 ungrounded reconstruction / hallucination。

---

## 论文价值：为什么这件事必须修

如果不修，reviewer 会提出一个非常致命的问题：

> 你们不是在测试 context management，而是在惩罚“当前轮不附图时的视觉回答”。

这会直接动摇：
- Information Decoupling 的合理性
- State Evolution Testing 的有效性
- Evidence Dependency Tracking 的可信度

如果修好，反而会形成一个清晰的技术点：

> 我们显式区分 fresh perception 与 recalled state，并让 evaluator 按 exposure history 而非当前 prompt 表面形式进行判分。

这个点是有论文价值的。

---

## 与 simulator 不同步的具体修复方向

## 方向 A：simulator 向 evaluator 传“当前轮图片 + 历史可引用图片”
这是推荐方向。

### simulator 负责提供
- visible image refs
- observed image refs
- target variables
- turn input mode

### evaluator 负责解释
- fresh claim / recalled claim / unsupported claim

这是最清晰的职责边界。

---

## 方向 B：evaluator 自己从历史 turn 反推图片可用性
不推荐。

原因：
- evaluator 不应去猜 simulator 的协议
- interleaved 模式下反推尤其脆弱
- 很容易和日志字段不一致

---

## 单 task 和 interleaved 是否统一？

建议统一。

### 统一原则
- single-task 只是 interleaved 的特例
- 都用同一个 image exposure store
- 区别只在于 scheduler，不在于评测协议

### 为什么要统一
1. 实现更简单
2. evaluator 不需要区分两套逻辑
3. 正式论文主要跑 interleaved，但 supplementary 可以自然支持 single-task

---

## 需要新增/修改的接口

## simulator -> evaluator context
建议至少追加：

```json
{
  "turn_input_mode": "memory_only",
  "visible_image_refs": [],
  "memory_image_refs": ["Image 0", "Image 1"],
  "fresh_visual_required": false,
  "target_variables": ["img0_has_chair"],
  "image_policy": "send_once_then_probe"
}
```

## evaluator output
建议追加：

```json
{
  "evidence_mode": "recalled_state",
  "faithfulness_basis": "supported_by_prior_exposure",
  "unsupported_claims": ["..."]
}
```

---

## Reviewer 可能的意见

### Q1. 你们怎么知道模型是在用 earlier observation，而不是瞎猜？
回答方向：
- 我们要求 simulator 显式提供 exposure history
- evaluator 区分 recalled state 与 unsupported new detail
- 后续再结合 state schema 做结构化约束

### Q2. 你们是不是把历史看到的图重新发给 evaluator，这样会泄漏信息？
这个问题要谨慎。

建议说明：
- evaluator 拿到图片是为了核验 response 是否能由 earlier observed evidence 支撑
- 它不是给 target model 用的，不影响被测模型输入协议

### Q3. single-task 和 interleaved 的协议是否一致？
建议回答：
- 是，single-task 是 interleaved 的特例，评测协议统一

---

## 任务拆分

### 子任务 A：梳理 evaluator 当前到底依赖哪些字段
### 子任务 B：定义 turn-level evaluation context
### 子任务 C：实现 image exposure store
### 子任务 D：让 evaluator 改按 protocol 而不是 prompt 表面形式判分
### 子任务 E：补充单 task / interleaved 一致性测试

---

## 阶段性验收标准

1. evaluator 能区分 fresh visual turn 与 memory-only turn。
2. 在 memory-only turn 中，合法 recall 不会被系统性判成 hallucination。
3. simulator 和 evaluator 使用统一的 image exposure contract。
4. single-task 与 interleaved 使用同一套协议。

---

## 暂不展开的内容

- evaluator 如何使用历史图片做多模态核验的具体 prompt 设计
- state variable extraction 的详细算法
- 图像缓存的存储优化

这些后续再细化。
