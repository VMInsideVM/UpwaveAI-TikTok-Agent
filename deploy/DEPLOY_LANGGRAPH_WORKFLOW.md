# 部署 LangGraph 工作流

## 概述

本文档说明如何在生产环境部署 LangGraph URL 构建工作流。

## 前置条件

- Python 3.10+
- 现有的 UpwaveAI-TikTok-Agent 系统已运行
- 虚拟环境已配置

## 部署步骤

### 步骤 1: 备份现有系统

在 Agent 服务器上:

```bash
cd /root/UpwaveAI-TikTok-Agent

# 备份当前代码
cp -r . ../UpwaveAI-TikTok-Agent-backup-$(date +%Y%m%d)

# 确认备份
ls -la ../UpwaveAI-TikTok-Agent-backup-*
```

### 步骤 2: 拉取最新代码

```bash
cd /root/UpwaveAI-TikTok-Agent

# 确保在正确的分支
git status

# 拉取最新代码
git pull origin main

# 验证新文件存在
ls -la url_build_workflow.py
ls -la test_url_workflow.py
```

### 步骤 3: 安装 LangGraph 依赖

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装 langgraph
pip install langgraph>=0.2.0

# 或者重新安装所有依赖
pip install -r requirements.txt

# 验证安装
python -c "import langgraph; print('✅ LangGraph 版本:', langgraph.__version__)"
```

### 步骤 4: 配置环境变量

编辑 `.env` 文件:

```bash
nano .env
```

添加工作流开关 (在文件末尾):

```bash
# ============================================================================
# LangGraph 工作流配置 (新增)
# ============================================================================

# 是否启用 LangGraph 工作流 (true/false)
USE_LANGGRAPH_WORKFLOW=true

# 工作流调试模式 (true/false)
LANGGRAPH_DEBUG=false
```

保存并退出 (Ctrl+O, Enter, Ctrl+X)

### 步骤 5: 测试工作流 (本地)

在本地 Windows 环境测试:

```powershell
# 确保虚拟环境已激活
.\.venv\Scripts\Activate.ps1

# 运行测试
python test_url_workflow.py
```

**预期输出**:
```
🧪 测试: LangGraph URL 构建工作流
...
✅ review_parameters 已被强制调用
...
🎉 测试通过!
🔥 结论: LangGraph 工作流成功强制执行了 review_parameters!
```

如果测试失败,检查:
- langgraph 是否正确安装
- agent.py 和 agent_tools.py 是否最新
- API 服务 (playwright_api.py) 是否运行

### 步骤 6: 测试工作流 (服务器)

在 Agent 服务器上测试:

```bash
cd /root/UpwaveAI-TikTok-Agent
source .venv/bin/activate

# 确保 Playwright API 服务运行
curl http://127.0.0.1:8000/health || echo "⚠️ API 服务未运行"

# 运行测试
python test_url_workflow.py
```

### 步骤 7: 重启服务

```bash
# 重启 chatbot-api 服务
supervisorctl restart chatbot-api

# 查看日志确认启动成功
supervisorctl tail -f chatbot-api stderr

# 检查是否有 LangGraph 相关日志
# 应该看到: "✅ LangGraph 工作流已启用"
```

### 步骤 8: 验证功能

#### 8.1 健康检查

```bash
curl http://127.0.0.1:8001/api/health
```

应该返回:
```json
{
  "status": "healthy",
  "langgraph_enabled": true
}
```

#### 8.2 前端测试

1. 访问 https://upwaveai.com/agent/
2. 登录系统
3. 开始新对话
4. 按照正常流程输入:
   - 商品: "口红"
   - 国家: "美国"
   - 粉丝范围: "1万到10万"
   - 数量: "20个"

5. **关键验证点**:
   - 当 agent 构建完 URL 后
   - **必定会展示参数摘要** (无法跳过)
   - 看到类似输出:
   ```
   📋 当前筛选参数摘要

   🎯 商品信息
      • 商品名称: 口红
      • 商品分类: 口红
      • 目标数量: 20 个达人

   🌍 目标地区: 美国

   🔍 筛选条件
      • 粉丝数: 10,000 - 100,000
      ...

   请确认参数是否正确？
   ```

6. **成功标志**:
   - ✅ 参数摘要**总是**出现
   - ✅ 格式完整清晰
   - ✅ Agent 等待用户确认

7. **失败标志**:
   - ❌ Agent 构建 URL 后直接询问排序方式 (跳过了参数展示)
   - ❌ 没有看到参数摘要
   - ❌ 用户不知道当前筛选条件

### 步骤 9: 监控日志

```bash
# 实时监控日志
tail -f /root/UpwaveAI-TikTok-Agent/logs/chatbot-api.log

# 或使用 supervisorctl
supervisorctl tail -f chatbot-api stderr
```

**关键日志**:
```
[Agent] 🔥 使用 LangGraph 工作流执行...
[URLBuildWorkflow] 🚀 开始执行工作流
[URLBuildWorkflow] 📍 步骤1: 构建搜索 URL
[URLBuildWorkflow] 📍 步骤2: 强制调用 review_parameters
[URLBuildWorkflow] ✅ 工作流执行完成
[Agent] ✅ 工作流执行完成
```

## 回滚方案

如果出现问题,快速回滚:

### 方案 1: 禁用工作流

编辑 `.env`:
```bash
USE_LANGGRAPH_WORKFLOW=false
```

重启服务:
```bash
supervisorctl restart chatbot-api
```

系统会降级回原有的 WorkflowEnforcer (Callback 方案)。

### 方案 2: 完全回滚代码

```bash
cd /root

