# M3Bench GitHub 上传检查清单

## ✅ 已上传内容（与本地一致）

- [x] `dataprovider/` 目录（完整）
- [x] `human_annotations/` 目录（完整）
- [x] `simulator_test_log/` 目录（完整）
- [x] `src/` 目录（完整）
- [x] `tools/` 目录（完整）
- [x] `ACTION_SPACE_DESIGN.md`
- [x] `README.md`
- [x] `dataset_configs.yaml`
- [x] `generate_all_tasks_v2.py`
- [x] `run_batch_test.py`
- [x] `run_mm_experiment.py`
- [x] `test_action_diversity.py`
- [x] `test_batch_with_real_logs.py`

---

## 🔴 第一批：核心必需文件（立即上传）

```bash
# 1. 添加配置和依赖
git add .gitignore
git add requirements.txt
git add requirements_dataprovider.txt

# 2. 添加核心运行脚本
git add run_experiment.py
git add view_tasks.py

# 3. 提交
git commit -m "feat: add essential config files and main scripts"
git push
```

**这一批包含：**
- [ ] `.gitignore` - Git忽略规则（新创建）
- [ ] `requirements.txt` - Python依赖
- [ ] `requirements_dataprovider.txt` - DataProvider依赖
- [ ] `run_experiment.py` - 主实验脚本
- [ ] `view_tasks.py` - 任务查看工具

---

## 🔶 第二批：数据处理和测试（推荐上传）

```bash
# 1. 添加数据集处理脚本
git add mantis_dataset_loader.py
git add analyze_mantis_dataset.py
git add quick_analyze_mantis.py
git add extract_parquet_samples.py
git add simple_parquet_reader.py

# 2. 添加测试和监控脚本
git add test_api_fix.py
git add test_evaluator_fix.py
git add test_without_compression.py
git add monitor_experiment.py

# 3. 添加测试套件和配置目录
git add tests/
git add configs/

# 4. 提交
git commit -m "feat: add dataset processing scripts and test suite"
git push
```

**这一批包含：**
- [ ] `mantis_dataset_loader.py` - Mantis数据集加载器
- [ ] `analyze_mantis_dataset.py` - Mantis分析工具
- [ ] `quick_analyze_mantis.py` - 快速分析
- [ ] `extract_parquet_samples.py` - Parquet样本提取
- [ ] `simple_parquet_reader.py` - Parquet读取
- [ ] `test_api_fix.py` - API修复测试
- [ ] `test_evaluator_fix.py` - 评估器测试
- [ ] `test_without_compression.py` - 无压缩测试
- [ ] `monitor_experiment.py` - 实验监控
- [ ] `tests/` 目录 - 完整测试套件
- [ ] `configs/` 目录 - 配置文件

---

## 🔶 第三批：文档（完善项目）

```bash
# 1. 添加用户文档
git add PROJECT_OVERVIEW.md
git add DATASET_SETUP_CN.md
git add API_CONFIGURATION.md
git add QUICKSTART_DATAPROVIDER.md

# 2. 添加技术文档
git add DATAPROVIDER_SUMMARY.md
git add BATCH_GENERATION_GUIDE.md
git add PERFORMANCE_OPTIMIZATION.md
git add MANTIS_DATASET_REPORT.md

# 3. 添加项目总结文档
git add IMPLEMENTATION_SUMMARY.md
git add TASK_COMPLETION_SUMMARY.md
git add DELIVERY_SUMMARY.md
git add TROUBLESHOOTING.md

# 4. 添加docs目录
git add docs/

# 5. 提交
git commit -m "docs: add comprehensive documentation"
git push
```

**这一批包含：**
- [ ] `PROJECT_OVERVIEW.md` - 项目概览
- [ ] `DATASET_SETUP_CN.md` - 数据集设置指南（重要）
- [ ] `API_CONFIGURATION.md` - API配置说明（重要）
- [ ] `QUICKSTART_DATAPROVIDER.md` - 快速开始
- [ ] `DATAPROVIDER_SUMMARY.md` - DataProvider总结
- [ ] `BATCH_GENERATION_GUIDE.md` - 批量生成指南
- [ ] `PERFORMANCE_OPTIMIZATION.md` - 性能优化
- [ ] `MANTIS_DATASET_REPORT.md` - Mantis数据集报告
- [ ] `IMPLEMENTATION_SUMMARY.md` - 实现总结
- [ ] `TASK_COMPLETION_SUMMARY.md` - 任务完成
- [ ] `DELIVERY_SUMMARY.md` - 交付总结
- [ ] `TROUBLESHOOTING.md` - 故障排查
- [ ] `docs/` 目录 - 架构文档

