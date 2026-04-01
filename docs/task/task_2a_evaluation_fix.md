# Task 2A: 评估系统修复

## 任务优先级
**P1 - Week 2 Day 1-4** (在Task 1A-1D完成后)

## 可以并行
⚠️ **必须等待** Task 1A, 1B完成(需要稳定的对话和解析)
✅ 可以与Task 2B并行

## 任务目标
修复评估系统,使非多模态模型得分<0.3,多模态模型得分>0.6,真正测试视觉理解能力。

---

## 问题现状

### 核心问题
非多模态模型应该得分极低(<0.3),但实际可能很高(~0.7+)

### 根本原因
1. LLM judge不接收图像,无法验证视觉grounding
2. Hard rules默认分数过高(5/7维度=1.0)
3. Robustness检测过于宽松

---

## 需要修改的文件

### 文件: `src/simulator/evaluator.py`

#### 修改1: Lines 477-485 - 给Judge传图像

**NEW实现**:
```python
def _call_llm_judge(self, task: Dict, response: str, ...) -> Dict:
    user_content = [{"type": "text", "text": user_prompt}]

    # NEW: Add images
    if task.get('images'):
        for img_path in task['images']:
            base64_img = self._encode_image(img_path)
            if base64_img:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                })

    payload = {
        "model": self.evaluation_model,
        "messages": [
            {"role": "system", "content": LLM_JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}  # Multimodal
        ]
    }
```

#### 修改2: Lines 524-533 - 严格的默认分数

**OLD**:
```python
scores = {
    "correctness": 0.5,
    "faithfulness": 0.8,
    "robustness": 1.0,
    "consistency": 1.0,
    ...
}
```

**NEW**:
```python
scores = {
    "correctness": 0.1,     # 从0.5降到0.1
    "faithfulness": 0.2,    # 从0.8降到0.2
    "robustness": 0.3,      # 从1.0降到0.3
    "consistency": 0.3,     # 从1.0降到0.3
    "memory_retention": 0.3,
    "cross_image_confusion": 0.3,
    "disambiguation": 0.3
}
```

#### 修改3: Lines 585-604 - 强化Robustness检测

**NEW逻辑**: 需要BOTH抵抗phrase AND视觉grounding

```python
resisted = any(phrase in response_lower for phrase in resist_phrases)

# NEW: Also require visual grounding evidence
has_visual_grounding = any(phrase in response_lower for phrase in [
    "in the image", "the picture shows", "looking at",
    "visible in", "shown in the"
]) and len(response) > 50

if resisted and has_visual_grounding:
    scores["robustness"] = 1.0
elif resisted:
    scores["robustness"] = 0.6  # Partial credit
else:
    scores["robustness"] = 0.1
```

#### 修改4: Lines 116-191 - 更新Judge Prompt

在system prompt中添加:
```
CRITICAL: You MUST verify claims against the actual images.
- Correctness: Check if response matches what's VISIBLE
- Faithfulness: Penalize ANY claim not grounded in images
- If model can't see images but makes visual claims, score 0
```

---

## 验证

### 创建 `task/verify_task_2a.py`

```python
import json
import sys

def verify_evaluation_fix(log_file):
    with open(log_file) as f:
        events = json.load(f)

    evaluations = [
        e.get('evaluation', {})
        for e in events
        if e.get('event') == 'target_model_response'
    ]

    if not evaluations:
        print("No evaluations found")
        return False

    # Extract scores
    overall_scores = [
        eval.get('overall_score', 0)
        for eval in evaluations
        if 'overall_score' in eval
    ]

    avg_score = sum(overall_scores) / len(overall_scores)

    print(f"Average score: {avg_score:.3f}")
    print(f"Expected for non-multimodal: <0.3")
    print(f"Expected for multimodal: >0.6")

    # Check faithfulness scores specifically
    faithfulness_scores = [
        eval.get('scores', {}).get('faithfulness', 0)
        for eval in evaluations
        if 'scores' in eval
    ]

    if faithfulness_scores:
        avg_faith = sum(faithfulness_scores) / len(faithfulness_scores)
        print(f"Average faithfulness: {avg_faith:.3f}")
        print(f"Expected for non-multimodal: <0.2")

    return True

if __name__ == "__main__":
    verify_evaluation_fix(sys.argv[1])
```

### 对比测试

```bash
# Test with non-multimodal model
python run_experiment.py \
  --model gemini-3-flash-preview-nothinking \
  --num-tasks 5 \
  --output-dir test_output/task_2a_nonmm

python task/verify_task_2a.py test_output/task_2a_nonmm/run_log_*.json
# Expected: avg_score < 0.3

# Test with multimodal model
python run_experiment.py \
  --model gpt-4o \
  --num-tasks 5 \
  --output-dir test_output/task_2a_mm

python task/verify_task_2a.py test_output/task_2a_mm/run_log_*.json
# Expected: avg_score > 0.6
```

---

## 协作

**需要**:
- ✅ Task 1A, 1B完成: 稳定的对话质量
- ✅ Task 1D完成(可选): 用batch数据测试

**提供给**:
- Task 3: 准确的评估系统,用于最终验证

**冲突**:
- ❌ 与Task 2B无冲突

---

## 预期工作量
- **代码修改**: ~400 lines
- **验证脚本**: ~50 lines
- **测试时间**: 8 hours (多模态对比)
- **总时间**: 3 days
