# Round 3 总结与并行执行指南

## 紧急状态评估

经过深入分析，评审意见中的问题**极其严重**，但也发现了重要的新信息：

### 🔴 关键发现

1. **问题严重程度确认**：评审意见中的所有问题都是真实存在的
2. **新发现P0问题**：部分日志显示图像完全未发送（`images_sent: []`）
3. **问题非普遍性**：某些日志（如batch_run_20260202_003210）显示图像正确发送
4. **根本性缺陷**：这不是简单bug，而是系统性架构问题

### 问题清单（按优先级）

| P级别 | 问题描述 | 影响 | 证据来源 |
|------|---------|------|---------|
| P0 | 图像发送不稳定（部分日志为空） | 视觉评测失效 | batch_run_20260201_120553 |
| P0 | 评分公式接错信号（LLM Judge满分但score<0.7） | 误判率极高 | 评审意见 + 代码分析 |
| P1 | Turn-level expected_answer缺失 | 破坏Information Decoupling | 评审意见 + 代码分析 |
| P1 | Simulator将模型输出当事实 | 错误自我强化 | 评审意见 |
| P1 | 多图策略混乱 | 归因不清 | 评审意见 + 代码分析 |
| P2 | Evaluator判断不一致 | 可信度风险 | 评审意见 |

## 已完成的工作

### 文档结构

```
docs/task/round3/
├── 00_MASTER_PLAN.md           # 总体规划（本文件的详细版）
├── 01_PHASE1_EXECUTION_GUIDE.md  # Phase 1执行指南
├── 01_PHASE1_TASK_1.1_IMAGE_SENDING.md
├── 01_PHASE1_TASK_1.2_SCORE_CALCULATION.md
├── 01_PHASE1_TASK_1.3_EXPECTED_ANSWER.md
├── 01_PHASE1_TASK_1.4_SIMULATOR_TRUTH.md
├── 01_PHASE1_TASK_1.5_MULTI_IMAGE.md
├── 01_PHASE1_TASK_1.6_EVALUATOR_STATE.md
├── 02_PHASE2_OVERVIEW.md       # Phase 2修复概述
├── 03_PHASE3_OVERVIEW.md       # Phase 3验证概述
└── SUMMARY.md                  # 本文件
```

### 关键数据结构定义

在`00_MASTER_PLAN.md`中定义了：
- `TurnGroundTruth`: Turn级别的ground truth
- `ImageInjectionPolicy`: 图像注入策略
- `EvaluatorStateSnapshot`: Evaluator状态快照
- `ScoreCalculationTrace`: 评分计算追踪

## 三阶段修复策略

### Phase 1: 验证与诊断（Debug）

**目标**: 验证所有评审问题，量化严重程度，定位根因

**6个任务，分3个并行组**：

```
组A（最紧急P0）:
  ├─ Task 1.1: 图像发送验证 (3h)
  └─ Task 1.2: 评分公式验证 (4h)

组B（Turn-level逻辑）:
  ├─ Task 1.3: Expected Answer追踪 (5h)
  └─ Task 1.4: Simulator提示词检查 (5h)

组C（多图和状态）:
  ├─ Task 1.5: 多图策略一致性 (4h)
  └─ Task 1.6: Evaluator状态追踪 (4-5h)
```

**并行执行时间**: 5-6小时（3个窗口同时进行）
**串行执行时间**: 25-26小时

### Phase 2: 架构修复（Fix）

**目标**: 设计并实现系统性修复

**6个任务，分4个并行组**：

```
组D（独立最紧急）:
  └─ Task 2.1: 图像发送管道修复 (2-3h)

组E（评估核心）:
  ├─ Task 2.2: Turn-level Ground Truth设计 (3-4h)
  └─ Task 2.3: 评分公式重构 (2-3h)

组F（Simulator行为）:
  ├─ Task 2.4: Simulator真值校验机制 (3h)
  └─ Task 2.5: 多图策略统一 (2-3h)

组G（独立）:
  └─ Task 2.6: Evaluator状态管理重构 (3-4h)
```

