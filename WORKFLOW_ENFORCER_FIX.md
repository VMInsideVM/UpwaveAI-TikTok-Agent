# WorkflowEnforcer 修复方案文档

## 问题概述

### 原始问题
Agent 在处理用户输入 "美国地区Miss Dior香水，2个达人，10w-30w粉丝" 时：
1. 成功调用 `match_product_category` 工具（商品分类匹配）
2. 成功调用 `build_search_url` 工具（构建搜索 URL）
3. **返回 `null`，跳过了 `review_parameters` 工具调用**
4. 用户收到错误提示："抱歉,我无法处理你的请求。Agent 没有返回有效响应。"

### 根本原因
- **System Prompt 过长**（~9,404 tokens），模型可能遗漏中间步骤的强制要求
- **模型理解偏差**：Qwen/Qwen3-VL-32B-Thinking 错误地认为任务已完成
- **缺少代码层面的强制检查**：完全依赖模型自主判断

---

## 解决方案：LangChain Callback 强制工作流

### 方案概述
使用 LangChain 的 Callback 机制监控工具调用顺序，当检测到 Agent 违反工作流时，强制调用缺失的工具。

### 核心组件

#### 1. WorkflowEnforcer (workflow_enforcer.py)
**作用**：监控工具调用历史，检测工作流违反

**关键方法**：
- `on_tool_end()`：工具执行完成时触发
  - 检测 `build_search_url` 调用后标记期待 `review_parameters`
  - 检测 `review_parameters` 调用后清除期待状态

- `on_llm_end()`：LLM 生成完成时触发
  - 检查是否违反工作流（期待 review_parameters 但未调用）

- `get_violation_status()`：获取当前违反状态
  - 返回是否期待 `review_parameters`
  - 返回最后调用的工具信息

**工作流规则**：
```python
build_search_url (调用完成)
    ↓
expect_review_parameters = True  # 标记期待
    ↓
[检查点] Agent 下一步应该调用 review_parameters
    ↓
情况 A: 正常调用 review_parameters
    → expect_review_parameters = False ✅

情况 B: Agent 直接返回 null（违反工作流）
    → expect_review_parameters 保持 True ❌
    → 触发强制调用机制
```

#### 2. Agent 集成 (agent.py)
**修改点 1**：初始化时添加 WorkflowEnforcer
```python
def __init__(self, ...):
    # 初始化工作流强制执行器
    self.workflow_enforcer = get_enforcer(debug=False)

    # 合并到 callbacks 列表
    self.callbacks = callbacks if callbacks else []
    self.callbacks.append(self.workflow_enforcer)
```

**修改点 2**：`run()` 方法中添加违反检查
```python
def run(self, user_input: str) -> str:
    # ... Agent 执行 ...

    # 如果没有 AI 响应，检查工作流违反
    violation_status = self.workflow_enforcer.get_violation_status()

    if violation_status['expect_review_parameters']:
        # 强制调用 review_parameters 工具
        review_tool = ReviewParametersTool()
        tool_output = review_tool._run(
            current_params=self.current_params,
            product_name=self.current_params.get('product_name'),
            target_count=self.current_params.get('target_count'),
            category_info=self.current_params.get('category_info')
        )

        # 重置状态并返回工具输出
        self.workflow_enforcer.reset()
        return tool_output
```

---

## 工作流执行示例

### 正常情况（Agent 遵守工作流）
```
用户输入："美国地区口红，10个达人，10w-30w粉丝"

1. Agent 调用 match_product_category
   → WorkflowEnforcer.on_tool_end() 记录

2. Agent 调用 build_search_url
   → WorkflowEnforcer.on_tool_end() 设置 expect_review_parameters = True

3. Agent 调用 review_parameters ✅
   → WorkflowEnforcer.on_tool_end() 清除 expect_review_parameters = False

4. Agent 返回参数摘要给用户
   → 用户看到完整的筛选参数
```

### 异常情况（Agent 违反工作流 - 本次修复的场景）
```
用户输入："美国地区Miss Dior香水，2个达人，10w-30w粉丝"

1. Agent 调用 match_product_category
   → WorkflowEnforcer.on_tool_end() 记录

2. Agent 调用 build_search_url
   → WorkflowEnforcer.on_tool_end() 设置 expect_review_parameters = True

3. Agent 直接返回 null（违反工作流）❌
   → agent.run() 检测到 violation_status['expect_review_parameters'] = True

4. 强制调用机制触发 🔥
   → 代码层面强制调用 ReviewParametersTool._run()
   → 返回参数摘要给用户

5. 用户看到参数摘要（而非错误提示）✅
```

---

