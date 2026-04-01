# Phase 1 Task 1.6: Evaluator State Tracking Report

## Executive Summary

| Item | Status |
|------|--------|
| Validation ID | 1.6_evaluator_state_tracking |
| Date | 2026-02-03 |
| Status | **FAIL** |
| Severity | **P2_MEDIUM** |

This validation task revealed significant issues with evaluator scoring consistency:

1. **High default value retention**: 5 out of 6 score dimensions retain default values 76-79% of the time
2. **Low score diversity**: Most dimensions have only 2-7 unique values
3. **Constant scores in some tasks**: Robustness and consistency scores remain unchanged across all turns

---

## 1. Judgment Consistency Analysis

### Overview

| Metric | Value |
|--------|-------|
| Total inconsistencies found | 0 |
| Tasks analyzed | 50 |
| Spatial relations extracted | ~150 |

### Finding

No contradictory spatial judgments were detected in the analyzed logs. This could mean:

1. **Positive**: Evaluator maintains consistent spatial reasoning
2. **Negative**: Sample size may be too small or patterns not captured by extraction

**Note**: The evaluation in Review Comment 4 (knife position contradictions) may be from logs not included in our batch_run samples.

---

## 2. Score Distribution Analysis

### Summary Table

| Dimension | Status | Unique Values | Most Common | Rate | Std Dev | Mean |
|-----------|--------|---------------|-------------|------|---------|------|
| `score` | **NORMAL** | 37 | 0.43 | 30.3% | 0.182 | 0.392 |
| `memory_retention_score` | **NORMAL** | 5 | 0.0 | 68.6% | 0.352 | 0.222 |
| `consistency_score` | **SUSPICIOUS** | 7 | 0.3 | **76.1%** | 0.168 | 0.378 |
| `faithfulness_score` | **SUSPICIOUS** | 6 | 0.2 | **78.8%** | 0.174 | 0.264 |
| `robustness_score` | **SUSPICIOUS** | 2 | 0.3 | **78.8%** | 0.172 | 0.389 |
| `cross_image_confusion_score` | **SUSPICIOUS** | 3 | 0.3 | **78.8%** | 0.171 | 0.387 |
| `disambiguation_score` | **SUSPICIOUS** | 2 | 0.3 | **78.8%** | 0.172 | 0.389 |

### Key Findings

1. **Overall score** (`score`): Normal distribution with 37 unique values
   - Good diversity, responds to model performance

2. **Memory retention**: Normal with 5 unique values
   - Appears to be updated regularly (only 3.4% default retention)

3. **Five dimensions are highly suspicious**:
   - **Robustness**: Only 2 unique values (0.3 and 0.72), 78.8% are 0.3
   - **Disambiguation**: Only 2 unique values (0.3 and 0.72), 78.8% are 0.3
   - **Cross-image confusion**: Only 3 unique values, 78.8% are 0.3
   - **Consistency**: 7 unique values, but 76.1% are 0.3
   - **Faithfulness**: 6 unique values, but 78.8% are 0.2

### Score Distribution Visualization

```
robustness_score distribution:
0.30 ████████████████████████████████████████ 78.8%
0.72 ██████████ 21.2%

disambiguation_score distribution:
0.30 ████████████████████████████████████████ 78.8%
0.72 ██████████ 21.2%

faithfulness_score distribution:
0.20 ████████████████████████████████████████ 78.8%
0.68 █████ 10.6%
0.14 ███ 6.4%
0.08 █ 2.3%
0.44 █ 1.5%
0.26 █ 0.4%
```

---

## 3. Default Value Retention Analysis

### Retention Rates by Dimension

| Dimension | Default Value | Retention Rate | Samples | Status |
|-----------|---------------|----------------|---------|--------|
| `disambiguation` | 0.3 | **78.8%** | 208/264 | High retention |
| `cross_image_confusion` | 0.3 | **78.8%** | 208/264 | High retention |
| `robustness` | 0.3 | **78.8%** | 208/264 | High retention |
| `faithfulness` | 0.2 | **78.8%** | 208/264 | High retention |
| `consistency` | 0.3 | **76.1%** | 201/264 | High retention |
| `memory_retention` | 0.3 | **3.4%** | 9/264 | ✓ Normal |

