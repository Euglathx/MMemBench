# Round 2: 接口定义与协作需求

## 概述

Round 2 聚焦于**端到端验证**，各任务之间的协作主要体现在**数据流动**和**验证脚本集成**。

---

## 1. 数据流接口定义

### 1.1 实验输出 → 验证脚本

#### Interface: Run Log JSON

**生产者**: `run_experiment.py`, `run_batch_test.py`
**消费者**: 所有验证脚本

**格式规范** (必须严格遵守):

```json
[
  {
    "event": "task_start",
    "task_id": "ac_mscoco_001",
    "task_type": "attribute_comparison",
    "timestamp": "2026-02-01T10:00:00",
    ...
  },
  {
    "event": "core_model_decision",
    "turn": 0,
    "action": "guidance",
    "message_to_model": "...",
    "parse_error": false,  // MUST have (Task 1A)
    "error_reason": null,   // MUST have (Task 1A)
    ...
  },
  {
    "event": "target_model_response",
    "turn": 0,
    "target_response": "...",
    "evaluation": {
      "overall_score": 0.75,
      "scores": {
        "correctness": 0.8,
        "faithfulness": 0.7,
        "robustness": 0.9,
        ...
      },
      "llm_judge_output": {...}
    },
    ...
  },
  {
    "event": "task_end",
    ...
  }
]
```

**必须字段**:
- `event`: 事件类型
- `turn`: 回合编号 (for decision/response events)
- `action`: 动作类型 (for decision events)
- `parse_error`: 是否解析失败 (for decision events) -- **Task 1A 依赖**
- `target_response`: 模型响应 (for response events)
- `evaluation`: 评估结果 (for response events) -- **Task 2A 依赖**

#### Interface: Batch Results JSON

**生产者**: `run_batch_test.py`
**消费者**: `verify_task_1d.py`, `convert_batch_results_to_runlog.py`

**格式规范**:

```json
{
  "batch_id": "batch_20260201_100000",
  "task_results": [
    {
      "task_id": "ac_mscoco_001",
      "task_type": "attribute_comparison",
      "completed": true,
      "turns_used": 8,
      "turns": [  // MUST have (Task 1D)
        {
          "turn": 0,
          "action": "guidance",
          "query": "...",
          "response": "...",
          "images_sent": ["path1.jpg", "path2.jpg"],
          "evaluation": {...},
          "timestamp": "2026-02-01T10:00:01",
          "phase": "exploration",
          "difficulty": 1
        },
        ...
      ],
      "conversation_history": [...],  // Alias for compatibility
      "scores": {...},
      "full_result": {...}
    }
  ],
  "summary": {...}
}
```

**必须字段**:
- `turns`: 对话历史详情 -- **Task 1D 核心依赖**
- `turns[].turn`: 回合编号
- `turns[].action`: 动作类型
- `turns[].query`: 用户查询
- `turns[].response`: 模型响应
- `turns[].evaluation`: 评估结果

---

### 1.2 验证脚本 → 报告生成器

#### Interface: 验证结果返回值

**生产者**: `verify_task_*.py`
**消费者**: `verify_all.py`, `generate_report.py`

**标准返回格式** (建议):

每个验证脚本应该在标准输出打印验证结果，并通过 exit code 表示通过/失败：

```python
# 标准输出格式 (供人阅读)
print("=== Task XY Verification ===")
print(f"Metric 1: {value1} (target: {target1})")
print(f"Metric 2: {value2} (target: {target2})")
print(f"Status: {'PASS' if passed else 'FAIL'}")

# Exit code (供脚本判断)
sys.exit(0 if passed else 1)
```

**可选**: 输出 JSON 格式供程序解析

```python
# 使用 --json 参数时输出
if args.json:
    result = {
        "task": "1A",
        "metrics": {
            "parse_errors": 0,
            "please_continue": 0,
            ...
        },
        "pass": True
    }
    print(json.dumps(result))
    sys.exit(0)
```

---

## 2. 任务协作矩阵

### 2.1 Round 2 任务依赖关系

```
Task 3-1 (创建验证脚本)
    └───> Task 3-2 (非多模态实验) ─┐
    └───> Task 3-3 (多模态实验) ───┤
                                 ├──> Task 3-4 (运行验证) ──> Task 3-5 (生成报告)
                                 │
                         (可并行)
```

### 2.2 并行执行策略

#### 策略 A: 单人顺序执行 (推荐)

```
Day 1: Task 3-1 (0.5d) + 开始 Task 3-2 (0.5d)
Day 2: 完成 Task 3-2 (0.5d) + Task 3-3 (0.5d)
Day 3: 完成 Task 3-3 (0.5d) + Task 3-4 (0.5d)
Day 4: Task 3-5 (0.5d) + 优化和文档 (0.5d)
```

