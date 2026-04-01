# Round 2: 端到端验证与最终报告

## Round 2 目标
完成 Task 3 的全系统端到端验证，确保所有 6 个任务的组合达到预期效果。

---

## 时间规划

```
Day 1-2: 准备与测试
Day 3-4: 运行实验
Day 5: 验证与报告
```

---

## Task 3-1: 创建验证脚本集成

**优先级**: P0 - 必须完成
**预计时间**: 0.5 day
**可并行**: ✅ 可独立完成

### 任务目标
创建 `task/verify_all.py` 和 `task/generate_report.py`，整合所有验证脚本。

### 具体要求

#### 文件 1: `task/verify_all.py`

集成所有单项验证脚本：

```python
import subprocess
import sys
import glob
from pathlib import Path

def run_verification(test_dir: str):
    """运行所有验证脚本."""
    tests = [
        ("Task 1A - Parse Error", "python task/verify_task_1a.py"),
        ("Task 1D - Batch Integration", "python task/verify_task_1d.py"),
        ("Task 2A - Evaluation Fix", "python task/verify_task_2a.py"),
        ("Task 2B - Action Diversity", "python task/verify_task_2b.py"),
    ]

    # 查找所有测试输出
    run_logs = glob.glob(f"{test_dir}/**/run_log_*.json", recursive=True)
    batch_results = glob.glob(f"{test_dir}/**/batch_results_*.json", recursive=True)

    results = {}

    for name, base_cmd in tests:
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print('='*60)

        # 根据任务选择输入文件
        if "1A" in name or "2A" in name or "2B" in name:
            cmd = f"{base_cmd} {' '.join(run_logs)}"
        elif "1D" in name:
            cmd = f"{base_cmd} {' '.join(batch_results)}"
        else:
            cmd = base_cmd

        result = subprocess.run(cmd, shell=True)
        results[name] = result.returncode == 0

    # 最终汇总
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print('='*60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return all_passed

if __name__ == "__main__":
    test_dir = sys.argv[1] if len(sys.argv) > 1 else "test_output"
    passed = run_verification(test_dir)
    sys.exit(0 if passed else 1)
```

#### 文件 2: `task/generate_report.py`

生成详细的验证报告（markdown 格式）：