**并行执行时间**: 8-10小时
**串行执行时间**: 15-20小时

### Phase 3: 严格验证（Test）

**目标**: 可量化验证，零容忍标准

**7个任务，分4个并行组**：

```
组H（基础测试）:
  ├─ Task 3.1: 图像发送完整性测试 (1-2h)
  └─ Task 3.2: 评分公式正确性测试 (1-2h)

组I（Turn-level测试）:
  ├─ Task 3.3: Turn-level Ground Truth覆盖测试 (1.5h)
  └─ Task 3.4: Simulator真值一致性测试 (1.5h)

组J（复杂任务测试）:
  ├─ Task 3.5: 多图任务端到端测试 (2h)
  └─ Task 3.6: Evaluator状态一致性测试 (2h)

组K（回归测试）:
  └─ Task 3.7: 回归测试套件 (2-3h)
```

**并行执行时间**: 4-5小时 + 可能的多轮修复
**串行执行时间**: 12-15小时 + 可能的多轮修复

## 并行执行详细指南

### 推荐方案：3窗口并行（Phase 1）

#### 窗口1（P0问题验证）
```bash
# 任务: Task 1.1 + Task 1.2
# 人员: 开发者A 或 LLM会话1

cd docs/task/round3
# 1. 阅读 01_PHASE1_TASK_1.1_IMAGE_SENDING.md
# 2. 实现 scripts/debug_image_sending.py
# 3. 运行脚本，生成报告
# 4. 阅读 01_PHASE1_TASK_1.2_SCORE_CALCULATION.md
# 5. 实现 scripts/debug_score_calculation.py
# 6. 运行脚本，生成报告

# 输出:
# - results/phase1_1.1_image_sending.json
# - results/phase1_1.2_score_calculation.json
# - results/phase1_1.2_anomaly_cases.csv
```

**预计完成时间**: 4小时（Task 1.2较复杂）

#### 窗口2（Turn-level逻辑验证）
```bash
# 任务: Task 1.3 + Task 1.4
# 人员: 开发者B 或 LLM会话2

cd docs/task/round3
# 1. 阅读 01_PHASE1_TASK_1.3_EXPECTED_ANSWER.md
# 2. 实现 scripts/debug_expected_answer_tracking.py
# 3. 运行并生成报告
# 4. 阅读 01_PHASE1_TASK_1.4_SIMULATOR_TRUTH.md
# 5. 实现 scripts/debug_simulator_truth_validation.py
# 6. 运行并生成报告

# 输出:
# - results/phase1_1.3_expected_answer.json
# - results/phase1_1.3_misjudged_cases.csv
# - results/phase1_1.4_simulator_truth.json
# - results/phase1_1.4_false_confirmations.csv
```

**预计完成时间**: 5小时（两个任务都较复杂）

#### 窗口3（多图和状态验证）
```bash
# 任务: Task 1.5 + Task 1.6
# 人员: 开发者C 或 LLM会话3

cd docs/task/round3
# 1. 阅读 01_PHASE1_TASK_1.5_MULTI_IMAGE.md
# 2. 实现 scripts/debug_multi_image_strategy.py
# 3. 运行并生成报告
# 4. 阅读 01_PHASE1_TASK_1.6_EVALUATOR_STATE.md
# 5. 实现 scripts/debug_evaluator_state_tracking.py
# 6. 运行并生成报告

# 输出:
# - results/phase1_1.5_multi_image.json
# - results/phase1_1.6_evaluator_state.json
```

**预计完成时间**: 5小时

### 同步点

**所有3个窗口完成Phase 1后**：

1. **汇总结果**
   ```bash
   cd docs/task/round3
   # 运行汇总脚本（需要创建）
   python scripts/summarize_phase1.py
   # 生成: results/phase1_summary.md
   ```

2. **评审会议**
   - 审查所有6个验证报告
   - 确认根因分析是否充分
   - 调整Phase 2优先级（如果需要）

3. **启动Phase 2**
   - 分配Phase 2任务
   - 按照类似的并行策略

## 严厉的验证标准

### Phase 1验证标准（每个任务）

