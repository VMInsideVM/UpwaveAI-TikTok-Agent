# 测试文档 - 批量获取达人详细数据功能

## 📋 测试文件说明

本项目包含 3 个测试文件，用于验证新增的批量获取达人详细数据功能：

### 1. `test_api_direct.py` - API 基础功能测试
**用途**: 快速验证 API 服务是否正常运行
**耗时**: < 10 秒
**推荐**: ⭐⭐⭐⭐⭐ 首次测试必运行

**测试内容**:
- ✅ 健康检查 (`GET /health`)
- ✅ 页面导航 (`POST /navigate`)
- ✅ 获取当前 URL (`GET /current_url`)
- ✅ API 文档访问 (`GET /docs`)

**运行方式**:
```bash
python test_api_direct.py
```

---

### 2. `test_quick.py` - 快速功能测试
**用途**: 测试单个达人数据获取
**耗时**: 5-10 秒（首次） / < 1 秒（缓存）
**推荐**: ⭐⭐⭐⭐ 验证核心功能

**测试内容**:
- ✅ 创建测试 JSON 文件（1 个达人）
- ✅ 调用 `/process_influencer_list` API
- ✅ 验证文件生成
- ✅ 显示文件内容摘要

**运行方式**:
```bash
python test_quick.py
```

**测试达人 ID**: `7288986759428588590`

---

### 3. `test_process_influencer.py` - 完整功能测试
**用途**: 测试批量处理多个达人
**耗时**: 25-50 秒（首次，5 个达人） / < 1 秒（缓存）
**推荐**: ⭐⭐⭐ 完整验证所有功能

**测试内容**:
- ✅ 健康检查
- ✅ 创建测试 JSON 文件（5 个达人）
- ✅ 批量处理达人列表
- ✅ 验证文件生成
- ✅ 显示详细统计信息
- ✅ 列出失败的 ID

**运行方式**:
```bash
python test_process_influencer.py
```

**测试达人 ID**:
- `7288986759428588590`
- `7170541438504420394`
- `6951979291350795269`
- `6829673971714688006`
- `7344820820893000743`

---

## 🚀 快速开始

### 前置条件

1. **启动 Chrome（CDP 模式）**
   ```bash
   # Windows
   chrome.exe --remote-debugging-port=9224

   # macOS
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9224

   # Linux
   google-chrome --remote-debugging-port=9224
   ```

2. **启动 Playwright API 服务**
   ```bash
   # 方式 1: 直接运行
   python playwright_api.py

   # 方式 2: 使用启动脚本
   python start_api.py
   ```

   等待看到以下输出：
   ```
   ✅ Playwright API 服务启动成功！(Async 模式)
   📡 API 文档: http://127.0.0.1:8000/docs
   ```

### 测试流程（推荐顺序）

#### Step 1: 基础功能测试
```bash
python test_api_direct.py
```

**预期输出**:
```
✅ 状态: healthy
   Playwright 初始化: True
✅ 导航成功
✅ 当前 URL: https://www.fastmoss.com/zh/influencer/detail/...
✅ API 文档可访问
```

#### Step 2: 快速功能测试
```bash
python test_quick.py
```

**预期输出**:
```
✅ 成功!
📊 结果:
   • 总数: 1
   • 缓存: 0 (或 1，如果之前测试过)
   • 获取: 1 (或 0，如果使用缓存)
   • 失败: 0
   • 耗时: 0:00:05 (首次) 或 0:00:00 (缓存)
✅ 文件已生成: influencer/7288986759428588590.json
```

#### Step 3: 完整功能测试
```bash
python test_process_influencer.py
```

**预期输出**:
```
✅ API 服务状态: healthy
✅ 测试 JSON 文件已创建
✅ API 调用成功!

📊 处理结果:
   • 总达人数: 5
   • 使用缓存: 1 (如果之前测试过)
   • 重新获取: 4
   • 失败: 0
   • 耗时: 0:00:25

📁 验证文件生成...
   influencer 目录包含 5 个文件
   ✓ 7288986759428588590.json 已生成
   ✓ 7170541438504420394.json 已生成
```

---

## 📁 文件结构

测试完成后，会生成以下文件：

```
fastmoss_MVP/
├── output/
│   ├── test_single.json              # 快速测试的输入文件
│   └── test_influencer_list.json     # 完整测试的输入文件
├── influencer/
│   ├── 7288986759428588590.json      # 达人详细数据
│   ├── 7170541438504420394.json
│   ├── 6951979291350795269.json
│   ├── 6829673971714688006.json
│   └── 7344820820893000743.json
└── ...
```

每个 `influencer/{id}.json` 文件包含：
- `target_url`: 达人详情页 URL
- `capture_time`: 数据采集时间（格式：YYYY-MM-DD HH:MM:SS）
- `total_requests`: API 请求总数
- `api_responses`: 8 种 API 响应类型的数据
  - `datalist`: 数据列表（按 field_type 分组）
  - `baseInfo`: 基本信息
  - `authorIndex`: 作者索引
  - `getStatInfo`: 统计信息
  - `fansPortrait`: 粉丝画像
  - `labelList`: 标签列表
  - `cargoStat`: 货物统计
  - `cargoSummary`: 货物摘要