```python
import json
import glob
from pathlib import Path
from collections import Counter
from datetime import datetime

def analyze_logs(test_dir: str) -> dict:
    """分析所有测试输出."""
    # 读取所有 run_log
    run_logs = glob.glob(f"{test_dir}/**/run_log_*.json", recursive=True)
    batch_results = glob.glob(f"{test_dir}/**/batch_results_*.json", recursive=True)

    analysis = {
        "timestamp": datetime.now().isoformat(),
        "test_directory": test_dir,
        "task_1a": analyze_parse_errors(run_logs),
        "task_1b": analyze_text_hints(run_logs),
        "task_1c": analyze_truncation(run_logs),
        "task_1d": analyze_batch_integration(batch_results),
        "task_2a": analyze_evaluation_scores(run_logs),
        "task_2b": analyze_action_diversity(run_logs),
    }

    return analysis

def analyze_parse_errors(run_logs):
    # 统计 parse error
    total_decisions = 0
    parse_errors = 0
    please_continue = 0
    failed_to_parse = 0

    for log_file in run_logs:
        with open(log_file) as f:
            events = json.load(f)

        for event in events:
            if event.get('event') == 'core_model_decision':
                total_decisions += 1
                if event.get('parse_error'):
                    parse_errors += 1
                msg = event.get('message_to_model', '').lower()
                if 'please continue' in msg:
                    please_continue += 1
                if 'failed to parse' in msg:
                    failed_to_parse += 1

    return {
        "total_decisions": total_decisions,
        "parse_errors": parse_errors,
        "please_continue_count": please_continue,
        "failed_to_parse_count": failed_to_parse,
        "pass": parse_errors == 0 and please_continue == 0 and failed_to_parse == 0
    }

# ... (其他分析函数)

def generate_markdown_report(analysis: dict, output_path: str):
    """生成 Markdown 报告."""
    report = f"""# M3Bench 系统验证报告

生成时间: {analysis['timestamp']}
测试目录: {analysis['test_directory']}

---

## 1. Task 1A - 解析修复

- 总决策次数: {analysis['task_1a']['total_decisions']}
- Parse Errors: {analysis['task_1a']['parse_errors']} (目标: 0)
- "Please continue" 出现: {analysis['task_1a']['please_continue_count']} (目标: 0)
- "Failed to parse" 出现: {analysis['task_1a']['failed_to_parse_count']} (目标: 0)

状态: {'PASS' if analysis['task_1a']['pass'] else 'FAIL'}

---

## 2. Task 1B - 文本提示最小化

- 平均视觉词汇/turn: {analysis['task_1b'].get('avg_visual_words_per_turn', 'N/A')}
- 目标: < 2.0

状态: {'PASS' if analysis['task_1b'].get('pass') else 'FAIL'}

---

## 3. Task 1C - 截断修复

- 总响应数: {analysis['task_1c']['total_responses']}
- 截断响应数: {analysis['task_1c']['truncated_responses']}
- 截断率: {analysis['task_1c']['truncation_rate']:.1f}% (目标: 0%)

状态: {'PASS' if analysis['task_1c']['pass'] else 'FAIL'}

---

## 4. Task 1D - Batch 集成

- 总任务数: {analysis['task_1d']['total_tasks']}
- 有 turn 详情的任务: {analysis['task_1d']['tasks_with_turns']}
- 覆盖率: {analysis['task_1d']['coverage']:.1f}% (目标: 100%)

状态: {'PASS' if analysis['task_1d']['pass'] else 'FAIL'}

---

## 5. Task 2A - 评估系统修复

### 非多模态模型 (Baseline)
- 平均分数: {analysis['task_2a']['nonmm_avg_score']:.2f} (目标: < 0.3)
- Faithfulness: {analysis['task_2a']['nonmm_faithfulness']:.2f} (目标: < 0.2)

### 多模态模型
- 平均分数: {analysis['task_2a']['mm_avg_score']:.2f} (目标: > 0.6)
- Faithfulness: {analysis['task_2a']['mm_faithfulness']:.2f} (目标: > 0.6)

### Score Gap
- Gap: {analysis['task_2a']['score_gap']:.2f} (目标: > 0.4)

状态: {'PASS' if analysis['task_2a']['pass'] else 'FAIL'}

---

## 6. Task 2B - 动作空间扩展

- 唯一动作种类: {analysis['task_2b']['unique_actions']} (目标: >= 8)
- 最大单一动作占比: {analysis['task_2b']['max_action_pct']:.1f}% (目标: <= 40%)

动作分布:
{analysis['task_2b']['action_distribution']}

状态: {'PASS' if analysis['task_2b']['pass'] else 'FAIL'}

---

## 总结

通过的任务: {sum(1 for k, v in analysis.items() if isinstance(v, dict) and v.get('pass'))} / 6

整体状态: {'ALL PASS - 系统达标' if all(v.get('pass') for k, v in analysis.items() if isinstance(v, dict)) else 'PARTIAL FAIL - 需要修复'}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"报告已生成: {output_path}")

if __name__ == "__main__":
    import sys
    test_dir = sys.argv[1] if len(sys.argv) > 1 else "test_output"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "validation_report.md"

    analysis = analyze_logs(test_dir)
    generate_markdown_report(analysis, output_path)
```

### 验收标准
- [ ] `verify_all.py` 能正确调用所有验证脚本
- [ ] `generate_report.py` 能生成完整的 markdown 报告
- [ ] 报告包含所有 6 个任务的验证结果

---

## Task 3-2: 运行非多模态模型实验

**优先级**: P0 - 必须完成
**预计时间**: 1 day (包括运行时间)
**依赖**: Task 3-1
**可并行**: ✅ 可与 Task 3-3 并行

### 任务目标
运行非多模态模型 (baseline) 实验，预期得到低分 (< 0.3)。

### 运行命令

```bash
# 使用 run_18 数据
python run_batch_test.py \
  --model gemini-3-flash-preview-nothinking \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 3 \
  --num-batches 3 \
  --output-dir test_output/final_nonmm

# 或使用单任务模式
python run_experiment.py \
  --model gemini-3-flash-preview-nothinking \
  --task-files "generated_tasks_v2/run_18/tasks/attribute_comparison_mscoco14.jsonl" \
  --num-tasks 10 \
  --output-dir test_output/final_nonmm
```

### 验收标准
- [ ] 生成 `run_log_*.json` 文件
- [ ] 生成 `batch_results_*.json` 文件 (如果使用 batch 模式)
- [ ] 平均分数 < 0.3
- [ ] Faithfulness < 0.2

---

## Task 3-3: 运行多模态模型实验

**优先级**: P0 - 必须完成
**预计时间**: 1 day (包括运行时间)
**依赖**: Task 3-1
**可并行**: ✅ 可与 Task 3-2 并行

### 任务目标
运行多模态模型实验，预期得到高分 (> 0.6)。

### 运行命令

```bash
# 使用 run_18 数据
python run_batch_test.py \
  --model gpt-4o \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 3 \
  --num-batches 3 \
  --output-dir test_output/final_mm

# 或使用单任务模式
python run_experiment.py \
  --model gpt-4o \
  --task-files "generated_tasks_v2/run_18/tasks/attribute_comparison_mscoco14.jsonl" \
  --num-tasks 10 \
  --output-dir test_output/final_mm
```

