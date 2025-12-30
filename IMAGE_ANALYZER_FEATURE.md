# 图像分析功能说明

## 功能概述

Agent 现在支持使用专门的视觉模型（`IMAGE_MODEL`）分析图像，将图像内容转换为文本描述，然后传递给主 Agent 进行后续处理。

这实现了**双模型协作**：
- 🖼️ **视觉模型**（Qwen/Qwen3-VL-235B-A22B-Thinking）：理解图像，提取商品信息
- 🤖 **主模型**（DeepSeek-V3.1-Terminus）：处理文本，执行工作流程

---

## 架构设计

### 模型分工

```
┌─────────────────────────────────────────────────┐
│   用户输入：图片 URL 或本地路径                    │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│   主 Agent (DeepSeek-V3.1-Terminus)             │
│   - 检测到用户提供了图片                          │
│   - 调用 analyze_image 工具                      │
└─────────────────┬───────────────────────────────┘
                  │ 调用工具
                  ▼
┌─────────────────────────────────────────────────┐
│   图像分析器 (IMAGE_MODEL)                       │
│   - 模型: Qwen/Qwen3-VL-235B-A22B-Thinking      │
│   - 接收图像（base64 或 URL）                    │
│   - 生成文本描述                                 │
└─────────────────┬───────────────────────────────┘
                  │ 返回文本
                  ▼
┌─────────────────────────────────────────────────┐
│   主 Agent 继续处理                              │
│   - 接收图像分析结果（纯文本）                    │
│   - 提取商品名称、类别等信息                      │
│   - 继续工作流程（匹配分类、构建 URL 等）         │
└─────────────────────────────────────────────────┘
```

### 为什么要分离？

1. **避免上下文污染**：主 Agent 只处理文本，专注于工作流程逻辑
2. **模型专业化**：视觉模型专注于图像理解，主模型专注于任务编排
3. **性能优化**：图像处理和文本处理分离，避免 token 浪费
4. **成本控制**：视觉模型调用次数可控，只在需要时使用

---

## 核心组件

### 1. 图像分析器（`image_analyzer.py`）

**类**：`ImageAnalyzer`

**功能**：
- 分析本地图像文件
- 分析网络图像 URL
- 提取商品信息（名称、类别、特征、目标人群等）
- 支持自定义分析提示词

**关键方法**：

```python
# 分析本地图像
result = analyzer.analyze_image_from_path(
    image_path="product.jpg",
    prompt="请描述这个商品"
)

# 分析网络图像
result = analyzer.analyze_image_from_url(
    image_url="https://example.com/product.jpg",
    prompt="这是什么商品？"
)

# 提取商品信息（返回结构化数据）
product_info = analyzer.analyze_product_image(
    image_path="lipstick.jpg"
)
# 返回: {
#   "product_name": "YSL圣罗兰口红",
#   "category": "美妆个护",
#   "features": "正红色、哑光质地",
#   ...
# }
```

### 2. LangChain 工具（`agent_tools.py`）

**类**：`AnalyzeImageTool`

**输入参数**：
- `image_path` (可选): 本地图像路径（如：`"product.jpg"`）
- `image_url` (可选): 网络图像 URL（如：`"https://..."`）
- `analysis_type`: 分析类型
  - `"general"`: 通用描述
  - `"product"`: 商品信息提取
- `custom_prompt` (可选): 自定义提示词

**使用示例**：

```python
# Agent 内部调用（通过 LangChain）
tool = AnalyzeImageTool()

# 分析网络图像（通用）
result = tool._run(
    image_url="https://example.com/watch.jpg",
    analysis_type="general"
)

# 分析本地图像（商品信息）
result = tool._run(
    image_path="C:/images/lipstick.jpg",
    analysis_type="product"
)

# 自定义提示词
result = tool._run(
    image_url="https://example.com/shoes.jpg",
    custom_prompt="这双鞋适合什么年龄段的用户？"
)
```

### 3. Agent 集成（`agent.py`）

**System Prompt 更新**：

在 Agent 的系统提示中添加了图像理解能力说明：