---

## ⚙️ 缓存机制测试

### 测试缓存有效性

1. **首次运行**（无缓存）:
   ```bash
   python test_quick.py
   ```
   输出：`• 获取: 1`（耗时 5-10 秒）

2. **再次运行**（有缓存，3 天内）:
   ```bash
   python test_quick.py
   ```
   输出：`• 缓存: 1`（耗时 < 1 秒）

3. **测试缓存过期**:
   - 手动修改 `influencer/7288986759428588590.json` 中的 `capture_time`
   - 改为 4 天前：`2025-10-31 12:00:00`
   - 再次运行测试，会重新爬取

### 测试不同缓存有效期

修改测试文件中的 `cache_days` 参数：

```python
# test_quick.py 中
response = requests.post(
    f"{API_BASE_URL}/process_influencer_list",
    json={
        "json_file_path": test_file,
        "cache_days": 7  # 改为 7 天
    }
)
```

---

## 🐛 故障排查

### 问题 1: 无法连接到 API 服务
```
❌ 无法连接到 API 服务 (http://127.0.0.1:8000)
```

**解决方案**:
1. 确认 Playwright API 服务已启动：`python playwright_api.py`
2. 检查端口 8000 是否被占用：`netstat -ano | findstr 8000`
3. 查看 API 服务的控制台输出是否有错误

---

### 问题 2: Playwright 未初始化
```
❌ Playwright 未初始化
```

**解决方案**:
1. 确认 Chrome 运行在 CDP 端口 9224
2. 检查防火墙是否阻止端口 9224
3. 重启 Chrome 和 API 服务

---

### 问题 3: 测试超时
```
⏰ API 请求超时（600秒）
```

**解决方案**:
1. 这可能是正常的（处理大量达人时）
2. 检查网络连接
3. 查看 API 服务日志，确认正在处理
4. 减少测试的达人数量

---

### 问题 4: 部分达人获取失败
```
⚠️ 失败的达人 ID:
   - 6829673971714688006
```

**可能原因**:
1. 达人 ID 不存在或已删除
2. 网络波动导致页面加载失败
3. 达人详情页结构变化

**解决方案**:
- 单个失败不影响整体流程
- 查看 API 日志获取详细错误信息
- 可以手动重试失败的 ID

---

## 📊 性能基准

| 测试场景 | 达人数量 | 首次耗时 | 缓存耗时 |
|---------|---------|---------|---------|
| 快速测试 | 1 | 5-10 秒 | < 1 秒 |
| 完整测试 | 5 | 25-50 秒 | < 1 秒 |
| 实际场景 | 287 | 16-35 分钟 | 1-2 秒 |

**注意**: 耗时取决于网络速度和页面复杂度

---

## 🔧 高级测试

### 测试大批量处理

使用真实的导出文件测试：

```bash
# 假设您已经通过 Agent 生成了文件
python -c "
import requests
response = requests.post(
    'http://127.0.0.1:8000/process_influencer_list',
    json={
        'json_file_path': 'output/tiktok_达人推荐_女士香水_20251104_165214.json',
        'cache_days': 3
    },
    timeout=3600  # 1 小时超时
)
print(response.json())
"
```

### 测试并发（不推荐）

虽然 API 支持并发请求，但不推荐同时处理多个批次：
- 可能触发反爬机制
- 影响数据质量
- 增加服务器负载

---

## 📝 测试报告模板

测试完成后，可以按以下模板记录结果：

```
测试日期: 2025-11-04
测试人员: [您的名字]
测试文件: test_process_influencer.py

环境信息:
- Python 版本: 3.x
- Playwright 版本: x.x.x
- Chrome 版本: xxx

测试结果:
✅ test_api_direct.py - 通过
✅ test_quick.py - 通过
✅ test_process_influencer.py - 通过

性能数据:
- 单个达人耗时: 7 秒
- 5 个达人耗时: 35 秒
- 缓存命中率: 20% (1/5)

问题记录:
- 无

备注:
[其他需要记录的信息]
```

---

## 🎯 下一步

测试通过后：
1. ✅ 重启 Playwright API 服务
2. ✅ 通过 Agent 使用新功能
3. ✅ 处理真实的达人列表文件
4. ✅ 查看 `influencer/` 目录中的详细数据

---

## 📚 相关文档

- [API 文档](http://127.0.0.1:8000/docs) - 启动服务后访问
- [CLAUDE.md](CLAUDE.md) - 项目整体文档
- [playwright_api.py](playwright_api.py) - API 实现源码
- [agent_tools.py](agent_tools.py) - Agent 工具实现

---

**祝测试顺利！** 🎉
