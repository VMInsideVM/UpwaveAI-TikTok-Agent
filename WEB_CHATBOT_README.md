# 🤖 TikTok 达人推荐聊天机器人使用指南

## 概述

您的 TikTok 达人推荐 Agent 现在已经升级为网页聊天机器人！可以通过浏览器进行交互，支持多用户并发使用。

## ✨ 新功能特性

- ✅ **网页聊天界面**：现代化的聊天 UI，无需命令行
- ✅ **实时通信**：基于 WebSocket 的流式响应
- ✅ **多用户支持**：每个用户拥有独立的会话和对话历史
- ✅ **自动重连**：连接断开后自动尝试重连
- ✅ **调试模式关闭**：生产环境友好，无冗余调试信息
- ✅ **保留 CLI 模式**：仍可通过 `run_agent.py` 使用命令行模式

## 🚀 快速启动

### 方式一：使用启动脚本（推荐）

```bash
# 1. 确保 Chrome 运行在 CDP 端口 9224
chrome.exe --remote-debugging-port=9224

# 2. 启动 Playwright API（终端 1）
python start_api.py

# 3. 启动聊天机器人服务（终端 2）
python start_chatbot.py

# 4. 打开浏览器访问
# http://127.0.0.1:8001/
```

### 方式二：直接运行

```bash
# 1. Chrome CDP
chrome.exe --remote-debugging-port=9224

# 2. Playwright API（终端 1）
python playwright_api.py

# 3. 聊天机器人（终端 2）
python chatbot_api.py

# 4. 打开浏览器
# http://127.0.0.1:8001/
```

## 📂 新增文件

```
UpwaveAI-TikTok-Agent/
├── chatbot_api.py          # 聊天机器人 API 服务（端口 8001）
├── session_manager.py      # 会话管理模块（多用户隔离）
├── start_chatbot.py        # 聊天机器人启动脚本
├── static/
│   └── index.html          # 网页聊天界面
└── WEB_CHATBOT_README.md   # 本文件
```

## 🔧 修改的文件

- **agent.py**
  - 添加 `async def run_streaming()` 方法（支持流式输出）
  - 关闭调试模式：`debug=False`（第 195 行）

- **requirements.txt**
  - 添加 `websockets>=11.0`

- **CLAUDE.md**
  - 新增"Running as Web Chatbot"章节
  - 更新架构图和启动说明

## 🏗️ 系统架构

```
┌─────────────────────────────────────┐
│   用户浏览器                         │
│   http://127.0.0.1:8001             │
└──────────────┬──────────────────────┘
               │ WebSocket
               ▼
┌─────────────────────────────────────┐
│   聊天机器人 API (端口 8001)         │
│   - chatbot_api.py                  │
│   - session_manager.py              │
│   - 多用户会话隔离                   │
└──────────────┬──────────────────────┘
               │ HTTP
               ▼
┌─────────────────────────────────────┐
│   Playwright API (端口 8000)        │
│   - playwright_api.py               │
│   - 处理爬虫操作                     │
└──────────────┬──────────────────────┘
               │ CDP
               ▼
┌─────────────────────────────────────┐
│   Chrome 浏览器 (端口 9224)          │
└─────────────────────────────────────┘
```

## 🌐 API 端点

### REST API

- `GET /` - 聊天界面（HTML）
- `GET /api/health` - 健康检查
- `POST /api/sessions` - 创建新会话
- `DELETE /api/sessions/{session_id}` - 删除会话
- `GET /api/sessions/{session_id}/status` - 获取会话状态
- `GET /api/sessions` - 列出所有会话

### WebSocket

- `WS /ws/{session_id}` - 实时聊天通信

### API 文档

- 交互式文档：http://127.0.0.1:8001/docs
- OpenAPI 规范：http://127.0.0.1:8001/openapi.json

## 💡 使用说明

### 1. 启动服务

按照上述"快速启动"步骤启动所有服务。