#### 策略 B: 双人并行执行

```
人员 A:
  Day 1: Task 3-1 (0.5d) + Task 3-2 setup (0.5d)
  Day 2: Task 3-2 运行和验证 (1d)

人员 B:
  Day 1: 准备测试数据 (1d)
  Day 2: Task 3-3 运行和验证 (1d)

Day 3: 合并，Task 3-4 (0.5d) + Task 3-5 (0.5d)
```

---

## 3. 文件和目录协作规范

### 3.1 测试输出目录结构

```
test_output/
├── final_nonmm/              # 非多模态模型实验 (Task 3-2)
│   ├── run_log_20260201_*.json
│   └── batch_results_20260201_*.json (if batch mode)
│
├── final_mm/                 # 多模态模型实验 (Task 3-3)
│   ├── run_log_20260201_*.json
│   └── batch_results_20260201_*.json (if batch mode)
│
└── final/                    # 最终综合测试 (可选)
    ├── run_log_*.json
    └── batch_results_*.json
```

**协作规则**:
- ❌ 不同任务不要覆盖彼此的输出目录
- ✅ 使用不同的 `--output-dir` 参数
- ✅ 保持时间戳一致性便于追踪

### 3.2 脚本和工具文件

```
task/
├── verify_task_1a.py         # 已存在
├── verify_task_1d.py         # 已存在
├── verify_task_2a.py         # 已存在
├── verify_task_2b.py         # 已存在
├── verify_all.py             # Task 3-1 创建
└── generate_report.py        # Task 3-1 创建

task/round2/
├── 00_validation_report.md   # Round 1 总结
├── 01_task_planning.md       # Round 2 任务规划
├── 02_interface_and_collaboration.md  # 本文档
└── final_validation_report.md  # Task 3-5 生成
```

---

## 4. 数据共享协议

### 4.1 测试数据集使用

**共享资源**: `generated_tasks_v2/run_18/`

**协作规则**:
- ✅ 所有实验使用 run_18 数据集
- ❌ 不修改原始数据
- ✅ 如需测试特定场景，复制到独立目录

### 4.2 模型配置共享

**非多模态基线**: `gemini-3-flash-preview-nothinking`
**多模态目标**: `gpt-4o`

**协作规则**:
- ✅ 统一使用这两个模型进行对比
- ✅ 如需添加其他模型，记录到文档
- ✅ 确保相同的 `max_tokens`, `temperature` 等参数

---

## 5. 验证脚本接口契约

### 5.1 `verify_task_1a.py`

**输入**: `run_log_*.json` 文件路径（支持多个）
**输出**: 标准输出 + Exit code
**检查项**:
- `parse_error` count = 0
- "Please continue" count = 0
- "Failed to parse" count = 0

**调用示例**:
```bash
python task/verify_task_1a.py test_output/final_mm/run_log_*.json
```

### 5.2 `verify_task_1d.py`

**输入**: `batch_results_*.json` 文件路径（支持多个）
**输出**: 标准输出 + Exit code
**检查项**:
- 所有任务有 `turns` 字段
- `turns` 不为空
- Turn 结构完整（必需字段存在）

**调用示例**:
```bash
python task/verify_task_1d.py test_output/final_mm/batch_results_*.json
```

### 5.3 `verify_task_2a.py`

**输入**: `run_log_*.json` 文件路径 + 可选 `--non-multimodal` 或 `--multimodal` 标志
**输出**: 标准输出 + Exit code
**检查项**:
- 非多模态: `avg_score < 0.3`, `faithfulness < 0.2`
- 多模态: `avg_score > 0.6`, `faithfulness > 0.6`

**调用示例**:
```bash
python task/verify_task_2a.py test_output/final_nonmm/run_log_*.json --non-multimodal
python task/verify_task_2a.py test_output/final_mm/run_log_*.json --multimodal
```

### 5.4 `verify_task_2b.py`

**输入**: `run_log_*.json` 文件路径
**输出**: 标准输出 + Exit code
**检查项**:
- 唯一动作种类 >= 8
- 最大单一动作占比 <= 40%

**调用示例**:
```bash
python task/verify_task_2b.py test_output/final_mm/run_log_*.json
```

### 5.5 `verify_all.py` (新创建)

**输入**: 测试输出目录路径
**输出**: 汇总结果 + Exit code
**功能**: 自动调用所有单项验证脚本

**调用示例**:
```bash
python task/verify_all.py test_output
```

### 5.6 `generate_report.py` (新创建)

