# 任务间接口契约

## 目的
确保并行任务不会产生代码冲突或接口不兼容。

---

## 文件修改映射表

| 文件 | Task 1A | Task 1B | Task 1C | Task 1D | Task 2A | Task 2B |
|------|---------|---------|---------|---------|---------|---------|
| `strategic_simulator.py` | ✅ Lines 558-567, 439-487 | ❌ | ✅ Lines 669, 806, ... | ✅ 添加conversation_history | ❌ | ✅ Lines 307-346 |
| `llm_user_simulator.py` | ✅ Lines 129-140 | ✅ 添加sanitize方法 | ❌ | ❌ | ❌ | ❌ |
| `batch_task_simulator.py` | ❌ | ❌ | ❌ | ✅ Lines 337-385 | ❌ | ❌ |
| `evaluator.py` | ❌ | ❌ | ❌ | ❌ | ✅ 多处 | ❌ |
| `action_selector.py` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Lines 148-194 |
| `action_space.py` | ❌ | ❌ | ❌ | ❌ | ✅ Lines 47-62 | ✅ difficulty_level |

### 潜在冲突

#### 冲突1: Task 1A vs Task 1C (都修改strategic_simulator.py)
**位置**:
- 1A: 修改函数定义和调用处
- 1C: 只修改max_tokens参数

**解决**:
1. Task 1C非常简单,建议先完成
2. 或者Task 1A在修改时注意保留1C的max_tokens=2048

**合并策略**:
```python
# Task 1A的修改
parsed = self._parse_core_response(
    content=response.get('content', ''),
    reasoning_content=response.get('reasoning_content', '')
)

# Task 1C的修改
target_response = self.llm_client.call_target_model(
    messages=target_messages,
    images=images_to_send if images_to_send else None,
    max_tokens=2048  # 1C的修改
)

# 两者不冲突,在不同行
```

#### 冲突2: Task 1A vs Task 1D (都修改strategic_simulator.py)
**位置**:
- 1A: 修改_parse_core_response函数
- 1D: 添加conversation_history属性

**解决**:
- 完全不同的修改点,无冲突
- 合并时无需特殊处理

#### 冲突3: Task 2A vs Task 2B (都可能修改action_space.py)
**位置**:
- 2A: 移除guidance的expected_answer
- 2B: 调整difficulty_level

**解决**:
- 不同的action定义字段
- 确保修改不同的action或同一action的不同字段

---

## 函数签名契约

### Contract 1: `_parse_core_response()`
**修改者**: Task 1A

**OLD签名**:
```python
def _parse_core_response(self, content: str) -> Dict[str, Any]:
```

**NEW签名**:
```python
def _parse_core_response(
    self,
    content: str,
    reasoning_content: str = ""  # 新增,有默认值
) -> Dict[str, Any]:
```

**影响**:
- 所有调用者需要更新,但因为有默认值,旧代码不会立即break
- Task 1C, 1D, 2B如果调用此函数,需要注意

**迁移**:
```python
# 兼容旧调用
parsed = self._parse_core_response(content)  # 仍然有效

# 新调用
parsed = self._parse_core_response(content, reasoning_content)  # 推荐
```

---

### Contract 2: `StrategicSimulator.conversation_history`
**修改者**: Task 1D

**新增属性**:
```python
class StrategicSimulator:
    def __init__(self, ...):
        self.conversation_history = []  # NEW
```

**影响**:
- 其他任务可以读取但不应修改
- Task 2B如果需要读取历史,可以用这个

**访问协议**:
```python
# 只读访问 (OK)
recent_actions = [h['action'] for h in self.conversation_history[-3:]]

# 修改 (仅Task 1D)
self.conversation_history.append({...})
```

---

### Contract 3: `LLMUserSimulator._sanitize_message_for_target()`
**修改者**: Task 1B

**新增方法**:
```python
def _sanitize_message_for_target(
    self,
    message: str,
    images: List[str]
) -> str:
    """Remove visual descriptions from message."""
```

**影响**:
- 私有方法,其他任务不应调用
- 只在llm_user_simulator内部使用

---

### Contract 4: `Evaluator._call_llm_judge()` 参数变更
**修改者**: Task 2A

**OLD调用**:
```python
llm_scores = self._call_llm_judge(
    response=response,
    expected_answer=expected_answer,
    ...
)
```

**NEW需求**: 传递task对象以获取images

