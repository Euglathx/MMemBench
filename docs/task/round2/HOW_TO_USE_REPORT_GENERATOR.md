# 报告生成器使用指南

## 快速开始

### 生成验证报告

当实验完成后，运行以下命令生成验证报告：

```bash
python task/generate_report.py test_output task/round2/final_validation_report.md
```

参数说明：
- 第一个参数：测试输出目录（默认: `test_output`）
- 第二个参数：报告输出路径（默认: `validation_report.md`）

### 运行所有验证脚本

在生成报告前，可以先运行验证脚本检查各项指标：

```bash
python task/verify_all.py test_output
```

---

## 报告内容

生成的报告包含：

### 1. 执行摘要
- 整体通过/失败状态
- 关键指标概览表（一目了然的达标情况）

### 2. 详细验证结果
- Task 1A: 解析修复
- Task 1B: 文本提示最小化
- Task 1C: 截断修复
- Task 1D: Batch集成
- Task 2A: 评估系统修复
- Task 2B: 动作空间扩展

### 3. 后续建议
- 已达标任务摘要
- 未达标任务的具体改进建议
- 性能优化建议
- 扩展功能建议
- 已知限制

### 4. 附录
- 运行环境信息
- 重现步骤
- 联系方式

---

## 数据要求

脚本会自动扫描测试目录，查找以下文件：

### 必需的文件

1. **run_log文件**: `test_output/**/run_log_*.json`
   - 包含每个turn的详细日志
   - 用于Task 1A, 1B, 1C, 2A, 2B的分析

2. **batch_results文件**: `test_output/**/batch_results_*.json`
   - 包含批次执行的结果
   - 用于Task 1D的分析

### 目录结构建议

```
test_output/
├── final_nonmm/          # 非多模态模型实验结果
│   ├── run_log_*.json
│   └── batch_results_*.json
└── final_mm/             # 多模态模型实验结果
    ├── run_log_*.json
    └── batch_results_*.json
```

脚本会根据路径自动区分多模态和非多模态日志。

---

## 常见问题

### Q1: 报告显示某些任务的分数为0.00？

**原因**: 缺少相应的日志文件（通常是多模态实验数据）

**解决**: 确保Task 3-3的多模态实验已完成，并生成了run_log文件

### Q2: 报告显示"No actions found"？

**原因**: run_log中没有找到core_model_decision事件或action字段

**解决**: 检查run_log文件格式是否正确，确保包含完整的决策日志

### Q3: Task 1D覆盖率为0%？

**原因**: batch_results文件为空或结构不符合预期

**解决**:
- 检查batch_results文件大小（脚本会自动跳过0字节文件）
- 确认文件包含results -> task_results结构

### Q4: 如何查看详细的错误信息？

在Python中直接运行脚本可以看到详细的错误堆栈：

```bash
python task/generate_report.py test_output report.md
```

---

## 高级用法

### 仅分析特定目录

```bash
# 仅分析非多模态结果
python task/generate_report.py test_output/final_nonmm report_nonmm.md

# 仅分析多模态结果
python task/generate_report.py test_output/final_mm report_mm.md
```

### 自定义分析函数

如果需要自定义分析逻辑，可以编辑 [generate_report.py](../generate_report.py) 中的以下函数：

- `analyze_parse_errors()`: Task 1A
- `analyze_text_hints()`: Task 1B
- `analyze_truncation()`: Task 1C
- `analyze_batch_integration()`: Task 1D
- `analyze_evaluation_scores()`: Task 2A
- `analyze_action_diversity()`: Task 2B

---

## 维护和更新

### 更新指标阈值

如果需要调整验证阈值（如将Task 1B的目标从2.0改为1.5），编辑各分析函数中的`pass`判断条件。

例如，在`analyze_text_hints()`中：

```python
"pass": avg_visual_words < 2.0  # 改为 1.5
```

### 添加新的验证任务

1. 编写新的分析函数（如`analyze_task_1e()`）
2. 在`analyze_logs()`中添加调用
3. 在`generate_markdown_report()`中添加相应的报告节
4. 更新`_generate_failed_tasks_recommendations()`添加建议

---

## 示例输出

查看示例报告：[final_validation_report.md](final_validation_report.md)

---

## 脚本依赖

- Python 3.7+
- 标准库: `json`, `glob`, `pathlib`, `collections`, `datetime`, `os`

无需安装额外的第三方包。

---

## 联系和支持

如有问题或建议，请查看：
- Task规划文档: [01_task_planning.md](01_task_planning.md)
- 完成报告: [task_3-5_completion.md](task_3-5_completion.md)
- 主README: [README.md](README.md)
