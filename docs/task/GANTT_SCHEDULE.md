# M3Bench修复任务 - 甘特图式执行计划

## 总览

```
时间轴: Week 1 ------------ Week 2 ------------ Week 3 ----

阶段1   [======Task 1A======]
        [======Task 1B======]
        [=Task 1C=]
                [======Task 1D======]
        └─────────┴─── 同步点1 ───┘

阶段2                    [========Task 2A========]
                                [====Task 2B====]
                        └─────────┴─── 同步点2 ───┘

阶段3                                    [====Task 3====]
                                        └─ 最终验证 ─┘
```

---

## 阶段1: 基础修复 (Week 1)

### 可并行窗口组 A (Day 1-3)

| 窗口 | 任务 | 文件 | 独立性 | 时间 |
|-----|------|------|-------|------|
| 窗口1 | [Task 1A](task_1a_parsing_fix.md) | `strategic_simulator.py` | 100% | 2d |
| 窗口2 | [Task 1B](task_1b_text_hints.md) | `llm_user_simulator.py` | 100% | 2d |
| 窗口3 | [Task 1C](task_1c_truncation_fix.md) | `strategic_simulator.py` | 100% | 0.5d |

**协作点**: 无冲突,完全独立
**阻塞**: 无

### 可并行窗口组 B (Day 4-5)

| 窗口 | 任务 | 依赖 | 时间 |
|-----|------|------|------|
| 窗口1 | [Task 1D](task_1d_batch_integration.md) | ⚠️ 建议1A完成 | 2d |

**协作点**: 等待Task 1A避免parse error干扰测试
**阻塞**: Task 1A建议完成,但可强行并行

### 同步点1 (Day 5 End)

运行验证脚本:
```bash
# 验证Task 1A
python task/verify_task_1a.py test_output/phase1/run_log_*.json

# 验证Task 1D
python task/verify_task_1d.py test_output/phase1/batch_results_*.json

# 检查对话质量
grep -c "Please continue" test_output/phase1/*.json
grep -c "Failed to parse" test_output/phase1/*.json
```

**通过标准**:
- [ ] Parse errors = 0
- [ ] Batch有turn details
- [ ] run_18数据可加载

---

## 阶段2: 评估与动作 (Week 2)

### 并行窗口组 C (Day 1-6)

| 窗口 | 任务 | 依赖 | 可并行 | 时间 |
|-----|------|------|-------|------|
| 窗口1 | [Task 2A](task_2a_evaluation_fix.md) | ✅ Task 1A,1B完成 | 与2B并行 | 3d |
| 窗口2 | [Task 2B](task_2b_action_space.md) | ✅ Task 1A完成 | 与2A并行 | 2d |

**时间轴**:
```
Day 1-4: 窗口1做Task 2A
Day 5-6: 窗口1做Task 2B部分验证
         窗口2做Task 2B主要开发
```

**协作点**:
- 两个任务修改不同文件(`evaluator.py` vs `action_selector.py`)
- 无代码冲突

### 同步点2 (Day 6 End)

运行对比测试:
```bash
# 非多模态模型测试
python run_experiment.py --model gemini-3-flash-preview-nothinking \
  --num-tasks 5 --output-dir test_output/phase2_nonmm

# 多模态模型测试
python run_experiment.py --model gpt-4o \
  --num-tasks 5 --output-dir test_output/phase2_mm

# 验证评估
python task/verify_task_2a.py test_output/phase2_*/run_log_*.json

# 验证动作多样性
python task/verify_task_2b.py test_output/phase2_mm/run_log_*.json
```

**通过标准**:
- [ ] 非多模态 avg_score < 0.3
- [ ] 多模态 avg_score > 0.6
- [ ] 动作种类 >= 8

---

## 阶段3: 端到端验证 (Week 3)

### 顺序窗口 (Day 1-5)

| 窗口 | 任务 | 依赖 | 时间 |
|-----|------|------|------|
| 窗口1 | [Task 3](task_3_validation.md) | ✅ 所有前置任务 | 2d |

**不可并行** - 需要完整系统

运行:
```bash
python task/verify_all.py
python task/generate_report.py
```

---

## 实际执行建议

### 单人执行
按阶段顺序:
1. Week 1: 做Task 1A → 1B → 1C → 1D
2. Week 2: 做Task 2A → 2B
3. Week 3: 做Task 3

### 双人执行
#### Week 1
- 人员A: Task 1A + Task 1C
- 人员B: Task 1B
- Day 4合并,一起做Task 1D

#### Week 2
- 人员A: Task 2A
- 人员B: Task 2B
- Day 6合并验证

### 三人执行
#### Week 1 (最高效)
- 窗口1: Task 1A
- 窗口2: Task 1B
- 窗口3: Task 1C → 协助1A/1B
- Day 4: 窗口1+2做Task 1D,窗口3验证

#### Week 2
- 窗口1: Task 2A
- 窗口2: Task 2B
- 窗口3: 编写验证脚本

---

## 同步协议

### 每日同步 (如果并行)
每天结束时:
1. 提交代码到各自分支: `task-1a`, `task-1b`, etc.
2. 在task文件夹创建日志: `task_1a_day1.log`
3. 更新进度: 在README.md中标记完成的步骤

### 阶段同步
每个阶段结束:
1. 合并所有分支到 `dev` 分支
2. 运行同步点验证脚本
3. 如果失败,回退修复,再验证
4. 通过后,开始下一阶段

### 冲突解决
如果遇到merge冲突(理论上不应该):
- Task 1A vs 1C: strategic_simulator.py冲突
  - 解决: 1A的修改在函数内,1C只改参数,手动合并
- 其他组合: 应该无冲突

---

## 关键路径

```
Task 1A (解析) → Task 2A (评估) → Task 3 (验证)
    ↓
Task 1D (Batch) ────────────────→ Task 3
    ↓
Task 2B (动作) ─────────────────→ Task 3
```

**最短完成时间**: 3 weeks (如果严格顺序)
**并行完成时间**: 2.5 weeks (3人协作)
**现实时间**: 3-4 weeks (考虑debug和返工)

---

## 每日检查清单

### Week 1 Day 1
- [ ] 启动Task 1A, 1B, 1C
- [ ] 每个窗口创建独立分支
- [ ] 读取各自的task markdown
- [ ] 开始编码

### Week 1 Day 3 (第一个同步点)
- [ ] Task 1A, 1B完成编码
- [ ] Task 1C已完成
- [ ] 运行各自的verify脚本
- [ ] 合并到dev分支

### Week 1 Day 5 (阶段1结束)
- [ ] Task 1D完成
- [ ] 运行同步点1验证
- [ ] 确认run_18数据可用
- [ ] ✅ 阶段1验收

### Week 2 Day 4
- [ ] Task 2A基本完成
- [ ] Task 2B开始或进行中
- [ ] 中期测试

### Week 2 Day 6 (阶段2结束)
- [ ] Task 2A, 2B都完成
- [ ] 运行同步点2验证
- [ ] 对比测试通过
- [ ] ✅ 阶段2验收

### Week 3 Day 5 (最终)
- [ ] Task 3验证完成
- [ ] 生成报告
- [ ] 所有指标达标
- [ ] ✅ 项目完成
