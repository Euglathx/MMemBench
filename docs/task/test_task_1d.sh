#!/bin/bash
# Task 1D 快速测试脚本
#
# 用法: bash task/test_task_1d.sh

set -e  # 遇到错误立即退出

echo "======================================"
echo "Task 1D: Batch数据集成 - 快速测试"
echo "======================================"
echo ""

# 定义输出目录
OUTPUT_DIR="test_output/task_1d"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEST_DIR="${OUTPUT_DIR}/test_${TIMESTAMP}"

echo "[Step 1] 创建测试目录..."
mkdir -p "${TEST_DIR}"
echo "  ✓ 目录: ${TEST_DIR}"
echo ""

# 检查 run_18 数据是否存在
RUN18_DATA="generated_tasks_v2/run_18/tasks/attribute_comparison_mscoco14.jsonl"
if [ ! -f "${RUN18_DATA}" ]; then
    echo "  ⚠️  WARNING: run_18 数据未找到"
    echo "  预期路径: ${RUN18_DATA}"
    echo "  尝试使用其他测试数据..."

    # 尝试查找其他JSONL文件
    JSONL_FILES=$(find generated_tasks_v2 -name "*.jsonl" 2>/dev/null | head -n 1)
    if [ -z "${JSONL_FILES}" ]; then
        echo "  ❌ ERROR: 未找到任何测试数据"
        echo "  请先生成任务数据或指定正确的路径"
        exit 1
    fi
    RUN18_DATA="${JSONL_FILES}"
    echo "  使用: ${RUN18_DATA}"
fi
echo ""

echo "[Step 2] 运行batch测试 (2个任务, 1个batch)..."
python run_batch_test.py \
  --task-files "${RUN18_DATA}" \
  --tasks-per-batch 2 \
  --num-batches 1 \
  --output-dir "${TEST_DIR}"

if [ $? -ne 0 ]; then
    echo "  ❌ Batch测试失败"
    exit 1
fi
echo "  ✓ Batch测试完成"
echo ""

# 查找生成的batch结果文件
BATCH_RESULT=$(find "${TEST_DIR}" -name "batch_results_*.json" | head -n 1)
if [ -z "${BATCH_RESULT}" ]; then
    echo "  ❌ ERROR: 未找到batch结果文件"
    exit 1
fi
echo "  结果文件: ${BATCH_RESULT}"
echo ""

echo "[Step 3] 验证batch结果包含turn详情..."
python task/verify_task_1d.py "${BATCH_RESULT}"

if [ $? -ne 0 ]; then
    echo "  ❌ 验证失败"
    exit 1
fi
echo ""

echo "[Step 4] 转换为runlog格式..."
RUNLOG_FILE="${TEST_DIR}/converted_runlog.json"
python tools/convert_batch_results_to_runlog.py \
  "${BATCH_RESULT}" \
  "${RUNLOG_FILE}"

if [ $? -ne 0 ]; then
    echo "  ❌ 转换失败"
    exit 1
fi
echo "  ✓ 转换完成: ${RUNLOG_FILE}"
echo ""

echo "[Step 5] 检查placeholder..."
PLACEHOLDER_COUNT=$(grep -c "detailed log not available" "${RUNLOG_FILE}" || true)
echo "  Placeholder事件数: ${PLACEHOLDER_COUNT}"

if [ ${PLACEHOLDER_COUNT} -eq 0 ]; then
    echo "  ✓ 没有placeholder,所有turn使用真实数据"
else
    echo "  ⚠️  发现 ${PLACEHOLDER_COUNT} 个placeholder事件"
fi
echo ""

echo "[Step 6] 完整验证 (包括runlog)..."
python task/verify_task_1d.py "${BATCH_RESULT}" "${RUNLOG_FILE}"

if [ $? -ne 0 ]; then
    echo "  ❌ 完整验证失败"
    exit 1
fi
echo ""

echo "======================================"
echo "✅ Task 1D 测试通过!"
echo "======================================"
echo ""
echo "测试结果保存在: ${TEST_DIR}"
echo "  - Batch结果: ${BATCH_RESULT}"
echo "  - Runlog: ${RUNLOG_FILE}"
echo ""
echo "下一步:"
echo "  1. 检查 ${BATCH_RESULT} 中的 'turns' 字段"
echo "  2. 检查 ${RUNLOG_FILE} 是否包含完整的turn事件"
echo "  3. 与Task 1A-1C集成测试"
echo ""
