# 响应验证器使用指南

## 功能概述

响应验证器（Response Validator）是一个自动检测机制，确保 Agent 在调用 `review_parameters` 工具后，必须将工具返回的完整内容展示给用户。

### 问题背景

在参数确认流程中，Agent 应该：
1. 调用 `review_parameters` 工具获取格式化的参数摘要
2. **完整复制**工具返回的文本发送给用户
3. **不得总结、改写、省略或添加**额外内容

但 LLM 经常会违反这个规则，例如：
- ❌ "好的，我已经为您整理了筛选参数，请确认..."（总结）
- ❌ "参数如下：商品女士香水，粉丝10万-25万..."（改写）
- ✅ 直接复制完整的参数摘要（正确）

## 工作原理

### 1. 工具调用记录

当 `review_parameters` 工具被调用时，会自动将输出记录到验证器：

```python
# 在 agent_tools.py 的 ReviewParametersTool._run() 中
from response_validator import get_validator

validator = get_validator()
validator.record_tool_call('review_parameters', output)
```

### 2. 响应验证

在 `chatbot_api.py` 的 `stream_agent_response()` 函数中：

```python
# 获取 agent 响应后
validator = get_validator(debug=True)
is_valid, retry_prompt = validator.validate_response(response)

if not is_valid:
    # 触发自动重试
    response = agent.run(retry_prompt)
```

### 3. 验证规则

验证器检查两个方面：

**A. 完整性检查** - 确保响应包含所有特征标记：
- "📋 **当前筛选参数摘要**"
- "🎯 **商品信息**"
- "🌍 **目标地区**"
- "🔍 **筛选条件**"
- "请确认以上参数是否满意"

**B. 违规模式检测** - 识别总结/改写行为：
- "参数如下："
- "已为您整理参数"
- "参数已展示"
- "请确认参数"（但没有完整展示）
- "好的，我已为您整理"

### 4. 自动重试机制

如果验证失败：

1. **第1次重试**：
   - 发送状态消息："检测到格式问题，正在重新生成回复...（1/2）"
   - 使用强制性重试提示重新调用 agent
   - 重新验证响应

2. **第2次重试**：
   - 如果仍然失败，再次重试
   - 最多重试 2 次

3. **重试失败**：
   - 如果 2 次重试后仍然失败，使用最后的响应（避免无限循环）

## 重试提示模板

重试提示包含：

```text
⚠️ **系统检测到错误**：你没有完整展示筛选参数！

**违规行为**：你对 review_parameters 工具返回的内容进行了总结、改写或省略。

**强制要求**：
1. **必须**将以下内容**逐字逐句**地复制到你的回复中
2. **不得**进行任何总结、改写、省略或添加
3. **不得**说"参数已展示"、"请确认参数"等额外话语
4. **直接**将下面的文本作为你的完整回复发送给用户

---

[工具返回的原始内容]

---

**立即重新生成回复**，严格遵守以上要求！
```

## 配置选项

### 调试模式

启用调试模式以查看详细的验证日志：

```python
# 在 chatbot_api.py 中
validator = get_validator(debug=True)  # 启用调试模式
```

调试输出示例：
```
[ResponseValidator] 记录工具调用: review_parameters
[ResponseValidator] 缺失标记: 🌍 **目标地区**
[ResponseValidator] 发现违规模式: 参数如下[：:]
⚠️ 响应验证失败（第 1/2 次），触发自动重试
```

### 最大重试次数

在 `chatbot_api.py` 中调整：

```python
MAX_RETRIES = 2  # 最多重试 2 次
```

建议值：
- `1` - 快速失败，适合测试
- `2` - 默认值，平衡性能和准确性
- `3` - 更多尝试，但可能延迟响应

## 测试

### 运行验证器测试

```bash
python response_validator.py
```

测试用例包括：
1. ✅ 正确展示参数（应该通过）
2. ❌ 违规总结（应该被拦截）
3. ❌ 部分展示（应该被拦截）

### 测试场景示例

**场景 1：正确行为**
```
Agent 调用 review_parameters
工具返回：📋 **当前筛选参数摘要**...（完整内容）
Agent 回复：📋 **当前筛选参数摘要**...（完整复制）
验证器：✅ 通过
```

