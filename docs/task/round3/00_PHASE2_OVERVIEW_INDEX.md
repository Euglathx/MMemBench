# Phase 2 任务规划总览

**阶段**: Phase 2 - Implementation (实现阶段)
**创建时间**: 2026-02-03
**总预估时间**: 18-24小时 (串行) | 11-14小时 (并行)

---

## 快速导航

| 任务组 | 任务编号 | 文档 | 状态 | 预估时间 |
|-------|---------|------|------|---------|
| **Group D** | Task 2.1 | [已完成](../report/stage2/任务完成报告_2.1.md) | ✅ 完成 | 2-3h |
| **Group E** | Tasks 2.2 & 2.3 | [并行组E文档](./02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md) | ⏳ 待执行 | 5-7h (并行) |
| **Group F** | Tasks 2.4 & 2.5 | [并行组F文档](./02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md) | ⏳ 待执行 | 5-6h (并行) |
| **Group G** | Task 2.6 | [独立组G文档](./02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md) | ⏳ 待执行 | 3-4h |

---

## 执行策略

### 并行执行计划 (推荐)

```
时间轴    Group D    Group E         Group F         Group G
------    --------   -----------     -----------     ---------
Day 1     Task 2.1   Task 2.2 (开始) Task 2.4 (开始)
          ✅ 完成    Task 2.3 (开始) Task 2.5 (开始)

Day 2                Task 2.2 (完成) Task 2.4 (完成)
                     Task 2.3 (完成) Task 2.5 (完成)

Day 3                              Task 2.6 (开始)
Day 4                                              Task 2.6 (完成)

总时间: ~11-14小时 (4天,每天3-4小时)
```

### 串行执行计划 (备选)

```
Task 2.1 → Task 2.2 → Task 2.3 → Task 2.4 → Task 2.5 → Task 2.6
  ✅        ⏳         ⏳         ⏳         ⏳         ⏳
2-3h      3-4h       2-3h       3-4h       2-3h       3-4h

总时间: ~18-24小时 (6-7天,每天3-4小时)
```

---

## 任务详细信息

### ✅ Task 2.1: 图像发送管道修复 (已完成)

**优先级**: P1 (Highest - Blocking)
**依赖**: Phase 1 Task 1.1
**状态**: ✅ **COMPLETED** (2026-02-03)

**修复内容**:
- 4策略图像路径解析系统
- 详细日志记录
- 验证机制防止空 images_sent
- 10个单元测试 (全部通过)

**文档**:
- [任务完成报告 (中文)](../report/stage2/任务完成报告_2.1.md) ⭐ 推荐
- [技术报告 (英文)](../report/stage2/PHASE2_TASK2.1_IMAGE_PIPELINE_FIX_REPORT.md)
- [验证脚本](../report/stage2/validate_image_fix.py)

**测试**:
```bash
cd /e/Code/M3Bench/M3Bench_new
python -m pytest tests/test_image_resolution.py -v
```

---

### ⏳ 并行组 E: Tasks 2.2 & 2.3

**文档**: [02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md](./02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md)

#### Task 2.2: Turn-Level Ground Truth 设计与实现

**优先级**: P1 (High)
**依赖**: Phase 1 Task 1.3
**预估时间**: 3-4小时

**修复问题**:
- 100% turns 使用 task-level expected_answer
- 71个 turns (26.9%) 应该使用 turn-level expected
- 6个确认误判案例

**核心交付**:
- `TurnGroundTruth` 数据类
- `TaskState` 更新 (添加 turn_ground_truths)
- `_generate_turn_ground_truth()` 方法
- Evaluator 支持 turn-level context
- Phase-aware evaluation

**关键文件**:
- `src/simulator/strategic_simulator.py` - 生成 turn-level ground truth
- `src/simulator/evaluator.py` - 使用 turn-level context
- `tests/test_turn_ground_truth.py` - 单元测试

#### Task 2.3: 评分公式重构

**优先级**: P0 (Critical)
**依赖**: Phase 1 Task 1.2
**预估时间**: 2-3小时

**修复问题**:
- LLM Judge 10/10 但 final score = 0.64 < 0.7
- Hard scores 默认值 (0.1-0.3) 污染最终分数
- 权重配置不合理 (llm_weight = 0.6)

**核心交付**:
- Hard scores 默认值调整 (0.1-0.3 → 0.5)
- LLM Judge 权重提高 (0.6 → 0.8)
- 详细评分计算日志
- 单元测试和回归测试

**关键文件**:
- `src/simulator/evaluator.py` - 调整默认值和权重
- `tests/test_score_calculation.py` - 单元测试
- `tests/test_evaluator_regression.py` - 回归测试

**并行执行建议**:
- Day 1: 各自独立开发
- Day 2: Task 2.2 先合并,Task 2.3 后合并
- Day 3: 联合验证

---

### ⏳ 并行组 F: Tasks 2.4 & 2.5

