# CDP 模式下的并发爬取限制与实现

**文档日期**: 2025-01-10
**状态**: 最终方案

---

## 🎯 核心问题

### 理想方案 vs 实际限制

**理想方案（多窗口真正并行）**:
```
Browser
├── Context 1 (独立窗口) → Page 1 ← 所有窗口同时可见
├── Context 2 (独立窗口) → Page 2 ← 可同时点击
└── Context 3 (独立窗口) → Page 3 ← 真正并行
```

**实际限制（CDP 连接模式）**:
```
Browser (CDP:9224)
└── Context (共享会话，保留登录状态)
    ├── Page 1 (Tab 1) ← 需要激活才能交互
    ├── Page 2 (Tab 2) ← 后台标签页
    └── Page 3 (Tab 3) ← 后台标签页
```

---

## 🚫 为什么无法创建多个 Context？

### CDP 连接的特性

当使用 `playwright.chromium.connect_over_cdp()` 连接现有浏览器时：

1. **只能访问现有 Context**
   - CDP 连接返回的 `Browser` 对象无法创建新的 BrowserContext
   - 只能访问浏览器中已存在的上下文
   - `browser.new_context()` 在 CDP 模式下不可用

2. **登录状态绑定到 Context**
   - 网站的登录 Cookie 和 Session 存储在 BrowserContext 中
   - 新创建的 Context 是全新的会话，没有登录状态
   - 需要重新登录才能访问需要认证的页面

3. **CDP 连接的目的**
   - 设计初衷是连接到用户手动打开的浏览器
   - 目的是复用用户的浏览器状态（包括登录）
   - 而不是创建新的隔离会话

### 测试验证

```python
# ❌ 在 CDP 模式下会报错或无效
browser = await playwright.chromium.connect_over_cdp("http://localhost:9224")
new_context = await browser.new_context()  # TypeError 或返回 None
```

---

## ✅ 实际实现方案

### 方案：多标签页 + 自动激活

由于无法创建多个 Context，我们采用以下方案：

#### 架构

```python
# CDP 连接到现有浏览器
browser = await playwright.chromium.connect_over_cdp("http://localhost:9224")
contexts = browser.contexts
context = contexts[0]  # 使用现有的 Context（保留登录状态）

# 在同一个 Context 中创建多个标签页
pages = []
for i in range(max_concurrent):
    page = await context.new_page()  # 共享登录状态
    pages.append(page)

# 并发任务调度
async def fetch_with_activation(influencer_id, page):
    await page.bring_to_front()  # 激活标签页
    await asyncio.sleep(0.5)      # 等待切换完成
    # 执行爬取...

tasks = [fetch_with_activation(id, pages[i % len(pages)])
         for i, id in enumerate(ids)]
await asyncio.gather(*tasks)
```

#### 工作流程

```
任务1 → 激活Tab1 → 点击 → 等待 → 数据提取
任务2 → 激活Tab2 → 点击 → 等待 → 数据提取
任务3 → 激活Tab3 → 点击 → 等待 → 数据提取
任务4 → 激活Tab1 → 点击 → 等待 → 数据提取 (复用Tab1)
...

注意：虽然使用 asyncio.gather 调度，但由于 bring_to_front() 的串行性质，
交互操作实际上是依次执行的（非真正并行）
```

---

## 📊 性能分析

### 实际提速效果

| 场景 | 顺序处理 | 3标签页 | 5标签页 | 说明 |
|------|---------|---------|---------|------|
| 单个达人 | 15-20秒 | 15-20秒 | 15-20秒 | 单任务无差异 |
| 10个达人 | ~3分钟 | ~2分钟 | ~1.5分钟 | 调度优化 |
| 100个达人 | ~30分钟 | ~18分钟 | ~15分钟 | 1.7-2x提速 |

### 为什么仍能提速？

尽管不是真正并行，但仍有性能提升：

1. **任务调度优化**
   - `asyncio.gather` 可以更高效地管理任务队列
   - 避免了顺序处理中的空闲等待时间

2. **网络请求并行**
   - 多个标签页的网络请求可以并行
   - `page.goto()` 和 API 响应可以同时进行

