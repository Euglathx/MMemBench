#!/usr/bin/env pwsh
# ========================================
# M3Bench 快速测试脚本 (PowerShell)
# ========================================
#
# 使用优化的模型配置，大幅提升速度
# 预期速度：约2-3分钟/批次（vs 默认15分钟）
#

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "M3Bench 快速测试模式" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "配置:" -ForegroundColor Yellow
Write-Host "  Core Model: claude-3-5-sonnet-20241022-c (更稳定的JSON输出)"
Write-Host "  Target Model: gemini-2.5-flash-image-preview"
Write-Host "  Eval Model: claude-3-5-haiku-20241022-c"
Write-Host "  Max Turns: 25"
Write-Host ""

# 设置快速模型
# 注意: Core Model 使用 Claude，因为 Gemini-3-pro 经常返回非JSON格式
$env:M3BENCH_CORE_MODEL = "claude-3-5-sonnet-20241022-c"
$env:M3BENCH_TARGET_MODEL = "gemini-2.5-flash-image-preview"
$env:M3BENCH_EVAL_MODEL = "claude-3-5-haiku-20241022-c"

# 运行测试
python run_batch_test.py `
    --tasks-per-batch 2 `
    --num-batches 1 `
    --max-turns-per-session 25 `
    --max-turns-per-task 8 `
    --min-turns-per-task 4 `
    --verbose

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "测试完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "查看详细配置: PERFORMANCE_OPTIMIZATION.md" -ForegroundColor Yellow
Write-Host ""
