# M3Bench 实验系统使用指南

## 系统架构

```
数据生成 → 模型测试 → 日志解析 → 结果聚合 → 可视化
    ↓           ↓           ↓           ↓           ↓
generate   run_batch   log_parser  result_agg  visualizer
```

## 完整工作流程

### 第一步：生成任务数据（可选）

如果 `generated_tasks_v2/run_18/` 中的任务不够，可以生成更多：

```bash
python generate_all_tasks_v2.py --datasets mscoco14 vcr --num-samples 30 --split val
```

**支持的数据集**:
- mscoco14
- vcr
- scienceqa (需要配置)
- docvqa (需要配置)
- realworldqa (需要配置)

**支持的任务类型**:
- attribute_bridge_reasoning (ABR)
- attribute_comparison (AC)
- relation_comparison (RC)
- visual_noise_filtering (VNF)
- rationale_based_abr (VCR专用)

### 第二步：运行模型测试

#### 方式1：单个模型测试

```bash
python run_batch_test.py \
  --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
  --tasks-per-batch 4 \
  --num-batches 8 \
  --max-turns-per-session 40 \
  --min-turns-per-task 20 \
  --max-turns-per-task 35 \
  --model "gpt-5"
```

**参数说明**:
- `--tasks-per-batch`: 每个session测试几个任务
- `--num-batches`: 运行几个batch
- `--max-turns-per-session`: session最大轮数
- `--min-turns-per-task`: 每个任务至少多少轮
- `--max-turns-per-task`: 每个任务最多多少轮
- `--model`: 模型名称（用于日志命名）

**模型配置**:

API配置在 `src/simulator/llm_client.py` 中：
```python
DEFAULT_API_URL = "https://globalai.vip/v1/chat/completions"
DEFAULT_API_KEY = "sk-PcyvuAqtt0yHsP88Mga584zkJIeP7VrSC2l4QOaK0wGpSx3R"
DEFAULT_CORE_MODEL = "gpt-5.2"  # 用于生成问题
DEFAULT_TARGET_MODEL = "gpt-5-mini"  # 被测试的模型
```

也可以通过环境变量设置：
```bash
export M3BENCH_API_URL="https://your-api-endpoint.com/v1/chat/completions"
export M3BENCH_API_KEY="your-api-key"
export M3BENCH_CORE_MODEL="gpt-5.2"
export M3BENCH_TARGET_MODEL="gpt-5"
```

#### 方式2：多模型批量测试

```bash
python run_batch_test_multi_model.py \
  --models gpt-5 gemini-2.5-pro gemini-2.5-flash kimi-k2.5 \
  --tasks-per-batch 4 \
  --num-batches 8 \
  --max-turns 40
```

**注意**: 需要修改 `llm_client.py` 中的 `DEFAULT_TARGET_MODEL` 或者在代码中添加模型映射逻辑。

### 第三步：分析日志

#### 单模型分析

```bash
python run_analysis.py \
  --log-dir "simulator_test_log/batch_run_YYYYMMDD_HHMMSS" \
  --model-name "gpt-5" \
  --output-dir "experiment_results/gpt-5"
```

输出：
- `aggregated_results.json` - 完整的结构化数据
- `analysis_report.txt` - 文本报告
- `visualizations/` - 6个图表

#### 多模型对比分析

```bash
python run_multi_model_comparison.py
```

这会：
1. 为每个模型运行分析
2. 生成多模型对比图表
3. 保存到 `experiment_results/multi_model_comparison/`

### 第四步：查看结果

生成的图表：
1. **01_radar_chart.png** - 雷达图（7维度）
2. **02_bar_chart.png** - 柱状图（总分）
3. **03_turn_progression.png** - 折线图（性能衰减）
4. **04_lag_analysis.png** - Lag分析（记忆保持）
5. **05_error_distribution.png** - 错误分布
6. **06_comparison_table.png** - 对比表格

## 图表说明

### 雷达图
- **用途**: 多维度能力概览
- **维度**: Overall, Faithfulness, Robustness, Consistency, Memory, Image Confusion, Disambiguation
- **解读**: 面积越大，能力越强

### 柱状图
- **用途**: 总分对比
- **X轴**: 模型名称
- **Y轴**: 平均分
- **解读**: 柱子越高，性能越好

### 折线图
- **用途**: 性能随轮次变化
- **X轴**: Turn编号（1-30+）
- **Y轴**: 平均分
- **解读**:
  - 上升趋势 = 性能提升
  - 下降趋势 = 性能衰减（记忆丢失）
  - 平稳 = 性能稳定

### Lag分析图
- **左图**: 分数 + 置信区间
  - 蓝色线：平均分
  - 阴影：标准差范围
