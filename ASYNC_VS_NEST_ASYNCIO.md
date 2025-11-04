# Async API vs nest_asyncio 对比

## 当前方案：nest_asyncio（已采用）

### 改动内容
```python
# 只需在文件开头添加 2 行
import nest_asyncio
nest_asyncio.apply()
```

### 修改的文件
- run_agent.py（2 行）
- agent_tools.py（2 行）
- agent.py（2 行）
- agent_simple.py（2 行）
- main.py（2 行）

**总计：10 行代码，5 个文件，5 分钟完成**

---

## 备选方案：改用 Async API（未采用）

### 需要改动的内容

#### 1. main.py - 所有核心函数改为异步

```python
# 之前
def initialize_playwright():
    global playwright_instance, browser, context, page
    playwright_instance = sync_playwright().start()
    browser = playwright_instance.chromium.connect_over_cdp("http://localhost:9224")
    context = browser.contexts[0]
    page = context.pages[0]

def navigate_to_url(url: str, wait_for_load: bool = True) -> bool:
    global page
    initialize_playwright()
    try:
        if wait_for_load:
            page.goto(url, wait_until="networkidle", timeout=60000)
        else:
            page.goto(url, timeout=30000)
        time.sleep(2)
        return True
    except Exception as e:
        print(f"❌ 访问 URL 失败: {e}")
        return False

def get_max_page_number():
    page.wait_for_load_state('networkidle')
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    # ... 更多同步代码
    return max_page

def get_table_data_as_dataframe(max_pages=None):
    # 循环爬取多页
    for page_num in range(1, max_pages + 1):
        page.goto(page_url)
        page.wait_for_load_state('networkidle')
        # ... 更多同步代码
    return df
```

```python
# 改为异步后
async def initialize_playwright():
    global playwright_instance, browser, context, page
    playwright_instance = async_playwright().start()
    playwright_instance = await playwright_instance.__aenter__()
    browser = await playwright_instance.chromium.connect_over_cdp("http://localhost:9224")
    context = browser.contexts[0]
    page = context.pages[0]

async def navigate_to_url(url: str, wait_for_load: bool = True) -> bool:
    global page
    await initialize_playwright()  # await!
    try:
        if wait_for_load:
            await page.goto(url, wait_until="networkidle", timeout=60000)  # await!
        else:
            await page.goto(url, timeout=30000)  # await!
        await asyncio.sleep(2)  # await!
        return True
    except Exception as e:
        print(f"❌ 访问 URL 失败: {e}")
        return False

async def get_max_page_number():
    await page.wait_for_load_state('networkidle')  # await!
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")  # await!
    # ... 所有 page 操作都要 await
    return max_page

async def get_table_data_as_dataframe(max_pages=None):
    # 循环爬取多页
    for page_num in range(1, max_pages + 1):
        await page.goto(page_url)  # await!
        await page.wait_for_load_state('networkidle')  # await!
        # ... 所有操作都要 await
    return df
```

#### 2. agent_tools.py - 所有工具改为异步

```python
# 之前
class GetMaxPageTool(BaseTool):
    name: str = "get_max_page_number"
    description: str = "获取搜索结果的最大页数..."
    args_schema: type[BaseModel] = MaxPageInput

    def _run(self, url: str) -> str:
        try:
            print(f"🌐 正在访问: {url}")
            if not navigate_to_url(url):
                return "❌ 无法访问搜索页面..."

            print("📊 正在获取最大页数...")
            max_page = get_max_page_number()

            if max_page <= 1:
                return f"⚠️ 当前筛选条件下只找到 1 页数据..."

            estimated_count = max_page * 10
            return f"✅ 最大页数: {max_page}, 预计约有 {estimated_count} 个达人"

        except Exception as e:
            return f"❌ 获取最大页数失败: {str(e)}"
```

```python
# 改为异步后
class GetMaxPageTool(BaseTool):
    name: str = "get_max_page_number"
    description: str = "获取搜索结果的最大页数..."
    args_schema: type[BaseModel] = MaxPageInput

    # 同步版本必须返回错误或调用异步
    def _run(self, url: str) -> str:
        return "❌ 请使用异步版本"

    # 新增异步版本
    async def _arun(self, url: str) -> str:
        try:
            print(f"🌐 正在访问: {url}")
            if not await navigate_to_url(url):  # await!
                return "❌ 无法访问搜索页面..."

            print("📊 正在获取最大页数...")
            max_page = await get_max_page_number()  # await!

            if max_page <= 1:
                return f"⚠️ 当前筛选条件下只找到 1 页数据..."

            estimated_count = max_page * 10
            return f"✅ 最大页数: {max_page}, 预计约有 {estimated_count} 个达人"

        except Exception as e:
            return f"❌ 获取最大页数失败: {str(e)}"
```

**所有 8 个工具都要这样改！**

#### 3. agent.py - Agent 改为异步

