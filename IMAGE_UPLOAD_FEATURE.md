# 📸 图片上传功能说明

## 功能概述

聊天机器人现已支持**图片上传和视觉分析**功能！用户可以上传图片，LLM 将通过视觉能力理解图片内容并提供智能回复。

### ✨ 新增特性

- 📤 **图片上传**：点击图片按钮选择图片文件
- 👁️ **实时预览**：上传前查看图片预览
- 🖼️ **消息展示**：图片与文本一起显示在聊天记录中
- 🧠 **视觉理解**：LLM 可以"看懂"图片并基于图片内容回答问题
- 🔄 **Base64 传输**：安全高效的图片数据传输

---

## 使用方法

### 1. 上传图片

#### 方式一：点击上传按钮
1. 点击输入框左侧的 **📷 图片按钮**
2. 在文件选择器中选择图片
3. 支持的格式：JPG、PNG、GIF、WebP 等
4. 文件大小限制：**5MB**

#### 方式二：拖拽上传（未来功能）
- 直接将图片拖到输入框

### 2. 预览和编辑
- 选择图片后，会在输入框上方显示 **预览**
- 点击预览图右上角的 **× 按钮** 可以移除图片
- 可以**更换图片**：再次点击上传按钮

### 3. 发送消息
- **纯图片**：不输入文字，直接点击"发送"
- **图文混合**：输入文字描述 + 上传图片，一起发送
- **纯文字**：不上传图片，正常文字对话

### 4. 查看历史
- 发送的图片会显示在聊天记录中
- 点击图片可以**放大查看**（在新标签页打开）

---

## 典型使用场景

### 场景 1：商品图片识别

```
用户：[上传商品图片]
     这个商品适合在哪个国家推广？

Agent：根据图片，这是一款时尚口红。建议在以下国家推广：
       1. 美国 - 美妆市场发达
       2. 英国 - 对奢侈品接受度高
       3. 日本 - 美妆文化浓厚

       我可以帮您在这些国家找到合适的达人...
```

### 场景 2：达人主页截图分析

```
用户：[上传达人主页截图]
     这个达人的粉丝画像如何？

Agent：从截图看，这位达人：
       - 粉丝数：约 50 万
       - 互动率：较高（评论数/粉丝数 约 2%）
       - 内容方向：时尚美妆
       - 适合推广：口红、香水、服饰等产品
```

### 场景 3：竞品分析

```
用户：[上传竞品推广视频截图]
     他们用的是什么推广策略？

Agent：从图片分析，竞品推广策略：
       1. 使用头部达人（粉丝 > 100万）
       2. 采用"开箱评测"形式
       3. 强调产品特色卖点

       建议您也可以采用类似策略...
```

---

## 技术实现

### 前端 ([static/index.html](static/index.html))

#### 1. 图片上传界面
```html
<!-- 图片上传按钮 -->
<button type="button" class="image-upload-btn" id="uploadBtn">
    <svg>...</svg> <!-- 图片图标 -->
</button>

<!-- 隐藏的文件输入 -->
<input type="file" id="imageInput" accept="image/*" style="display: none;">

<!-- 图片预览 -->
<div class="image-preview-container" id="imagePreviewContainer">
    <img id="previewImage">
    <button class="image-preview-remove">×</button>
</div>
```

#### 2. JavaScript 处理逻辑
```javascript
// 图片选择处理
function handleImageSelect(event) {
    const file = event.target.files[0];

    // 文件类型检查
    if (!file.type.startsWith('image/')) {
        showError('请选择图片文件');
        return;
    }

    // 文件大小检查（5MB）
    if (file.size > 5 * 1024 * 1024) {
        showError('图片大小不能超过 5MB');
        return;
    }

    // 读取并转换为 Base64
    const reader = new FileReader();
    reader.onload = (e) => {
        selectedImage = e.target.result;  // Base64 字符串
        previewImage.src = selectedImage;
        imagePreviewContainer.classList.add('active');
    };
    reader.readAsDataURL(file);
}

// 发送消息（包含图片）
function sendMessage(message) {
    const data = {
        type: 'message',
        content: message,
        image: selectedImage  // Base64 图片数据
    };

    websocket.send(JSON.stringify(data));
}
```