**场景 2：违规总结**
```
Agent 调用 review_parameters
工具返回：📋 **当前筛选参数摘要**...（完整内容）
Agent 回复："好的，我已经为您整理了筛选参数..."
验证器：❌ 失败 - 发现违规模式
重试：使用强制提示重新生成
```

**场景 3：部分展示**
```
Agent 调用 review_parameters
工具返回：📋 **当前筛选参数摘要**...（完整内容）
Agent 回复："参数如下：商品女士香水，粉丝10万-25万..."
验证器：❌ 失败 - 缺失特征标记
重试：使用强制提示重新生成
```

## 前端用户体验

用户在网页聊天界面中会看到：

1. **正常流程**：
   ```
   [AI] 正在处理您的请求...
   [AI] 正在分析参数...
   [AI] 📋 **当前筛选参数摘要**
        🎯 **商品信息**...
   ```

2. **触发重试**：
   ```
   [AI] 正在处理您的请求...
   [系统] 检测到格式问题，正在重新生成回复...（1/2）
   [AI] 📋 **当前筛选参数摘要**
        🎯 **商品信息**...
   ```

3. **多次重试**：
   ```
   [系统] 检测到格式问题，正在重新生成回复...（1/2）
   [系统] 检测到格式问题，正在重新生成回复...（2/2）
   [AI] 📋 **当前筛选参数摘要**...
   ```

## 性能影响

- **成功案例（无重试）**：无额外延迟
- **1次重试**：+5-15秒（取决于 LLM 响应速度）
- **2次重试**：+10-30秒

建议：
- 在生产环境中监控重试率
- 如果重试率 >20%，考虑优化 Agent 提示词
- 可以通过调整 `MAX_RETRIES` 来平衡准确性和性能

## 扩展到其他工具

如果需要为其他工具添加类似的验证：

1. **在工具中记录输出**：
   ```python
   from response_validator import get_validator

   def _run(self, ...):
       output = "..."  # 生成输出

       # 记录到验证器
       validator = get_validator()
       validator.record_tool_call('tool_name', output)

       return output
   ```

2. **在验证器中添加规则**：
   ```python
   # response_validator.py

   class ResponseValidator:
       TOOL_MARKERS = {
           'review_parameters': [
               "📋 **当前筛选参数摘要**",
               # ...
           ],
           'another_tool': [
               "特征标记1",
               "特征标记2",
           ]
       }
   ```

## 故障排查

### 问题 1：验证器未检测到工具调用

**原因**：工具未正确记录输出

**解决方案**：
```python
# 检查工具是否调用了 record_tool_call
validator = get_validator(debug=True)  # 启用调试
# 应该看到: [ResponseValidator] 记录工具调用: review_parameters
```

### 问题 2：误报（正确响应被标记为违规）

**原因**：特征标记太严格或违规模式太宽泛

**解决方案**：
```python
# 调整 response_validator.py 中的标记
PARAMETER_REVIEW_MARKERS = [
    # 减少必需标记，或使用更宽松的匹配
]
```

### 问题 3：重试循环（一直重试失败）

**原因**：Agent 无法理解重试提示

**解决方案**：
- 检查 `MAX_RETRIES` 设置（确保有上限）
- 优化重试提示的措辞
- 考虑在 Agent 的系统提示中强调这个要求

## 最佳实践

1. **启用调试模式**（开发环境）：
   ```python
   validator = get_validator(debug=True)
   ```

2. **监控重试率**：
   - 如果 >10%，优化 Agent 提示词
   - 如果 >30%，检查验证规则是否过于严格

3. **用户友好的状态消息**：
   ```python
   await websocket.send_json({
       "type": "status",
       "content": "正在优化回复格式...",  # 比"检测到错误"更友好
       "timestamp": datetime.now().isoformat()
   })
   ```

4. **日志记录**：
   ```python
   if not is_valid:
       print(f"⚠️ 响应验证失败")
       print(f"   原始响应长度: {len(response)}")
       print(f"   重试提示: {retry_prompt[:100]}...")
   ```

## 总结

响应验证器确保 Agent 遵守"完整展示参数"的规则：

- ✅ 自动检测违规行为
- ✅ 自动重试生成正确回复
- ✅ 最多2次重试，避免无限循环
- ✅ 对用户透明（仅显示最终正确结果）
- ✅ 可扩展到其他工具

这个机制大大提高了用户体验，确保用户始终能看到完整、清晰的筛选参数摘要。