---

## 🔹 第四批：辅助工具（可选）

```bash
# 1. 添加批量运行脚本
git add batch_run.sh
git add batch_run.bat
git add run_fast_test.bat

# 2. 添加其他文本文件
git add FILE_LIST.txt
git add MANTIS_ANALYSIS_SUMMARY.txt
git add "motivation和架构等.txt"

# 3. 添加运行脚本目录（如果有内容）
git add run_scripts/

# 4. 提交
git commit -m "chore: add batch scripts and auxiliary files"
git push
```

**这一批包含：**
- [ ] `batch_run.sh` / `batch_run.bat` - 批量运行脚本
- [ ] `run_fast_test.bat` - 快速测试
- [ ] `FILE_LIST.txt` - 文件清单
- [ ] `MANTIS_ANALYSIS_SUMMARY.txt` - 分析摘要
- [ ] `motivation和架构等.txt` - 项目思路
- [ ] `run_scripts/` 目录 - 运行脚本集合

---

## ❌ 不应上传的内容（已在.gitignore中排除）

这些内容太大或包含敏感信息，不应该上传到GitHub：

### 数据目录
- ❌ `data/` - 数据集文件（几十GB）
- ❌ `generated_tasks/` - V1生成的任务（已废弃）
- ❌ `generated_tasks_v2/` - V2生成的任务（运行时生成）
- ❌ `generated_tasks_unified/` - 统一任务（运行时生成）

### 运行时输出
- ❌ `simulator_test_log/*` - 日志内容（保留目录结构）
- ❌ `results/` - 实验结果
- ❌ `output/` - 输出目录
- ❌ `batch_test_results/` - 批量测试结果
- ❌ `experiment_images/` - 实验图像

### Python缓存
- ❌ `__pycache__/` - Python字节码
- ❌ `*.pyc` - 编译文件
- ❌ `.pytest_cache/` - pytest缓存

### IDE配置
- ❌ `.vscode/` - VSCode配置
- ❌ `.idea/` - PyCharm配置

### 敏感文件
- ❌ `.env` - 环境变量（可能包含API密钥）
- ❌ `**/api_key*` - API密钥
- ❌ `credentials.json` - 凭证

---

## 📋 验证命令

上传前检查：

```bash
# 查看哪些文件会被上传
git status

# 查看哪些文件被gitignore排除
git status --ignored

# 检查是否有敏感文件
git diff --cached | grep -i "api_key\|password\|secret\|token"
```

---

## 🎯 总结

### 必须上传（不上传项目无法运行）：
1. ✅ `.gitignore` + `requirements.txt` + `requirements_dataprovider.txt`
2. ✅ `run_experiment.py` + `view_tasks.py`

### 强烈推荐上传（完整功能）：
3. ✅ 数据集处理脚本（5个.py文件）
4. ✅ 测试脚本（4个test_*.py）+ `tests/` 目录
5. ✅ `configs/` 目录

### 推荐上传（用户体验）：
6. ✅ 用户文档（DATASET_SETUP_CN.md, API_CONFIGURATION.md等）
7. ✅ `docs/` 目录

### 可选上传（便利性）：
8. ✅ 批量脚本和其他工具

---

## 🚨 特别注意

1. **在git add之前**，确保 `.gitignore` 已经提交
2. **检查API密钥**：确保没有硬编码的API密钥
3. **数据集说明**：在README中添加数据集下载说明（因为data/不上传）
4. **保持目录结构**：虽然排除了内容，但可以用.gitkeep保持空目录

```bash
# 创建.gitkeep来保持目录结构
touch simulator_test_log/.gitkeep
touch results/.gitkeep
touch output/.gitkeep

git add simulator_test_log/.gitkeep
git add results/.gitkeep
git add output/.gitkeep
```

---

生成时间：2026-02-03
