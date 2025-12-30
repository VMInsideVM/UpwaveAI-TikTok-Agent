# 自动图片分析功能

## 功能概述

用户上传图片后，系统会**自动调用视觉模型分析图片内容**，无需用户手动输入"这是我的商品图片"等提示语。

## 工作流程

```
用户上传图片 (可选文字描述)
         ↓
前端发送到后端 (WebSocket)
         ↓
chatbot_api.py 检测到 image_data
         ↓
调用 agent.run_with_image(text, image_data)
         ↓
┌────────────────────────────────────────┐
│ 双模型协作流程 (agent.py:581-701)      │
├────────────────────────────────────────┤
│ 1️⃣ 视觉模型分析图片                    │
│    - 模型: IMAGE_MODEL (Qwen3-VL-235B) │
│    - 提取: 商品名称、类别、特征等       │
│    - 输出: 文本描述                     │
├────────────────────────────────────────┤
│ 2️⃣ 合并文本                            │
│    - 用户文字 + 图片分析结果            │
│    - 构建完整的上下文                   │
├────────────────────────────────────────┤
│ 3️⃣ 传给主 Agent                        │
│    - 模型: OPENAI_MODEL (DeepSeek-V3.1) │
│    - 输入: 纯文本（包含图片分析结果）   │
│    - 继续正常工作流程                   │
└────────────────────────────────────────┘
         ↓
主 Agent 继续处理
  → 匹配分类
  → 构建 URL
  → 确认参数
  → ...
```

## 用户体验

### 场景 1: 只上传图片（无文字）

**用户操作**：
1. 点击上传按钮，选择商品图片
2. 直接点击发送（不输入任何文字）

**系统响应**：
```
[用户看到自己上传的图片]

Agent: 根据您上传的商品图片，我看到这是一款 YSL圣罗兰口红，正红色、哑光质地，
      属于美妆个护类别，适合25-40岁追求品质的女性。

      请问：
      - 您需要推广到哪个国家/地区？
      - 需要找多少个达人？
      - 对达人的粉丝数量有要求吗？
```

### 场景 2: 上传图片 + 文字描述

**用户操作**：
1. 上传商品图片
2. 输入："找10个美国的达人，粉丝100w以上"
3. 点击发送

**系统响应**：
```
[用户看到自己上传的图片和文字]

Agent: 根据您的要求和图片分析：
      - 商品：YSL圣罗兰口红（正红色、哑光质地）
      - 目标：美国市场
      - 达人数量：10个
      - 粉丝要求：100万以上

      正在为您匹配商品分类...
      [继续正常流程]
```

### 场景 3: 先聊天，后上传图片

**对话示例**：
```
用户: 我想找美国的达人推广口红
Agent: 好的！请问您的口红是什么品牌？有什么特色？

[用户上传口红图片]

Agent: 收到您的图片！这是 YSL圣罗兰口红，正红色、哑光质地。
      请问需要多少个达人？对粉丝数量有要求吗？

用户: 10个达人，粉丝100万以上
Agent: 明白了！正在为您匹配分类...
```

## 技术实现

### 1. 前端上传（已实现）