**文档**: [02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md](./02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md)

#### Task 2.4: Simulator 真值校验机制

**优先级**: P1 (High)
**依赖**: Phase 1 Task 1.4
**预估时间**: 3-4小时

**修复问题**:
- 模型错误被无条件存储和传播
- 错误传播率 28.57%
- 无任何真值验证机制
- 一致性检查基于模型声明而非 ground truth

**核心交付**:
- `_validate_model_claims()` 方法
- `is_correct` 标记添加到 model_claims
- `get_conversation_history(filter_incorrect=True)`
- 一致性检查基于 ground truth
- 错误传播防止

**关键文件**:
- `src/simulator/strategic_simulator.py` - Claim 验证
- `src/simulator/memory_store.py` - 历史过滤
- `tests/test_truth_validation.py` - 单元测试

#### Task 2.5: 多图策略统一

**优先级**: P1 (High)
**依赖**: Phase 1 Task 1.5, Task 2.1
**预估时间**: 2-3小时

**修复问题**:
- 54% turns 发送 0 张图像
- 两个 simulators 使用不同图像策略
- AC 任务定义与 expected_answer 不对齐
- Evaluator 不知道 images_sent

**核心交付**:
- `ImageInjectionPolicy` 枚举
- `ImagePolicyManager` 类
- 两个 simulators 使用统一策略
- `images_sent` 传递给 evaluator
- AC 任务定义修复 (可选)

**关键文件**:
- `src/simulator/image_policy.py` - 策略管理 (新文件)
- `src/simulator/strategic_simulator.py` - 使用策略
- `src/simulator/llm_user_simulator.py` - 使用策略
- `src/simulator/evaluator.py` - 接收 images_sent
- `tests/test_image_strategy.py` - 单元测试

**并行执行建议**:
- Day 1-2: 完全独立开发
- Day 3: 合并并联合测试

---

### ⏳ 独立组 G: Task 2.6

**文档**: [02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md](./02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md)

#### Task 2.6: Evaluator 状态管理重构

**优先级**: P2 (Medium)
**依赖**: Phase 1 Task 1.6
**预估时间**: 3-4小时

**修复问题**:
- 5个维度保留默认值 76-79% 时间
- Robustness 和 disambiguation 只有 2 个唯一值
- 某些任务分数完全不变
- 缺少调试机制

**核心交付**:
- 动态 faithfulness, robustness, consistency 评分
- 动态 cross_image_confusion, disambiguation 评分
- `EvaluatorStateSnapshot` 调试工具
- 内部一致性检查
- 详细维度更新日志

**关键文件**:
- `src/simulator/evaluator.py` - 动态评分逻辑
- `tests/test_evaluator_dynamics.py` - 单元测试

**执行建议**: 在 Tasks 2.2-2.5 完成后执行,以充分利用新增的 context 信息。

---

## Phase 1 发现总结

| Phase 1 Task | 发现 | 严重程度 | Phase 2 修复 |
|-------------|------|---------|-------------|
| Task 1.1 | 46.1% turns 空 images_sent | P1 | Task 2.1 ✅ |
| Task 1.2 | LLM Judge 满分但 score < 0.7 | P0 | Task 2.3 ⏳ |
| Task 1.3 | 100% turns 使用 task-level expected | P1 | Task 2.2 ⏳ |
| Task 1.4 | 无真值验证,错误传播 | P1 | Task 2.4 ⏳ |
| Task 1.5 | 54% turns 无图像,策略不一致 | P1 | Task 2.5 ⏳ |
| Task 1.6 | 5个维度像常量 (76-79% 默认值) | P2 | Task 2.6 ⏳ |

---

## 依赖关系图

```
Phase 1 Reports
    ↓
┌───────────────────────────────────────┐
│ Task 2.1 (Group D) - Image Pipeline  │ ✅ DONE
└───────────────────────────────────────┘
         ↓ (provides better image resolution)
         ↓
    ┌────────────────────────────────┐
    │  并行组 E (可同时执行)           │
    │  ├─ Task 2.2: Turn Ground Truth│
    │  └─ Task 2.3: Score Formula    │
    └────────────────────────────────┘
                ↓
    ┌────────────────────────────────┐
    │  并行组 F (可同时执行)           │
    │  ├─ Task 2.4: Truth Validation │
    │  └─ Task 2.5: Image Strategy   │
    └────────────────────────────────┘
                ↓
    ┌────────────────────────────────┐
    │  独立组 G                       │
    │  └─ Task 2.6: Evaluator State  │
    └────────────────────────────────┘
```

**关键依赖**:
- Task 2.5 依赖 Task 2.1 (使用增强的图像解析)
- Task 2.6 建议在 Tasks 2.2-2.5 后执行 (利用新 context)
- Tasks 2.2 & 2.3 可完全并行
- Tasks 2.4 & 2.5 可完全并行

---

## 协作指南

### 如果有多个开发者