### 验收标准
- [ ] 生成 `run_log_*.json` 文件
- [ ] 生成 `batch_results_*.json` 文件 (如果使用 batch 模式)
- [ ] 平均分数 > 0.6
- [ ] Faithfulness > 0.6
- [ ] 动作种类 >= 8

---

## Task 3-4: 运行所有验证脚本

**优先级**: P0 - 必须完成
**预计时间**: 0.5 day
**依赖**: Task 3-2, 3-3

### 任务目标
对所有实验结果运行验证脚本，确保所有指标达标。

### 运行命令

```bash
# 运行全部验证
python task/verify_all.py test_output

# 单独验证每个任务
python task/verify_task_1a.py test_output/final_mm/run_log_*.json
python task/verify_task_1d.py test_output/final_mm/batch_results_*.json
python task/verify_task_2a.py test_output/final_nonmm/run_log_*.json test_output/final_mm/run_log_*.json
python task/verify_task_2b.py test_output/final_mm/run_log_*.json
```

### 验收标准

#### Task 1A
- [ ] Parse errors = 0
- [ ] "Please continue" = 0
- [ ] "Failed to parse" = 0

#### Task 1B
- [ ] 平均视觉词汇/turn < 2.0

#### Task 1C
- [ ] 截断率 = 0%

#### Task 1D
- [ ] Batch results 有 turn details
- [ ] 覆盖率 = 100%
- [ ] 转换后无 placeholder

#### Task 2A
- [ ] 非多模态 avg < 0.3
- [ ] 多模态 avg > 0.6
- [ ] Score gap > 0.4

#### Task 2B
- [ ] 唯一动作 >= 8
- [ ] 最大占比 <= 40%

---

## Task 3-5: 生成最终报告

**优先级**: P0 - 必须完成
**预计时间**: 0.5 day
**依赖**: Task 3-4

### 任务目标
生成最终验证报告，总结所有指标和发现。

### 运行命令

```bash
python task/generate_report.py test_output task/round2/final_validation_report.md
```

### 报告内容

报告应包含：

1. **执行摘要**
   - 所有任务的通过/失败状态
   - 关键指标达标情况
   - 整体系统评估

2. **详细验证结果**
   - 每个任务的详细指标
   - Before/After 对比
   - 问题发现和解决方案

3. **数据可视化** (可选)
   - 动作分布图
   - 分数对比图
   - 时间序列图

4. **后续建议**
   - 性能优化建议
   - 扩展功能建议
   - 已知限制

### 验收标准
- [ ] 报告完整覆盖所有 6 个任务
- [ ] 包含所有关键指标
- [ ] 格式清晰，易于阅读
- [ ] 提供明确的通过/失败判断

---

## 可选任务 (如有时间)

### Optional 1: 补充 Task 1B/1C 验证脚本

创建标准化的 `verify_task_1b.py` 和 `verify_task_1c.py`。

### Optional 2: 性能和成本分析

分析实验的：
- Token 使用量
- API 调用次数
- 总成本估算
- 平均响应时间

### Optional 3: 自动化对比报告

生成 before/after 对比表格，展示：
- 各指标的改进幅度
- 问题解决数量
- 系统整体提升

---

## 风险与应对

### 风险 1: 实验运行时间过长

**缓解措施**:
- 先用小数据集测试 (num-tasks=3)
- 确认无误后再运行完整实验
- 使用 batch 模式提高效率

### 风险 2: 某些指标未达标

**应对方案**:
1. 检查日志，定位问题
2. 微调相关参数 (如 hint_level, llm_judge_weight)
3. 必要时回退代码，重新调试
4. 记录问题到报告的"后续建议"部分

### 风险 3: API 成本超预算

**应对方案**:
- 优先使用较便宜的模型 (gemini)
- 限制实验规模 (num-batches=3)
- 使用缓存避免重复调用

---

## 总时间估算

| 任务 | 时间 | 可并行 |
|------|------|-------|
| Task 3-1 | 0.5 day | - |
| Task 3-2 | 1 day | 与 3-3 并行 |
| Task 3-3 | 1 day | 与 3-2 并行 |
| Task 3-4 | 0.5 day | - |
| Task 3-5 | 0.5 day | - |

**总计**: 2.5 天 (并行) 或 3 天 (顺序)

---

## 成功标准

Round 2 完成的定义：

- [ ] 所有 6 个任务的验证脚本运行通过
- [ ] 生成完整的最终报告
- [ ] 所有关键指标达标
- [ ] 文档清晰，可复现

达成后，M3Bench 系统修复项目即告完成。
