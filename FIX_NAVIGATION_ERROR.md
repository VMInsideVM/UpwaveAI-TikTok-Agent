# 导航错误修复说明

## 问题描述

Agent 在调用 `navigate_to_url()` 时报错：
```
❌ 无法访问搜索页面。可能原因:
1. URL 格式不正确
2. 网络连接问题
3. 页面加载超时
请检查 URL 是否完整(包含分类后缀)
```

实际错误信息：
```
It looks like you are using Playwright Sync API inside the asyncio loop.
Please use the Async API instead.
```

## 根本原因

**LangChain 使用 asyncio 事件循环，而 Playwright 使用同步 API**，两者在同一线程中冲突。

当 LangChain Agent 调用工具（如 `GetMaxPageTool`）时：
1. LangChain 在 asyncio 事件循环中运行
2. 工具调用 `navigate_to_url()` → 使用 `sync_playwright`
3. Playwright 检测到 asyncio 循环存在 → 抛出异常

## 修复方案

### ✅ 已应用的修复

使用 `nest_asyncio` 库，允许嵌套的事件循环共存。

#### 修改的文件（全部已修改）：

1. **run_agent.py** (第 6-8 行) ⭐ **最关键**
   ```python
   import nest_asyncio
   nest_asyncio.apply()
   ```

2. **agent_tools.py** (第 6-8 行) ⭐ **非常重要**
   ```python
   import nest_asyncio
   nest_asyncio.apply()
   ```

3. **agent.py** (第 14-16 行)
   ```python
   import nest_asyncio
   nest_asyncio.apply()
   ```

4. **agent_simple.py** (第 6-8 行)
   ```python
   import nest_asyncio
   nest_asyncio.apply()
   ```

5. **main.py** (第 10-11 行)
   ```python
   import nest_asyncio
   nest_asyncio.apply()
   ```

6. **requirements.txt** (第 13 行)
   ```
   nest-asyncio>=1.5.0
   ```

#### 🔑 关键点

**必须在所有入口文件的最开始调用 `nest_asyncio.apply()`**，在任何其他导入之前！

- ✅ `run_agent.py` - 主入口（用户启动 Agent）
- ✅ `agent_tools.py` - 工具定义（LangChain 调用工具时导入）
- ✅ 测试脚本 - 所有测试文件

### 📦 安装依赖

```bash
pip install nest-asyncio
```

或者重新安装所有依赖：
```bash
pip install -r requirements.txt
```

## 测试修复

### 方法 1: Agent 工具测试（⭐ 最推荐）
```bash
python test_agent_navigation.py
```

这个脚本会：
- 模拟真实的 Agent 工具调用场景
- 测试 `GetMaxPageTool`（最容易出错的工具）
- 测试 `ScrapeInfluencersTool`（可选）
- 验证 nest_asyncio 是否完全生效

### 方法 2: 基础导航测试
```bash
python test_navigation_fix.py
```

这个脚本会：
- 测试模块导入
- 测试 Playwright 初始化
- 测试导航到百度
- 测试导航到 fastmoss
- 检查页面元素

### 方法 3: 完整诊断
```bash
python diagnose_navigation.py
```

输入要测试的 URL，或直接回车使用默认 URL。

### 方法 4: 直接运行 Agent
```bash
python run_agent.py
```

正常使用 Agent，测试真实场景。

## 技术细节

### 为什么会发生这个问题？

1. **LangChain 的异步特性**
   - LangChain 内部使用 `asyncio` 来管理工具调用
   - 即使你使用同步 API，底层仍有事件循环

2. **Playwright 的检测机制**
   - Playwright 会检查当前线程是否有活动的 `asyncio` 事件循环
   - 如果检测到，会建议使用 `async_playwright` 而不是 `sync_playwright`

3. **nest_asyncio 的作用**
   - 打补丁到 `asyncio` 模块，允许嵌套事件循环
   - 让同步代码可以在异步上下文中安全运行
   - 对性能影响极小

### 其他可能的解决方案（未采用）

#### 方案 A: 全部改为异步 API
```python
from playwright.async_api import async_playwright
```
**缺点**：需要重写所有函数，改动太大

#### 方案 B: 在单独线程中运行 Playwright
```python
import threading
```
**缺点**：增加复杂度，可能出现线程安全问题

#### 方案 C: 使用 multiprocessing
**缺点**：进程间通信复杂，性能开销大

## 验证修复成功的标志

✅ Agent 可以成功访问 URL
✅ 不再报 "asyncio loop" 错误
✅ `get_max_page_number` 工具正常工作
✅ `scrape_influencer_data` 工具正常工作

## 如果问题仍然存在

### 1. 确认 nest_asyncio 已安装
```bash
python -c "import nest_asyncio; print(nest_asyncio.__version__)"
```
应该输出版本号（如 `1.6.0`）

### 2. 确认修改已生效
检查 `main.py` 和 `agent.py` 文件开头是否包含：
```python
import nest_asyncio
nest_asyncio.apply()
```

### 3. 重启 Python 环境
如果在 Jupyter 或 IDE 中运行，重启 kernel/session

### 4. 检查其他错误
如果不是 asyncio 错误，可能是：
- Chrome 没有在 CDP 9224 端口运行
- URL 缺少必需的分类参数
- 网络连接问题
- 页面需要登录

运行 `python diagnose_navigation.py` 获取详细诊断信息。

## 相关文件

- `main.py:722-764` - navigate_to_url 函数
- `agent_tools.py:238-262` - GetMaxPageTool 工具
- `agent_tools.py:307-331` - ScrapeInfluencersTool 工具
- `agent.py` - Agent 主控制器
- `test_navigation_fix.py` - 修复测试脚本
- `diagnose_navigation.py` - 诊断脚本

## 参考资料

- [nest_asyncio GitHub](https://github.com/erdewit/nest_asyncio)
- [Playwright Sync vs Async](https://playwright.dev/python/docs/library#sync-api)
- [LangChain Tools Documentation](https://python.langchain.com/docs/modules/agents/tools/)
