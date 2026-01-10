# LangGraph 工作流快速开始指南

## 🚀 5 分钟快速上手

### 步骤 1: 重新创建虚拟环境 (解决路径问题)

```bash
# Windows PowerShell
cd C:\Users\Hank\PycharmProjects\UpwaveAI-TikTok-Agent

# 删除旧虚拟环境
Remove-Item -Recurse -Force .venv

# 创建新虚拟环境
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1
```

### 步骤 2: 安装依赖

```bash
# 升级 pip
python -m pip install --upgrade pip

# 安装所有依赖 (包括 langgraph)
pip install -r requirements.txt

# 验证 langgraph 安装
python -c "import langgraph; print(f'✅ LangGraph {langgraph.__version__} 已安装')"
```

预期输出:
```
✅ LangGraph 0.2.x 已安装
```

### 步骤 3: 测试工作流

```bash
# 运行工作流测试
python test_url_workflow.py
```

预期输出:
```
======================================================================
🧪 测试: LangGraph URL 构建工作流
======================================================================

📍 步骤1: 初始化 Agent...
✅ Agent 初始化成功
✅ LangGraph URL 构建工作流已启用  ← 关键!

📍 步骤2: 创建 URL 构建工作流...
✅ 工作流创建成功

📍 步骤3: 准备测试参数...
  商品: 口红
  国家: 美国
  粉丝范围: 10,000 - 100,000
  目标数量: 20 个达人

📍 步骤4: 执行工作流...
----------------------------------------------------------------------
[URLBuildWorkflow] 🚀 开始执行工作流
[URLBuildWorkflow] 📍 步骤1: 构建搜索 URL
  ✅ URL 构建成功
[URLBuildWorkflow] 📍 步骤2: 强制调用 review_parameters
  ✅ 参数展示完成
[URLBuildWorkflow] ✅ 工作流执行完成
----------------------------------------------------------------------
✅ 工作流执行成功

📍 步骤5: 验证结果...
✅ URL 已构建
✅ review_parameters 已被强制调用  ← 关键!
✅ 参数展示输出已生成

📍 步骤6: 展示给用户的内容:
======================================================================
[🔔 请将以下内容完整展示给用户]

📋 **当前筛选参数摘要**

🎯 **商品信息**
   • 商品名称: 口红
   • 商品分类: 口红
   • 目标数量: 20 个达人

🌍 **目标地区**: 美国

🔍 **筛选条件**
   • 粉丝数: 10,000 - 100,000
   • 推广渠道: 不限制
   ...

请确认参数是否正确？
======================================================================

======================================================================
🎉 测试通过!
======================================================================

✅ 验证结果:
  1. build_search_url 被正确调用
  2. review_parameters 被强制调用 (无法跳过)  ← 成功!
  3. 参数展示内容已生成
  4. 工作流保证了正确的执行顺序

🔥 结论: LangGraph 工作流成功强制执行了 review_parameters!
```

### 步骤 4: 交互式测试 (可选)

```bash
# 启动 agent 进行交互测试
python run_agent.py
```

测试对话:
```
Agent: 你好! 我是 TikTok 达人推荐助手...

用户: 我想在美国找20个达人推广口红

Agent: [Agent] 🔥 触发 LangGraph 工作流  ← 看到这个!
       [Agent] 🚀 使用 LangGraph 工作流执行...
       [URLBuildWorkflow] ...
       [Agent] ✅ 工作流执行完成

       📋 当前筛选参数摘要  ← 必定出现!

       🎯 商品信息
          • 商品名称: 口红
          • 目标数量: 20 个达人

       🌍 目标地区: 美国

       请确认参数是否正确？

用户: 确认

Agent: [继续流程...]
```

## ✅ 验证清单

完成上述步骤后,检查以下内容:

- [ ] 虚拟环境已重新创建
- [ ] langgraph 已成功安装
- [ ] 测试输出显示 "✅ LangGraph URL 构建工作流已启用"
- [ ] 测试输出显示 "✅ review_parameters 已被强制调用"
- [ ] 看到完整的参数摘要展示
- [ ] 测试结论显示 "🎉 测试通过!"

## 🔧 故障排查

### 问题 1: langgraph 导入失败

**症状**:
```
ModuleNotFoundError: No module named 'langgraph'
```

**解决**:
```bash
pip install langgraph
```

### 问题 2: 虚拟环境路径错误

**症状**:
```
Fatal error in launcher: Unable to create process
```

**解决**:
按照步骤 1 重新创建虚拟环境。

### 问题 3: 工作流初始化失败

**症状**:
```
⚠️ LangGraph 工作流初始化失败
```

**检查**:
```bash
# 检查文件是否存在
ls url_build_workflow.py
ls agent_tools.py

# 检查 Python 路径
python -c "import sys; print('\n'.join(sys.path))"
```

### 问题 4: API 服务未运行

**症状**:
```
❌ 无法连接到 Playwright API 服务
```

**解决**:
```bash
# 启动 API 服务 (新终端)
python start_api.py

# 或
python playwright_api.py
```

## 📖 进一步阅读

- [LANGGRAPH_INTEGRATION_COMPLETE.md](LANGGRAPH_INTEGRATION_COMPLETE.md) - 完整的集成说明
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - 详细的集成指南
- [LANGGRAPH_EVALUATOR_PROPOSAL.md](LANGGRAPH_EVALUATOR_PROPOSAL.md) - 方案说明和对比
- [deploy/DEPLOY_LANGGRAPH_WORKFLOW.md](deploy/DEPLOY_LANGGRAPH_WORKFLOW.md) - 生产部署指南

## 🎯 核心要点

### 工作流做了什么?

1. **build_search_url** → 构建搜索 URL
2. **强制边** → 无条件路由
3. **force_review** → 强制调用 review_parameters
4. **返回输出** → 展示参数摘要给用户

### 为什么有效?

- ✅ 使用 LangGraph 状态图
- ✅ `add_edge()` 创建无条件边
- ✅ Agent 无法跳过任何步骤
- ✅ 100% 保证 review_parameters 被调用

### 何时触发?

当同时满足以下条件:
- ✅ 必要参数已收集 (国家、商品、数量)
- ✅ URL 还未构建
- ✅ 参数还未确认

## 🚀 下一步

### 本地开发

- 阅读 [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- 启用调试模式 (agent.py line 78: `debug=True`)
- 自定义工作流触发条件

### 生产部署

- 阅读 [deploy/DEPLOY_LANGGRAPH_WORKFLOW.md](deploy/DEPLOY_LANGGRAPH_WORKFLOW.md)
- 按照部署检查清单操作
- 监控工作流执行日志

### 扩展工作流

- 创建数量检查工作流
- 创建爬取工作流
- 实现参数调整循环

---

## 💡 提示

### 查看调试输出

修改 `agent.py` line 78:
```python
# 从
self.url_workflow = create_url_build_workflow(self, debug=False)

# 改为
self.url_workflow = create_url_build_workflow(self, debug=True)
```

### 禁用工作流 (用于对比测试)

修改 `agent.py` line 432:
```python
# 从
if self.url_workflow and self._should_use_workflow():

# 改为
if False:  # 临时禁用工作流
```

### 查看工作流图

```python
from IPython.display import Image, display

# 在 Jupyter notebook 中
workflow = create_url_build_workflow(agent)
display(Image(workflow.graph.get_graph().draw_mermaid_png()))
```

---

**祝使用愉快! LangGraph 工作流已经为你保驾护航,review_parameters 100% 被调用!** 🎉