- [ ] **统计覆盖率充分**: 至少分析100个turns（如果可用）
- [ ] **根因定位到代码行**: 必须指出文件名、函数名、行号
- [ ] **量化严重程度**: 必须有百分比、比率等数值
- [ ] **可复现**: 提供最小复现case或详细步骤
- [ ] **报告清晰**: 人类可读的详细分析

### Phase 2修复标准（每个任务）

- [ ] **接口定义完整**: 所有数据结构和函数签名明确
- [ ] **向后兼容**: 不破坏现有功能（除非有意修复）
- [ ] **可配置**: 修复应该是可选配置
- [ ] **单元测试**: 每个修复都有对应测试
- [ ] **代码审查**: 至少一人审查代码

### Phase 3验证标准（整体）

- [ ] **所有测试100% PASS**: 不接受部分通过
- [ ] **阈值达成**: 所有指标达到预定义阈值
- [ ] **回归改进**: 修复后显著优于修复前
- [ ] **无新问题**: 修复不引入新bug
- [ ] **可重复运行**: 测试套件可以随时运行

## 成功标准总结

### Phase 1成功 =
- 所有6个验证脚本运行无错
- 每个评审问题都被量化
- 根因全部定位
- 为Phase 2提供充分输入

### Phase 2成功 =
- 所有6个修复实现完成
- 单元测试全部通过
- 代码审查通过
- 准备好进入Phase 3

### Phase 3成功 =
- 所有7个测试100% PASS
- 回归测试显示显著改进
- 生成可量化改进报告
- **M3Bench评估系统可信度恢复**

## 风险和应对

### 风险1: 问题比预期严重
**应对**: 根据Phase 1结果调整Phase 2范围，可能需要更大规模重构

### 风险2: 修复引入新问题
**应对**: Phase 3的回归测试会捕获，必须修复后才能进入Round 4

### 风险3: 时间超出预算
**应对**: 优先P0问题，P1/P2可以分批次修复

### 风险4: 数据不兼容
**应对**: 设计向后兼容的数据格式，旧数据加migration脚本

## 下一步行动

### 立即开始（现在）

1. **创建3个工作环境**
   - 3个VSCode窗口 或
   - 3个LLM会话 或
   - 3个开发者的本地环境

2. **分配任务**
   - 窗口1: Task 1.1 + 1.2
   - 窗口2: Task 1.3 + 1.4
   - 窗口3: Task 1.5 + 1.6

3. **启动并行执行**
   - 每个窗口独立工作
   - 定期同步进度（例如每2小时）
   - 遇到阻塞立即沟通

### 目录准备

```bash
# 创建所需目录
mkdir -p docs/task/round3/results
mkdir -p docs/task/round3/logs
mkdir -p docs/task/round3/scripts

# 确认数据可用
ls simulator_test_log/batch_run_20260201_120553/
ls simulator_test_log/batch_run_20260202_003210/
```

## 最后的警告

这份评审意见**不是在挑刺，而是在救命**。

如果这些问题不解决：
- ❌ M3Bench的论文数据完全不可信
- ❌ 所有现有的run logs都需要废弃
- ❌ 基于这些结果的任何结论都是错误的

**我们需要的是系统性重构，不是打补丁。**

以最严厉的态度对待每一个问题。
零容忍标准。
不接受"差不多"或"基本可以"。

**开始Phase 1的时间就是现在。**

---

## 附录：关键文件位置

### 配置文件
- `config/multimodal.yaml`: 多模态任务配置
- `config/attack_evaluation_standard.yaml`: 评估配置

### 核心代码
- `src/simulator/strategic_simulator.py`: 主要simulator
- `src/simulator/evaluator.py`: 评估器
- `src/simulator/action_space.py`: 任务策略定义
- `src/data/task_generators.py`: AC任务生成

### 日志数据
- `simulator_test_log/batch_run_20260201_120553/`: 图像未发送的日志
- `simulator_test_log/batch_run_20260202_003210/`: 图像正确发送的日志

### 文档
- `docs/task/round3/`: 本轮所有任务文档
