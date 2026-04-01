# Task 3: 全系统端到端验证

## 任务优先级
**Week 3 Day 1-5** (所有Task 1-2完成后)

## 顺序执行
❌ **不可并行** - 需要所有前置任务完成

## 任务目标
验证所有修复有效,确保系统整体达标。

---

## 验证清单

### 1. 对话质量验证
- [ ] "Please continue" = 0
- [ ] "Failed to parse" = 0
- [ ] 无截断响应
- [ ] 动作多样性 >= 8种

### 2. 评估准确性验证
- [ ] 非多模态模型 avg_score < 0.3
- [ ] 多模态模型 avg_score > 0.6
- [ ] Score gap > 0.4

### 3. Batch集成验证
- [ ] Batch results有turn details
- [ ] 转换后无placeholder
- [ ] run_18数据可用

---

## 验证脚本

创建 `task/verify_all.py`:

```python
import subprocess
import sys

def run_verification():
    """Run all verification scripts."""
    tests = [
        ("Task 1A", "python task/verify_task_1a.py test_output/final/run_log_*.json"),
        ("Task 1D", "python task/verify_task_1d.py test_output/final/batch_results_*.json"),
        ("Task 2A", "python task/verify_task_2a.py test_output/final/run_log_*.json"),
        ("Task 2B", "python task/verify_task_2b.py test_output/final/run_log_*.json"),
    ]

    results = {}
    for name, cmd in tests:
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print('='*60)
        result = subprocess.run(cmd, shell=True)
        results[name] = result.returncode == 0

    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print('='*60)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    return all_passed

if __name__ == "__main__":
    passed = run_verification()
    sys.exit(0 if passed else 1)
```

---

## 运行流程

### Step 1: 生成测试数据
```bash
# Non-multimodal baseline
python run_batch_test.py \
  --model gemini-3-flash-preview-nothinking \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 3 \
  --num-batches 3 \
  --output-dir test_output/final_nonmm

# Multimodal test
python run_batch_test.py \
  --model gpt-4o \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 3 \
  --num-batches 3 \
  --output-dir test_output/final_mm
```

### Step 2: 运行验证
```bash
python task/verify_all.py
```

### Step 3: 生成报告
创建 `task/generate_report.py` 生成markdown报告,包含:
- 所有指标的before/after对比
- 每个任务的完成状态
- 遇到的问题和解决方案

---

## 预期工作量
- **验证脚本整合**: ~100 lines
- **测试运行**: 8 hours
- **报告生成**: 4 hours
- **总时间**: 2 days
