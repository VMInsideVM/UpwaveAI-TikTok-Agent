# 修复：强制要求传入目标达人数量参数

## 问题描述

用户报告：前端确认生成报告的弹窗里的积分计算使用的达人数量不正确，应该和发送给 report agent 的需求达人数量参数一致。

### 根本原因

1. **Agent (LLM) 有时会忘记传递 `target_influencer_count` 参数**
   - 即使提示词中要求"必须传入"
   - LLM 在调用 `build_search_url` 时可能省略这个参数

2. **之前的容错机制太宽松**
   - 当没有收到参数时，自动使用默认值 10
   - 导致用户指定的数量被忽略，确认弹窗显示错误的积分

### 数据流

```
用户输入 "我要40个达人"
    ↓
Agent 收集需求
    ↓
Agent 调用 build_search_url()
    ❌ 忘记传入 target_influencer_count=40
    ↓
BuildURLTool 自动设置默认值 10  ❌
    ↓
agent.target_influencer_count = 10  ❌
    ↓
确认弹窗显示: 10 个达人 × 100 = 1000 积分  ❌
    ↓
实际应该显示: 40 个达人 × 100 = 4000 积分  ✅
```

## 解决方案

### 修改 1: 强制要求参数（agent_tools.py）

**文件**: [agent_tools.py:248-262](agent_tools.py#L248-L262)

**修改前**:
```python
# ⭐ 存储目标达人数量
if target_influencer_count is not None:
    agent.target_influencer_count = target_influencer_count
    agent.current_params['target_count'] = target_influencer_count
    print(f"✅ 已保存目标达人数量: {target_influencer_count} 个")
else:
    # ⚠️ 如果没有传入，使用默认值并警告
    print(f"⚠️ 警告：未传入 target_influencer_count 参数，将使用默认值 10")
    agent.target_influencer_count = 10  # ❌ 自动设置默认值
    agent.current_params['target_count'] = 10
```

**修改后**:
```python
# ⭐ 存储目标达人数量
if target_influencer_count is not None and target_influencer_count > 0:
    agent.target_influencer_count = target_influencer_count
    agent.current_params['target_count'] = target_influencer_count
    print(f"✅ 已保存目标达人数量: {target_influencer_count} 个")
else:
    # ⚠️ 如果没有传入，返回错误提示，要求 Agent 重新提供
    error_msg = (
        "❌ 错误：你没有传入 target_influencer_count 参数！\n\n"
        "请先向用户询问需要多少个达人，然后重新调用 build_search_url 工具，"
        "并传入 target_influencer_count 参数。\n\n"
        "示例：build_search_url(..., target_influencer_count=10)"
    )
    print(f"⚠️ {error_msg}")
    return error_msg  # ✅ 返回错误，强制 Agent 重新调用
```

**关键改进**:
- ❌ 不再自动设置默认值
- ✅ 返回明确的错误消息
- ✅ Agent 会看到错误并重新调用工具
- ✅ 确保用户指定的数量不会丢失

### 修改 2: 增强提示词（agent.py）

**文件**: [agent.py:103-120](agent.py#L103-L120)

**修改前**:
```python
1. **理解需求**: 询问用户的商品名称、目标国家、达人数量、粉丝要求等
   - 收集所有需要的信息（商品、国家、数量、筛选条件）
   - 提取用户需要的达人数量并记录

3. **构建搜索 URL**: 使用 build_search_url 工具构建 URL
   - 传入所有收集到的筛选参数
   - ⚠️ **必须传入 target_influencer_count 参数**（用户需要的达人数量）
   - 工具会自动将参数存储起来
   - ✅ 完成后立即进入步骤4
```

**修改后**:
```python
1. **理解需求**: 询问用户的商品名称、目标国家、达人数量、粉丝要求等
   - 收集所有需要的信息（商品、国家、数量、筛选条件）
   - ⚠️ **特别重要：必须明确询问用户需要多少个达人！**
   - 将用户指定的达人数量记录下来（如果用户没说，默认10个）

3. **构建搜索 URL**: 使用 build_search_url 工具构建 URL
   - 传入所有收集到的筛选参数
   - 🚨 **极其重要：必须传入 target_influencer_count 参数！**
   - 这个参数是用户需要的达人数量（从步骤1中获取）
   - 示例调用：build_search_url(country_name="美国", ..., target_influencer_count=10)
   - 如果忘记传入这个参数，工具会返回错误，你需要重新调用
   - ✅ 完成后立即进入步骤4
```

**关键改进**:
- ⚠️ → 🚨 增强警告级别
- ✅ 添加具体示例
- ✅ 明确说明如果忘记会收到错误
- ✅ 要求在步骤1就询问用户数量

## 修复后的数据流

```
用户输入 "我要40个达人"
    ↓
Agent 收集需求（提示词强调必须询问数量）
    ↓
Agent 调用 build_search_url(target_influencer_count=40)  ✅
    ↓
BuildURLTool 验证参数
    - 如果有值: 保存到 agent.target_influencer_count = 40  ✅
    - 如果缺失: 返回错误，Agent 重新调用  ✅
    ↓
chatbot_api.py 读取 agent.target_influencer_count = 40  ✅
    ↓
发送 WebSocket 消息: {"influencer_count": 40}  ✅
    ↓
前端确认弹窗显示: 40 个达人 × 100 = 4000 积分  ✅
```

## 测试场景

### 场景 1: 用户明确指定数量

**输入**:
```
用户: 我要推广女士香水，需要40个达人
```

**期望行为**:
1. Agent 调用 `build_search_url(..., target_influencer_count=40)`
2. `agent.target_influencer_count = 40`
3. 确认弹窗显示: **40 个达人 × 100 = 4000 积分**

**验证日志**:
```
✅ 已保存目标达人数量: 40 个
📊 从 Agent 获取目标达人数: 40
📊 确认弹窗 - 达人数量: 40, 扣除积分: 4000
```

### 场景 2: Agent 忘记传递参数（旧问题）

**Agent 调用**:
```python
build_search_url(
    country_name="美国",
    followers_min=100000,
    followers_max=250000
    # ❌ 忘记传入 target_influencer_count
)
```

**期望行为**:
1. `BuildURLTool` 返回错误消息
2. Agent 看到错误，询问用户需要多少个达人
3. Agent 重新调用 `build_search_url(..., target_influencer_count=10)`
4. 成功保存参数

**验证日志**:
```
⚠️ ❌ 错误：你没有传入 target_influencer_count 参数！

请先向用户询问需要多少个达人，然后重新调用 build_search_url 工具，
并传入 target_influencer_count 参数。

示例：build_search_url(..., target_influencer_count=10)
```

### 场景 3: 用户没有指定数量

**输入**:
```
用户: 帮我找美国市场的口红达人
```

**期望行为**:
1. Agent 主动询问："您需要多少个达人？"
2. 用户回复或 Agent 使用默认值 10
3. Agent 调用 `build_search_url(..., target_influencer_count=10)`
4. 确认弹窗显示: **10 个达人 × 100 = 1000 积分**

## 优势

### ✅ 数据准确性
- 用户指定的达人数量不会丢失
- 确认弹窗显示的积分与实际扣除一致
- 避免用户误解和信任问题

### ✅ 强制执行
- 不再依赖 LLM 的"自觉性"
- 通过返回错误强制 Agent 修正行为
- 确保关键参数不会被遗漏

### ✅ 用户体验
- 积分计算透明准确
- 避免"我说40个为什么扣1000积分"的困惑
- 增强系统可信度

### ✅ 可调试性
- 清晰的日志输出
- 错误消息明确指出问题
- 容易追踪数据流

## 潜在风险

### ⚠️ Agent 可能反复调用

如果 LLM 理解能力差，可能会：
1. 第一次调用忘记传参数 → 收到错误
2. 第二次调用仍然忘记 → 收到错误
3. 陷入循环

**缓解措施**:
- 提示词已经多次强调
- 错误消息包含示例代码
- LangChain ReAct 框架有重试机制

### ⚠️ 用户体验可能稍慢

之前是立即使用默认值，现在可能需要额外一轮对话。

**缓解措施**:
- 提示词要求在步骤1就询问数量
- 大多数用户会在首次描述需求时提到数量

## 总结

✅ **核心改进**: 从"宽容容错"转变为"严格验证"

✅ **关键原则**: 关键业务参数（影响计费）必须明确传递，不能猜测或使用默认值

✅ **实现方式**:
- 后端强制验证（agent_tools.py）
- 前端明确提示（agent.py）
- 清晰的错误消息和日志

✅ **期望结果**: 用户看到的积分扣除与实际需求完全一致，建立信任