**输入**: 测试输出目录路径 + 报告输出路径
**输出**: Markdown 格式报告文件
**功能**: 分析所有日志，生成详细报告

**调用示例**:
```bash
python task/generate_report.py test_output task/round2/final_validation_report.md
```

---

## 6. 异常处理和回退策略

### 6.1 验证失败时的处理流程

```
运行实验 → 验证脚本 → FAIL
                       ↓
                   分析日志
                       ↓
              ┌────────┴────────┐
              ↓                 ↓
         参数调整          代码修复
              ↓                 ↓
         重新实验          重新实验
              ↓                 ↓
              └────────┬────────┘
                       ↓
                   验证通过 → 生成报告
```

### 6.2 常见失败场景和应对

| 失败场景 | 可能原因 | 应对措施 |
|---------|---------|---------|
| Task 1A 失败 (parse_error > 0) | o1-preview 特殊响应格式 | 检查日志，完善 fallback 逻辑 |
| Task 1C 失败 (截断率 > 0) | max_tokens 不足 | 增加到 3072 或 4096 |
| Task 1D 失败 (无 turns) | Batch 流程未正确捕获 | 检查 batch_task_simulator.py |
| Task 2A 失败 (score gap < 0.4) | Judge 权重不够高 | 调整 llm_judge_weight |
| Task 2B 失败 (动作 < 8) | 难度门槛仍太高 | 进一步降低 difficulty_level |

### 6.3 紧急回退

如果系统级问题导致无法完成验证：

1. **回退到 Round 1 完成状态**
   ```bash
   git checkout <round1-final-commit>
   ```

2. **创建修复分支**
   ```bash
   git checkout -b round2-hotfix
   ```

3. **单独修复问题**，再重新运行验证

---

## 7. 通信和同步机制

### 7.1 进度跟踪

在 `task/round2/progress.md` 中记录每日进度：

```markdown
# Round 2 进度跟踪

## Day 1 (2026-02-01)
- [x] Task 3-1 完成 (verify_all.py, generate_report.py 创建)
- [x] Task 3-2 启动 (非多模态实验运行中)
- [ ] Task 3-3 待开始

## Day 2 (2026-02-02)
- [x] Task 3-2 完成
- [x] Task 3-3 完成
...
```

### 7.2 问题日志

在 `task/round2/issues.md` 中记录遇到的问题和解决方案：

```markdown
# Round 2 问题日志

## Issue #1: Task 2A 非多模态模型分数仍过高 (0.45)

**时间**: 2026-02-02 10:00
**描述**: 运行非多模态实验后，平均分数为 0.45，超过目标 0.3
**根因**: llm_judge_weight 设为 0.5，hard rules 仍有较高权重
**解决**: 调整 llm_judge_weight 为 0.7
**验证**: 重新运行，分数降至 0.28 ✓
```

---

## 8. 最终交付物清单

### 8.1 代码文件

- [ ] `task/verify_all.py`
- [ ] `task/generate_report.py`
- [ ] (可选) `task/verify_task_1b.py`
- [ ] (可选) `task/verify_task_1c.py`

### 8.2 数据文件

- [ ] `test_output/final_nonmm/run_log_*.json`
- [ ] `test_output/final_nonmm/batch_results_*.json`
- [ ] `test_output/final_mm/run_log_*.json`
- [ ] `test_output/final_mm/batch_results_*.json`

### 8.3 报告文件

- [ ] `task/round2/00_validation_report.md` (Round 1 总结)
- [ ] `task/round2/01_task_planning.md` (Round 2 规划)
- [ ] `task/round2/02_interface_and_collaboration.md` (本文档)
- [ ] `task/round2/final_validation_report.md` (最终验证报告)
- [ ] (可选) `task/round2/progress.md`
- [ ] (可选) `task/round2/issues.md`

### 8.4 文档文件

- [ ] 更新 `README.md` 添加 Round 2 完成说明
- [ ] 更新 `GANTT_SCHEDULE.md` 标记所有任务完成

---

## 9. 成功验收标准

Round 2 完成时，应满足：

### 代码和脚本
- [ ] 所有验证脚本运行无错误
- [ ] `verify_all.py` 返回 PASS

### 实验结果
- [ ] 非多模态模型 avg_score < 0.3
- [ ] 多模态模型 avg_score > 0.6
- [ ] Score gap > 0.4
- [ ] 动作种类 >= 8
- [ ] Parse errors = 0
- [ ] 截断率 = 0%
- [ ] Batch turn 覆盖率 = 100%

### 文档
- [ ] 最终报告完整且清晰
- [ ] 所有问题有记录和解决方案
- [ ] 后续建议明确

---

**Round 2 完成后，M3Bench 修复项目正式结束。**