### 2. 访问聊天界面

在浏览器中打开：http://127.0.0.1:8001/

### 3. 开始对话

- 界面加载后会自动创建会话
- 在输入框中输入您的需求，例如：
  ```
  我要在美国推广口红，需要找 50 个达人，粉丝在 10 万到 50 万之间
  ```
- Agent 会实时响应，引导您完成整个流程

### 4. 多用户使用

- 每个浏览器标签页/用户都会获得独立的会话
- 对话历史互不干扰
- **注意**：爬虫操作会排队执行（单浏览器限制）

## ⚠️ 注意事项

### 启动顺序

**必须按顺序启动**：
1. ✅ Chrome CDP (端口 9224)
2. ✅ Playwright API (端口 8000)
3. ✅ 聊天机器人 API (端口 8001)
4. ✅ 打开浏览器访问

### 已知限制

1. **单浏览器实例**
   - 同一时间只能为一个用户执行爬虫操作
   - 多个用户同时爬取时会排队等待

2. **内存会话**
   - 会话存储在内存中
   - 服务器重启后会话丢失
   - 适合短期使用，不适合长期持久化需求

3. **无身份验证**
   - 任何人访问 URL 都可以使用
   - 适合内部网络或受信任环境
   - 生产环境建议添加身份验证

### 端口占用

确保以下端口可用：
- **9224** - Chrome CDP
- **8000** - Playwright API
- **8001** - 聊天机器人 API

## 🔄 CLI 模式（保留）

如果您仍然喜欢命令行交互，可以继续使用：

```bash
# 启动 Playwright API
python start_api.py

# 启动 CLI Agent
python run_agent.py
```

CLI 模式和网页模式互不影响，可以根据需要选择使用。

## 🐛 故障排查

### 问题 1: 无法连接到服务器

**症状**：浏览器显示"无法连接到服务器"

**解决方案**：
1. 检查 Playwright API 是否运行：`http://127.0.0.1:8000/health`
2. 检查聊天机器人服务是否运行：`http://127.0.0.1:8001/api/health`
3. 查看终端是否有错误信息

### 问题 2: 会话创建失败

**症状**：提示"Playwright API 服务不可用"

**解决方案**：
1. 确认 Chrome 已启动：访问 `http://127.0.0.1:9224/json/version`
2. 确认 Playwright API 运行正常
3. 按正确顺序重新启动所有服务

### 问题 3: 消息发送后无响应

**症状**：输入消息后一直显示"正在输入"

**解决方案**：
1. 检查浏览器控制台（F12）是否有错误
2. 检查 WebSocket 连接状态
3. 刷新页面重新建立连接

### 问题 4: 端口被占用

**症状**：启动时提示"端口已被占用"

**解决方案**：
```bash
# Windows: 查找占用端口的进程
netstat -ano | findstr :8001

# 关闭占用端口的进程
taskkill /PID <进程ID> /F
```

## 📦 安装依赖

如果遇到缺少依赖的问题：

```bash
pip install -r requirements.txt
```

新增的依赖：
- `websockets>=11.0` - WebSocket 支持

## 🎯 下一步优化建议

如果需要进一步改进，可以考虑：

1. **添加身份验证**
   - 实现用户登录系统
   - JWT token 验证

2. **持久化会话**
   - 使用 Redis 存储会话
   - 数据库存储对话历史

3. **浏览器池**
   - 支持多个 Playwright 浏览器实例
   - 提高并发处理能力

4. **消息队列**
   - 使用 Celery/RQ 处理长时间任务
   - 改善用户体验

5. **监控和日志**
   - 添加日志系统
   - 监控服务健康状态

## 📞 获取帮助

- 查看完整文档：[CLAUDE.md](CLAUDE.md)
- API 文档：http://127.0.0.1:8001/docs
- 检查服务健康：http://127.0.0.1:8001/api/health

---

**祝您使用愉快！** 🎉