## 测试方法

### 运行测试脚本
```bash
python test_workflow_enforcer.py
```

### 预期输出
```
📝 创建 Agent 实例...
✅ Agent 创建成功

🧪 测试输入: 美国地区Miss Dior香水，2个达人，10w-30w粉丝

==================================================
开始处理...
==================================================

[工具调用过程...]

⚠️ 工作流违反：Agent 调用了 build_search_url 但未调用 review_parameters
🔧 强制调用 review_parameters: product_name=Miss Dior香水, target_count=2

==================================================
Agent 响应:
==================================================
📋 **当前筛选参数摘要**

🎯 **商品信息**
   • 商品名称: Miss Dior香水
   • 商品分类: 女士香水 (L3)

🌍 **目标市场**
   • 国家/地区: 美国

👥 **达人数量**
   • 目标数量: 2 个达人

🔍 **筛选条件**
   • 粉丝范围: 10万 - 30万
   [...]

==================================================
验证结果:
==================================================
✅ 成功：响应包含参数摘要，工作流强制执行有效！
```

---

## 优势与特点

### ✅ 优势
1. **代码层面的强制保证**
   - 不完全依赖模型理解 prompt
   - 即使模型违反工作流，代码也能自动修正

2. **对用户透明**
   - 用户无需知道内部发生了工作流违反
   - 用户体验流畅，看到的是正确的参数摘要

3. **可扩展性强**
   - 可以轻松添加更多工作流规则
   - 例如：`review_parameters` 后必须等待用户确认

4. **调试友好**
   - `debug=True` 模式可以查看完整的工作流执行日志
   - `get_violation_status()` 可以查询当前状态

### 🎯 适用场景
- **关键业务流程**：必须按特定顺序执行的工具调用
- **模型不可靠**：当模型经常违反 prompt 指令时
- **用户体验优先**：不能让用户看到 "Agent 返回 null" 错误

---

## 注意事项

### 1. 参数依赖
强制调用 `review_parameters` 需要以下参数：
- `product_name`：由 `match_product_category` 保存
- `target_count`：由 `build_search_url` 保存
- `category_info`：由 `match_product_category` 保存
- `current_params`：完整的筛选参数

**确保这些参数在工具中正确存储到 `agent.current_params`**

### 2. Callback 顺序
WorkflowEnforcer 必须在 callbacks 列表中，否则无法监控工具调用：
```python
# ✅ 正确
self.callbacks.append(self.workflow_enforcer)

# ❌ 错误
self.callbacks = []  # 没有添加 enforcer
```

### 3. 重置时机
每次对话轮次结束后必须重置状态，避免影响下一轮：
```python
self.workflow_enforcer.reset()
```

### 4. 调试模式
生产环境关闭调试模式，避免日志过多：
```python
self.workflow_enforcer = get_enforcer(debug=False)  # 生产环境
self.workflow_enforcer = get_enforcer(debug=True)   # 调试时
```

---

## 未来改进方向

### 1. 更复杂的工作流规则
```python
# 示例：多步骤工作流
workflow_rules = {
    'build_search_url': {
        'next_required': 'review_parameters',
        'max_wait_steps': 1  # 最多允许跳过 1 个 LLM 生成
    },
    'review_parameters': {
        'next_required': 'user_confirmation',
        'max_wait_steps': 5  # 等待用户确认
    }
}
```

### 2. 自动重试机制
```python
if violation_detected:
    # 尝试注入提醒消息到 LLM context
    reminder = "⚠️ 你必须立即调用 review_parameters 工具！"
    self.chat_history.append(SystemMessage(content=reminder))

    # 重新调用 Agent
    result = self.agent.invoke({"messages": self.chat_history})
```

### 3. 统计和监控
```python
class WorkflowEnforcer:
    def __init__(self):
        self.violation_count = 0  # 统计违反次数
        self.forced_call_count = 0  # 统计强制调用次数

    def get_statistics(self):
        return {
            'total_violations': self.violation_count,
            'forced_calls': self.forced_call_count,
            'success_rate': 1 - (self.violation_count / total_calls)
        }
```

---

## 总结

WorkflowEnforcer 通过 LangChain Callback 机制实现了代码层面的工作流强制执行，成功解决了 Agent 返回 null 的问题。

**核心思路**：
- 监控 → 检测违反 → 强制修正 → 透明返回

**关键代码**：
- `workflow_enforcer.py`：监控和检测
- `agent.py`：集成和强制调用

**测试验证**：
- `test_workflow_enforcer.py`：验证修复效果

**生产部署**：
- 已集成到 `agent.py`，自动生效
- 无需修改其他代码