**位置**：[static/index.html:1452-1461](static/index.html#L1452-L1461)

```javascript
// 上传按钮
<button type="button" class="upload-btn" id="uploadBtn">
    <svg>...</svg>
</button>
<input type="file" id="fileInput" accept="image/*" style="display: none;">

// 处理上传
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);  // 转换为 base64
    }
});

// 发送到后端
const payload = {
    type: "message",
    content: userInput,
    image: currentFileData  // base64 格式
};
websocket.send(JSON.stringify(payload));
```

### 2. 后端接收（已实现）

**位置**：[chatbot_api.py:1011-1119](chatbot_api.py#L1011-L1119)

```python
# 解析消息
message_data = json.loads(data)
content = message_data.get("content", "")
image_data = message_data.get("image", None)  # 获取图片数据

# 调用 Agent（带图片）
await stream_agent_response(agent, content, websocket, image_data, session_id)
```

### 3. Agent 处理（新实现）

**位置**：[agent.py:581-701](agent.py#L581-L701)

**关键代码**：

```python
def run_with_image(self, user_input: str, image_data: str) -> str:
    """双模型协作流程"""

    # 步骤 1: 使用视觉模型分析图片
    from image_analyzer import get_image_analyzer
    analyzer = get_image_analyzer()

    # 准备提示词
    if user_input and user_input.strip():
        analysis_prompt = f"""用户说："{user_input}"

请分析这张图片，提取商品名称、类别、特征、目标人群等信息。
请结合用户的描述和图片内容，给出详细的分析结果。"""
    else:
        analysis_prompt = """请分析这张商品图片，提取商品名称、类别、特征等信息。"""

    # 调用视觉模型
    message = HumanMessage(
        content=[
            {"type": "text", "text": analysis_prompt},
            {"type": "image_url", "image_url": {"url": image_data}}
        ]
    )
    response = analyzer.image_model.invoke([message])
    image_analysis = response.content

    # 步骤 2: 合并文本
    if user_input:
        combined_input = f"""{user_input}

【图片分析结果】
{image_analysis}

请根据以上信息继续处理。"""
    else:
        combined_input = f"""用户上传了一张商品图片。

【图片分析结果】
{image_analysis}

请询问用户还需要提供哪些信息（如目标国家、达人数量等）。"""

    # 步骤 3: 调用主 Agent（纯文本）
    return self.run(combined_input)
```

## 关键改进

### 修复前 ❌

```python
# 旧实现：直接把图片传给主模型（会失败）
message_content = [
    {"type": "text", "text": user_input},
    {"type": "image_url", "image_url": {"url": image_data}}
]
self.chat_history.append(HumanMessage(content=message_content))
result = self.agent.invoke({"messages": self.chat_history})
# ❌ DeepSeek-V3.1 不支持视觉，会报错
```

### 修复后 ✅

```python
# 新实现：先用视觉模型分析，再传文本给主模型
analyzer = get_image_analyzer()
image_analysis = analyzer.image_model.invoke([...])  # 视觉模型分析
combined_input = f"{user_input}\n【图片分析结果】\n{image_analysis}"
return self.run(combined_input)  # 主模型处理纯文本
# ✅ 两个模型各司其职，完美协作
```

## 优势

1. **完全自动化**
   - 用户只需上传图片
   - 无需输入"这是我的商品图片"
   - 系统自动识别并分析

2. **智能合并**
   - 用户文字 + 图片分析 = 完整上下文
   - 主 Agent 获得充分的信息
   - 提高分类匹配准确性

3. **模型专业化**
   - 视觉模型：Qwen3-VL-235B（专注图像理解）
   - 主模型：DeepSeek-V3.1（专注任务编排）
   - 各自发挥所长

4. **用户体验友好**
   - 支持"只上传图片"
   - 支持"图片 + 文字"
   - 支持"先聊天后上传"

## 测试方法

### 1. 启动服务

```bash
# 终端 1: 启动 Playwright API
python start_api.py

# 终端 2: 启动聊天机器人
python start_chatbot.py
```

### 2. 打开网页

访问：http://127.0.0.1:8001/

### 3. 测试场景

**测试 1：只上传图片**
1. 点击上传按钮（📎 图标）
2. 选择一张商品图片（如：口红、手表、鞋子等）
3. 直接点击发送（不输入文字）
4. 观察 Agent 是否自动识别商品并询问后续信息

**测试 2：图片 + 文字**
1. 上传商品图片
2. 输入："找10个美国的达人，粉丝100万以上"
3. 点击发送
4. 观察 Agent 是否结合图片和文字进行处理

**测试 3：先聊天后上传**
1. 输入："我想推广一款口红"
2. Agent 询问商品信息
3. 上传口红图片
4. 观察 Agent 是否自动分析图片并继续对话

### 4. 查看日志

在 chatbot_api.py 的控制台查看：
```
[INFO] 检测到图片输入，启动双模型协作流程
[INFO] 正在使用视觉模型分析图片（data URL格式）...
[OK] 视觉模型分析完成，结果长度: 456 字符
[INFO] 图片分析结果（前200字符）: 这是一款YSL圣罗兰口红...
[INFO] 将图片分析结果传递给主 Agent
```

## 注意事项

1. **图片格式支持**
   - JPEG / JPG ✅
   - PNG ✅
   - GIF ✅
   - WebP ✅

2. **图片大小限制**
   - 前端限制：10MB
   - 推荐：< 5MB
   - 大图片会增加上传和分析时间

3. **成本考虑**
   - 视觉模型调用成本：约 $0.002/次（Qwen3-VL-235B）
   - 每次上传图片都会调用视觉模型
   - 建议：只上传必要的商品图片

4. **网络要求**
   - 图片上传需要稳定的网络连接
   - 分析过程可能需要 3-10 秒
   - 前端会显示"正在输入"指示器

## 未来改进

1. **图片缓存**
   - 相同图片不重复分析
   - 使用图片哈希值作为缓存键

2. **批量上传**
   - 支持一次上传多张图片
   - 自动识别并分析所有商品

3. **更智能的提示词**
   - 根据对话上下文调整分析重点
   - 例如：已知是口红，重点分析颜色和质地

4. **OCR 文字提取**
   - 提取图片中的品牌名、产品型号
   - 提高商品识别准确性

## 总结

通过自动图片分析功能，用户现在可以：

✅ **直接上传图片** - 无需手动描述
✅ **自动识别商品** - 视觉模型智能分析
✅ **流畅对话体验** - 图片和文字无缝结合
✅ **双模型协作** - 各自发挥专长，效果更好

用户体验大幅提升！🎉
