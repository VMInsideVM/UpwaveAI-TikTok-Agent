# 🚀 快速启动指南

## 第一次使用? 跟着这个指南 3 分钟搞定!

---

## 📋 前置要求检查清单

在开始之前,确保你有:

- [ ] Python 3.8 或更高版本
- [ ] Google Chrome 浏览器
- [ ] 稳定的网络连接
- [ ] 已配置 `.env` 文件 (SiliconFlow API)

---

## 🎯 3 步启动

### 步骤 1: 安装依赖 (首次运行)

打开终端,进入项目目录:

```bash
cd c:\Users\Hank\PycharmProjects\fastmoss_MVP
pip install -r requirements.txt
```

**预计时间**: 1-2 分钟

**如果出错**:
- 确保 Python 版本 >= 3.8: `python --version`
- 使用国内镜像: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

---

### 步骤 2: 启动 Chrome (CDP 模式)

**重要**: 必须以调试模式启动 Chrome

**Windows**:
```bash
chrome.exe --remote-debugging-port=9224
```

**如果 chrome.exe 不在 PATH 中**:
```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9224
```

**其他系统**:
- macOS: `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9224`
- Linux: `google-chrome --remote-debugging-port=9224`

**预计时间**: 10 秒

**成功标志**: Chrome 打开一个新窗口,地址栏下方显示 "Chrome 正在受到自动测试软件的控制"

---

### 步骤 3: 运行测试 (可选但推荐)

在新的终端窗口(保持 Chrome 运行):

```bash
python test_components.py
```

**预计时间**: 30 秒

**应该看到**:
```
✅ 所有依赖导入成功!
✅ 环境变量配置完整!
✅ 分类文件完整!
✅ 分类匹配模块正常!
✅ Agent 工具模块正常!
✅ 输出目录存在!
```

如果提示测试 LLM 连接,输入 `y` 测试(需要网络)。

---

### 步骤 4: 启动 Agent!

```bash
python run_agent.py
```

**预计时间**: 5 秒

**应该看到欢迎界面**:
```
╔═══════════════════════════════════════════════════════════════╗
║      🚀 TikTok 达人推荐智能助手 v1.0 🚀                      ║
╚═══════════════════════════════════════════════════════════════╝

我可以帮助你找到最适合推广你商品的 TikTok 达人!

📋 **可用的筛选参数**:
...
```

---

## 💬 第一次对话示例

### 示例 1: 简单需求

```
👤 你: 我要推广口红,在美国找 20 个达人

🤖 Agent: 好的!请问你对达人的粉丝数量有要求吗?

👤 你: 10万到50万粉丝,要有邮箱

🤖 Agent:
  [开始执行]
  🔍 正在分析商品 "口红"...
  ✅ 匹配到: 美妆个护 > 彩妆 > 口红
  🔗 正在构建搜索 URL...
  📊 正在检查可用达人数量...
  ✅ 约有 500 个符合条件的达人
  🌐 正在爬取前 20 个达人数据...
  ✅ 数据爬取成功!
  📁 正在导出 Excel...

  ✅ 完成!
  文件: output/tiktok_达人推荐_口红_20250103_143025.xlsx
  共 20 个达人
```

### 示例 2: 复杂需求

```
👤 你: 我要推广瑜伽垫,在印尼找 50 个达人,粉丝 5 万到 20 万,
     女粉为主,18-34 岁,关注互动率和带货能力

🤖 Agent:
  [理解你的需求]
  - 商品: 瑜伽垫
  - 国家: 印度尼西亚
  - 数量: 50 个
  - 粉丝: 50,000 - 200,000
  - 粉丝特征: 女性为主, 18-34岁
  - 关注维度: 互动率 + 带货能力

  [开始执行]
  🔍 分析商品分类...
  ✅ 运动与户外 > 瑜伽用品

  📊 检查数量...
  ⚠️  只找到约 30 个达人,但你需要 50 个

  💡 建议调整:
  1. 放宽粉丝范围: 3万-30万
  2. 取消年龄限制

  是否接受调整? (y/n)

👤 你: y

🤖 Agent:
  ✅ 重新搜索...
  📈 现在约有 80 个达人

  因为你关注多个维度,我会:
  1. 按"互动率"爬取前 50 个
  2. 按"近28天总销量"爬取前 50 个
  3. 合并去重

  [爬取中...]
  ✅ 完成! 共获得 65 个达人(去重后)
```

---

## ❓ 常见问题快速解决

### Q: 提示 "Playwright 未初始化"

**A**: Chrome 没有以 CDP 模式启动

**解决**:
```bash
# 关闭所有 Chrome 窗口
# 重新运行:
chrome.exe --remote-debugging-port=9224
```

---

### Q: 提示 "❌ 无法连接 LLM"

**A**: 检查 `.env` 配置和网络

**解决**:
```bash
# 1. 检查 .env 文件
cat .env

# 2. 测试网络连接
ping api.siliconflow.cn

# 3. 重新运行测试
python test_components.py
```

---

### Q: 提示 "❌ 找不到商品分类"

**A**: 商品名称太模糊或不在 29 个分类中

**解决**:
- 使用更具体的商品名
- 例如: "护肤品" → "面霜"
- 例如: "衣服" → "女装连衣裙"

---

### Q: Agent 回复很慢

**A**: 这是正常的,LLM 推理需要时间

**预期速度**:
- 普通回复: 3-5 秒
- 分类推理: 5-10 秒
- 爬取数据: 根据数量,可能 1-5 分钟

---

### Q: 爬取失败

**A**: 可能是网站响应问题或筛选条件太严

**解决**:
1. Agent 会自动重试 3 次
2. 如果仍失败,尝试放宽筛选条件
3. 检查 Chrome 是否已登录 FastMoss

---

## 🎓 学习路径

### 新手 (第 1 天)

1. ✅ 跟着快速启动指南运行成功
2. ✅ 尝试 3-5 个不同的商品推荐
3. ✅ 熟悉基本的筛选参数
4. ✅ 查看导出的 Excel 文件

### 进阶 (第 2-3 天)

1. 📖 阅读 `README.md` 了解详细功能
2. 📝 编辑 `knowledge_base.md` 添加自己的经验
3. 🧪 尝试复杂的多维度筛选
4. 📊 分析 Excel 数据,总结规律

### 高级 (第 4-7 天)

1. 📚 阅读 `IMPLEMENTATION_SUMMARY.md` 理解架构
2. 🔧 修改 `agent.py` 自定义 Agent 行为
3. 🛠️ 在 `agent_tools.py` 中添加新工具
4. 🚀 根据实际使用优化参数和策略

---

## 📚 相关文档

| 文档 | 用途 |
|------|------|
| `QUICK_START.md` | 本文档,快速上手 |
| `README.md` | 详细功能说明和使用指南 |
| `knowledge_base.md` | 参数说明,可编辑 |
| `IMPLEMENTATION_SUMMARY.md` | 技术架构和实现细节 |

---

## 🎉 准备好了吗?

现在你已经了解了所有必要的信息!

**开始你的第一个达人推荐任务**:

```bash
# 1. 启动 Chrome (如果还没启动)
chrome.exe --remote-debugging-port=9224

# 2. 新终端,运行 Agent
python run_agent.py

# 3. 输入你的需求,例如:
"我要推广口红,在美国找 20 个达人,粉丝 10 万到 50 万"
```

**祝你使用愉快!** 🚀

---

**如有问题,查看**:
- 📖 `README.md` - 详细文档
- 🧪 `python test_components.py` - 测试诊断
- 🐛 GitHub Issues - 提交问题

**最后更新**: 2025-01-03
