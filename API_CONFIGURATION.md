# M3Bench API 配置说明

## 问题诊断: 503 Service Unavailable 错误

503错误通常出现在两个地方：

### 1. LLM Judge 调用失败（最常见）

**症状**：日志显示 "LLM judge call failed: 503"

**原因**：
- **错误的模型名称** - 原代码默认使用 `gpt_4o_image`，这个模型名在某些API平台上不存在
- **图像过大** - LLM Judge 也需要发送图像进行评估
- **请求体过大** - 包含长文本提示 + 多张图像

**解决方案**：
1. **设置正确的模型** - 通过环境变量 `M3BENCH_EVAL_MODEL` 设置与你的API兼容的模型
2. **使用与 TARGET_MODEL 相同的模型** - 现已自动默认使用与 TARGET_MODEL 相同的模型

### 2. 图像传输失败

**症状**：日志显示 "Target model attempt X failed"

**原因**：
1. **图像过大** - 多张高分辨率图像编码后的请求体超过API限制
2. **请求体超限** - 某些API网关对请求体大小有限制（如10MB、20MB）
3. **超时** - 上传大图像需要更长时间
4. **服务器限流** - 短时间内发送过多大请求

## 解决方案

### 1. 已自动优化的功能 (v最新版)

本项目已在 `src/simulator/llm_client.py` 中添加了以下优化：

- ✅ **自动图像压缩**: 超过5MB的图像会自动压缩
- ✅ **请求体大小监控**: 记录payload大小到日志
- ✅ **详细错误日志**: 503错误时显示可能的原因
- ✅ **支持环境变量配置**: 可通过环境变量设置API参数

### 2. 环境变量配置 (推荐)

你可以通过环境变量配置API参数，而不需要修改代码：

#### Windows (PowerShell):
```powershell
$env:M3BENCH_API_URL="https://globalai.vip/v1/chat/completions"
$env:M3BENCH_API_KEY="sk-你的API密钥"
$env:M3BENCH_CORE_MODEL="gemini-3-pro-image-preview"
$env:M3BENCH_TARGET_MODEL="gemini-2.5-flash-image-preview"
$env:M3BENCH_EVAL_MODEL="gemini-2.5-flash-image-preview"  # LLM Judge 模型（可选，默认与 TARGET_MODEL 相同）
```

#### Windows (CMD):
```cmd
set M3BENCH_API_URL=https://globalai.vip/v1/chat/completions
set M3BENCH_API_KEY=sk-你的API密钥
set M3BENCH_CORE_MODEL=gemini-3-pro-image-preview
set M3BENCH_TARGET_MODEL=gemini-2.5-flash-image-preview
set M3BENCH_EVAL_MODEL=gemini-2.5-flash-image-preview
```

#### Linux/Mac:
```bash
export M3BENCH_API_URL="https://globalai.vip/v1/chat/completions"
export M3BENCH_API_KEY="sk-你的API密钥"
export M3BENCH_CORE_MODEL="gemini-3-pro-image-preview"
export M3BENCH_TARGET_MODEL="gemini-2.5-flash-image-preview"
export M3BENCH_EVAL_MODEL="gemini-2.5-flash-image-preview"
```

**重要提示**：如果你看到 "LLM judge call failed: 503" 错误，很可能是 `M3BENCH_EVAL_MODEL` 的模型名称在你的API平台上不存在。请确保设置了正确的模型名称。

### 3. 代码中直接配置

如果不想使用环境变量，也可以在创建LLMClient时直接传参：

```python
from src.simulator import LLMClient

client = LLMClient(
    api_url="https://globalai.vip/v1/chat/completions",
    api_key="sk-你的API密钥",
    core_model="gemini-3-pro-image-preview",
    target_model="gemini-2.5-flash-image-preview",
    timeout=120  # 增加超时时间到120秒
)
```

### 4. 调整图像大小限制

如果仍然遇到503错误，可以降低图像大小限制。修改 `src/simulator/llm_client.py` 中的默认值：

```python
# 在 _encode_image 方法中
def _encode_image(self, image_path: str, max_size_mb: float = 3.0):  # 从5.0改为3.0
    ...
```

### 5. 增加超时时间

如果是网络慢导致的超时，可以增加timeout参数：

```python
client = LLMClient(timeout=180)  # 3分钟超时
```

## 调试技巧

### 查看日志

运行时会输出详细日志，包括：
- Payload大小
- 图像压缩信息
- 具体的API错误响应

```python
import logging
logging.basicConfig(level=logging.DEBUG)  # 启用DEBUG级别日志
```

### 检查图像大小

在发送请求前检查图像大小：

```bash
# Windows
dir /s images\*.jpg

# Linux/Mac
find images -name "*.jpg" -exec ls -lh {} \;
```

### 测试连接

使用内置的测试功能：

```python
from src.simulator import LLMClient

client = LLMClient()
results = client.test_connection()
print(f"Core model: {'OK' if results['core_model'] else 'FAILED'}")
print(f"Target model: {'OK' if results['target_model'] else 'FAILED'}")
```

## 依赖安装

图像压缩功能需要 Pillow 库：

```bash
pip install Pillow
```

如果没有安装Pillow，遇到大图像时会跳过该图像并记录警告。

## 常见问题

### Q: 我的API key可以正常对话，为什么传图像就503?

A: 这是因为图像编码成base64后会显著增大请求体。例如一张5MB的图片，base64编码后会变成约6.6MB，多张图片会快速超过API限制。

### Q: 自动压缩后还是503怎么办?

A: 尝试以下方案：
1. 减少每次发送的图像数量
2. 降低 `max_size_mb` 参数 (如改为2.0或3.0)
3. 检查你的API服务商的具体限制
4. 联系API服务商确认payload限制

### Q: 如何知道我的API有payload限制?

A: 查看日志中的警告信息：
```
WARNING - Large payload detected: 12.34MB. This may cause API errors.
```

如果看到这个警告并且遇到503，说明很可能是payload过大。

### Q: 压缩会影响测试结果吗?

A: 理论上可能有轻微影响，但：
- 压缩使用高质量算法 (LANCZOS resize, 85% JPEG quality)
- 只在必要时压缩（超过5MB）
- 对于VLM测试，轻微的质量损失通常不会显著影响结果

如果担心影响，可以：
1. 使用更小的原始图像
2. 增加API的payload限制（如果可以）
3. 调整压缩参数

## 技术支持

如果问题仍未解决，请提供以下信息：

1. 完整的错误日志
2. Payload大小 (从日志中查看)
3. 使用的API服务商和模型
4. 图像数量和大小
5. Python版本和依赖版本

---

**最后更新**: 2026-02-01
**版本**: v1.0