### 后端 ([chatbot_api.py](chatbot_api.py))

#### 1. WebSocket 消息接收
```python
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # 解析消息
    message_data = json.loads(data)
    content = message_data.get("content", "")
    image_data = message_data.get("image", None)  # Base64 图片

    if message_type == "message" and (content or image_data):
        # 处理图文消息
        await stream_agent_response(agent, content, websocket, image_data)
```

#### 2. 流式响应处理
```python
async def stream_agent_response(
    agent: TikTokInfluencerAgent,
    user_input: str,
    websocket: WebSocket,
    image_data: Optional[str] = None
):
    def run_with_progress():
        # 如果有图片，调用支持视觉输入的方法
        if image_data:
            return agent.run_with_image(user_input, image_data)
        else:
            return agent.run(user_input)

    response = await loop.run_in_executor(None, run_with_progress)
    # 流式发送响应...
```

### Agent 层 ([agent.py](agent.py:413-495))

#### 多模态消息处理
```python
def run_with_image(self, user_input: str, image_data: str) -> str:
    """运行 Agent 处理用户输入（支持图片）"""

    # 构建多模态消息
    message_content = []

    # 添加文本
    if user_input and user_input.strip():
        message_content.append({
            "type": "text",
            "text": user_input
        })

    # 添加图片
    if image_data:
        message_content.append({
            "type": "image_url",
            "image_url": {
                "url": image_data  # Base64 Data URL
            }
        })

    # 创建多模态消息
    self.chat_history.append(HumanMessage(content=message_content))

    # 调用 LLM（支持视觉能力的模型）
    result = self.agent.invoke({"messages": self.chat_history})

    return extract_response(result)
```

---

## 数据流程

```
┌─────────────────────────────────────────────────────────┐
│  1. 用户选择图片                                         │
│     - 浏览器文件选择器                                   │
│     - FileReader API 读取文件                           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  2. 转换为 Base64                                        │
│     - reader.readAsDataURL(file)                        │
│     - 格式：data:image/jpeg;base64,/9j/4AAQ...          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  3. 通过 WebSocket 发送                                  │
│     {                                                    │
│       "type": "message",                                 │
│       "content": "这是什么商品？",                       │
│       "image": "data:image/jpeg;base64,..."              │
│     }                                                    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  4. chatbot_api.py 接收                                  │
│     - 解析 JSON 消息                                     │
│     - 提取 content 和 image                             │
│     - 传递给 agent                                       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  5. agent.py 处理                                        │
│     - 构建多模态消息                                     │
│     - 调用 LangChain agent                              │
│     - LangChain 将图片发送给 LLM                        │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  6. LLM 视觉分析                                         │
│     - Qwen3-VL-30B 处理图片                             │
│     - 理解图片内容                                       │
│     - 生成回复                                           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  7. 流式返回响应                                         │
│     - chatbot_api 流式发送                              │
│     - 前端实时显示                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 样式特性

### 图片预览样式
```css
.image-preview-container {
    padding: 10px;
    background: #f9fafb;
    border-radius: 12px;
    margin-bottom: 10px;
}

.image-preview img {
    max-width: 200px;
    max-height: 200px;
    border-radius: 8px;
    border: 2px solid #e5e7eb;
}

.image-preview-remove {
    position: absolute;
    top: -8px;
    right: -8px;
    width: 24px;
    height: 24px;
    background: #ef4444;
    color: white;
    border-radius: 50%;
}
```

### 消息中的图片样式
```css
.message-image {
    max-width: 300px;
    max-height: 300px;
    border-radius: 12px;
    margin-top: 10px;
    cursor: pointer;
    transition: transform 0.3s;
}

