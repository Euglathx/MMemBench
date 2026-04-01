# Phase 2 任务规划 - 快速指南

**创建时间**: 2026-02-03
**总预估时间**: 11-14小时 (并行) | 18-24小时 (串行)

---

## 📋 任务总览

| 任务 | 文档 | 优先级 | 时间 | 状态 |
|-----|------|--------|------|------|
| **Task 2.1** | [完成报告](../report/stage2/任务完成报告_2.1.md) | P1 | 2-3h | ✅ 完成 |
| **Task 2.2** | [并行组E](./02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md#task-22-turn-level-ground-truth-设计与实现) | P1 | 3-4h | ⏳ 待执行 |
| **Task 2.3** | [并行组E](./02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md#task-23-评分公式重构) | P0 | 2-3h | ⏳ 待执行 |
| **Task 2.4** | [并行组F](./02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md#task-24-simulator-真值校验机制) | P1 | 3-4h | ⏳ 待执行 |
| **Task 2.5** | [并行组F](./02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md#task-25-多图策略统一) | P1 | 2-3h | ⏳ 待执行 |
| **Task 2.6** | [独立组G](./02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md) | P2 | 3-4h | ⏳ 待执行 |

---

## 🎯 核心问题与修复

### ✅ Task 2.1: 图像发送管道修复 (已完成)
- **问题**: 46.1% 的 turns 发送 0 张图像
- **修复**: 4策略路径解析 + 详细日志 + 验证机制
- **结果**: 10/10 测试通过,路径解析成功率 ~100%

### Task 2.2: Turn-Level Ground Truth
- **问题**: 100% turns 用 task-level expected,导致 71 个中间 turns 误判
- **修复**: `TurnGroundTruth` 数据结构 + phase-aware evaluation
- **核心**: 每个 turn 独立的 expected answer

### Task 2.3: 评分公式重构
- **问题**: LLM Judge 10/10 但最终 score = 0.64 < 0.7
- **修复**: Hard scores 默认值 0.5 (中性) + LLM weight 提升到 0.8
- **核心**: 解除 hard scores 对 LLM Judge 的污染

### Task 2.4: Simulator 真值校验
- **问题**: 模型错误被无条件存储和传播 (错误传播率 28.57%)
- **修复**: `_validate_model_claims()` + 历史过滤 + 一致性检查基于 ground truth
- **核心**: 验证 claims vs ground truth,防止错误自我强化

### Task 2.5: 多图策略统一
- **问题**: 两个 simulators 用不同图像策略,54% turns 无图像
- **修复**: `ImagePolicyManager` 统一策略 + images_sent 传递给 evaluator
- **核心**: 策略一致性 + evaluator 知道发送了哪些图像

### Task 2.6: Evaluator 状态管理
- **问题**: 5 个维度保留默认值 76-79% 时间,像常量
- **修复**: 所有维度动态计算 + EvaluatorStateSnapshot 调试工具
- **核心**: 每个 turn 都更新所有维度分数

---

## 🚀 执行策略

### 并行执行 (推荐)

```
Week 1:
  Mon-Tue: Group E (Tasks 2.2 & 2.3) 并行开发
  Wed-Thu: Group F (Tasks 2.4 & 2.5) 并行开发
  Fri:     Group G (Task 2.6) 独立开发

总时间: 1周 (每天2-3小时) 或 11-14小时总工时
```

### 串行执行 (单人)

```
Task 2.1 ✅ → Task 2.2 → Task 2.3 → Task 2.4 → Task 2.5 → Task 2.6
2-3h         3-4h       2-3h       3-4h       2-3h       3-4h

总时间: 18-24小时 (6-7天,每天3-4小时)
```

---

## 📖 详细规划文档

### 主索引
- [Phase 2 总览](./00_PHASE2_OVERVIEW_INDEX.md) ⭐ **完整信息**

### 任务组文档
1. **并行组 E** (Tasks 2.2 & 2.3): [02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md](./02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md)
   - Turn-Level Ground Truth 设计与实现
   - 评分公式重构
   - 可并行执行,5-7小时

2. **并行组 F** (Tasks 2.4 & 2.5): [02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md](./02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md)
   - Simulator 真值校验机制
   - 多图策略统一
   - 可并行执行,5-6小时

3. **独立组 G** (Task 2.6): [02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md](./02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md)
   - Evaluator 状态管理重构
   - 独立执行,3-4小时
   - 建议在 Tasks 2.2-2.5 后执行

---

## 📂 每个任务包含什么

每份任务文档都包含:

### 1. 任务背景
- Phase 1 发现的问题详情
- 统计数据和具体示例
- 根本原因分析
- 代码位置定位

### 2. 任务需求
- 修复目标
- 核心交付物清单
- 当前情况说明
- 期望的改进

### 3. 实现设计
- 详细的技术方案
- 代码示例 (Python)
- 新增/修改的类和方法
- 数据结构设计

### 4. 期望输出
- 需要修改的文件列表
- 单元测试用例
- 验证报告模板
- 集成测试要求

### 5. 接口定义
- 新增的 API 接口
- 更新的接口参数
- 配置选项
- 兼容性说明

### 6. 协作要求
- 与其他任务的并行协作策略
- 依赖的 Phase 1 报告
- 代码冲突避免方案
- 合并策略建议

### 7. 验证标准
- 成功标准检查清单
- 测试用例示例
- 量化指标
- Before/After 对比

---

## 🔑 关键设计原则

所有 Phase 2 任务遵循以下原则:

1. **最小侵入性**: 不破坏现有接口
2. **向后兼容**: 保持已有功能正常工作
3. **可测试性**: 每个修复都有单元测试
4. **可配置性**: 通过参数控制行为
5. **详细日志**: 便于调试和验证

---

## ✅ 验证清单

完成所有任务后,验证以下指标:

| 指标 | Phase 1 | Phase 2 目标 |
|------|---------|-------------|
| 空 images_sent 率 | 46.1% | < 5% |
| LLM Judge 10/10 后 score | 0.64 | > 0.80 |
| Turn-level evaluation 覆盖 | 0% | 100% (71 turns) |
| 错误传播率 | 28.57% | 0% |
| 图像策略一致性 | 不一致 | 100% |
| 维度默认值保留率 | 76-79% | < 20% |

---

## 📞 快速链接

- **Phase 1 报告**: [docs/task/round3/report/](../report/)
- **Phase 2 已完成**: [Task 2.1 报告](../report/stage2/任务完成报告_2.1.md)
- **Phase 2 规划**:
  - [总览索引](./00_PHASE2_OVERVIEW_INDEX.md)
  - [并行组E](./02_PHASE2_TASKS_2.2_2.3_PARALLEL_GROUP_E.md)
  - [并行组F](./02_PHASE2_TASKS_2.4_2.5_PARALLEL_GROUP_F.md)
  - [独立组G](./02_PHASE2_TASK_2.6_INDEPENDENT_GROUP_G.md)

---

**使用建议**:
1. 先阅读 [总览索引](./00_PHASE2_OVERVIEW_INDEX.md) 了解整体情况
2. 根据执行策略选择任务组
3. 阅读具体任务组的详细文档
4. 参考 Task 2.1 的完成报告作为模板

---

**文档版本**: 1.0
**创建时间**: 2026-02-03
**状态**: 规划完成,准备执行
