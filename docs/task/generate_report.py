import json
import glob
from pathlib import Path
from collections import Counter
from datetime import datetime

def analyze_logs(test_dir: str) -> dict:
    """分析所有测试输出."""
    # 读取所有 run_log
    run_logs = glob.glob(f"{test_dir}/**/run_log_*.json", recursive=True)
    batch_results = glob.glob(f"{test_dir}/**/batch_results_*.json", recursive=True)

    analysis = {
        "timestamp": datetime.now().isoformat(),
        "test_directory": test_dir,
        "task_1a": analyze_parse_errors(run_logs),
        "task_1b": analyze_text_hints(run_logs),
        "task_1c": analyze_truncation(run_logs),
        "task_1d": analyze_batch_integration(batch_results),
        "task_2a": analyze_evaluation_scores(run_logs),
        "task_2b": analyze_action_diversity(run_logs),
    }

    return analysis

def analyze_parse_errors(run_logs):
    """分析解析错误 (Task 1A)."""
    total_decisions = 0
    parse_errors = 0
    please_continue = 0
    failed_to_parse = 0

    for log_file in run_logs:
        with open(log_file, encoding='utf-8') as f:
            events = json.load(f)

        for event in events:
            if event.get('event') == 'core_model_decision':
                total_decisions += 1
                # 检查是否有解析错误标志
                if event.get('parse_error'):
                    parse_errors += 1
                # 检查message_to_model中的错误信息
                msg = event.get('message_to_model', '').lower()
                if 'please continue' in msg:
                    please_continue += 1
                if 'failed to parse' in msg:
                    failed_to_parse += 1

    return {
        "total_decisions": total_decisions,
        "parse_errors": parse_errors,
        "please_continue_count": please_continue,
        "failed_to_parse_count": failed_to_parse,
        "pass": parse_errors == 0 and please_continue == 0 and failed_to_parse == 0
    }

def analyze_text_hints(run_logs):
    """分析文本提示最小化 (Task 1B)."""
    total_turns = 0
    total_visual_words = 0

    # 定义视觉词汇列表
    visual_vocab = [
        'screenshot', 'image', 'pixel', 'coordinate', 'color',
        'top-left', 'bottom-right', 'ui', 'button', 'icon'
    ]

    for log_file in run_logs:
        with open(log_file, encoding='utf-8') as f:
            events = json.load(f)

        for event in events:
            if event.get('event') == 'core_model_decision':
                total_turns += 1
                msg = event.get('message_to_model', '').lower()
                # 计算视觉词汇数量
                word_count = sum(msg.count(word) for word in visual_vocab)
                total_visual_words += word_count

    avg_visual_words = total_visual_words / total_turns if total_turns > 0 else 0

    return {
        "total_turns": total_turns,
        "total_visual_words": total_visual_words,
        "avg_visual_words_per_turn": avg_visual_words,
        "pass": avg_visual_words < 2.0
    }

def analyze_truncation(run_logs):
    """分析截断修复 (Task 1C)."""
    total_responses = 0
    truncated_responses = 0

    for log_file in run_logs:
        with open(log_file, encoding='utf-8') as f:
            events = json.load(f)

        for event in events:
            if event.get('event') == 'core_model_decision':
                total_responses += 1
                response = event.get('model_response', '')
                # 检查是否被截断 (响应长度达到上限或包含截断标志)
                if len(response) > 4000 or response.endswith('...'):
                    truncated_responses += 1

    truncation_rate = (truncated_responses / total_responses * 100) if total_responses > 0 else 0

    return {
        "total_responses": total_responses,
        "truncated_responses": truncated_responses,
        "truncation_rate": truncation_rate,
        "pass": truncated_responses == 0
    }

