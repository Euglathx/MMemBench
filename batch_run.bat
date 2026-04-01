@echo off
REM Batch Run Script for M3Bench Conversation Generation (Windows)
REM ================================================================

echo ==========================================
echo M3Bench Batch Conversation Generator
echo ==========================================
echo.

REM Configuration
set NUM_TASKS=100
set MAX_TURNS=30
set MIN_TURNS=20
set TASK_DIR=generated_tasks_v2/run_13
set OUTPUT_DIR=simulator_test_log
set BATCH_SIZE=10

echo Configuration:
echo   Target conversations: %NUM_TASKS%
echo   Turns per conversation: %MIN_TURNS%-%MAX_TURNS%
echo   Task directory: %TASK_DIR%
echo   Output directory: %OUTPUT_DIR%
echo.

REM Step 1: Generate offline tasks (if needed)
if not exist "%TASK_DIR%" (
    echo [Step 1] Generating offline tasks...
    python tests\generate_all_tasks_v2.py --num-samples 100
    echo.
) else (
    echo [Step 1] Task directory exists, skipping generation
    echo.
)

REM Step 2: Run batch conversation generation
echo [Step 2] Starting batch conversation generation...
echo.

python tests\batch_test_user_simulator.py ^
    --num-tasks %NUM_TASKS% ^
    --max-turns %MAX_TURNS% ^
    --min-turns %MIN_TURNS% ^
    --task-dir %TASK_DIR% ^
    --output-dir %OUTPUT_DIR% ^
    --batch-size %BATCH_SIZE% ^
    --verbose

echo.
echo ==========================================
echo Batch generation complete!
echo ==========================================
echo.
echo Check results in: %OUTPUT_DIR%\
echo   - batch_statistics.json (summary)
echo   - run_log_*.json (detailed logs)
echo.

pause