```python
llm_scores = self._call_llm_judge(
    task=task,  # NEW
    response=response,
    expected_answer=expected_answer,
    ...
)
```

**影响**:
- 调用者需要传递task对象
- strategic_simulator.py中的evaluator调用需要更新

---

## 数据格式契约

### Format 1: Batch Result JSON
**定义者**: Task 1D

**格式**:
```json
{
  "task_id": "...",
  "task_type": "...",
  "completed": true,
  "turns_used": 5,
  "turns": [  // NEW字段
    {
      "turn": 0,
      "action": "guidance",
      "query": "...",
      "response": "...",
      "images_sent": ["..."],
      "evaluation": {...},
      "timestamp": "..."
    }
  ],
  "scores": {...}
}
```

**消费者**:
- `convert_batch_results_to_runlog.py`
- Task 3验证脚本

**兼容性**: 添加新字段,不影响现有字段读取

---

### Format 2: Run Log JSON
**保持不变**: 所有任务都应保持此格式

**格式**:
```json
[
  {
    "event": "task_start",
    "task_id": "...",
    ...
  },
  {
    "event": "core_model_decision",
    "turn": 0,
    "action": "...",
    "message_to_model": "...",
    ...
  },
  {
    "event": "target_model_response",
    "turn": 0,
    "target_response": "...",
    "evaluation": {...},
    ...
  }
]
```

**不应修改**: event类型, 核心字段名
**可添加**: 新字段(如parse_error标记)

---

## 配置文件契约

### Config 1: User Simulator配置
**修改者**: Task 1B

**新增配置**:
```yaml
# config/simulator.yaml
user_simulator:
  minimize_text_hints: true
  hint_level: "minimal"  # minimal | moderate | full
```

**其他任务**: 不应修改这些配置

---

### Config 2: Target Model max_tokens
**修改者**: Task 1C

**建议**: 添加到CLI参数或配置

```yaml
# config/simulator.yaml
simulator:
  target_max_tokens: 2048  # 从800增加
```

---

## 分支策略

### 推荐分支结构
```
main (或master)
  └── dev (开发主分支)
       ├── task-1a (Task 1A开发)
       ├── task-1b (Task 1B开发)
       ├── task-1c (Task 1C开发)
       ├── task-1d (Task 1D开发)
       ├── task-2a (Task 2A开发)
       └── task-2b (Task 2B开发)
```

### 合并流程

#### 阶段1结束
```bash
# 切换到dev
git checkout dev

# 合并Task 1A
git merge task-1a --no-ff

# 合并Task 1B (无冲突)
git merge task-1b --no-ff

# 合并Task 1C (可能与1A有strategic_simulator.py冲突)
git merge task-1c --no-ff
# 解决冲突: 保留1A的函数修改 + 1C的max_tokens修改

# 合并Task 1D
git merge task-1d --no-ff

# 运行测试
python task/verify_phase1.py

# 如果通过,推送dev
git push origin dev
```

---

## 测试数据共享

### 共享测试数据集
所有任务使用相同的测试数据:

```
generated_tasks_v2/run_18/tasks/
  ├── attribute_comparison_mscoco14.jsonl
  ├── attribute_comparison_vcr.jsonl
  └── ...
```

**协议**:
- ❌ 不要修改run_18数据
- ✅ 可以读取用于测试
- ✅ 创建新的test_output目录存储结果

### 测试输出隔离
每个任务使用独立的输出目录:

```
test_output/
  ├── task_1a/
  │   └── run_log_*.json
  ├── task_1b/
  ├── task_2a_nonmm/  # 非多模态测试
  ├── task_2a_mm/     # 多模态测试
  └── final/          # Task 3最终测试
```

---

## 冲突检测清单

在合并前检查:

```bash
# 检查文件冲突
git diff --name-only dev task-1a
git diff --name-only dev task-1b

# 如果同一文件被多个分支修改,检查具体行
git diff dev task-1a -- src/simulator/strategic_simulator.py
git diff dev task-1c -- src/simulator/strategic_simulator.py

# 查找同时修改的行
comm -12 \
  <(git diff dev task-1a --unified=0 | grep '^@@' | cut -d' ' -f3) \
  <(git diff dev task-1c --unified=0 | grep '^@@' | cut -d' ' -f3)
```

---

## 紧急回滚

如果合并后发现严重问题:

```bash
# 回滚到合并前
git reset --hard HEAD~1

# 或创建回滚分支
git checkout -b revert-task-1a
git revert <commit-hash>
```
