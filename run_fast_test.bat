@echo off
REM ========================================
REM M3Bench 快速测试脚本 (Windows)
REM ========================================
REM
REM 使用优化的模型配置，大幅提升速度
REM 预期速度：约2-3分钟/批次（vs 默认15分钟）
REM

echo ========================================
echo M3Bench 快速测试模式
echo ========================================
echo.
echo 配置:
echo   Core Model: gemini-2.5-flash-image-preview
echo   Target Model: gemini-2.5-flash-image-preview
echo   Eval Model: claude-3-5-haiku-20241022-c
echo   Max Turns: 25
echo.

REM 设置快速模型
set M3BENCH_CORE_MODEL=gemini-2.5-flash-image-preview
set M3BENCH_TARGET_MODEL=gemini-2.5-flash-image-preview
set M3BENCH_EVAL_MODEL=claude-3-5-haiku-20241022-c

REM 运行测试
python run_batch_test.py ^
    --tasks-per-batch 2 ^
    --num-batches 1 ^
    --max-turns-per-session 25 ^
    --max-turns-per-task 8 ^
    --min-turns-per-task 4 ^
    --verbose

echo.
echo ========================================
echo 测试完成！
echo ========================================
echo.
echo 查看详细配置: PERFORMANCE_OPTIMIZATION.md
echo.
pause
