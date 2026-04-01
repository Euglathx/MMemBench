# Round 4 任务执行总览

**创建时间**: 2026-02-05
**总预计时间**: 20-26 小时
**并行窗口数**: 最多 4 个

---

## 快速导航

| Phase | Window | 任务名称 | 优先级 | 预计时间 | 文件 |
|-------|--------|---------|--------|---------|------|
| Phase 1 | W1 | 配置审计 | HIGH | 3h | [phase1-window1.md](./phase1-window1.md) |
| Phase 1 | W2 | 代码逻辑验证 | HIGH | 4h | [phase1-window2.md](./phase1-window2.md) |
| Phase 2 | W1 | 评估框架重构 🔴 | P0 | 4-6h | [phase2-window1.md](./phase2-window1.md) |
| Phase 2 | W2 | Prompt 图像数量匹配 | P1 | 2h | [phase2-window2.md](./phase2-window2.md) |
| Phase 2 | W3 | Evaluator 视觉一致性 | P1 | 2-3h | [phase2-window3.md](./phase2-window3.md) |
| Phase 2 | W4 | Consistency Check 图像 | P1 | 1-2h | [phase2-window4.md](./phase2-window4.md) |

---

## Phase 1: 诊断（7 小时）

**目标**: 找出 Round 3 每个修复失败的具体原因

### 并行执行策略

```
Window 1 (3h)                Window 2 (4h)
┌─────────────┐              ┌──────────────┐
│ 配置审计     │              │ 代码验证      │
│             │              │              │
│ 检查配置文件 │              │ 创建测试脚本  │
│ 检查硬编码  │              │ 运行 2 个任务 │
│ 生成审计报告│              │ 检查 6 个点  │
└─────────────┘              └──────────────┘
       │                            │
       └────────────┬───────────────┘
                    ↓
          Phase 1 完成
          生成失败检查点列表
                    ↓
              进入 Phase 2
```

**可并行**: 完全并行，互不依赖

**输出**:
- `phase1_config_audit.md` - 配置差异报告
- `phase1_code_verification_report.md` - 验证报告
- `phase1_failed_checkpoints.csv` - 失败列表

---

## Phase 2: 修复（9-13 小时）

**目标**: 针对性解决 Phase 1 中失败的检查点

### 并行执行策略

```
Window 1 (4-6h)           Window 2 (2h)           Window 3 (2-3h)         Window 4 (1-2h)
┌─────────────┐           ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│ 评估框架重构│           │ Prompt 匹配 │         │ Evaluator   │         │ Consistency │
│ 🔴 P0       │           │             │         │ 一致性      │         │ Check 图像  │
│             │           │ 动态生成    │         │             │         │             │
│ Turn Purpose│           │ image_ref   │         │ 视觉事实    │         │ 图像传递    │
│ vs Expected │           │             │         │ 缓存        │         │ 修复        │
└─────────────┘           └─────────────┘         └─────────────┘         └─────────────┘
       │                         │                        │                       │
       └─────────────────────────┴────────────────────────┴───────────────────────┘
                                          │
                                    Phase 2 完成
                                    所有修复实现
                                          │
                                    进入 Phase 3
```

**并行性**: 4 个 windows 完全并行（代码模块独立）

**优先级**:
- **P0** (必须): Window 1 - 评估框架重构（最关键）
- **P1** (强烈建议): Windows 2, 3, 4

**输出**:
- 修改后的代码文件
- 各个修复报告
- 测试脚本

---

## 关键修复说明

### 🔴 Phase 2 Window 1: 评估框架重构（最高优先级）

**为什么最重要**:
- 这是用户反馈的核心问题
- Round 3 的**概念框架错了**，不是简单的 bug 修复
- 影响所有中间 turn 的评估

**核心变化**:
- 从 "expected answer" → "turn purpose"
- 中间 turn 是"可靠性检查"，不是"答对答案"
- LLM Judge prompt 重构，明确告知不要按最终答案扣分

**数据结构**:
```python
TurnEvaluationContext:
    turn_purpose: str                    # "entity_grounding", "spatial_reasoning", "reliability_check"
    is_reliability_check: bool           # true/false
    task_ground_truth: str               # 重命名自 expected_answer
    evaluation_focus: List[str]          # ["entity_identification"], 不包括 "final_answer_match"
```

---

## 执行建议

### 串行执行（单人/单 window）

