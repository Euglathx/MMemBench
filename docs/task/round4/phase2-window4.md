# Phase 2 Window 4: Consistency Check 图像传递修复

**任务编号**: ROUND4-P2-W4
**预计时间**: 1-2 小时
**依赖**: Phase 1 完成
**优先级**: P1 - MEDIUM
**可并行**: 与 Window 1, 2, 3 完全并行

---

## 任务目标

修复评审报告 5.2 问题：最终 consistency check 时模型回复 "I can't view images"。

**问题**: `run_consistency_check()` 的调用链中图像参数传递有问题，或者 consistency check 使用的 prompt 格式与常规 turn 不同。

---

## 背景信息

### 评审发现
AC_0 任务的最终 consistency_check 中：
- 模型回复: "I can't view the images right now..."
- 说明调用时没有传递图像参数

### 已知
- 前面的 turns 都能看到图像
- 只有最后的 consistency check 没有图像

---

## 任务详细要求

### 1. 找到 consistency_check 调用位置

**文件**: `src/simulator/strategic_simulator.py`

**搜索**: `run_consistency_check` 或 `consistency_check`

### 2. 检查图像传递

**检查点**:

#### 2.1 `run_consistency_check()` 方法

```python
def run_consistency_check(self):
    """运行最终一致性检查"""

    # 检查：是否调用了 _get_images_for_turn()?
    images_to_send = self._get_images_for_turn("consistency_check")  # ✓ 应该有这行

    # 检查：是否传递给模型?
    response = self.target_model.generate(
        messages=[...],
        images=images_to_send  # ✓ 应该传递
    )
```

#### 2.2 `_get_images_for_turn()` 是否支持 "consistency_check" action?

检查 `_get_images_for_turn()` 方法：

```python
def _get_images_for_turn(self, action: str) -> List[str]:
    """获取这个 turn 应该发送的图像"""

    # 检查：是否有针对 "consistency_check" 的特殊处理?
    if action == "consistency_check":
        # 应该返回所有任务图像（或根据策略）
        return self.task_state.images  # ✓
```

### 3. 修复逻辑

#### 修复方案 1: 确保调用 _get_images_for_turn()

如果 `run_consistency_check()` 没有调用图像获取：

```python
def run_consistency_check(self):
    """运行最终一致性检查"""
    # NEW: 确保传递图像
    images_to_send = self._get_images_for_turn("consistency_check")

    # 添加验证
    if not images_to_send and self.task_state.images:
        # 如果没有获取到图像但任务有图像，这是 bug
        error_msg = (
            f"[Critical] Consistency check failed to get images for task {self.task_state.task_id}. "
            f"Expected {len(self.task_state.images)} images, got 0."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(
        f"[Consistency Check] Sending {len(images_to_send)} images "
        f"(task has {len(self.task_state.images)} total images)"
    )

    # 生成 consistency prompt
    prompt = self._generate_consistency_check_from_ground_truth()

    # 调用模型（确保传递图像）
    response = self.target_model.generate(
        messages=[{"role": "user", "content": prompt}],
        images=images_to_send  # ✓ 确保传递
    )

    return response
```

#### 修复方案 2: 修复 _get_images_for_turn() 支持

如果 `_get_images_for_turn()` 对 "consistency_check" 返回空列表：

```python
def _get_images_for_turn(self, action: str) -> List[str]:
    """获取这个 turn 应该发送的图像"""
    # ... 现有逻辑 ...

    # NEW: 特殊处理 consistency_check
    if action == "consistency_check":
        # Consistency check 应该发送所有任务图像
        logger.debug(
            f"[Image Injection] Action 'consistency_check': "
            f"sending all {len(self.task_state.images)} task images"
        )
        return self._resolve_image_paths(self.task_state.images)

    # ... 现有逻辑 ...
```

#### 修复方案 3: 检查 image_policy 配置

如果使用 `ImagePolicyManager`：

```python
# 在 ImagePolicyManager 中添加对 consistency_check 的支持
def get_images_for_action(self, action: str, all_images: List[str], turn: int) -> List[str]:
    """根据 action 返回应该发送的图像"""
    # ... 现有逻辑 ...

    # NEW: consistency_check 总是发送所有图像
    if action == "consistency_check":
        return all_images

    # ... 现有逻辑 ...
```

---

## 接口定义

### 输入
- Phase 1 验证报告
- 当前代码库

### 输出

#### 修改的文件
- `src/simulator/strategic_simulator.py` - 修复 `run_consistency_check()` 或 `_get_images_for_turn()`
- （可能）`src/simulator/image_policy.py` - 如果使用 image policy

#### 文档
- `docs/task/round4/phase2_fix2.3_report.md`

---

## 协作要求

**独立性**: 高
- 只修改 simulator 内部逻辑

**无冲突**: 与其他 windows 无代码冲突

---

## 验证标准

### Must Have
1. ✅ 运行任务到 consistency check
2. ✅ 检查模型响应，不应该说 "I can't view images"
3. ✅ 检查日志，显示发送了 N 张图像

### Nice to Have
1. 添加单元测试
2. 验证所有任务类型（ABR, AC）

---

## 测试方法

**集成测试脚本**: `scripts/round4_test_fix2.3.py`

```python
simulator = StrategicSimulator()
simulator.start_task(test_task)

# 运行到最后
while not simulator.is_task_complete():
    simulator.step()

# 检查 consistency check
run_log = simulator.get_run_log()
consistency_check = run_log.get("consistency_check", {})

# 验证
if "response" in consistency_check:
    response = consistency_check["response"]
    if "can't view" in response.lower() or "unable to see" in response.lower():
        print("❌ FAIL: 模型说无法看到图像")
    else:
        print("✅ PASS: 模型能看到图像")

    # 检查发送的图像
    images_sent = consistency_check.get("images_sent", [])
    print(f"Images sent: {len(images_sent)}")
    assert len(images_sent) > 0, "❌ FAIL: 未发送图像"
```

---

## 交付物清单

- [ ] 修改后的 `src/simulator/strategic_simulator.py`
- [ ] （可能）修改后的 `src/simulator/image_policy.py`
- [ ] 测试脚本 `scripts/round4_test_fix2.3.py`
- [ ] 修复报告 `docs/task/round4/phase2_fix2.3_report.md`

---

## 注意事项

1. **断言检查**: 添加 RuntimeError 如果应该有图像但实际没有
2. **日志详细**: 记录发送了多少图像
3. **向后兼容**: 确保旧任务仍能运行

---

**任务开始时间**: _____________
**任务完成时间**: _____________
**执行人**: _____________