#### 方案 A: 2人团队
- **Person 1**: Tasks 2.2 + 2.4
- **Person 2**: Tasks 2.3 + 2.5
- **一起**: Task 2.6

**时间线**: ~7-9天

#### 方案 B: 3人团队
- **Person 1**: Tasks 2.2 + 2.3
- **Person 2**: Tasks 2.4 + 2.5
- **Person 3**: Task 2.6 (+ 协助测试)

**时间线**: ~5-6天

### 如果是单人开发

按照组顺序执行:
1. ✅ Task 2.1 (已完成)
2. Tasks 2.2 + 2.3 (串行或并行,根据精力)
3. Tasks 2.4 + 2.5 (串行或并行)
4. Task 2.6

**时间线**: ~2-3周 (每天3-4小时)

---

## 测试策略

### 单元测试

每个任务都应该有独立的单元测试:
- Task 2.2: `tests/test_turn_ground_truth.py`
- Task 2.3: `tests/test_score_calculation.py`
- Task 2.4: `tests/test_truth_validation.py`
- Task 2.5: `tests/test_image_strategy.py`
- Task 2.6: `tests/test_evaluator_dynamics.py`

### 集成测试

在所有任务完成后:
1. 运行完整的 simulator 测试
2. 使用真实 run logs 验证
3. 对比 Phase 1 问题是否解决

### 验证脚本

参考 Task 2.1 的验证脚本模式,为每个任务创建验证脚本。

---

## 报告生成

### 每个任务的报告结构

1. **技术报告** (英文): `PHASE2_TASK2.X_[NAME]_REPORT.md`
   - 实现摘要
   - 代码变更详情
   - Before/After 对比
   - 测试结果

2. **完成摘要** (中文): `TASK2.X_COMPLETION_SUMMARY.md`
   - 快速摘要
   - 关键成果
   - 验证结果

3. **验证脚本**: `validate_task_2.X.py` (如果适用)

### 报告位置

所有 Phase 2 报告保存在:
```
docs/task/round3/report/stage2/
├── README.md (导航文档)
├── PHASE2_TASK2.1_IMAGE_PIPELINE_FIX_REPORT.md ✅
├── TASK2.1_COMPLETION_SUMMARY.md ✅
├── 任务完成报告_2.1.md ✅
├── validate_image_fix.py ✅
└── (后续任务报告...)
```

---

## 成功标准

### 整体成功标准

- [ ] 所有 6 个任务完成并测试通过
- [ ] Phase 1 发现的所有 P0/P1 问题已修复
- [ ] 回归测试通过 (无破坏现有功能)
- [ ] 文档完整 (每个任务有技术报告)
- [ ] 代码审查完成

### 量化指标

| 指标 | Phase 1 | Phase 2 目标 | 验证方法 |
|------|---------|-------------|----------|
| 空 images_sent 率 | 46.1% | < 5% | Task 2.1 测试 |
| LLM Judge 10/10 → score | 0.64 | > 0.80 | Task 2.3 测试 |
| Turn-level evaluation | 0% | 100% | Task 2.2 测试 |
| 错误传播率 | 28.57% | 0% | Task 2.4 测试 |
| 图像策略一致性 | 不一致 | 100% 一致 | Task 2.5 测试 |
| 维度默认值保留率 | 76-79% | < 20% | Task 2.6 测试 |

---

## 资源链接

### Phase 1 报告
- [Task 1.1: Image Sending](../report/PHASE1_TASK1.1_IMAGE_SENDING_REPORT.md)
- [Task 1.2: Score Calculation](../report/phase1_1.2_score_calculation.json)
- [Task 1.3: Expected Answer](../report/PHASE1_TASK1.3_EXPECTED_ANSWER_REPORT.md)
- [Task 1.4: Truth Validation](../report/PHASE1_TASK1.4_SIMULATOR_TRUTH_VALIDATION_REPORT.md)
- [Task 1.5: Multi-Image Strategy](../report/PHASE1_TASK1.5_MULTI_IMAGE_STRATEGY_REPORT.md)
- [Task 1.6: Evaluator State](../report/PHASE1_TASK1.6_EVALUATOR_STATE_REPORT.md)

### Phase 2 任务规划
- [并行组 E: Tasks 2.2 & 2.3](./02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md)
- [并行组 F: Tasks 2.4 & 2.5](./02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md)
- [独立组 G: Task 2.6](./02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md)

### Phase 2 完成报告
- [Task 2.1 报告](../report/stage2/任务完成报告_2.1.md) ✅

---

## 联系与支持

如有问题或需要澄清:
1. 查看相应任务的详细规划文档
2. 参考 Phase 1 报告了解问题背景
3. 查看已完成的 Task 2.1 作为参考示例

---

**文档版本**: 1.0
**最后更新**: 2026-02-03
**维护者**: Claude Code Assistant
**状态**: Phase 2 规划完成,等待执行
