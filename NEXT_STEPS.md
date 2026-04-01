# M3Bench 实验完整工作流程指南

## 📌 当前状态

✅ **已完成**:
- 核心分析模块开发完成
- 6个论文级图表生成器实现
- 4个模型的模拟数据分析完成
- 完整的使用文档编写

⏳ **进行中**:
- 真实API测试运行中（后台进程）

## 🚀 下一步操作

### 方案A：使用已生成的模拟数据（立即可用）

如果你想**立即看到完整的多模型对比效果**，使用模拟数据：

```bash
# 直接生成多模型对比图表
python run_multi_model_comparison.py
```

**优点**:
- 立即得到结果
- 4个模型的完整对比
- 30+轮对话的完整数据
- 可以看到所有图表的完整效果

**缺点**:
- 数据是模拟的，不是真实API调用

**结果位置**: `experiment_results/multi_model_comparison/`

---

### 方案B：使用真实API（需要等待）

如果你想用真实API生成数据：

#### 步骤1：检查API测试状态
```bash
# 查看后台测试进度
tail -f /tmp/claude/e--Code-M3Bench-M3Bench-new/tasks/be7056f.output

# 或查看生成的日志
ls -lh simulator_test_log/batch_run_gpt-5_*/
```

#### 步骤2：为其他模型运行测试

**修改模型配置**（`src/simulator/llm_client.py` 第38-40行）:

```python
# 修改为要测试的模型
DEFAULT_CORE_MODEL = "gpt-5.2"          # 用于生成问题（保持不变）
DEFAULT_TARGET_MODEL = "gemini-2.5-pro" # 改为被测试的模型
```

然后运行：
```bash
python run_batch_test.py \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 3 \
  --num-batches 5 \
  --max-turns-per-session 35 \
  --min-turns-per-task 20 \
  --max-turns-per-task 30 \
  --model "gemini-2.5-pro"
```

#### 步骤3：分析结果

```bash
# 分析gpt-5结果
python run_analysis.py \
  --log-dir "simulator_test_log/batch_run_gpt-5_YYYYMMDD_HHMMSS" \
  --model-name "gpt-5" \
  --output-dir "experiment_results/models/gpt-5"

# 分析gemini-2.5-pro结果
python run_analysis.py \
  --log-dir "simulator_test_log/batch_run_gemini-2.5-pro_YYYYMMDD_HHMMSS" \
  --model-name "gemini-2.5-pro" \
  --output-dir "experiment_results/models/gemini-2.5-pro"

# 对其他模型重复...
```

#### 步骤4：生成多模型对比

```bash
python run_multi_model_comparison.py
```

---

## 📊 预期输出

### 单个模型分析输出
```
experiment_results/models/{model_name}/
├── aggregated_results.json      # 结构化数据
├── analysis_report.txt          # 文本报告
└── visualizations/
    ├── 01_radar_chart.png
    ├── 02_bar_chart.png
    ├── 03_turn_progression.png
    ├── 04_lag_analysis.png
    ├── 05_error_distribution.png
    └── 06_comparison_table.png
```

### 多模型对比输出
```
experiment_results/multi_model_comparison/
├── 01_radar_chart.png           # 4个模型的雷达图
├── 02_bar_chart.png             # 4个柱子
├── 03_turn_progression.png      # 4条线（30+轮）
├── 04_lag_analysis.png          # 4个模型的Lag对比
├── 05_error_distribution.png    # 错误分布
└── 06_comparison_table.png      # 详细对比表格
```

---

## 🎯 建议方案

**我推荐**：

### 快速演示（5分钟）
```bash
# 已经完成了，图表就在这里
experiment_results/multi_model_comparison/
```

### 完整实验（30分钟-2小时）

1. **收集真实API数据**
```bash
# 循环运行每个模型
for model in "gpt-5" "gemini-2.5-pro" "gemini-2.5-flash" "kimi-k2.5"; do
  # 修改 llm_client.py 中的 DEFAULT_TARGET_MODEL = model
  python run_batch_test.py --model "$model" --num-batches 5
done
```

2. **分析所有模型**
```bash
python run_multi_model_comparison.py
```

3. **查看结果**
```bash
experiment_results/multi_model_comparison/
experiment_results/models/*/analysis_report.txt
```

---

## 📋 核心命令速查

### 生成任务（如需要更多数据）
```bash
python generate_all_tasks_v2.py --datasets mscoco14 vcr --num-samples 30
```

### 运行单个模型测试
```bash
python run_batch_test.py --model "gpt-5" --num-batches 5 --max-turns-per-task 35
```

### 分析单个模型
```bash
python run_analysis.py --log-dir "simulator_test_log/batch_run_XXX" --model-name "gpt-5"
```

### 多模型对比
```bash
python run_multi_model_comparison.py
```

---

## ⚙️ 参数优化建议

### 如果API调用速度慢
```bash
--num-batches 3      # 减少批次
--tasks-per-batch 2  # 减少每批任务数
```

### 如果想要更详细的数据
```bash
--max-turns-per-task 40  # 增加轮数
--tasks-per-batch 5      # 增加每批任务数
--num-batches 10         # 增加批次数
```

### 如果只想快速测试
```bash
--max-turns-per-session 30  # 减少session长度
--max-turns-per-task 20     # 减少每个任务的轮数
--num-batches 2             # 只运行2个批次
```

---

## 🔍 故障排查

### 问题：API连接失败
**解决**:
1. 检查API URL和KEY是否正确
2. 检查网络连接
3. 检查模型名称是否支持

### 问题：内存不足
**解决**:
- 减少 `--tasks-per-batch`
- 减少 `--max-turns-per-task`
- 分次运行，而不是一次性运行所有batch

### 问题：图表显示不完整
**解决**:
- 删除旧的visualizations目录
- 重新运行分析
- 确保有足够的数据（至少10个任务）

---

## 📝 论文中使用结果

### 如何引用图表

**Figure 1**: Radar chart showing multi-dimensional performance comparison across 4 models.

**Figure 2**: Overall score comparison. Error bars represent standard deviation.

**Figure 3**: Performance degradation across conversation turns, showing memory retention challenges.

**Figure 4**: Lag analysis - left: score progression with confidence intervals; right: correlation with turn number.

**Figure 5**: Error distribution analysis across (a) error types, (b) conversation phases, and (c) action types.

**Table 1**: Detailed performance comparison across 7 evaluation dimensions.

### 如何生成LaTeX表格

```python
# 从 aggregated_results.json 提取数据
import json
import pandas as pd

with open('experiment_results/models/gpt-5/aggregated_results.json') as f:
    data = json.load(f)

# 提取统计数据
dimensions = ['score', 'faithfulness', 'robustness', 'consistency',
              'memory_retention', 'cross_image_confusion', 'disambiguation']

for dim in dimensions:
    mean = data['statistics']['score_stats'][dim]['mean']
    std = data['statistics']['score_stats'][dim]['std']
    print(f"{dim.ljust(25)} & {mean:.3f}±{std:.3f}")
```

---

## 🎓 总结

你现在有了一个**完整的、可用于论文的实验系统**：

✅ 支持任意数量的模型
✅ 支持30+轮的长对话
✅ 生成6个论文级图表
✅ 自动计算7个评分维度
✅ 完整的多模型对比

**立即开始**: 选择方案A（模拟数据）或方案B（真实API），然后运行：
```bash
python run_multi_model_comparison.py
```

结果就在 `experiment_results/multi_model_comparison/`

需要帮助吗？
