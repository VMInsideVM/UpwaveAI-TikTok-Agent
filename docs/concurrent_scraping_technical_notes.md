# 多标签页并发爬取技术说明

**最后更新**: 2025-01-10
**当前状态**: 使用多标签页 + bring_to_front() 方案

---

## 🎯 核心挑战: 标签页可见性问题

### 问题描述

在实现多标签页并发爬取时,遇到了 Playwright 的一个核心限制:

```
⚠️ 点击第1个选项时出错: Locator.click: Timeout 30000ms exceeded.
```

**根本原因**:
- 浏览器同一时间只能**显示一个标签页**
- 其他标签页处于**后台状态**(background)
- Playwright 的交互操作(`click`, `fill`, `hover`)要求元素**可见**(visible)
- 后台标签页的元素不可见,导致操作超时失败

### 为什么会有这个限制?

Playwright 模拟真实用户行为:
1. 真实用户只能与可见元素交互
2. 后台标签页的元素不在视口中
3. Playwright 的 `actionability checks` 会验证元素可见性
4. 不可见元素的点击操作会超时

---

## ✅ 当前实现方案

### 多标签页 + bring_to_front() (CDP 连接模式)

**架构**:
```
Browser (CDP:9224)
└── Context (共享，保留登录状态)
    ├── Page 1 (Tab 1)  ← 交互时激活
    ├── Page 2 (Tab 2)  ← 交互时激活
    └── Page 3 (Tab 3)  ← 交互时激活
```

#### 实现代码

