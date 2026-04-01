# M3Bench 故障排查指南

## 常见问题和解决方案

### 1. "LLM judge call failed: 503" ✅ 已解决

**症状**：
```
WARNING - LLM judge call failed: 503
```

**原因**：
- 使用了错误的模型名称 `gpt_4o_image`

**解决方案**：
```powershell
# 设置正确的评估模型
$env:M3BENCH_EVAL_MODEL="gemini-2.5-flash-image-preview"
```

详见：[API_CONFIGURATION.md](API_CONFIGURATION.md)

---

### 2. "Failed to parse core model response as JSON" ⚠️ 当前问题

**症状**：
```
WARNING - Failed to parse core model response as JSON: Expecting value: line 1 column 1 (char 0)
INFO - Parse failed on attempt 1, retrying with explicit JSON instruction
WARNING - All 2 parse attempts failed, using fallback
```

**原因**：
某些模型（特别是 `gemini-3-pro-image-preview`）不稳定，经常返回非JSON格式的响应。

**解决方案**：

#### 方案A：换用Claude作为Core Model（推荐） ✅

```powershell
# Claude 对 JSON 格式的遵守非常好
$env:M3BENCH_CORE_MODEL="claude-3-5-sonnet-20241022-c"
```

**优点**：
- JSON 格式稳定
- 响应质量高
- 几乎不会出现解析错误

#### 方案B：使用GPT-4o

```powershell
$env:M3BENCH_CORE_MODEL="gpt-4o"
```

**优点**：
- JSON 格式稳定
- 支持 `response_format=json_object`（如果API支持）

#### 方案C：继续使用Gemini但接受偶尔的fallback

Gemini 偶尔会解析失败，但代码有 fallback 机制会自动处理。如果不介意看到警告，可以继续使用。

**影响**：
- 警告会出现但不影响运行
- Fallback 会使用基于规则的动作选择
- 整体测试仍然有效

---

### 3. 程序运行很慢

**症状**：
- 4个任务需要15分钟

**原因**：
- 使用了较强的模型
- 每轮3次API调用

**解决方案**：

详见：[PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)

快速方案：
```powershell
# 使用快速模型
$env:M3BENCH_CORE_MODEL="claude-3-5-sonnet-20241022-c"
$env:M3BENCH_EVAL_MODEL="claude-3-5-haiku-20241022-c"

# 或直接运行
.\run_fast_test.ps1
```

---

### 4. "Both content and reasoning_content are empty"

**症状**：
```
WARNING - Both content and reasoning_content are empty
```

**原因**：
- API 返回了空响应
- 可能是网络问题或API限流

**解决方案**：
1. 检查网络连接
2. 检查API配额和限流
3. 等待几秒后重试
4. 检查API key是否有效

---

### 5. "Image not found" 或图像路径错误

**症状**：
```
WARNING - Image not found: /path/to/image.jpg
```

**原因**：
- 图像路径不正确
- 图像文件不存在

**解决方案**：
1. 检查图像文件是否存在
2. 确认路径是绝对路径还是相对路径
3. 运行任务生成脚本确保图像已复制：
   ```bash
   python generate_all_tasks_v2.py
   ```

---

### 6. Timeout 错误

**症状**：
```
requests.exceptions.Timeout: ...
```

**原因**：
- 网络慢
- 图像太大
- API响应慢

**解决方案**：

```python
# 增加超时时间
from src.simulator import LLMClient

client = LLMClient(timeout=180)  # 3分钟超时
```

或在创建 Evaluator 时：
```python
evaluator = Evaluator(timeout=180)
```

---

## 推荐的稳定配置

### 配置1：最稳定（推荐用于生产）

```powershell
$env:M3BENCH_CORE_MODEL="claude-3-5-sonnet-20241022-c"
$env:M3BENCH_TARGET_MODEL="gemini-2.5-flash-image-preview"  # 你要测试的模型
$env:M3BENCH_EVAL_MODEL="claude-3-5-haiku-20241022-c"
```

**特点**：
- ✅ JSON解析稳定
- ✅ 速度快
- ✅ 成本低
- ✅ 几乎没有错误

### 配置2：全Claude（最稳定但成本稍高）

```powershell
$env:M3BENCH_CORE_MODEL="claude-3-5-sonnet-20241022-c"
$env:M3BENCH_TARGET_MODEL="claude-3-5-sonnet-20241022-c"
$env:M3BENCH_EVAL_MODEL="claude-3-5-haiku-20241022-c"
```

### 配置3：全GPT（如果你有OpenAI API）

```powershell
$env:M3BENCH_API_URL="https://api.openai.com/v1/chat/completions"
$env:M3BENCH_API_KEY="sk-your-openai-key"
$env:M3BENCH_CORE_MODEL="gpt-4o"
$env:M3BENCH_TARGET_MODEL="gpt-4o"
$env:M3BENCH_EVAL_MODEL="gpt-4o-mini"
```

---

## 模型兼容性表

| 模型 | JSON稳定性 | 图像支持 | 推荐用途 |
|------|-----------|---------|----------|
| claude-3-5-sonnet-20241022-c | ⭐⭐⭐⭐⭐ | ✅ | Core Model |
| claude-3-5-haiku-20241022-c | ⭐⭐⭐⭐⭐ | ✅ | Eval Model |
| gemini-2.5-flash-image-preview | ⭐⭐⭐⭐ | ✅ | Target/Eval |
| gemini-3-pro-image-preview | ⭐⭐ | ✅ | 不推荐作为Core |
| gpt-4o | ⭐⭐⭐⭐⭐ | ✅ | Core/Target |
| gpt-4o-mini | ⭐⭐⭐⭐ | ✅ | Eval Model |
| gpt-3.5-turbo | ⭐⭐⭐⭐⭐ | ❌ | 不支持图像 |

---

## 调试技巧

### 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

或在命令行：
```bash
python run_batch_test.py --verbose
```

### 查看完整的API响应

在 `src/simulator/strategic_simulator.py` 的 `_parse_core_response` 方法中添加：

```python
# 在第644行附近添加
if not text_to_parse:
    logger.warning("Both content and reasoning_content are empty")
    logger.debug(f"Full response: {content}")  # 添加这行
    logger.debug(f"Full reasoning: {reasoning_content}")  # 添加这行
```

### 测试单个模型

```python
from src.simulator import LLMClient

client = LLMClient(core_model="claude-3-5-sonnet-20241022-c")

# 测试
response = client.call_core_model([
    {"role": "user", "content": "Please respond with JSON: {\"action\": \"test\", \"message\": \"hello\"}"}
], max_tokens=100)

print(response)
```

---

## 获取帮助

如果问题仍未解决：

1. **查看日志文件** - 在 `simulator_test_log/` 目录
2. **检查API状态** - 访问你的API平台控制台
3. **测试API连接** - 运行 `python test_api_fix.py`
4. **查看文档** - [API_CONFIGURATION.md](API_CONFIGURATION.md)

---

**最后更新**: 2026-02-02
**版本**: v1.0