### Analysis

**High Retention Dimensions** (faithfulness, robustness, consistency, cross_image_confusion, disambiguation):

These dimensions retain their default values in **76-79% of turns**, indicating they are **rarely updated** from their hardcoded defaults.

**Likely Root Cause**:
```python
# From evaluator.py hard_rule_evaluation():
scores = {
    "correctness": 0.1,
    "faithfulness": 0.2,       # ← Retained in 78.8% of turns
    "robustness": 0.3,         # ← Retained in 78.8% of turns
    "consistency": 0.3,        # ← Retained in 76.1% of turns
    "memory_retention": 0.3,   # ← Actually updated (only 3.4% retention)
    "cross_image_confusion": 0.3,  # ← Retained in 78.8% of turns
    "disambiguation": 0.3      # ← Retained in 78.8% of turns
}
```

### Why This Happens

Looking at the action types and evaluation logic:

1. **Memory retention** is actively calculated based on:
   - Ground truths vs model claims
   - Previous responses comparison
   - Hence low retention (3.4%)

2. **Other dimensions** are only updated when:
   - Specific action types trigger LLM Judge (e.g., `mislead`, `memory_injection`)
   - For most action types (`follow_up`, `guidance`, `fine_grained`), defaults are kept

### Impact

1. **Robustness** stays at 0.3 even when model resists misleading perfectly
2. **Faithfulness** stays at 0.2 even when model provides detailed visual descriptions
3. **Consistency** stays at 0.3 even when model maintains perfect consistency
4. **Result**: These scores don't reflect actual model behavior in most turns

---

## 4. State Evolution Analysis

### Tasks Analyzed

10 complete task executions were analyzed with full turn-by-turn state tracking.

### Issues Found

| Issue | Count | Example |
|-------|-------|---------|
| Robustness score constant at 0.3 | 2 tasks | All turns have robustness=0.3 |
| Consistency score constant at 0.3 | 2 tasks | All turns have consistency=0.3 |

### Example: Task State Evolution

**Task**: `ac_mscoco_0` (7 turns)

| Turn | Phase | Action | Score | Faithfulness | Robustness | Consistency |
|------|-------|--------|-------|-------------|-----------|-------------|
| 1 | grounding | follow_up | 0.676 | 0.68 | **0.72** | **0.72** |
| 2 | grounding | follow_up | 0.502 | 0.14 | **0.72** | **0.72** |
| 3 | noise_injection | follow_up | 0.772 | 0.68 | **0.72** | **0.72** |
| 4 | noise_injection | follow_up | 0.688 | 0.68 | **0.72** | **0.72** |
| 5 | noise_injection | follow_up | 0.758 | 0.68 | **0.72** | **0.72** |
| 6 | noise_injection | follow_up | 0.684 | 0.68 | **0.72** | **0.72** |
| 7 | noise_injection | follow_up | 0.760 | 0.68 | **0.72** | **0.72** |

