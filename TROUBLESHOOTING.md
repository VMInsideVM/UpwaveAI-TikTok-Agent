# 故障排查指南

## 问题: Agent 访问 URL 获取最大页面数量失败

### 🔍 问题表现
- Agent 在调用 `get_max_page_number` 工具时失败
- 返回错误消息: "无法访问搜索页面" 或 "获取最大页数失败"

### ✅ 解决方案

#### 1. 检查 Chrome 浏览器是否正在运行

**问题**: Playwright 需要连接到运行中的 Chrome 浏览器

**解决**:
```bash
# Windows
chrome.exe --remote-debugging-port=9224 --user-data-dir="C:\chrome-debug"

# 或者使用 Chrome 的完整路径
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9224 --user-data-dir="C:\chrome-debug"
```

**验证**:
- 浏览器窗口应该打开
- 访问 `http://localhost:9224/json` 应该看到 JSON 响应

#### 2. 确认 CDP 端口 9224 可访问

**检查端口**:
```bash
# Windows
netstat -ano | findstr :9224
```

**如果端口被占用**:
- 关闭占用该端口的其他 Chrome 实例
- 或使用其他端口(需要修改 `main.py` 中的端口号)

#### 3. 验证 Playwright 初始化

**测试脚本**:
```python
python test_get_max_page.py
```

**预期输出**:
```
✅ Playwright 初始化成功
✅ 最大页数: XX, 预计约有 XXX 个达人
```

#### 4. 检查 URL 格式

**正确的 URL 格式**:
```
https://www.fastmoss.com/zh/influencer/search?region=US&sale_category_l1=2
```

**关键点**:
- ✅ 必须包含分类后缀 (`sale_category_l1`, `sale_category_l2`, 或 `sale_category_l3`)
- ✅ URL 应该由 Agent 工具自动构建(不建议手动拼接)

**Agent 正确流程**:
1. 使用 `build_search_url` 构建基础 URL
2. 使用 `match_product_category` 获取分类信息(包含 `url_suffix`)
3. 将 `url_suffix` 追加到基础 URL
4. 使用完整 URL 调用 `get_max_page_number`

#### 5. 网络和加载问题

**症状**: 页面加载超时

**解决**:
- 检查网络连接
- 确保可以访问 `https://www.fastmoss.com`
- 增加 `navigate_to_url` 的超时时间(当前 60 秒)

#### 6. 查看详细错误日志

**开启调试模式**:
修改 `agent.py` 第 130 行:
```python
debug=True  # 已开启
```

**运行时查看控制台输出**:
- 🔧 初始化信息
- 🌐 URL 访问信息
- 📊 页面数据获取信息
- ❌ 具体错误信息和堆栈跟踪

### 🧪 测试修复

#### 测试 1: 组件测试
```bash
python test_components.py
```

#### 测试 2: 单独测试获取页数
```bash
python test_get_max_page.py
```

#### 测试 3: 完整 Agent 测试
```bash
python run_agent.py
```

测试对话:
```
你: 我要推广口红,在美国找20个达人
Agent: (应该能成功匹配分类并获取页数)
```

### 📋 常见错误代码

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `Playwright 未初始化` | Chrome 未运行或连接失败 | 启动 Chrome with CDP |
| `无法访问搜索页面` | URL 错误或网络问题 | 检查 URL 格式 |
| `只找到 1 页数据` | 筛选条件太严格或分类错误 | 放宽条件或检查分类 |
| `获取最大页数失败` | 页面元素未加载 | 增加等待时间 |

### 🔧 最新改进 (v1.1)

#### GetMaxPageTool 增强:
1. ✅ 更好的错误处理和提示信息
2. ✅ 自动检测 Playwright 初始化状态
3. ✅ 详细的失败原因诊断
4. ✅ 堆栈跟踪输出(便于调试)
5. ✅ 智能提示(当只找到1页时给出建议)

#### 改进的错误消息:
- 明确指出可能的原因
- 提供具体的检查步骤
- 包含解决建议

### 📞 如果问题仍然存在

1. **运行完整诊断**:
   ```bash
   python test_get_max_page.py
   ```

2. **收集以下信息**:
   - 错误消息全文
   - 控制台输出
   - `netstat` 输出
   - Chrome 版本
   - 使用的 URL

3. **检查这些文件**:
   - `agent_tools.py` (GetMaxPageTool 实现)
   - `main.py` (navigate_to_url 和 get_max_page_number)
   - `.env` (环境配置)

### 💡 预防性建议

1. **每次使用前启动 Chrome**:
   ```bash
   chrome.exe --remote-debugging-port=9224 --user-data-dir="C:\chrome-debug"
   ```

2. **保持浏览器窗口打开**:
   - 不要关闭 CDP 连接的 Chrome 窗口
   - 可以手动导航到 fastmoss.com 确保网站可访问

3. **定期检查端口**:
   - 确保 9224 端口不被其他程序占用

4. **使用测试脚本验证**:
   - 运行 Agent 前先执行 `test_get_max_page.py`
   - 确保基础功能正常

---

## 其他常见问题

### 问题: 分类匹配失败

**症状**: `match_product_category` 返回 None

**解决**: 查看 `test_new_classifier.py` 测试结果

### 问题: Excel 导出失败

**症状**: 无法保存文件

**解决**: 检查 `output/` 目录权限

### 问题: LLM 连接失败

**症状**: Agent 无法响应

**解决**: 检查 `.env` 中的 API 配置
