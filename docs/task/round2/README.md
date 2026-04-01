# Round 2: 端到端验证 - 快速开始指南

## 当前状态
- **Round 1**: 所有6个任务的代码实现已完成并通过单独调试 ✓
- **Round 2**: 需要运行端到端实验，验证所有指标达标

---

## 快速导航

| 文档 | 用途 |
|------|------|
| [00_validation_report.md](00_validation_report.md) | Round 1 完成状态和代码验证 |
| [01_task_planning.md](01_task_planning.md) | Round 2 的5个任务详细规划 |
| [02_interface_and_collaboration.md](02_interface_and_collaboration.md) | 接口定义和协作需求 |

---

## Round 2 核心任务

```
Task 3-1: 创建验证脚本 (0.5 day)
    ↓
Task 3-2 & 3-3: 运行实验 (并行，各1 day)
    ↓
Task 3-4: 运行验证 (0.5 day)
    ↓
Task 3-5: 生成报告 (0.5 day)
```

**总时长**: 2.5 - 3 days

---

## 执行步骤 (TL;DR)

### Step 1: 创建验证脚本集成 (Task 3-1)

```bash
# 创建 verify_all.py 和 generate_report.py
# 参考 01_task_planning.md 中的代码模板
```

### Step 2: 运行非多模态实验 (Task 3-2)

```bash
python run_batch_test.py \
  --model gemini-3-flash-preview-nothinking \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 3 \
  --num-batches 3 \
  --output-dir test_output/final_nonmm
```

### Step 3: 运行多模态实验 (Task 3-3)

```bash
python run_batch_test.py \
  --model gpt-4o \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 3 \
  --num-batches 3 \
  --output-dir test_output/final_mm
```

### Step 4: 运行所有验证 (Task 3-4)

```bash
python task/verify_all.py test_output
```

### Step 5: 生成最终报告 (Task 3-5)

```bash
python task/generate_report.py test_output task/round2/final_validation_report.md
```

---

## 关键验证指标

### 必须通过的指标

| 任务 | 指标 | 目标 |
|------|------|------|
| Task 1A | Parse errors | 0 |
| Task 1A | "Please continue" | 0 |
| Task 1A | "Failed to parse" | 0 |
| Task 1B | 平均视觉词汇/turn | < 2.0 |
| Task 1C | 截断率 | 0% |
| Task 1D | Batch turn 覆盖率 | 100% |
| Task 2A | 非多模态 avg_score | < 0.3 |
| Task 2A | 多模态 avg_score | > 0.6 |
| Task 2A | Score gap | > 0.4 |
| Task 2B | 唯一动作种类 | >= 8 |
| Task 2B | 最大动作占比 | <= 40% |

---

## 故障排除

### 问题 1: 实验运行失败

**检查**:
- 确认 `generated_tasks_v2/run_18/` 数据存在
- 确认 API 密钥配置正确
- 检查网络连接

### 问题 2: 某个指标未达标

**步骤**:
1. 查看详细日志 (`test_output/*/run_log_*.json`)
2. 参考 `02_interface_and_collaboration.md` 的"异常处理"部分
3. 调整参数或修复代码
4. 重新运行实验

### 问题 3: API 成本过高

**缓解**:
- 减少 `num-batches` 参数
- 使用更便宜的模型测试
- 使用缓存避免重复调用

---

## 时间安排建议

### 单人执行

- **Day 1 上午**: Task 3-1 (0.5d)
- **Day 1 下午**: 启动 Task 3-2 (0.5d)
- **Day 2**: 完成 Task 3-2 + 启动 Task 3-3 (1d)
- **Day 3 上午**: 完成 Task 3-3 (0.5d)
- **Day 3 下午**: Task 3-4 + Task 3-5 (1d)

### 双人执行

- **人员 A**: Task 3-1 + Task 3-2 + 报告整合
- **人员 B**: 数据准备 + Task 3-3 + 验证运行

**节省时间**: 约 1 day

---

## 验收清单

完成 Round 2 前，确认：

- [ ] 所有验证脚本已创建 (`verify_all.py`, `generate_report.py`)
- [ ] 非多模态实验运行完成，生成日志
- [ ] 多模态实验运行完成，生成日志
- [ ] 所有验证脚本返回 PASS
- [ ] 最终报告已生成，内容完整
- [ ] 所有关键指标达标
- [ ] 问题和解决方案已记录

---

## 下一步

Round 2 完成后：

1. 提交所有代码和文档到代码库
2. 更新主 README.md 说明项目完成
3. (可选) 撰写 Paper/Blog 介绍修复过程
4. (可选) 发布新版本的 M3Bench

---

## 联系和支持

如有问题，参考：
- Round 1 实现总结: `task/task_*_implementation_summary.md`
- 详细任务规划: [01_task_planning.md](01_task_planning.md)
- 接口定义: [02_interface_and_collaboration.md](02_interface_and_collaboration.md)

**祝验证顺利！** 🎉
