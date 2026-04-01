# Phase 1 Task 1.1: 图像发送验证

## 任务目标

验证评审意见中的**P0级问题**：图像是否正确发送给VLM模型。

## 问题描述

从run log `run_log_ac_mscoco_1769393592_ysty_001.json` 发现：
- **所有turn的 `images_sent` 字段都是空列表 `[]`**
- 模型一直回答 "I'm unable to view images directly"
- 这比评审意见更严重：整个视觉评测完全失效

## 验证目标

1. 确认问题普遍性：是所有任务都有这个问题，还是只有特定任务？
2. 定位根因：图像路径解析失败？API调用参数错误？权限问题？
3. 追踪调用链：从 simulator → llm_client → API 的完整路径

## 验证脚本设计

### 脚本名称
`debug_image_sending.py`

### 验证步骤

#### Step 1: Run Log统计分析
```python
# 扫描所有run logs
# 统计:
# - 总turn数
# - images_sent为空的turn数
# - 按task_type分组统计
# - 按模型分组统计
```

**成功标准**:
- 如果 >80% 的turn images_sent为空 → P0问题确认
- 如果 <20% → 可能是特定场景问题

#### Step 2: 代码路径追踪
```python
# 追踪以下函数调用:
# 1. StrategicSimulator._get_images_for_turn()
#    - 返回值是什么？
#    - 图像路径解析逻辑
# 2. StrategicSimulator._ask_model()
#    - images参数如何传递？
# 3. LLMClient.call()
#    - messages中的image_url是否正确构造？
# 4. API请求payload
#    - 实际发送的JSON是什么？
```

**成功标准**:
- 找到图像丢失的确切位置

#### Step 3: 模拟调用测试
```python
# 创建最小复现case:
# 1. 构造一个简单的task
# 2. 手动调用 _get_images_for_turn()
# 3. 手动构造API payload
# 4. 验证图像是否正确编码
```

**成功标准**:
- 能够复现问题
- 或者证明最小case可以工作（说明问题在复杂流程中）

### 输出格式

```json
{
  "validation_id": "1.1_image_sending",
  "timestamp": "2026-02-03T...",
  "status": "FAIL" | "PASS",
  "statistics": {
    "total_turns": 1000,
    "empty_images_sent": 950,
    "empty_percentage": 95.0,
    "by_task_type": {
      "attribute_comparison": {"total": 300, "empty": 285},
      "beyond_imagenet": {"total": 700, "empty": 665}
    }
  },
  "root_cause": {
    "location": "strategic_simulator.py:_get_images_for_turn():line 910",
    "issue": "img_path does not exist, valid_images remains empty",
    "evidence": "Path(...).exists() returns False for all images"
  },
  "reproduction": {
    "minimal_case": "See debug_image_sending_minimal.py",
    "can_reproduce": true
  },
  "severity": "P0_CRITICAL",
  "recommended_fix": "Fix image path resolution in _get_images_for_turn()"
}
```

### 诊断输出

脚本应该输出详细的人类可读报告：

```
=== Image Sending Validation Report ===

Status: FAIL ❌

Problem Summary:
- 95.0% of turns have empty images_sent
- This affects ALL task types
- Models consistently report "cannot view images"

Root Cause:
Location: strategic_simulator.py:_get_images_for_turn(), line 910
Issue: Image path resolution fails
Evidence:
  - Task images: ['images/COCO_val2014_000000578292.jpg', ...]
  - Resolved path: /full/path/to/images/...
  - Path exists: False ❌

Why paths don't exist:
  - Base directory is incorrect
  - Expected: /path/to/generated_tasks_v2/run_XX/images/
  - Actual: /path/to/M3Bench_new/images/
  - Missing directory creation step

Impact:
  - 100% of visual evaluations are invalid
  - All run logs before this fix are unreliable
  - Need to re-run all experiments after fix

Recommended Actions:
1. Fix image path resolution in _get_images_for_turn()
2. Add path existence validation before sending
3. Add logging for image loading failures
4. Re-run all experiments

Minimal Reproduction:
Run: python debug_image_sending_minimal.py
Expected: Image paths should resolve correctly
Actual: Path.exists() returns False
```

## 变量和接口定义

### 输入
- `log_dir`: 包含run logs的目录路径
- `task_config`: 任务配置文件路径（可选，用于验证图像路径）

### 输出
- `validation_report.json`: 机器可读的验证结果
- `validation_report.txt`: 人类可读的详细报告
- `debug_minimal.py`: 最小复现脚本（如果可以复现）

### 接口

```python
class ImageSendingValidator:
    """验证图像发送问题"""

    def __init__(self, log_dir: str, task_dir: Optional[str] = None):
        """
        Args:
            log_dir: Run logs目录
            task_dir: 任务数据目录（包含images/）
        """
        pass

    def analyze_logs(self) -> Dict:
        """分析run logs，统计images_sent为空的情况"""
        pass

    def trace_code_path(self) -> Dict:
        """追踪代码调用路径，定位问题"""
        pass

    def create_minimal_reproduction(self) -> str:
        """创建最小复现脚本"""
        pass

    def generate_report(self) -> Tuple[Dict, str]:
        """生成验证报告"""
        pass
```

## 协作要求

### 与其他任务的依赖
- **独立任务**: 不依赖其他Phase 1任务
- **被依赖**: Task 2.1（图像发送管道修复）需要这个验证结果

### 与Phase 2的接口
- 必须明确指出根因位置（文件名、函数名、行号）
- 必须提供最小复现case
- 必须量化问题严重程度

### 数据共享
- 验证报告保存到 `round3/results/phase1_1.1_image_sending.json`
- 详细日志保存到 `round3/logs/phase1_1.1_debug.log`

## 成功标准

- [ ] 脚本运行无错误
- [ ] 统计覆盖所有可用run logs（至少100个turns）
- [ ] 根因定位到具体代码行
- [ ] 可以创建最小复现case
- [ ] 生成的报告清晰、可执行

## 时间估算

- 脚本开发: 1小时
- 日志分析: 0.5小时
- 代码追踪: 1小时
- 报告撰写: 0.5小时
- **总计: 约3小时**

## 风险和注意事项

1. **日志版本问题**: 不同时间的run logs可能格式不同
2. **路径问题**: Windows vs Linux路径差异
3. **权限问题**: 某些图像文件可能无权限读取

## 验证清单

在提交验证报告前，确认：
- [ ] 统计数据准确（手动抽查10个logs验证）
- [ ] 根因分析有代码证据支持
- [ ] 最小复现case可以独立运行
- [ ] 报告包含明确的修复建议
- [ ] 严重程度评级合理

---

**并行组**: A (可以与Task 1.2并行)
**优先级**: P0 (最高优先级)
**预估难度**: Medium (问题明确但需要仔细追踪)
