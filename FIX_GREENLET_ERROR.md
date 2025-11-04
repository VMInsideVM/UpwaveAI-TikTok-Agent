# Greenlet 线程切换错误修复

## 错误信息

```
greenlet.error: Cannot switch to a different thread
```

## 问题原因

Playwright 的 greenlet 必须在同一线程使用，但 LangChain 可能在多线程执行工具。

## 解决方案

修改 agent.py 使用单线程 AgentExecutor，或在主线程预热 Playwright。

详细说明见项目文档。