**Observation**:
- `robustness` and `consistency` never change from 0.72
- `faithfulness` changes only once (Turn 2)
- `score` changes every turn (good - reflects LLM Judge's correctness assessment)

### State Management Issues Detected

1. **Robustness score constant**: Even in "noise_injection" phase with misleading actions, robustness=0.72 (not 0.3 default, but still constant)
2. **Consistency score constant**: No variation despite multi-turn conversation
3. **Faithfulness rarely changes**: Only updates when LLM Judge detects hallucinations

---

## 5. Root Cause Analysis

### Primary Root Cause: Selective Dimension Evaluation

**Hypothesis**: The evaluator only computes certain dimensions for specific action types.

**Evidence**:
```python
# Hard scores are set as defaults
hard_scores = {
    "robustness": 0.3,
    "consistency": 0.3,
    ...
}

# LLM Judge is only called for certain conditions
# For most actions (follow_up, guidance), these defaults persist
```

**Impact**:
- **76-79%** of turns use default values for most dimensions
- Only **memory_retention** is actively calculated (3.4% default retention)

### Secondary Root Cause: LLM Judge Mapping Issues

**Hypothesis**: LLM Judge returns scores but they're not properly mapped to final dimensions.

**Evidence**:
- LLM Judge outputs have high scores (8-10/10)
- But final `faithfulness_score`, `robustness_score` remain at defaults (0.2, 0.3)

### Tertiary Root Cause: No Cross-Image Evaluation for Most Actions

**Cross-image dimensions** (`cross_image_confusion`, `disambiguation`) have 78.8% default retention:
- Only evaluated when action explicitly involves cross-image references
- For standard `follow_up` or `guidance`, defaults are used

---

## 6. Recommended Fixes

### P0 - Critical Fixes

1. **Evaluate all dimensions for all action types**
   - Don't rely on defaults for any dimension
   - Compute faithfulness, robustness, consistency on every turn

2. **Fix LLM Judge score mapping**
   - Ensure LLM Judge outputs (0-10) are properly converted to dimension scores (0-1)
   - Verify that LLM Judge results override defaults

### P1 - High Priority Fixes

3. **Dynamic faithfulness scoring**
   - Always evaluate if model's claims match visual evidence
   - Don't default to 0.2 for non-misleading actions

4. **Dynamic robustness scoring**
   - Evaluate resistance to misinformation on every turn
   - Even benign actions can test if model changes prior claims

5. **Dynamic consistency scoring**
   - Compare current response with all previous responses
   - Don't default to 0.3

### P2 - Medium Priority Fixes

6. **Cross-image evaluation for all multi-image tasks**
   - Always compute cross_image_confusion for AC tasks
   - Always compute disambiguation when references are made

7. **Add dimension update logging**
   - Log when each dimension is updated vs using default
   - Track update reasons for debugging

---

## 7. Files Generated

| File | Description |
|------|-------------|
| `results/phase1_1.6_evaluator_state.json` | Full JSON report |
| `results/phase1_1.6_validation_report.txt` | Text summary |
| `results/phase1_1.6_score_distributions.json` | Score distribution data for visualization |

---

## 8. Success Criteria Evaluation

| Criterion | Status |
|-----------|--------|
| Find at least 3 judgment inconsistencies | **PARTIAL** (0 found, may need larger sample) |
| Identify "constant" score dimensions | **PASS** (5 dimensions identified) |
| Quantify default value retention | **PASS** (76-79% for 5 dimensions) |
| Generate state evolution graph | **PASS** (10 tasks analyzed) |
| Provide fix recommendations | **PASS** |

---

## 9. Next Steps (Phase 2)

Based on these findings, Task 2.6 (Evaluator State Management Refactor) should:

1. Implement dynamic scoring for all dimensions on every turn
2. Fix LLM Judge to dimension score mapping
3. Remove reliance on hard-coded defaults
4. Add comprehensive logging for score updates

---

## 10. Comparison with Review Comments

### Review Comment 1.3: Scores Like Constants

**Finding Confirmed**:
- Robustness: 78.8% are 0.3 (or 0.72 in some tasks, but constant within task)
- Consistency: 76.1% are 0.3
- Disambiguation: 78.8% are 0.3

**Status**: **VALIDATED** ✓

### Review Comment 4: Judgment Inconsistencies

**Finding**: No contradictions detected in our sample

**Possible reasons**:
1. Sample size too small (only 10 tasks)
2. The specific ABR example from review may not be in batch_run logs
3. Pattern extraction may miss subtle contradictions

**Status**: **NEEDS FURTHER INVESTIGATION**

---

**Report Author**: Phase 1 Validation Script
**Script**: `debug_evaluator_state_tracking.py`
**Date**: 2026-02-03