**顺序**:
1. Phase 1 Window 1 (3h)
2. Phase 1 Window 2 (4h)
3. Phase 2 Window 1 (4-6h) ← 最关键
4. Phase 2 Window 2 (2h)
5. Phase 2 Window 3 (2-3h)
6. Phase 2 Window 4 (1-2h)

**总时间**: 20-26 小时

---

### 并行执行（多人/多 window）

**阶段 1 (最快 4h)**:
- Window A: Phase 1 Window 1 (3h)
- Window B: Phase 1 Window 2 (4h)

**同步点**: 等两个都完成

**阶段 2 (最快 6h)**:
- Window A: Phase 2 Window 1 (4-6h) ← 最关键
- Window B: Phase 2 Window 2 (2h) + Window 4 (1-2h)
- Window C: Phase 2 Window 3 (2-3h)

**总时间**: 10-13 小时

---

## 成功标准

### Phase 1 成功 =
- [x] 配置审计完成，找出所有配置差异
- [x] 至少运行 2 个测试任务
- [x] 所有 6 个检查点验证完成
- [x] 明确列出失败的检查点

### Phase 2 成功 =
- [x] 所有失败的检查点都有对应修复
- [x] 修复代码实现并测试通过
- [x] 每个修复有独立的测试脚本
- [x] 每个修复有完整的修复报告

---

## 风险与应对

### 风险 1: Phase 1 发现大量配置问题

**应对**: 先修复配置，重新运行测试，可能减少需要写的代码

### 风险 2: Window 1（评估框架重构）比预期复杂

**应对**:
- 这是 P0 任务，必须完成
- 其他 windows 可以等待或降级
- 如果时间不够，Phase 2 只做 Window 1

### 风险 3: 代码冲突（多人修改同一文件）

**应对**:
- Window 1 和 Window 3 都可能修改 `evaluator.py`
- 建议 Window 3 等待 Window 1 完成，或提前沟通

---

## 验证方法

每个 Phase 完成后，运行端到端测试：

```bash
# Phase 1 完成后
python scripts/round4_phase1_summary.py

# Phase 2 完成后
python scripts/round4_phase2_validation.py

# 运行完整的批量测试（20 个任务）
python scripts/round4_full_validation.py
```

---

## 文档结构

```
docs/task/round4/
├── README.md                               # 本文件（总览）
├── phase1-window1.md                       # Phase 1 Window 1 任务详情
├── phase1-window2.md                       # Phase 1 Window 2 任务详情
├── phase2-window1.md                       # Phase 2 Window 1 任务详情（最关键）
├── phase2-window2.md                       # Phase 2 Window 2 任务详情
├── phase2-window3.md                       # Phase 2 Window 3 任务详情
├── phase2-window4.md                       # Phase 2 Window 4 任务详情
├── phase1_config_audit.md                  # Phase 1 输出：配置审计报告
├── phase1_code_verification_report.md      # Phase 1 输出：代码验证报告
├── phase1_failed_checkpoints.csv           # Phase 1 输出：失败列表
├── phase2_fix2.0_report.md                 # Phase 2 输出：修复 2.0 报告
├── phase2_fix2.1_report.md                 # Phase 2 输出：修复 2.1 报告
├── phase2_fix2.2_report.md                 # Phase 2 输出：修复 2.2 报告
└── phase2_fix2.3_report.md                 # Phase 2 输出：修复 2.3 报告
```

---

## 下一步行动

### 立即开始（现在）

**如果单人执行**:
1. 阅读 [phase1-window1.md](./phase1-window1.md)
2. 开始配置审计

**如果多人/多 window 执行**:
1. 分配任务：
   - 开发者 A / Window A → Phase 1 Window 1
   - 开发者 B / Window B → Phase 1 Window 2
2. 约定同步时间（Phase 1 完成后）
3. 各自独立工作

---

## 关键用户反馈回顾

1. **图像传输已改善** - Task 2.1 部分生效
2. **Turn-level 评估的本质问题** - 需要重新设计评估框架（Phase 2 Window 1）
3. **Simulator "确认错误"可能是 ground truth 问题** - 暂时不修复，标记即可
4. **标注问题处理** - 只做检测，不做 LLM 重新标注

---

## 联系与支持

如有问题，查看具体任务文件中的"注意事项"和"验证标准"章节。

---

**创建时间**: 2026-02-05
**最后更新**: 2026-02-05
**版本**: 1.0
