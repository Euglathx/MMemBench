# Phase 1 Task 1.5: Multi-Image Strategy Validation Report

## Executive Summary

| Item | Status |
|------|--------|
| Validation ID | 1.5_multi_image_strategy |
| Date | 2026-02-03 |
| Status | **FAIL** |
| Severity | **P1_HIGH** |

This validation task uncovered significant issues with multi-image task handling in M3Bench:

1. **Inconsistent image sending**: 54% of turns send no images, 43% send all 3 images
2. **Strategy mismatch**: Two simulators use completely different image injection strategies
3. **Task definition misalignment**: 200 AC tasks have question/expected_answer mismatch

---

## 1. Image Sending Statistics

### Overview

| Metric | Value | Percentage |
|--------|-------|------------|
| Total AC turns analyzed | 224 | 100% |
| All images sent (3 images) | 96 | 42.9% |
| Some images sent (1-2) | 7 | 3.1% |
| No images sent (0) | 121 | **54.0%** |

### Distribution by Image Count

| Images Sent | Turn Count | Notes |
|-------------|------------|-------|
| 0 images | 121 turns | **Problem**: VLM cannot see anything |
| 1 image | 7 turns | Partial visibility |
| 3 images | 96 turns | Full visibility (correct) |

### Analysis

The data reveals a bimodal distribution:
- **~54% of turns** send **zero images** - the VLM is essentially blind
- **~43% of turns** send **all 3 images** - correct behavior

This inconsistency likely causes:
- Hallucinated responses when no images are sent
- Cross-image confusion when evaluating responses

---

## 2. Simulator Strategy Comparison

### Strategy Comparison

| Simulator | Policy | Implementation |
|-----------|--------|----------------|
| **StrategicSimulator** | `send_all_every_turn` | `_get_images_for_turn()` returns all valid images |
| **LLMUserSimulator** | `progressive` | `_get_images_to_send()` sends one at a time |

### Code Analysis

**StrategicSimulator** (`strategic_simulator.py:890-919`):
```python
def _get_images_for_turn(self, action: str) -> List[str]:
    """Determine which images to send for current turn

    For multimodal testing, we need to send ALL images on EVERY turn
    so the model can actually see and process the visual content.
    """
    # Send all images for all actions
    ...
```

**LLMUserSimulator** (`llm_user_simulator.py:517-537`):
```python
def _get_images_to_send(self, action: str) -> List[str]:
    """确定要发送给待测 VLM 的图片"""
    if action == "guidance" and task_images:
        # For guidance, show next image if not all shown
        if len(self.images_shown) < len(task_images):
            next_img_idx = len(self.images_shown)
            ...
```

### Finding

- **Used in batch run**: StrategicSimulator
- **Consistency**: **INCONSISTENT**
- **Impact**: If LLMUserSimulator were used instead, images would be sent progressively, leading to different (and potentially confusing) VLM experiences

---

## 3. Task Definition Alignment Analysis

### Overview

| Metric | Value |
|--------|-------|
| Total AC tasks checked | ~200 |
| Misaligned tasks | **200** |
| Misalignment rate | **~100%** |

### Common Misalignment Patterns

#### Pattern 1: Comparison Question with Single-Image Answer

**Example** (ac_mscoco_1):
- **Question**: "Count the person in each image. Which has more?"
- **Images**: 3 images
- **Expected**: "Image 0 has 3 person(s)"

**Issue**: Question asks "which has more" (comparison) but expected answer only mentions one image.

#### Pattern 2: Position Question with Incomplete Answer

**Example** (ac_mscoco_0):
- **Question**: "In which image is the person positioned bottommost?"
- **Images**: 3 images
- **Expected**: "Image 2 has the person bottommost"

**Issue**: While the answer identifies the correct image, it doesn't provide comparison context.

### Impact Analysis

1. **Evaluator confusion**: LLM Judge may mark correct comparative answers as wrong
2. **Scoring inconsistency**: Model gives "Image 2 has more persons than Image 0 and Image 1" but expected is only "Image 0 has 3 person(s)"
3. **Cross-image attribution issues**: Cannot properly evaluate if model correctly compared across images

---

## 4. Evaluator Image Awareness

### Findings

| Check | Result |
|-------|--------|
| Receives `images_sent` parameter | **False** |
| LLM Judge prompt accurate | True |
| Inconsistent cases found | 0 |

### Analysis

The evaluator does **not** receive information about which images were actually sent to the VLM. This means:

1. Evaluator cannot know if VLM had visibility to make visual claims
2. Hallucination detection is compromised when images weren't sent
3. Cross-image confusion scoring is unreliable

---

## 5. Root Causes Identified

1. **Inconsistent image sending**: Some turns send all images, others send none
   - Likely cause: Image path resolution failures in some runs
   - Impact: VLM cannot see images in ~54% of turns

2. **Strategy mismatch between simulators**: StrategicSimulator uses "send all" while LLMUserSimulator uses "progressive"
   - Impact: Inconsistent testing across different runs

3. **Task definition misalignment**: Expected answers don't match question types
   - Likely cause: Task generator creates single-image answers for multi-image questions
   - Impact: Incorrect evaluation of valid comparative responses

---

## 6. Recommended Fixes

### P0 - Critical Fixes

1. **Unify image sending strategy across simulators**
   - Recommend: Always send all task images on every turn
   - Implementation: Update LLMUserSimulator to match StrategicSimulator

2. **Fix image path resolution**
   - Root cause of 54% zero-image turns
   - Ensure consistent path handling across all runs

### P1 - High Priority Fixes

3. **Fix task definitions**
   - For comparison questions: Expected should be comparison result (e.g., "Image 0 has more than Image 1 and Image 2")
   - For counting questions: Expected should include all images' counts

4. **Pass `images_sent` to evaluator**
   - Allow evaluator to know what the VLM could actually see
   - Enable proper hallucination detection

### P2 - Medium Priority Fixes

5. **Add cross-image validation in task generator**
   - Validate that expected_answer type matches question type
   - Add automated checks for multi-image task consistency

---

## 7. Files Generated

| File | Description |
|------|-------------|
| `results/phase1_1.5_multi_image.json` | Full JSON report |
| `results/phase1_1.5_validation_report.txt` | Text summary |
| `results/phase1_1.5_misaligned_tasks.csv` | Misaligned task details |

---

## 8. Success Criteria Evaluation

| Criterion | Status |
|-----------|--------|
| Analyze at least 100 AC task turns | **PASS** (224 turns) |
| Clarify difference between simulator strategies | **PASS** |
| Find all misaligned task definitions | **PASS** (200 found) |
| Verify evaluator image perception issues | **PASS** |
| Provide fix recommendations | **PASS** |

---

## 9. Next Steps (Phase 2)

Based on these findings, Task 2.5 (Multi-Image Strategy Unification) should:

1. Implement unified image sending in both simulators
2. Fix image path resolution issues
3. Update task generator to create aligned expected answers
4. Add images_sent parameter to evaluator interface

---

**Report Author**: Phase 1 Validation Script
**Script**: `debug_multi_image_strategy.py`
**Date**: 2026-02-03