```markdown
## 图像理解能力:
你可以分析用户提供的图像（本地文件或网络 URL），提取图像中的商品信息。

**使用场景**:
- 用户上传了商品图片，但没有明确说明商品名称
- 用户提供了商品图片 URL，需要识别商品类型
- 需要从图片中提取商品信息用于后续筛选

**如何使用 analyze_image 工具**:
1. 当用户提供图片路径或 URL 时，使用 analyze_image 工具分析图像
2. 对于商品图片，使用 analysis_type="product" 提取商品信息
3. 工具会返回商品名称、类别、特征、目标人群等信息
4. 将提取的商品信息用于后续的分类匹配和参数收集
```

---

## 使用场景

### 场景 1: 用户上传商品图片（没有文字描述）

**用户输入**：
```
"这是我要推广的商品图片：https://example.com/lipstick.jpg，帮我找10个美国的达人"
```

**Agent 工作流程**：
```
1. 检测到图片 URL
2. 调用 analyze_image(image_url="https://...", analysis_type="product")
3. 视觉模型返回:
   {
     "product_name": "YSL圣罗兰口红",
     "category": "美妆个护",
     "features": "正红色、哑光质地、高端品牌",
     "target_audience": "25-40岁女性"
   }
4. Agent 提取商品名称："YSL圣罗兰口红"
5. 继续正常流程：match_product_category → build_search_url → ...
```

### 场景 2: 用户上传图片 + 部分文字

**用户输入**：
```
"看看这个产品：C:/images/shoes.png，我想找5个达人，粉丝10w-50w"
```

**Agent 工作流程**：
```
1. 调用 analyze_image(image_path="C:/images/shoes.png", analysis_type="general")
2. 视觉模型返回: "这是一双白色运动鞋，Nike 品牌，适合年轻人日常穿着"
3. Agent 提取: 商品名称="Nike白色运动鞋"
4. 从用户输入提取: 达人数量=5, 粉丝范围=10w-50w
5. 继续正常流程...
```

### 场景 3: 用户只提供图片，没有其他信息

**用户输入**：
```
"https://example.com/product.jpg"
```

**Agent 工作流程**：
```
1. 调用 analyze_image(image_url="https://...", analysis_type="product")
2. 视觉模型返回商品信息
3. Agent 回复：
   "我看到这是一款 XXX 商品。请问：
   - 您需要多少个达人？
   - 目标市场是哪个国家？
   - 对粉丝数量有要求吗？"
4. 收集完整信息后继续...
```

---

## 环境配置

### `.env` 文件配置

```env
# 主 Agent 模型（处理文本和工作流程）
OPENAI_MODEL="deepseek-ai/DeepSeek-V3.1-Terminus"

# 图像分析模型（处理图像理解）
IMAGE_MODEL="Qwen/Qwen3-VL-235B-A22B-Thinking"

# API 配置（共用）
OPENAI_API_KEY="sk-xxx"
OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
```

### 模型选择建议

**视觉模型选项**：
- `Qwen/Qwen3-VL-235B-A22B-Thinking` ✅ 推荐（性能强、支持思维链）
- `Qwen/Qwen2-VL-72B-Instruct`（性价比高）
- `Pro/Qwen/Qwen2-VL-7B-Instruct`（速度快、成本低）

**主模型选项**：
- `deepseek-ai/DeepSeek-V3.1-Terminus` ✅ 推荐（推理能力强）
- `Qwen/Qwen3-VL-30B-A3B-Instruct`（也支持视觉，但用于主 Agent 会浪费 token）

---

## 测试方法

### 1. 测试图像分析器（独立测试）

```bash
python test_image_analyzer.py
```

**测试内容**：
- 分析网络商品图像（手表）
- 提取商品信息
- 分析化妆品图像
- 分析服装图像

### 2. 测试 Agent 集成（CLI 模式）

```bash
# 启动 Playwright API
python start_api.py

# 启动 Agent（新终端）
python run_agent.py
```

**测试输入**：
```
用户: 这是我的商品图片：https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800
      帮我找10个美国的达人

预期行为:
1. Agent 调用 analyze_image 工具
2. 视觉模型返回商品描述
3. Agent 提取商品信息
4. 继续正常流程（匹配分类、构建 URL 等）
```

### 3. 测试 Web 聊天模式

```bash
# 启动 Playwright API
python start_api.py

# 启动聊天机器人（新终端）
python start_chatbot.py

# 打开浏览器访问
# http://127.0.0.1:8001/
```