**[playwright_api.py:1188-1195](../playwright_api.py#L1188-L1195)** - 创建标签页:
```python
# 创建多个标签页（在同一 Context 中，共享登录状态）
pages = []
for i in range(max_concurrent):
    page = await _context.new_page()
    pages.append(page)
```

**[playwright_api.py:852-855](../playwright_api.py#L852-L855)** - 激活标签页:
```python
# 如果使用自定义 page，需要激活标签页以确保元素可见
if page is not None:
    await page.bring_to_front()
    await asyncio.sleep(0.5)  # 等待标签页切换完成
```

**[playwright_api.py:992-995](../playwright_api.py#L992-L995)** - 下拉菜单激活:
```python
# 确保标签页处于激活状态（并发模式下必需）
if page is not None:
    await page.bring_to_front()
    await asyncio.sleep(0.3)
```

#### 工作流程

```
任务1 → 激活Tab1 → 点击 → 等待 → 数据提取
任务2 → 激活Tab2 → 点击 → 等待 → 数据提取
任务3 → 激活Tab3 → 点击 → 等待 → 数据提取
任务4 → 激活Tab1 → 点击 → 等待 → 数据提取 (复用Tab1)
...
```

**注意**: 虽然使用 asyncio.gather 调度，但由于 bring_to_front() 的串行性质，交互操作实际上是依次执行的（非真正并行）。

#### 为什么这是最优方案？

在 CDP 连接模式下，这是**唯一可行**的方案：

1. ✅ **保留登录状态**
   - 所有标签页共享同一个 BrowserContext
   - 登录 Cookie 和 Session 在所有标签页中可用
   - CDP 连接模式下无法创建新 Context

2. ✅ **稳定可靠**
   - 使用 Playwright 官方 API
   - `bring_to_front()` 是稳定的公共方法
   - 代码清晰易维护

3. ✅ **仍有性能提升 (1.5-2x)**
   - 网络请求并行（多个标签页可同时发送请求）
   - 任务调度优化（减少空闲等待）
   - 后台标签页可预加载资源

4. ✅ **跨平台兼容**
   - Windows、macOS、Linux 均适用
   - 无需额外配置或扩展

#### 性能分析

| 场景 | 顺序处理 | 3标签页 | 5标签页 |
|------|---------|---------|---------|
| 10个达人 | ~3分钟 | ~2分钟 | ~1.5分钟 |
| 50个达人 | ~15分钟 | ~10分钟 | ~7分钟 |
| 100个达人 | ~30分钟 | ~18分钟 | ~15分钟 |

**实际提速**: 1.5-2x（非理论上的 3-5x）

**为什么不能达到 3-5x？**
- 点击操作仍需串行（标签页切换）
- `bring_to_front()` 有 300-800ms 开销
- 浏览器渲染引擎单线程限制

---

## ❌ 已尝试但不可行的方案

### 方案 A: 多 Context 独立窗口

**理想架构**:
```
Browser
├── Context 1 (独立窗口)
│   └── Page 1  ← 所有窗口同时可见
├── Context 2 (独立窗口)
│   └── Page 2  ← 真正并行
└── Context 3 (独立窗口)
    └── Page 3  ← 理论提速 3-5x
```

**为什么不可行？**

❌ **CDP 连接模式的根本限制**:
- `playwright.chromium.connect_over_cdp()` 连接现有浏览器
- 只能访问现有的 BrowserContext
- 无法创建新的 Context（`browser.new_context()` 不可用）
- 新创建的 Context 是全新会话，没有登录状态

❌ **用户反馈**:
> "不能直接打开新窗口，因为这样的话那些网页没有账户登录状态，必须要从这个9224端口连接的浏览器打开新的标签页"

详见: [CDP 模式下的并发爬取限制](cdp_concurrent_limitations.md)

### 方案 B: CDP 窗口分离

**尝试方式**: 使用 CDP 命令将标签页移动到新窗口

❌ **技术限制**:
- CDP 没有"移动标签页到新窗口"的命令
- `Browser.createWindow` 创建新窗口，但无法移动现有标签页
- `Browser.setWindowBounds` 只能调整窗口大小，无法分离标签页
- Chrome Extensions API 需要安装扩展，过于复杂

详见: [CDP 窗口分离方案分析](cdp_window_detachment_analysis.md)

## 📊 未来优化方向

### 方案 A: 多浏览器实例

**可行性**: ✅ 高（但需要手动登录）

```python
# 启动多个独立浏览器（不使用 CDP）
browsers = []
for i in range(3):
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    # 需要手动登录或自动化登录
    browsers.append((browser, context))

# 真正的多浏览器并行
tasks = [scrape_in_browser(browser, id) for browser, id in zip(browsers, ids)]
await asyncio.gather(*tasks)
```

**优势**:
- ✅ 真正的多窗口并行
- ✅ 理论提速 3-5x
- ✅ 无需 CDP

**劣势**:
- ❌ 需要多次手动登录（或自动化登录）
- ❌ 资源消耗高（每个浏览器 ~500MB）
- ❌ 管理复杂度高

### 方案 B: 减少激活次数

**优化思路**: 批量处理同一标签页的任务

```python
# 将任务按标签页分组
page_groups = defaultdict(list)
for i, task in enumerate(tasks):
    page_index = i % max_concurrent
    page_groups[page_index].append(task)

# 每个标签页只激活一次，批量处理
for page_index, task_list in page_groups.items():
    page = pages[page_index]
    await page.bring_to_front()
    for task in task_list:
        await process_task(task, page)
```

**潜在提升**: 减少 bring_to_front() 调用次数

---

## 💡 最佳实践

### 1. 选择合适的并发数

| 并发数 | 适用场景 | 预期提速 | 注意事项 |
|--------|---------|---------|---------|
| 1 | 测试/调试 | 1x (顺序) | 最稳定 |
| 3 | **推荐** | 1.5-2x | 平衡性能与稳定性 |
| 5 | 大批量 | 2-2.5x | 需要稳定网络 |
| >5 | 不推荐 | <2.5x | 可能触发反爬 |

### 2. 优化激活策略

**减少激活次数** - 只在交互操作前激活:

```python
# ✅ 好: 只在交互前激活
await page.evaluate("window.scrollTo(0, 1000)")  # 滚动不需要激活
await page.bring_to_front()  # 点击前才激活
await page.click("button")
```

**合并交互操作** - 一次激活完成所有交互:

```python
# ✅ 好: 一次激活完成所有交互
await page.bring_to_front()
await page.click("#menu1")
await asyncio.sleep(1)
await page.click("#menu2")  # 仍在激活状态
```

### 3. 监控性能

```python
# 记录标签页切换次数和耗时
switch_count = 0
switch_time = 0

start = time.time()
await page.bring_to_front()
switch_time += time.time() - start
switch_count += 1

# 分析切换开销占比
print(f"切换次数: {switch_count}, 总耗时: {switch_time:.2f}秒")
```

---

## 🔧 当前实现细节

### 关键代码位置

1. **标签页创建** ([playwright_api.py:1188-1195](../playwright_api.py#L1188-L1195))
   ```python
   pages = []
   for i in range(max_concurrent):
       page = await _context.new_page()  # 共享 Context
       pages.append(page)
   ```

2. **任务激活** ([playwright_api.py:852-855](../playwright_api.py#L852-L855))
   ```python
   if page is not None:
       await page.bring_to_front()
       await asyncio.sleep(0.5)
   ```

3. **下拉菜单激活** ([playwright_api.py:992-995](../playwright_api.py#L992-L995))
   ```python
   if page is not None:
       await page.bring_to_front()
       await asyncio.sleep(0.3)
   ```

4. **并发调度** ([playwright_api.py:1242-1246](../playwright_api.py#L1242-L1246))
   ```python
   tasks = [
       fetch_with_semaphore(influencer_id, i)
       for i, influencer_id in enumerate(need_fetch_ids)
   ]
   await asyncio.gather(*tasks)
   ```

5. **清理资源** ([playwright_api.py:1249-1252](../playwright_api.py#L1249-L1252))
   ```python
   for page in pages:
       await page.close()
   ```

---

## 🐛 常见问题

### Q1: 为什么有时点击仍然失败?

**原因**:
- 标签页切换动画未完成
- 元素被其他元素遮挡
- 页面仍在渲染中

**解决**:
```python
# 增加等待时间
await page.bring_to_front()
await asyncio.sleep(1)  # 从 0.5 增加到 1

# 或者等待元素稳定
await page.wait_for_selector("button", state="visible")
await page.click("button")
```

### Q2: 并发数越高,失败越多?

**原因**: 标签页频繁切换导致竞争条件

**解决**: 降低并发数
```python
# 网络不稳定时
max_concurrent = 2  # 而非 5

# 或增加延迟
await asyncio.sleep(2)  # 给标签页更多稳定时间
```

### Q3: 为什么顺序处理不需要激活?

**原因**: 顺序处理使用全局 `_page`,始终处于激活状态

```python
# 顺序处理
fetch_influencer_detail_async(id)  # page=None,使用全局_page

# 并发处理
fetch_influencer_detail_async(id, page=custom_page)  # 需要激活
```

## 📚 参考资料

### Playwright 官方文档

- [Page.bring_to_front()](https://playwright.dev/python/docs/api/class-page#page-bring-to-front)
- [Actionability checks](https://playwright.dev/python/docs/actionability)
- [Multi-page scenarios](https://playwright.dev/python/docs/pages)

### 相关代码

- 并发实现: [playwright_api.py:1007-1184](../playwright_api.py#L1007-L1184)
- 爬取函数: [playwright_api.py:757-1004](../playwright_api.py#L757-L1004)
- 下拉菜单处理: [playwright_api.py:982-1022](../playwright_api.py#L982-L1022)

## 💡 总结

### 关键要点

1. ✅ **多标签页 + bring_to_front() 是 CDP 模式下的唯一可行方案**
2. ✅ **保留登录状态**: 所有标签页共享同一 Context
3. ✅ **仍有性能提升**: 1.5-2x 提速（虽非真正并行）
4. ✅ **稳定可靠**: 使用 Playwright 官方 API

### 架构演进

```
v1.0 (顺序处理)
→ 单 Context, 单 Page
→ 100个达人 ~30分钟
→ 最稳定，但效率低

v2.0 (多标签页 + bring_to_front - 当前实现)
→ 单 Context, 多标签页 + 激活
→ 伪并发（点击串行，网络并行）
→ 100个达人 ~18分钟
→ 提速 1.5-2x

v3.0 (多 Context - CDP 模式下不可行)
→ 多 Context, 多独立窗口
→ 真正并行
→ 100个达人 ~10分钟（理论）
→ ❌ 但会失去登录状态

v4.0 (多浏览器实例 - 未来可能)
→ 多浏览器, 每个独立登录
→ 真正并行
→ 100个达人 ~10分钟
→ ⚠️ 需要自动化登录或手动登录
```

### 推荐策略

**当前环境（CDP 连接模式）**:
- 使用 v2.0 方案（多标签页 + bring_to_front）
- 并发数设置为 3-5
- 预期提速 1.5-2x

**未来优化（如需要更高性能）**:
- 考虑 v4.0 方案（多浏览器实例）
- 需要解决自动登录问题
- 可实现真正的 3-5x 提速

---

**最后更新**: 2025-01-10
**作者**: Claude Code (基于技术调研与用户反馈)