.message-image:hover {
    transform: scale(1.02);  /* 悬停放大效果 */
}
```

---

## 限制和注意事项

### 当前限制

1. **文件大小**：最大 5MB
   - 超过限制会显示错误提示
   - 建议压缩大图片后上传

2. **支持格式**：
   - ✅ JPG/JPEG
   - ✅ PNG
   - ✅ GIF
   - ✅ WebP
   - ✅ BMP
   - ❌ 不支持其他格式

3. **单次上传**：
   - 一次只能上传 **1 张图片**
   - 如需多图，可分多次发送

4. **LLM 依赖**：
   - 需要使用**支持视觉能力**的 LLM
   - 当前配置：`Qwen3-VL-30B`
   - 如使用不支持视觉的模型，图片将被忽略

### 安全考虑

1. **数据传输**：
   - Base64 编码，仅在 WebSocket 中传输
   - 不存储图片文件
   - 断开连接后图片数据丢失

2. **隐私保护**：
   - 图片仅用于当前会话
   - 不上传到第三方服务器
   - 不保存用户上传的图片

3. **恶意文件防护**：
   - 前端验证文件类型
   - 后端可添加额外验证
   - 建议生产环境启用病毒扫描

---

## 故障排查

### 问题 1: 无法上传图片

**症状**：点击上传按钮无反应

**解决方案**：
1. 检查浏览器控制台是否有错误
2. 确认 uploadBtn 和 imageInput 元素存在
3. 检查事件监听器是否正确绑定
4. 刷新页面重试

### 问题 2: 图片预览不显示

**症状**：选择图片后没有预览

**解决方案**：
1. 检查文件是否符合格式要求
2. 查看控制台 `handleImageSelect` 是否有错误
3. 确认 FileReader API 可用（旧浏览器可能不支持）
4. 检查图片文件是否损坏

### 问题 3: LLM 无法识别图片

**症状**：发送图片后 LLM 只回复文字，忽略图片

**解决方案**：
1. 确认使用的 LLM 支持视觉能力
2. 检查 `.env` 文件中的模型配置：
   ```
   OPENAI_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"
   ```
3. 查看后端日志，确认图片数据已传递给 agent
4. 尝试简化提示词，如"图片中是什么？"

### 问题 4: 图片过大导致上传失败

**症状**：选择大图片后显示错误

**解决方案**：
1. 使用图片压缩工具减小文件大小
2. 推荐在线工具：TinyPNG、Squoosh
3. 或调整限制（修改 `handleImageSelect` 中的大小检查）

---

## 未来改进方向

### 短期优化

1. **多图上传**
   - 支持一次上传多张图片
   - 图片轮播显示

2. **图片编辑**
   - 裁剪、旋转
   - 添加标注

3. **拖拽上传**
   - 直接拖拽图片到聊天框
   - 更直观的交互

4. **粘贴上传**
   - Ctrl+V 粘贴截图
   - 快速分享屏幕截图

### 长期规划

1. **图片压缩**
   - 自动压缩大图片
   - 减少传输数据量

2. **OCR 文字识别**
   - 提取图片中的文字
   - 表格识别

3. **图片搜索**
   - 基于图片内容搜索相似达人
   - 反向图片搜索

4. **视频支持**
   - 上传短视频
   - 视频截帧分析

---

## 文件清单

### 修改的文件

1. **[static/index.html](static/index.html)**
   - 添加图片上传按钮和预览界面
   - 添加 JavaScript 图片处理逻辑
   - 添加图片相关 CSS 样式
   - 修改 `sendMessage` 函数支持图片

2. **[chatbot_api.py](chatbot_api.py:55-65)**
   - `stream_agent_response` 函数新增 `image_data` 参数
   - WebSocket 消息解析支持 `image` 字段
   - 传递图片数据给 agent

3. **[agent.py](agent.py:413-495)**
   - 新增 `run_with_image()` 方法
   - 支持 LangChain 多模态消息格式
   - Base64 图片数据处理

### 新增的文件

4. **[IMAGE_UPLOAD_FEATURE.md](IMAGE_UPLOAD_FEATURE.md)** （本文件）
   - 功能说明文档
   - 使用指南
   - 技术实现细节

---

## 总结

✅ **功能已完成**：
- 前端图片上传界面
- Base64 编码传输
- WebSocket 图片消息支持
- Agent 多模态处理
- LLM 视觉分析

🎯 **使用场景**：
- 商品图片识别
- 达人主页分析
- 竞品截图分析
- 视觉问答

🚀 **立即体验**：
1. 重启聊天机器人服务：`python start_chatbot.py`
2. 打开浏览器：`http://127.0.0.1:8001`
3. 点击图片按钮上传图片
4. 享受视觉 AI 体验！

---

**祝您使用愉快！** 📸✨
