# 前端显示真实达人数量修复说明

## 问题描述

**原始问题**：
前端确认弹窗中显示的达人数量始终为默认值 10，而不是用户实际需要的数量。

例如：
- 用户输入："美国地区这个商品，**2个达人**，10w-30w粉丝"
- 前端显示："此操作将消耗 1000 积分（**10 个达人** × 100 积分/个）" ❌
- 预期显示："此操作将消耗 200 积分（**2 个达人** × 100 积分/个）" ✅

## 根本原因

在 `chatbot_api.py:291`，获取达人数量的代码存在问题：

### 修复前的代码
```python
# ⭐ 从 Agent 实例获取真实的达人数量
agent = session_manager.get_agent(session_id)
influencer_count = 10  # 默认值 ❌

if agent:
    if hasattr(agent, 'target_influencer_count') and agent.target_influencer_count:
        influencer_count = agent.target_influencer_count
        print(f"✅ 从 Agent 获取目标达人数: {influencer_count}")
    else:
        print(f"⚠️ Agent 的 target_influencer_count 为空或不存在，使用默认值: {influencer_count}")
```

**问题**：
1. **单一数据源**：只从 `agent.target_influencer_count` 获取
2. **默认值优先**：初始值就设为 10，导致即使获取失败也不明显
3. **缺少备用方案**：没有尝试从 `agent.current_params` 获取

## 修复方案

### 修复后的代码

```python
# ⭐ 从 Agent 实例获取真实的达人数量
agent = session_manager.get_agent(session_id)
influencer_count = None  # 初始值为 None ✅

print(f"🔍 调试信息:")
print(f"  - session_id: {session_id}")
print(f"  - agent: {agent}")

if agent:
    # 方法 1: 从 current_params 获取（优先）✅
    if hasattr(agent, 'current_params') and agent.current_params:
        target_count = agent.current_params.get('target_count')
        if target_count:
            influencer_count = target_count
            print(f"✅ 从 Agent.current_params 获取目标达人数: {influencer_count}")

    # 方法 2: 从 target_influencer_count 属性获取（备用）✅
    if not influencer_count and hasattr(agent, 'target_influencer_count') and agent.target_influencer_count:
        influencer_count = agent.target_influencer_count
        print(f"✅ 从 Agent.target_influencer_count 获取目标达人数: {influencer_count}")

# 如果仍然没有获取到，使用默认值 10
if not influencer_count:
    influencer_count = 10
    print(f"⚠️ 无法从 Agent 获取达人数量，使用默认值: {influencer_count}")
else:
    print(f"✅ 最终使用的达人数量: {influencer_count}")
```

### 修复要点

1. **双重数据源**：
   - **优先**从 `agent.current_params['target_count']` 获取（由 `build_search_url` 工具保存）
   - **备用**从 `agent.target_influencer_count` 获取

2. **明确的默认值逻辑**：
   - 初始值设为 `None`
   - 只有在两个数据源都失败时才使用默认值 10
   - 添加明确的日志输出

3. **健壮性增强**：
   - 检查属性是否存在
   - 检查值是否为 None 或 0
   - 记录详细的调试信息

## 数据流向

### 用户输入 → Agent 存储 → 前端显示

```
1. 用户输入："美国地区口红，2个达人，10w-30w粉丝"
   ↓
2. Agent 调用 match_product_category 工具
   - 保存 product_name 到 current_params
   ↓
3. Agent 调用 build_search_url 工具
   - 接收 target_influencer_count=2
   - 保存到 agent.current_params['target_count'] = 2 ✅
   - 保存到 agent.target_influencer_count = 2 ✅
   ↓
4. Agent 调用 confirm_scraping 工具
   - 触发前端确认弹窗
   ↓
5. chatbot_api.py 检测到需要确认
   - 方法 1: 从 agent.current_params['target_count'] 获取 = 2 ✅
   - 方法 2: 从 agent.target_influencer_count 获取 = 2 ✅
   ↓
6. 发送 WebSocket 消息到前端
   {
     "type": "confirm_generate",
     "data": {
       "influencer_count": 2  ✅
     }
   }
   ↓
7. 前端显示
   "此操作将消耗 200 积分（2 个达人 × 100 积分/个）" ✅
```