**测试步骤**：
1. 在聊天界面输入图片 URL
2. 观察 Agent 是否调用图像分析工具
3. 查看视觉模型返回的文本描述
4. 验证 Agent 是否正确提取了商品信息

---

## 优势与特点

### ✅ 优势

1. **模型专业化**
   - 视觉模型专注图像理解（Qwen3-VL-235B）
   - 主模型专注任务编排（DeepSeek-V3.1）
   - 各司其职，性能最优

2. **无缝集成**
   - 用户无需了解底层实现
   - 提供图片 = 自动分析 = 提取信息
   - 整个过程对用户透明

3. **灵活性**
   - 支持本地文件和网络 URL
   - 支持通用描述和商品信息提取
   - 支持自定义分析提示词

4. **成本优化**
   - 只在需要时调用视觉模型
   - 主 Agent 不浪费 token 处理图像
   - 文本传递，避免重复编码图像

### 🎯 适用场景

- **电商平台**：用户上传商品图片寻找达人
- **品牌推广**：营销人员提供产品照片
- **快速识别**：用户不想手动输入商品名称
- **批量处理**：自动化处理大量商品图片

---

## 工作流程示例

### 完整对话示例

```
用户: 这是我的产品：https://example.com/watch.jpg，我想在美国推广

Agent: [调用 analyze_image 工具]
       📸 正在分析您的产品图片...

视觉模型返回:
       这是一款高端机械手表，银色不锈钢表壳，黑色皮质表带，
       适合商务人士佩戴。品牌为瑞士名表，目标人群为30-50岁成功男性。

Agent: 我看到这是一款高端机械手表。请问您需要多少个达人来推广？

用户: 10个达人，粉丝100w以上

Agent: [调用 match_product_category]
       [调用 build_search_url]
       [调用 review_parameters]

       📋 当前筛选参数摘要：
       - 商品名称: 高端机械手表
       - 商品分类: 钟表 (L3)
       - 目标市场: 美国
       - 达人数量: 10 个
       - 粉丝范围: 100万 以上

       请确认参数是否正确？

用户: 确认

Agent: [继续后续流程...]
```

---

## 注意事项

### 1. 图像格式支持

**支持的格式**：
- JPEG / JPG
- PNG
- GIF
- WebP

**不支持**：
- PDF（需要先转换为图像）
- SVG（矢量图需要渲染为位图）

### 2. 图像大小限制

- **推荐**：图像宽度 800-1200px
- **最大**：根据 API 限制（通常 5MB 以内）
- **建议**：压缩大图片以提高处理速度

### 3. 网络图像访问

- 确保图像 URL 可公开访问
- 避免需要登录或鉴权的图片
- 检查 URL 是否正确（返回 200 状态码）

### 4. 成本考虑

**视觉模型调用成本**：
- Qwen3-VL-235B-Thinking：约 $0.002/次（SiliconFlow 定价）
- 建议：只在必要时使用 `analysis_type="product"`

**优化建议**：
- 用户明确提供商品名称时，不调用图像分析
- 缓存分析结果，避免重复调用
- 使用较小的视觉模型（如 Qwen2-VL-7B）降低成本

---

## 未来改进方向

### 1. 批量图像处理

```python
# 支持一次分析多张图片
results = analyzer.batch_analyze([
    "product1.jpg",
    "product2.jpg",
    "product3.jpg"
])
```

### 2. 图像缓存

```python
# 避免重复分析同一张图片
if image_hash in cache:
    return cache[image_hash]
else:
    result = analyze_image(...)
    cache[image_hash] = result
```

### 3. OCR 文字提取

```python
# 提取图片中的文字（品牌名、产品型号等）
text = analyzer.extract_text_from_image(image_path)
```

### 4. 多模态融合

```python
# 同时处理图像和用户文字描述
result = analyzer.analyze_with_context(
    image_path="product.jpg",
    user_input="这是我新推出的限量版口红"
)
```

---

## 总结

通过添加图像分析功能，Agent 现在可以：

✅ **理解图像**：识别商品类型、特征、目标人群
✅ **提取信息**：自动获取商品名称、类别等关键数据
✅ **无缝集成**：图像 → 文本 → 工作流程，流畅自然
✅ **模型分工**：视觉模型 + 主模型，各司其职
✅ **成本优化**：按需调用，避免浪费

用户现在可以直接提供商品图片，Agent 会自动识别并推荐合适的 TikTok 达人！🎉