```python
# 之前
class TikTokInfluencerAgent:
    def __init__(self):
        self.llm = self._init_llm()
        self.tools = get_all_tools()
        self.agent = self._create_agent()

    def run(self, user_input: str) -> str:
        response = self.agent.invoke({"input": user_input})
        return response["output"]
```

```python
# 改为异步后
class TikTokInfluencerAgent:
    def __init__(self):
        self.llm = self._init_llm()
        self.tools = get_all_tools()
        self.agent = self._create_agent()

    async def run(self, user_input: str) -> str:
        response = await self.agent.ainvoke({"input": user_input})  # await!
        return response["output"]
```

#### 4. run_agent.py - 主程序改为异步

```python
# 之前
def main():
    agent = create_agent()

    while True:
        user_input = input("\n您: ").strip()

        if user_input in ['退出', 'exit', 'quit']:
            break

        response = agent.run(user_input)
        print(f"\nAgent: {response}")

if __name__ == "__main__":
    main()
```

```python
# 改为异步后
import asyncio

async def main():
    agent = create_agent()

    while True:
        # input() 是同步的，在异步环境中需要特殊处理
        user_input = await asyncio.get_event_loop().run_in_executor(
            None, input, "\n您: "
        )
        user_input = user_input.strip()

        if user_input in ['退出', 'exit', 'quit']:
            break

        response = await agent.run(user_input)  # await!
        print(f"\nAgent: {response}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 工作量对比

### nest_asyncio 方案（已完成）
- ✅ 修改行数：10 行
- ✅ 修改文件：5 个
- ✅ 需要理解：基本的 import
- ✅ 测试范围：所有现有测试仍有效
- ✅ 完成时间：5 分钟

### Async API 方案（未采用）
- ❌ 修改行数：200+ 行
- ❌ 修改文件：10+ 个
- ❌ 需要理解：async/await、asyncio、异步上下文管理
- ❌ 测试范围：需要重写所有测试
- ❌ 完成时间：8-16 小时

---

## 性能对比

### nest_asyncio
- 性能影响：< 1%
- 原因：只是打补丁，不改变执行流程

### Async API
- 理论性能提升：可忽略
- 原因：
  1. 你的爬虫是顺序执行的（一页一页爬）
  2. 没有并发需求
  3. 瓶颈在网络 I/O，不在代码执行

**结论：在你的场景下，异步不会带来性能提升！**

---

## 什么时候应该用 Async API？

### ✅ 适合场景
1. **高并发 Web 服务**
   ```python
   # 同时处理 1000 个请求
   async def handle_request(request):
       data = await fetch_data(request)
       return process(data)
   ```

2. **批量并发爬虫**
   ```python
   # 同时爬取 100 个页面
   async def scrape_all():
       tasks = [scrape_page(url) for url in urls]
       results = await asyncio.gather(*tasks)
   ```

3. **实时数据流**
   ```python
   # WebSocket 连接
   async for message in websocket:
       await process_message(message)
   ```

### ❌ 不适合场景（你的项目）
1. **顺序执行的任务**
   - 你的爬虫：访问 URL → 等待加载 → 爬取数据 → 下一页
   - 没有并发，异步无用

2. **简单的 CLI 工具**
   - 用户输入 → Agent 处理 → 输出结果
   - 同步更简单直观

3. **现有同步代码库**
   - 改造成本 > 收益

---

## 推荐决策流程

```
需要解决 asyncio 冲突？
    │
    ├─ 是全新项目？
    │   └─ 是 → 考虑用 Async API
    │   └─ 否 → 继续
    │
    ├─ 有高并发需求？
    │   └─ 是 → 考虑用 Async API
    │   └─ 否 → 继续
    │
    ├─ 团队熟悉异步编程？
    │   └─ 否 → 用 nest_asyncio ✅
    │   └─ 是 → 继续
    │
    ├─ 有时间重构（8+ 小时）？
    │   └─ 否 → 用 nest_asyncio ✅
    │   └─ 是 → 考虑用 Async API
    │
    └─ 建议：用 nest_asyncio ✅
```

---

## 总结

### 为什么选择 nest_asyncio？

1. **最小改动** - 只需 10 行代码
2. **零风险** - 不改变任何业务逻辑
3. **即刻可用** - 5 分钟完成修复
4. **向后兼容** - 所有现有代码照常工作
5. **易于维护** - 团队成员都能理解

### 如果将来需要异步怎么办？

可以逐步迁移：
1. 先用 nest_asyncio 解决当前问题 ✅
2. 评估是否真的需要并发（可能不需要）
3. 如果需要，可以逐个函数改造
4. 保持两个版本共存（同步 + 异步）

**Premature optimization is the root of all evil** - 过早优化是万恶之源

---

## 参考资料

- [nest_asyncio GitHub](https://github.com/erdewit/nest_asyncio)
- [Playwright Async API](https://playwright.dev/python/docs/api/class-playwright)
- [LangChain Async Tools](https://python.langchain.com/docs/modules/agents/tools/custom_tools#async-tools)
- [When to use async in Python](https://realpython.com/async-io-python/)