# 停止服务
supervisorctl stop chatbot-api

# 恢复备份
rm -rf UpwaveAI-TikTok-Agent
mv UpwaveAI-TikTok-Agent-backup-YYYYMMDD UpwaveAI-TikTok-Agent

# 重启服务
supervisorctl start chatbot-api
```

## 性能监控

### 关键指标

1. **响应时间**: 工作流增加 ~50-100ms (可忽略)
2. **成功率**: review_parameters 调用率应该 100%
3. **错误率**: 监控工作流执行异常

### 监控命令

```bash
# 查看最近的工作流执行
grep "URLBuildWorkflow" /root/UpwaveAI-TikTok-Agent/logs/chatbot-api.log | tail -20

# 统计成功率
grep "工作流执行完成" logs/chatbot-api.log | wc -l
grep "工作流执行失败" logs/chatbot-api.log | wc -l
```

## 故障排查

### 问题 1: langgraph 导入失败

**症状**:
```
ModuleNotFoundError: No module named 'langgraph'
```

**解决**:
```bash
source .venv/bin/activate
pip install langgraph
supervisorctl restart chatbot-api
```

### 问题 2: 工作流未启用

**症状**:
- 日志中没有 "LangGraph 工作流已启用"
- 参数摘要仍然可能被跳过

**检查**:
```bash
# 检查环境变量
grep "USE_LANGGRAPH_WORKFLOW" .env

# 应该是: USE_LANGGRAPH_WORKFLOW=true
```

**解决**:
```bash
# 确保设置为 true
echo "USE_LANGGRAPH_WORKFLOW=true" >> .env
supervisorctl restart chatbot-api
```

### 问题 3: 工作流执行失败

**症状**:
```
[Agent] ❌ 工作流执行失败: ...
```

**排查**:
```bash
# 启用调试模式
nano .env
# 设置: LANGGRAPH_DEBUG=true

# 重启服务
supervisorctl restart chatbot-api

# 查看详细日志
tail -f logs/chatbot-api.log
```

### 问题 4: API 服务未运行

**症状**:
```
❌ 无法连接到 Playwright API 服务
```

**解决**:
```bash
# 检查 API 服务状态
supervisorctl status playwright-api

# 如果未运行,启动它
supervisorctl start playwright-api

# 验证
curl http://127.0.0.1:8000/health
```

## 维护建议

### 日常维护

1. **每日检查**:
   ```bash
   # 检查工作流成功率
   grep "工作流执行完成" logs/chatbot-api.log | wc -l
   ```

2. **每周检查**:
   - 查看错误日志
   - 监控响应时间
   - 用户反馈

3. **每月检查**:
   - 更新依赖 (`pip list --outdated`)
   - 优化工作流性能
   - 代码审查

### 日志清理

```bash
# 压缩旧日志
cd /root/UpwaveAI-TikTok-Agent/logs
gzip chatbot-api.log.$(date -d "7 days ago" +%Y%m%d)

# 删除 30 天前的日志
find . -name "*.gz" -mtime +30 -delete
```

## 扩展计划

成功部署 URL 构建工作流后,考虑扩展:

### Phase 2: 数量检查工作流

```bash
# 创建新工作流
quantity_check_workflow.py

# 强制执行: get_max_page → analyze_quantity → suggest_adjustments
```

### Phase 3: 完整爬取工作流

```bash
# 创建爬取工作流
scraping_workflow.py

# 保证: 多页爬取 → 数据合并 → Excel 导出
```

### Phase 4: 全面迁移到 LangGraph

考虑将整个 agent 迁移到 LangGraph,获得:
- 完整的状态管理
- 持久化和恢复
- 多 agent 协作
- Human-in-the-loop 支持

## 成功标准

部署成功的标志:

- ✅ **技术指标**:
  - langgraph 正确安装
  - 工作流测试通过
  - 服务正常启动
  - 无错误日志

- ✅ **功能指标**:
  - review_parameters 调用率 100%
  - 参数摘要总是展示给用户
  - 用户可以确认参数后再继续

- ✅ **用户体验**:
  - 用户明确知道当前筛选条件
  - 可以在爬取前修改参数
  - 工作流程清晰透明

## 联系支持

如有问题,联系:
- 技术文档: `INTEGRATION_GUIDE.md`
- 工作流测试: `python test_url_workflow.py`
- LangGraph 文档: https://docs.langchain.com/oss/python/langgraph/

---

**部署检查清单**:

- [ ] 备份现有系统
- [ ] 拉取最新代码
- [ ] 安装 langgraph
- [ ] 配置环境变量
- [ ] 本地测试通过
- [ ] 服务器测试通过
- [ ] 重启服务
- [ ] 验证功能
- [ ] 监控日志
- [ ] 通知团队

祝部署顺利! 🚀
