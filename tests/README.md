# 测试脚本说明

这个目录包含3个独立的测试脚本，可以分别测试M3Bench的不同组件。

---

## 📁 文件清单

```
tests/
├── test_data_provider.py       # 测试数据加载
├── test_user_simulator.py      # 测试动作生成
└── test_end_to_end.py          # 测试完整流程
```

---

## 🎯 测试脚本功能

### 1. test_data_provider.py

**功能**: 测试数据加载和Scene Graph构建

**不需要**: VLM API

**输入**:
- `data/sample/` 目录（包含 images/, queries.json, scene_graphs.json）

**输出**:
- `output/data_provider_test.json` - 可供其他测试使用的任务列表

**用法**:
```bash
python tests/test_data_provider.py \
    --data_dir data/sample \
    --output output/data_provider_test.json \
    --split all \
    --max_tasks 10
```

### 2. test_user_simulator.py

**功能**: 测试动作选择和Prompt生成

**不需要**: VLM API（使用模拟回复）

**输入**:
- 任务JSON（可选，如果不提供则使用虚拟任务）

**输出**:
- `output/user_simulator_test.json` - 模拟的对话日志

**用法**:
```bash
# 方式1: 使用DataProvider的输出
python tests/test_user_simulator.py \
    --tasks_json output/data_provider_test.json \
    --max_turns 5 \
    --actions follow_up guidance update

# 方式2: 不依赖真实数据
python tests/test_user_simulator.py \
    --max_turns 5 \
    --actions follow_up negation mislead
```

### 3. test_end_to_end.py

**功能**: 测试完整流程（DataProvider + UserSimulator + VLM）

**需要**: VLM API

**输入**:
- 配置文件 `configs/test_config.yaml`（包含API配置）

**输出**:
- `output/end_to_end_test.json` - 完整的对话日志

**用法**:
```bash
python tests/test_end_to_end.py \
    --config configs/test_config.yaml \
    --verbose
```

---

## 🔄 测试流程建议

### 推荐顺序

```
1. test_data_provider.py
   ↓ (生成 data_provider_test.json)
2. test_user_simulator.py
   ↓ (验证动作生成逻辑)
3. test_end_to_end.py
   (测试与真实VLM的交互)
```

### 快速验证流程

```bash
# Step 1: 测试数据加载
python tests/test_data_provider.py --data_dir data/sample --output output/test.json

# Step 2: 测试动作生成
python tests/test_user_simulator.py --tasks_json output/test.json --max_turns 3

# Step 3: 端到端测试（需要API key）
python tests/test_end_to_end.py --config configs/test_config.yaml
```

---

## ⚙️ 命令行参数详解

### test_data_provider.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--data_dir` | 数据目录路径 | 必需 |
| `--output` | 输出JSON文件路径 | output/data_provider_test.json |
| `--split` | 数据划分 (all/train/test) | all |
| `--max_tasks` | 最多加载任务数 | None (全部) |

### test_user_simulator.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--tasks_json` | 任务JSON文件路径 | None (使用虚拟任务) |
| `--max_turns` | 最大对话轮次 | 5 |
| `--actions` | 允许的动作列表 | None (全部动作) |
| `--output` | 输出日志文件路径 | output/user_simulator_test.json |

### test_end_to_end.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config` | 配置文件路径 | 必需 |
| `--verbose` | 是否打印详细信息 | False |

---

## 📝 配置文件说明

`configs/test_config.yaml` 的结构：

```yaml
# 数据配置
data_dir: "data/sample"          # 或使用 tasks_json
max_tasks: 5

# VLM配置
vlm:
  api_type: "openai"             # 或 "custom"
  api_url: "..."                 # API地址
  api_key: "..."                 # API密钥
  model: "gpt-4-vision-preview"
  max_tokens: 500
  temperature: 0.7

# 测试配置
max_turns: 5                     # 每个episode的轮次
num_episodes: 2                  # 测试多少个任务
allowed_actions: [...]           # 允许的动作（可选）
output: "output/..."             # 输出路径
```

---

## 🎯 自定义和扩展

### 修改动作策略

编辑 `test_user_simulator.py` 中的 `SimpleUserSimulator.select_action()`:

```python
def select_action(self, turn, vlm_response, task, history):
    # 自定义你的策略
    if "错误" in vlm_response:
        return "negation"
    elif turn < 3:
        return "follow_up"
    else:
        return "update"
```

### 添加新动作

在 `SimpleUserSimulator.templates` 中添加：

```python
self.templates = {
    # 已有动作...
    'my_action': [
        "模板1: {param}",
        "模板2: {param}"
    ]
}
```

### 支持新的VLM API

编辑 `test_end_to_end.py` 中的 `VLMClient._call_custom_api()`:

```python
def _call_custom_api(self, messages, image_path=None):
    # 根据你的API格式实现
    response = requests.post(...)
    return response.json()['answer']
```

---

## 📊 输出文件格式

### data_provider_test.json

```json
{
  "metadata": {"total_tasks": 3, ...},
  "tasks": [
    {
      "task_id": "sample_001",
      "image_path": "...",
      "question": "...",
      "scene_graph": {...}
    }
  ]
}
```

### user_simulator_test.json

```json
{
  "task": {...},
  "turns": [
    {
      "turn": 0,
      "action": "follow_up",
      "user_query": "...",
      "vlm_response": "..."
    }
  ]
}
```

### end_to_end_test.json

```json
{
  "config": {...},
  "episodes": [
    {
      "task": {...},
      "turns": [...]
    }
  ]
}
```

---

## 🐛 故障排除

### ImportError

**问题**: 无法导入模块

**解决**: 确保在项目根目录运行：
```bash
cd /path/to/M3Bench
python tests/test_*.py
```

### API调用失败

**问题**: `[API Error: 401]`

**解决**:
1. 检查 `api_key` 是否正确
2. 检查 `api_url` 是否正确
3. 检查网络连接

### 图片加载失败

**问题**: `Image not found`

**解决**:
1. 确保图片在 `data/sample/images/`
2. 检查 `queries.json` 中的文件名是否正确

---

更多详细说明请参考：
- **快速开始**: `../QUICKSTART.md`
- **详细教程**: `../README_TESTS.md`
- **完整文档**: `../PROJECT_ARCHITECTURE.md`
