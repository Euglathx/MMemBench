# M3Bench 批量对话生成指南

## 概述

本指南说明如何使用批量对话生成工具从离线任务数据生成大量在线对话样本。

## 快速开始

### 方案A: 使用批量运行脚本（推荐）

**Windows:**
```bash
batch_run.bat
```

**Linux/Mac:**
```bash
chmod +x batch_run.sh
./batch_run.sh
```

### 方案B: 直接使用Python脚本

```bash
# 步骤1: 生成更多离线任务（如果需要）
python generate_all_tasks_v2.py --num-samples 100

# 步骤2: 批量生成对话
python tests/batch_test_user_simulator.py \
    --num-tasks 100 \
    --max-turns 30 \
    --min-turns 20 \
    --task-dir generated_tasks_v2/run_13 \
    --output-dir simulator_test_log \
    --batch-size 10
```

## 命令行参数

### batch_test_user_simulator.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--num-tasks` | 100 | 要生成的对话数量 |
| `--max-turns` | 30 | 每个对话的最大轮次 |
| `--min-turns` | 20 | 每个对话的最小轮次 |
| `--task-dir` | generated_tasks_v2/run_12 | 任务文件目录 |
| `--output-dir` | simulator_test_log | 输出目录 |
| `--batch-size` | 10 | 每N个任务保存一次进度 |
| `--task-types` | 全部 | 指定任务类型（可选） |
| `--max-retries` | 3 | 每个任务的最大重试次数 |
| `--verbose` | False | 打印详细日志 |

## 使用示例

### 示例1: 小规模测试（5个对话）

```bash
python tests/batch_test_user_simulator.py \
    --num-tasks 5 \
    --max-turns 25 \
    --min-turns 20
```

### 示例2: 标准批量生成（100个对话）

```bash
python tests/batch_test_user_simulator.py \
    --num-tasks 100 \
    --max-turns 30 \
    --min-turns 20 \
    --task-dir generated_tasks_v2/run_13
```

### 示例3: 只生成特定类型的对话

```bash
python tests/batch_test_user_simulator.py \
    --num-tasks 50 \
    --task-types attribute_comparison visual_noise_filtering
```

### 示例4: 大规模生成（500个对话）

```bash
python tests/batch_test_user_simulator.py \
    --num-tasks 500 \
    --max-turns 30 \
    --batch-size 20 \
    --output-dir simulator_logs_large_scale
```

## 输出文件

生成完成后，会在输出目录中创建以下文件：

```
simulator_test_log/
├── run_log_YYYYMMDD_HHMMSS.json       # 详细对话日志
├── memory_state_YYYYMMDD_HHMMSS.json  # 记忆状态
├── summary_YYYYMMDD_HHMMSS.json       # 对话摘要
├── batch_statistics.json              # 批量统计报告
└── batch_progress.json                # 进度跟踪文件
```

### batch_statistics.json 示例

```json
{
  "batch_id": "batch_20260119_001",
  "total_conversations": 100,
  "successful": 98,
  "failed": 2,
  "success_rate": 0.98,
  "task_type_distribution": {
    "attribute_comparison": 35,
    "visual_noise_filtering": 30,
    "attribute_bridge_reasoning": 20,
    "relation_comparison": 15
  },
  "average_turns": 23.5,
  "total_tokens_used": 2450000,
  "estimated_cost_usd": 12.25,
  "duration_seconds": 3600
}
```

## 验证结果

### 检查生成的对话数量

```bash
# Linux/Mac
find simulator_test_log -name "run_log_*.json" | wc -l

# Windows
dir simulator_test_log\run_log_*.json /b | find /c /v ""
```

### 查看统计报告

```bash
# Linux/Mac
cat simulator_test_log/batch_statistics.json | python -m json.tool

# Windows
type simulator_test_log\batch_statistics.json | python -m json.tool
```

### 检查总大小

```bash
# Linux/Mac
du -sh simulator_test_log/

# Windows
dir simulator_test_log /s
```

## 成本估算

基于平衡模式（20-30轮/对话）：

| 对话数量 | 预计Token数 | 估算成本（Gemini API） | 预计时间 |
|---------|------------|---------------------|---------|
| 5 | 100K-225K | $0.50-$1.10 | 2-5分钟 |
| 100 | 2M-4.5M | $10-$22 | 50-100分钟 |
| 500 | 10M-22.5M | $50-$110 | 4-8小时 |
| 1000 | 20M-45M | $100-$225 | 8-16小时 |

**注意**: 实际成本取决于API定价和对话复杂度。

## 故障排除

### 问题1: API连接失败

**错误**: `API connection failed!`

**解决方案**:
1. 检查 `src/simulator/llm_client.py` 中的API配置
2. 确认API密钥有效
3. 检查网络连接

### 问题2: 任务文件未找到

**错误**: `No tasks found!`

**解决方案**:
1. 确认任务目录存在：`ls generated_tasks_v2/run_12/tasks/`
2. 如果不存在，运行：`python generate_all_tasks_v2.py --num-samples 100`

### 问题3: 生成中断

**解决方案**:
- 进度已自动保存在 `batch_progress.json`
- 重新运行脚本会跳过已完成的任务（如果实现了恢复功能）
- 或者手动调整 `--num-tasks` 参数继续生成

### 问题4: 内存不足

**解决方案**:
- 减小 `--batch-size` 参数
- 减少 `--num-tasks` 参数
- 分批次运行

## 高级用法

### 自定义模拟器配置

编辑 `src/simulator/llm_user_simulator.py` 中的参数：

```python
simulator = LLMUserSimulator(
    llm_client=client,
    max_turns_per_task=30,
    min_turns_per_task=20,
    enable_filler_injection=True,
    filler_interval=5,
    enable_consistency_check=True
)
```

### 并行生成（实验性）

```bash
# 启动多个进程，每个生成不同的任务类型
python tests/batch_test_user_simulator.py --num-tasks 25 --task-types attribute_comparison &
python tests/batch_test_user_simulator.py --num-tasks 25 --task-types visual_noise_filtering &
python tests/batch_test_user_simulator.py --num-tasks 25 --task-types attribute_bridge_reasoning &
python tests/batch_test_user_simulator.py --num-tasks 25 --task-types relation_comparison &
```

**注意**: 并行运行时注意API速率限制。

## 相关文件

- `tests/batch_test_user_simulator.py` - 批量对话生成脚本
- `tests/test_user_simulator.py` - 原始测试脚本
- `src/simulator/llm_user_simulator.py` - 用户模拟器核心
- `src/simulator/llm_client.py` - LLM客户端
- `generate_all_tasks_v2.py` - 离线任务生成脚本
- `batch_run.sh` / `batch_run.bat` - 批量运行脚本

## 更多信息

详细的实现计划和架构说明，请参考：
- 计划文件: `C:\Users\16979\.claude\plans\iridescent-soaring-robin.md`
- 项目文档: `README.md`

## 联系方式

如有问题或建议，请提交Issue或联系项目维护者。