## 相关文件

### 修改文件
- `chatbot_api.py:289-315` - 修复达人数量获取逻辑

### 相关文件（未修改，但相关）
- `agent.py:66` - Agent 定义 `target_influencer_count` 属性
- `agent.py:64` - Agent 定义 `current_params` 字典
- `agent_tools.py:249-252` - `build_search_url` 工具保存达人数量
- `static/index.html:3178-3195` - 前端接收并显示达人数量

## 测试验证

### 测试步骤

1. **启动服务**：
   ```bash
   # 终端 1: 启动 Playwright API
   python start_api.py

   # 终端 2: 启动聊天机器人
   python start_chatbot.py
   ```

2. **打开浏览器**：
   访问 http://127.0.0.1:8001/

3. **测试用例**：

   **用例 1: 2 个达人**
   ```
   输入："美国地区口红，2个达人，10w-30w粉丝"
   预期弹窗显示："此操作将消耗 200 积分（2 个达人 × 100 积分/个）"
   ```

   **用例 2: 50 个达人**
   ```
   输入："美国地区运动鞋，50个达人，10w-100w粉丝"
   预期弹窗显示："此操作将消耗 5000 积分（50 个达人 × 100 积分/个）"
   ```

   **用例 3: 默认值（用户未指定）**
   ```
   输入："美国地区瑜伽垫，10w-30w粉丝"（没有指定达人数量）
   预期弹窗显示："此操作将消耗 1000 积分（10 个达人 × 100 积分/个）"
   ```

4. **查看日志输出**：
   在终端 2（chatbot_api.py）中查看日志：
   ```
   🔍 调试信息:
     - session_id: xxx
     - agent: <TikTokInfluencerAgent object>
   ✅ 从 Agent.current_params 获取目标达人数: 2
   ✅ 最终使用的达人数量: 2
   ```

## 预期结果

### 修复前 ❌
```
用户输入: "2个达人"
前端显示: "10 个达人 × 100 积分/个 = 1000 积分"  ❌ 错误
```

### 修复后 ✅
```
用户输入: "2个达人"
前端显示: "2 个达人 × 100 积分/个 = 200 积分"   ✅ 正确

用户输入: "50个达人"
前端显示: "50 个达人 × 100 积分/个 = 5000 积分" ✅ 正确

用户输入: 未指定达人数量
前端显示: "10 个达人 × 100 积分/个 = 1000 积分"  ✅ 正确（使用默认值）
```

## 注意事项

1. **确保 Agent 正确保存数据**
   - `build_search_url` 工具必须传入 `target_influencer_count` 参数
   - 如果忘记传入，工具会返回错误提示

2. **日志监控**
   - 启动 chatbot_api.py 后，查看控制台日志
   - 确认看到 "✅ 从 Agent.current_params 获取目标达人数: X"

3. **WebSocket 连接**
   - 确保前端与后端的 WebSocket 连接正常
   - 检查浏览器控制台是否有连接错误

## 未来改进

### 可能的增强方向

1. **更智能的默认值**：
   - 根据用户历史行为推荐达人数量
   - 根据商品类别建议典型达人数量范围

2. **前端输入验证**：
   - 添加达人数量输入框，让用户可以手动调整
   - 显示可用达人总数，避免用户请求过多

3. **积分预估**：
   - 在用户输入时实时显示预估积分消耗
   - 在参数确认阶段就显示积分信息

4. **错误处理**：
   - 如果无法获取达人数量，显示更友好的错误提示
   - 允许用户在确认弹窗中修改达人数量

## 总结

通过修改 `chatbot_api.py` 的达人数量获取逻辑，实现了：

✅ **双重数据源**：优先从 `current_params`，备用 `target_influencer_count`
✅ **明确的默认值**：只在无法获取时使用默认值 10
✅ **详细的日志**：方便调试和问题排查
✅ **用户体验提升**：前端显示真实的积分消耗

用户现在可以看到准确的达人数量和积分消耗，避免了困惑和误解。
