import subprocess
import sys
import glob
import os
from pathlib import Path

def run_verification(test_dir: str):
    """运行所有验证脚本."""

    # 查找测试输出，区分多模态和非多模态
    nonmm_run_logs = glob.glob(f"{test_dir}/**/final_nonmm/run_log_*.json", recursive=True)
    mm_run_logs = glob.glob(f"{test_dir}/**/final_mm/run_log_*.json", recursive=True)

    # 只选择非空的batch_results文件
    all_batch_results = glob.glob(f"{test_dir}/**/batch_results_*.json", recursive=True)
    batch_results = [f for f in all_batch_results if os.path.getsize(f) > 0]

    print("="*70)
    print("FILES FOUND:")
    print("="*70)
    print(f"Non-MM run logs: {len(nonmm_run_logs)}")
    for f in nonmm_run_logs:
        print(f"  - {f}")
    print(f"MM run logs: {len(mm_run_logs)}")
    for f in mm_run_logs:
        print(f"  - {f}")
    print(f"Non-empty batch results: {len(batch_results)}")
    for f in batch_results:
        print(f"  - {f} ({os.path.getsize(f)} bytes)")

    results = {}

    # Task 1A: Parse Error - 对所有run_log进行验证
    print(f"\n{'='*70}")
    print("Running: Task 1A - Parse Error (Non-MM logs)")
    print('='*70)
    task_1a_passed = True
    if nonmm_run_logs:
        for log_file in nonmm_run_logs:
            result = subprocess.run(f"python task/verify_task_1a.py {log_file}", shell=True)
            task_1a_passed = task_1a_passed and (result.returncode == 0)
    else:
        print("⚠️ No non-MM run logs found")
        task_1a_passed = False

    if mm_run_logs:
        print(f"\n{'='*70}")
        print("Running: Task 1A - Parse Error (MM logs)")
        print('='*70)
        for log_file in mm_run_logs:
            result = subprocess.run(f"python task/verify_task_1a.py {log_file}", shell=True)
            task_1a_passed = task_1a_passed and (result.returncode == 0)

    results["Task 1A - Parse Error"] = task_1a_passed

    # Task 1D: Batch Integration
    print(f"\n{'='*70}")
    print("Running: Task 1D - Batch Integration")
    print('='*70)
    task_1d_passed = False
    if batch_results:
        # 只验证第一个非空的batch_results文件
        result = subprocess.run(f"python task/verify_task_1d.py {batch_results[0]}", shell=True)
        task_1d_passed = result.returncode == 0
    else:
        print("⚠️ No non-empty batch results files found")
    results["Task 1D - Batch Integration"] = task_1d_passed

    # Task 2A: Evaluation Fix - 需要同时验证多模态和非多模态
    print(f"\n{'='*70}")
    print("Running: Task 2A - Evaluation Fix (Non-MM)")
    print('='*70)
    task_2a_nonmm_passed = False
    if nonmm_run_logs:
        # 验证第一个非多模态log
        result = subprocess.run(f"python task/verify_task_2a.py {nonmm_run_logs[0]} --non-multimodal", shell=True)
        task_2a_nonmm_passed = result.returncode == 0
    else:
        print("⚠️ No non-MM run logs found")

    task_2a_mm_passed = False
    if mm_run_logs:
        print(f"\n{'='*70}")
        print("Running: Task 2A - Evaluation Fix (MM)")
        print('='*70)
        # 验证第一个多模态log
        result = subprocess.run(f"python task/verify_task_2a.py {mm_run_logs[0]} --multimodal", shell=True)
        task_2a_mm_passed = result.returncode == 0
    else:
        print("⚠️ No MM run logs found - skipping MM evaluation check")
        # 如果没有MM数据，只要NonMM通过就算通过
        task_2a_mm_passed = True

    results["Task 2A - Evaluation Fix"] = task_2a_nonmm_passed and task_2a_mm_passed

    # Task 2B: Action Diversity - 通常只需要多模态模型验证，但也可以检查非多模态
    print(f"\n{'='*70}")
    print("Running: Task 2B - Action Diversity")
    print('='*70)
    task_2b_passed = False
    # 优先使用MM logs，如果没有则使用NonMM
    target_logs = mm_run_logs if mm_run_logs else nonmm_run_logs
    if target_logs:
        result = subprocess.run(f"python task/verify_task_2b.py {target_logs[0]}", shell=True)
        task_2b_passed = result.returncode == 0
    else:
        print("⚠️ No run logs found")
    results["Task 2B - Action Diversity"] = task_2b_passed

    # 最终汇总
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print('='*60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return all_passed

if __name__ == "__main__":
    test_dir = sys.argv[1] if len(sys.argv) > 1 else "test_output"
    passed = run_verification(test_dir)
    sys.exit(0 if passed else 1)