def analyze_batch_integration(batch_results):
    """分析 Batch 集成 (Task 1D)."""
    import os
    total_tasks = 0
    tasks_with_turns = 0

    for batch_file in batch_results:
        # 跳过空文件
        if os.path.getsize(batch_file) == 0:
            continue
        with open(batch_file, encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        # batch_results的结构: results -> task_results
        for batch in data.get('results', []):
            for task_result in batch.get('task_results', []):
                total_tasks += 1
                # 检查是否有turn相关的详情（turns或conversation_history）
                if (task_result.get('turns') or
                    task_result.get('conversation_history') or
                    task_result.get('turn_details')):
                    tasks_with_turns += 1

    coverage = (tasks_with_turns / total_tasks * 100) if total_tasks > 0 else 0

    return {
        "total_tasks": total_tasks,
        "tasks_with_turns": tasks_with_turns,
        "coverage": coverage,
        "pass": coverage == 100.0
    }

def analyze_evaluation_scores(run_logs):
    """分析评估系统修复 (Task 2A)."""
    # 分离多模态和非多模态模型的日志
    # 使用路径中的 'final_nonmm' 来区分
    nonmm_logs = [log for log in run_logs if 'final_nonmm' in log]
    mm_logs = [log for log in run_logs if 'final_mm' in log]

    def get_scores(logs):
        scores = []
        faithfulness_scores = []

        for log_file in logs:
            with open(log_file, encoding='utf-8') as f:
                events = json.load(f)

            for event in events:
                # 使用 task_end 事件（根据实际日志结构）
                if event.get('event') == 'task_end':
                    task_scores = event.get('scores', {})
                    if 'overall' in task_scores:
                        scores.append(task_scores['overall'])
                    if 'faithfulness' in task_scores:
                        faithfulness_scores.append(task_scores['faithfulness'])

        avg_score = sum(scores) / len(scores) if scores else 0
        avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0

        return avg_score, avg_faithfulness

    nonmm_avg, nonmm_faith = get_scores(nonmm_logs)
    mm_avg, mm_faith = get_scores(mm_logs)
    score_gap = mm_avg - nonmm_avg

    return {
        "nonmm_avg_score": nonmm_avg,
        "nonmm_faithfulness": nonmm_faith,
        "mm_avg_score": mm_avg,
        "mm_faithfulness": mm_faith,
        "score_gap": score_gap,
        "pass": (nonmm_avg < 0.3 and mm_avg > 0.6 and score_gap > 0.4 and
                 nonmm_faith < 0.2 and mm_faith > 0.6)
    }

def analyze_action_diversity(run_logs):
    """分析动作空间扩展 (Task 2B)."""
    all_actions = []

    for log_file in run_logs:
        with open(log_file, encoding='utf-8') as f:
            events = json.load(f)

        for event in events:
            if event.get('event') == 'core_model_decision':
                # action 字段直接在事件中（根据实际日志结构）
                action_type = event.get('action', '')
                if action_type:
                    all_actions.append(action_type)

    if not all_actions:
        return {
            "unique_actions": 0,
            "max_action_pct": 0,
            "action_distribution": "No actions found",
            "pass": False
        }

    action_counts = Counter(all_actions)
    unique_actions = len(action_counts)
    max_count = max(action_counts.values())
    max_action_pct = (max_count / len(all_actions) * 100) if all_actions else 0

    # 格式化动作分布
    dist_lines = []
    for action, count in action_counts.most_common():
        pct = count / len(all_actions) * 100
        dist_lines.append(f"  - {action}: {count} ({pct:.1f}%)")
    action_distribution = "\n".join(dist_lines)

    return {
        "unique_actions": unique_actions,
        "max_action_pct": max_action_pct,
        "action_distribution": action_distribution,
        "pass": unique_actions >= 8 and max_action_pct <= 40
    }

def _generate_passed_tasks_summary(analysis: dict) -> str:
    """生成已通过任务的摘要."""
    passed = []
    task_names = {
        'task_1a': 'Task 1A - 解析修复',
        'task_1b': 'Task 1B - 文本提示最小化',
        'task_1c': 'Task 1C - 截断修复',
        'task_1d': 'Task 1D - Batch集成',
        'task_2a': 'Task 2A - 评估系统修复',
        'task_2b': 'Task 2B - 动作空间扩展'
    }

    for key, name in task_names.items():
        if analysis.get(key, {}).get('pass'):
            passed.append(f"- ✅ **{name}**: 已达标")

    return '\n'.join(passed) if passed else "- 暂无完全达标的任务"

def _generate_failed_tasks_recommendations(analysis: dict) -> str:
    """生成未通过任务的改进建议."""
    recommendations = []

    # Task 1A
    if not analysis.get('task_1a', {}).get('pass'):
        recommendations.append("""
**Task 1A - 解析修复**:
- 检查core model的输出格式是否符合预期
- 验证JSON解析逻辑是否正确
- 考虑添加更严格的输出格式约束
""")

    # Task 1B
    if not analysis.get('task_1b', {}).get('pass'):
        avg_words = analysis.get('task_1b', {}).get('avg_visual_words_per_turn', 0)
        recommendations.append(f"""
**Task 1B - 文本提示最小化**:
- 当前平均视觉词汇/turn: {avg_words:.2f}，目标: < 2.0
- 建议：减少message_to_model中的视觉描述词汇
- 考虑使用更简洁的提示语言
- 优化hint_level设置，降低文本提示的详细程度
""")

    # Task 1C
    if not analysis.get('task_1c', {}).get('pass'):
        recommendations.append("""
**Task 1C - 截断修复**:
- 检查响应长度限制设置
- 验证是否正确处理长响应
- 考虑实现动态响应长度调整
""")

    # Task 1D
    if not analysis.get('task_1d', {}).get('pass'):
        coverage = analysis.get('task_1d', {}).get('coverage', 0)
        recommendations.append(f"""
**Task 1D - Batch集成**:
- 当前覆盖率: {coverage:.1f}%，目标: 100%
- 确保batch_results中包含所有任务的turn详情
- 检查数据收集和序列化逻辑
""")

    # Task 2A
    if not analysis.get('task_2a', {}).get('pass'):
        nonmm_avg = analysis.get('task_2a', {}).get('nonmm_avg_score', 0)
        mm_avg = analysis.get('task_2a', {}).get('mm_avg_score', 0)
        gap = analysis.get('task_2a', {}).get('score_gap', 0)
        recommendations.append(f"""
**Task 2A - 评估系统修复**:
- 非多模态平均分: {nonmm_avg:.2f}，目标: < 0.3
- 多模态平均分: {mm_avg:.2f}，目标: > 0.6
- Score gap: {gap:.2f}，目标: > 0.4
- 建议：
  - 如果多模态分数不足，检查模型是否正确接收图像
  - 如果非多模态分数过高，可能需要调整任务难度
  - 调整llm_judge_weight参数以优化评分系统
""")

    # Task 2B
    if not analysis.get('task_2b', {}).get('pass'):
        unique = analysis.get('task_2b', {}).get('unique_actions', 0)
        max_pct = analysis.get('task_2b', {}).get('max_action_pct', 0)
        recommendations.append(f"""
**Task 2B - 动作空间扩展**:
- 唯一动作种类: {unique}，目标: >= 8
- 最大单一动作占比: {max_pct:.1f}%，目标: <= 40%
- 建议：
  - 设计更多样化的任务来激发不同类型的动作
  - 检查core model的prompt是否鼓励多样化的策略
  - 考虑引入新的动作类型到action space
""")

    return '\n'.join(recommendations) if recommendations else "- 所有任务均已达标！"

def generate_markdown_report(analysis: dict, output_path: str):
    """生成 Markdown 报告."""
    # 计算通过的任务数
    passed_tasks = sum(1 for k, v in analysis.items() if isinstance(v, dict) and v.get('pass'))
    total_tasks = 6
    all_passed = all(v.get('pass') for k, v in analysis.items() if isinstance(v, dict))

    report = f"""# M3Bench 系统验证报告

生成时间: {analysis['timestamp']}
测试目录: {analysis['test_directory']}

---

## 执行摘要

### 整体结果

- **通过任务**: {passed_tasks} / {total_tasks}
- **整体状态**: {'✅ ALL PASS - 系统达标' if all_passed else '⚠️ PARTIAL FAIL - 需要修复'}

### 关键指标概览

| 任务 | 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|------|
| Task 1A | Parse errors | 0 | {analysis['task_1a']['parse_errors']} | {'✅' if analysis['task_1a']['pass'] else '❌'} |
| Task 1B | 平均视觉词汇/turn | < 2.0 | {analysis['task_1b'].get('avg_visual_words_per_turn', 0):.2f} | {'✅' if analysis['task_1b'].get('pass') else '❌'} |
| Task 1C | 截断率 | 0% | {analysis['task_1c']['truncation_rate']:.1f}% | {'✅' if analysis['task_1c']['pass'] else '❌'} |
| Task 1D | Batch覆盖率 | 100% | {analysis['task_1d']['coverage']:.1f}% | {'✅' if analysis['task_1d']['pass'] else '❌'} |
| Task 2A | Score gap | > 0.4 | {analysis['task_2a']['score_gap']:.2f} | {'✅' if analysis['task_2a']['pass'] else '❌'} |
| Task 2B | 唯一动作种类 | >= 8 | {analysis['task_2b']['unique_actions']} | {'✅' if analysis['task_2b']['pass'] else '❌'} |

---

## 详细验证结果

## 1. Task 1A - 解析修复

- 总决策次数: {analysis['task_1a']['total_decisions']}
- Parse Errors: {analysis['task_1a']['parse_errors']} (目标: 0)
- "Please continue" 出现: {analysis['task_1a']['please_continue_count']} (目标: 0)
- "Failed to parse" 出现: {analysis['task_1a']['failed_to_parse_count']} (目标: 0)

状态: **{'PASS' if analysis['task_1a']['pass'] else 'FAIL'}**

---

## 2. Task 1B - 文本提示最小化

- 总 turns: {analysis['task_1b']['total_turns']}
- 总视觉词汇数: {analysis['task_1b']['total_visual_words']}
- 平均视觉词汇/turn: {analysis['task_1b'].get('avg_visual_words_per_turn', 'N/A'):.2f}
- 目标: < 2.0

状态: **{'PASS' if analysis['task_1b'].get('pass') else 'FAIL'}**

---

## 3. Task 1C - 截断修复

- 总响应数: {analysis['task_1c']['total_responses']}
- 截断响应数: {analysis['task_1c']['truncated_responses']}
- 截断率: {analysis['task_1c']['truncation_rate']:.1f}% (目标: 0%)

状态: **{'PASS' if analysis['task_1c']['pass'] else 'FAIL'}**

---

## 4. Task 1D - Batch 集成

- 总任务数: {analysis['task_1d']['total_tasks']}
- 有 turn 详情的任务: {analysis['task_1d']['tasks_with_turns']}
- 覆盖率: {analysis['task_1d']['coverage']:.1f}% (目标: 100%)

状态: **{'PASS' if analysis['task_1d']['pass'] else 'FAIL'}**

---

## 5. Task 2A - 评估系统修复

### 非多模态模型 (Baseline)
- 平均分数: {analysis['task_2a']['nonmm_avg_score']:.2f} (目标: < 0.3)
- Faithfulness: {analysis['task_2a']['nonmm_faithfulness']:.2f} (目标: < 0.2)

### 多模态模型
- 平均分数: {analysis['task_2a']['mm_avg_score']:.2f} (目标: > 0.6)
- Faithfulness: {analysis['task_2a']['mm_faithfulness']:.2f} (目标: > 0.6)

### Score Gap
- Gap: {analysis['task_2a']['score_gap']:.2f} (目标: > 0.4)

状态: **{'PASS' if analysis['task_2a']['pass'] else 'FAIL'}**

---

## 6. Task 2B - 动作空间扩展

- 唯一动作种类: {analysis['task_2b']['unique_actions']} (目标: >= 8)
- 最大单一动作占比: {analysis['task_2b']['max_action_pct']:.1f}% (目标: <= 40%)

动作分布:
{analysis['task_2b']['action_distribution']}

状态: **{'PASS' if analysis['task_2b']['pass'] else 'FAIL'}**

---

## 总结

通过的任务: {sum(1 for k, v in analysis.items() if isinstance(v, dict) and v.get('pass'))} / 6

整体状态: **{'ALL PASS - 系统达标' if all(v.get('pass') for k, v in analysis.items() if isinstance(v, dict)) else 'PARTIAL FAIL - 需要修复'}**

---

## 后续建议

### 已达标的任务

{_generate_passed_tasks_summary(analysis)}

### 需要改进的任务

{_generate_failed_tasks_recommendations(analysis)}

### 性能优化建议

1. **API调用优化**: 考虑实现更智能的缓存机制，减少重复调用
2. **并行处理**: 对独立的任务可以考虑并行执行，提升总体效率
3. **错误恢复**: 增强重试机制，处理临时性的API失败（如503错误）

### 扩展功能建议

1. **更多模型支持**: 测试更多多模态和非多模态模型的���比
2. **可视化报告**: 生成图表展示各项指标的对比和趋势
3. **持续集成**: 将验证脚本集成到CI/CD流程中

### 已知限制

- Task 1B的视觉词汇计数可能需要更精细的NLP分析
- Task 2B的动作种类依赖于模型的实际行为，可能需要更多样化的任务来激发
- 评估指标的阈值（如0.3, 0.6）可能需要根据实际应用场景调整

---

## 附录

### 运行环境

- 测试目录: {analysis['test_directory']}
- 生成时间: {analysis['timestamp']}
- 分析的日志文件数量: 详见各任务详情

### 如何重现

```bash
# 1. 运行验证脚本
python task/verify_all.py {analysis['test_directory']}

# 2. 生成报告
python task/generate_report.py {analysis['test_directory']} report.md
```

### 联系方式

如有问题或建议，请参考项目文档或提交Issue。
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"报告已生成: {output_path}")

if __name__ == "__main__":
    import sys
    test_dir = sys.argv[1] if len(sys.argv) > 1 else "test_output"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "validation_report.md"

    analysis = analyze_logs(test_dir)
    generate_markdown_report(analysis, output_path)