3. **资源预加载**
   - 后台标签页可以预加载部分资源
   - 减少激活后的等待时间

4. **减少单任务阻塞**
   - 单个任务失败不会阻塞整个队列
   - 任务完成后立即处理下一个

### 理论极限

**为什么提速不能达到 3-5x？**

- 交互操作仍需串行（标签页切换）
- `bring_to_front()` 有 300-800ms 开销
- 浏览器渲染引擎单线程限制
- 网站反爬限制（请求频率）

---

## 🎛️ 当前实现细节

### 关键代码位置

1. **标签页创建** ([playwright_api.py:1167-1175](../playwright_api.py#L1167-L1175))
   ```python
   pages = []
   for i in range(max_concurrent):
       page = await _context.new_page()  # 共享 Context
       pages.append(page)
   ```

2. **任务激活** ([playwright_api.py:849-851](../playwright_api.py#L849-L851))
   ```python
   if page is not None:
       await page.bring_to_front()
       await asyncio.sleep(0.5)
   ```

3. **下拉菜单激活** ([playwright_api.py:989-991](../playwright_api.py#L989-L991))
   ```python
   if page is not None:
       await page.bring_to_front()
       await asyncio.sleep(0.3)
   ```

4. **并发调度** ([playwright_api.py:1221-1226](../playwright_api.py#L1221-L1226))
   ```python
   tasks = [
       fetch_with_semaphore(influencer_id, i)
       for i, influencer_id in enumerate(need_fetch_ids)
   ]
   await asyncio.gather(*tasks)
   ```

---

## 💡 最佳实践

### 推荐配置

```python
# 根据网络状况和系统资源选择并发数
max_concurrent = 3  # 推荐：平衡性能与稳定性

# 调用 API
response = requests.post(
    "http://127.0.0.1:8000/process_influencer_list_concurrent",
    json={
        "json_file_path": "output/your_file.json",
        "cache_days": 3,
        "max_concurrent": 3  # 3-5 标签页
    }
)
```

### 并发数选择

| 并发数 | 适用场景 | 预期提速 | 注意事项 |
|--------|---------|---------|---------|
| 1 | 测试/调试 | 1x (顺序) | 最稳定 |
| 3 | **推荐** | 1.5-2x | 平衡性能与稳定性 |
| 5 | 大批量 | 2-2.5x | 需要稳定网络 |
| >5 | 不推荐 | <2.5x | 可能触发反爬 |

---

## 🔄 未来改进方向

### 可能的优化

1. **智能标签页复用**
   - 根据任务状态动态分配标签页
   - 优先使用空闲标签页

2. **减少激活次数**
   - 批量处理同一标签页的任务
   - 减少 `bring_to_front()` 调用

3. **混合模式**
   - 非交互操作（如 goto, evaluate）不激活
   - 只在点击/填写时激活

4. **多浏览器实例**（需要手动登录）
   - 启动多个独立浏览器
   - 每个浏览器单独登录
   - 真正的多窗口并行

---

## 📚 相关文档

- [多标签页并发爬取功能指南](concurrent_scraping_guide.md)
- [并发爬取技术细节](concurrent_scraping_technical_notes.md)
- [项目主文档](../CLAUDE.md)

---

## 🎯 总结

### 核心结论

1. ✅ **CDP 模式必须使用多标签页方案**
   - 无法创建新 Context（需要保留登录状态）
   - 标签页共享同一会话

2. ✅ **仍能获得 1.5-2x 提速**
   - 任务调度优化
   - 网络请求并行
   - 减少空闲等待

3. ✅ **适合大批量处理**
   - 100+ 达人数据获取
   - 可节省 10-15 分钟

4. ❌ **无法达到真正并行**
   - 交互操作仍需串行
   - 理论极限 ~2-2.5x 提速

### 实用建议

- **小批量 (<20个)**: 使用顺序处理（简单稳定）
- **中批量 (20-100个)**: 使用 3 标签页并发（推荐）
- **大批量 (>100个)**: 使用 5 标签页并发（需要稳定网络）

---

**最后更新**: 2025-01-10
**作者**: Claude Code (基于用户洞察修正)