- **右图**: 相关系数
  - 正数：性能随轮次提升
  - 负数：性能随轮次下降
  - 接近0：无关联

### 错误分布图
- **左图**: 错误类型统计
- **中图**: 各阶段错误数
- **右图**: 各动作类型错误数
- **解读**: 哪里出错最多

### 对比表格
- **行**: 评分维度
- **列**: 模型名称
- **格式**: 平均分 ± 标准差

## API配置说明

### 当前配置
```python
API_URL = "https://globalai.vip/v1/chat/completions"
API_KEY = "sk-PcyvuAqtt0yHsP88Mga584zkJIeP7VrSC2l4QOaK0wGpSx3R"
```

### 支持的模型名称

根据API，可能支持：
- gpt-5, gpt-5.2, gpt-5-mini
- gemini-2.5-pro, gemini-2.5-flash
- kimi-k2.5
- 等等

### 如何修改模型

编辑 `src/simulator/llm_client.py`:

```python
# 第38-40行
DEFAULT_CORE_MODEL = "gpt-5.2"        # 改为你想用的模型
DEFAULT_TARGET_MODEL = "gpt-5-mini"   # 改为被测试的模型
```

或者使用环境变量：
```bash
export M3BENCH_TARGET_MODEL="gemini-2.5-pro"
python run_batch_test.py --model "gemini-2.5-pro"
```

## 常见问题

### Q1: 日志保存在哪里？
A: `simulator_test_log/batch_run_YYYYMMDD_HHMMSS/`

### Q2: 如何增加轮数？
A: 修改参数：
```bash
--max-turns-per-session 50 --max-turns-per-task 40
```

### Q3: 如何只测试特定任务类型？
A: 指定任务文件：
```bash
--task-files "generated_tasks_v2/run_18/tasks/attribute_comparison_*.jsonl"
```

### Q4: 错误：ModuleNotFoundError
A: 确保在项目根目录运行，或安装依赖：
```bash
pip install numpy matplotlib
```

### Q5: API调用失败
A: 检查：
1. API Key是否有效
2. API URL是否正确
3. 模型名称是否正确
4. 网络连接是否正常

### Q6: 如何添加Phase分隔线？
A: 编辑 `analysis/visualizer.py` 的 `plot_turn_progression` 函数：

```python
# 添加在绘图后
ax.axvline(x=5, linestyle='--', color='gray', alpha=0.5, label='Phase 1→2')
ax.axvline(x=10, linestyle='--', color='gray', alpha=0.5, label='Phase 2→3')
ax.axvline(x=15, linestyle='--', color='gray', alpha=0.5, label='Phase 3→4')
```

### Q7: 如何导出LaTeX表格？
A: 从 `aggregated_results.json` 手动生成，或使用pandas：

```python
import pandas as pd
import json

with open('aggregated_results.json') as f:
    data = json.load(f)

# 提取数据...
df = pd.DataFrame(data)
print(df.to_latex())
```

## 文件说明

### 核心文件
- `run_batch_test.py` - 批处理测试（单模型）
- `run_batch_test_multi_model.py` - 多模型测试
- `run_analysis.py` - 单模型分析
- `run_multi_model_comparison.py` - 多模型对比

### 分析模块
- `analysis/log_parser.py` - 日志解析
- `analysis/result_aggregator.py` - 结果聚合
- `analysis/visualizer.py` - 可视化
- `analysis/data_structures.py` - 数据结构

### 辅助工具
- `generate_mock_test_data.py` - 生成模拟数据（测试用）
- `generate_all_tasks_v2.py` - 生成任务数据

## 性能优化

### 减少API调用
- 减少 `--num-batches`
- 减少 `--tasks-per-batch`
- 减少 `--max-turns-per-task`

### 加快测试速度
- 使用更快的模型（如 gpt-5-mini）
- 减少任务数量
- 并行运行多个模型（需要多个进程）

### 节省成本
- 使用 `--max-tasks` 限制任务数
- 使用缓存（如果API支持）
- 使用免费的API（如有）

## 总结

完整流程：
```bash
# 1. 生成任务（如需要）
python generate_all_tasks_v2.py --num-samples 30

# 2. 运行测试
python run_batch_test.py --model "gpt-5" --num-batches 8 --max-turns-per-task 35

# 3. 分析结果
python run_analysis.py --log-dir "simulator_test_log/batch_run_XXX" --model-name "gpt-5"

# 4. 多模型对比（重复步骤2-3多次，然后运行）
python run_multi_model_comparison.py
```

现在你有了一个完整的、可工作的实验分析系统！
