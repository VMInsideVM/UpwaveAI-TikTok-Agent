# WebSocket Connection Closed 问题诊断指南

## 🔍 问题现象

WebSocket 连接在长时间操作中断开，显示 "connection closed"

## 📋 可能的原因及解决方案

### 1️⃣ 反向代理/负载均衡器超时

**症状**：
- 连接在固定时间后断开（如60秒、120秒）
- 错误发生在代理层，而非应用层

**常见场景**：
- Nginx 反向代理（默认60秒超时）
- Apache 反向代理
- Cloudflare 等 CDN（100秒超时）
- AWS ALB/ELB

**解决方案**：

#### Nginx 配置
```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # 关键配置：增加超时时间
    proxy_read_timeout 14400s;      # 4小时
    proxy_send_timeout 14400s;      # 4小时
    proxy_connect_timeout 60s;

    # 保持连接
    proxy_buffering off;
    proxy_cache off;
}
```

#### Apache 配置
```apache
ProxyPass /ws/ ws://127.0.0.1:8001/ws/
ProxyPassReverse /ws/ ws://127.0.0.1:8001/ws/

# 增加超时时间
ProxyTimeout 14400
```

### 2️⃣ 浏览器限制

**症状**：
- 不同浏览器表现不同
- 在特定浏览器中更容易断开

**原因**：
- 浏览器的 WebSocket 实现有差异
- 某些浏览器有硬编码的超时限制

**解决方案**：
1. 使用最新版本的浏览器
2. 测试多个浏览器（Chrome、Firefox、Edge）
3. 检查浏览器控制台的网络选项卡

### 3️⃣ 网络不稳定

**症状**：
- 断开时间不固定
- 移动网络或 WiFi 更容易出现

**解决方案**：
- 使用有线网络测试
- 检查网络质量
- 查看是否有中间设备（路由器、防火墙）

### 4️⃣ 防火墙/安全软件

**症状**：
- 企业网络中更容易出现
- 安装了安全软件后开始出现

**常见限制**：
- 企业防火墙限制长连接
- 杀毒软件拦截 WebSocket
- 家用路由器 NAT 超时

**解决方案**：
1. 临时禁用防火墙测试
2. 在防火墙中添加例外规则
3. 联系网络管理员

### 5️⃣ 操作系统 TCP 连接限制

**症状**：
- 在特定时间后断开（通常是2小时）
- Windows 系统更常见

**原因**：
- Windows TCP KeepAlive 默认2小时
- Linux TCP 连接跟踪超时

**Windows 解决方案**：
```powershell
# 减少 TCP KeepAlive 间隔（需要管理员权限）
netsh int tcp set global keepalive=enabled
reg add "HKLM\System\CurrentControlSet\Services\Tcpip\Parameters" /v KeepAliveTime /t REG_DWORD /d 300000 /f
```

**Linux 解决方案**：
```bash
# 临时修改
sudo sysctl -w net.ipv4.tcp_keepalive_time=300
sudo sysctl -w net.ipv4.tcp_keepalive_intvl=30
sudo sysctl -w net.ipv4.tcp_keepalive_probes=3

# 永久修改（添加到 /etc/sysctl.conf）
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 3
```

### 6️⃣ Python/Uvicorn 配置不当

**症状**：
- 本地测试也会断开
- 日志显示服务器主动关闭

**检查清单**：
- ✅ `timeout_keep_alive=14400` 已设置
- ✅ `ws_ping_interval=30` 已设置
- ✅ `ws_ping_timeout=60` 已设置

**验证方法**：
```bash
# 重启服务时应该看到：
⏱️  WebSocket 超时: 4小时 (支持长时间操作)
```

### 7️⃣ 客户端离开页面

**症状**：
- 用户切换标签页
- 浏览器进入休眠模式
- 手机锁屏

**解决方案**：
- 添加 Page Visibility API 检测
- 页面重新激活时重新连接

## 🛠️ 诊断步骤

### 第1步：检查日志

启动服务后，查看终端输出：

```bash
python start_chatbot.py
```

当连接关闭时，会看到：
```
[WebSocket] 客户端断开连接: session_xxx
  断开码: 1006 (或其他)
  断开原因: ...
```

### 第2步：查看断开码含义

| 断开码 | 含义 | 可能原因 |
|--------|------|----------|
| 1000 | 正常关闭 | 用户主动断开 |
| 1001 | Going Away | 浏览器关闭、页面跳转 |
| 1006 | 异常关闭 | **网络问题、超时、代理关闭** |
| 1008 | Policy Violation | 违反策略 |
| 1009 | Message Too Big | 消息过大 |
| 1011 | Internal Error | 服务器错误 |

**重点**：1006 通常表示网络层问题（超时、代理）

### 第3步：浏览器开发者工具

1. 打开浏览器 F12
2. 进入 Network 选项卡
3. 筛选 WS（WebSocket）
4. 查看连接详情：
   - 连接时长
   - 断开原因
   - 收发的消息

### 第4步：检查心跳日志

在浏览器控制台应该每20秒看到：
```
[KeepAlive] 发送客户端 ping
收到心跳响应: pong
```

如果没有看到，说明心跳机制未工作。

### 第5步：网络抓包（高级）

使用 Wireshark 或 tcpdump：
```bash
# Linux/Mac
sudo tcpdump -i any -s 0 -w websocket.pcap port 8001

# 分析捕获的数据包
wireshark websocket.pcap
```

查找 TCP RST（重置）或 FIN（关闭）包。

## ✅ 快速修复方案

### 方案1：直接连接（绕过代理）

如果你在使用 Nginx/Apache：

**临时测试**：
```
直接访问：http://127.0.0.1:8001
而不是：http://yourdomain.com
```

如果直接连接不断开，说明是代理问题。

### 方案2：增强客户端重连

修改 `static/index.html`，添加更激进的重连策略：

```javascript
let reconnectAttempts = 0;
const maxReconnectAttempts = 10;

websocket.onclose = () => {
    console.log('WebSocket 连接关闭');
    updateStatus(false, '连接已断开');
    isConnected = false;

    // 清理心跳
    if (clientPingInterval) {
        clearInterval(clientPingInterval);
        clientPingInterval = null;
    }

    // 指数退避重连
    if (reconnectAttempts < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
        console.log(`${delay/1000}秒后尝试重新连接... (尝试 ${reconnectAttempts + 1}/${maxReconnectAttempts})`);
        setTimeout(() => {
            if (!isConnected) {
                reconnectAttempts++;
                createSession();
            }
        }, delay);
    } else {
        console.error('已达到最大重连次数');
        showError('连接失败，请刷新页面重试');
    }
};

// 连接成功时重置计数器
websocket.onopen = () => {
    console.log('WebSocket 连接成功');
    updateStatus(true, '已连接');
    reconnectAttempts = 0;  // 重置
    // ... 其他代码
};
```

### 方案3：检查系统资源

```bash
# 检查服务器资源占用
top
free -h
df -h

# 检查网络连接数
netstat -an | grep 8001 | wc -l

# 检查进程限制
ulimit -a
```

如果资源不足，考虑：
- 增加内存
- 增加文件描述符限制
- 减少并发连接数

## 📊 监控建议

### 添加 WebSocket 连接监控

在 `chatbot_api.py` 中添加：

```python
# 全局连接统计
active_connections = 0

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    global active_connections

    await websocket.accept()
    active_connections += 1
    connection_start = datetime.now()

    print(f"[WebSocket] 新连接: {session_id} (当前活跃: {active_connections})")

    try:
        # ... 原有代码
        pass
    finally:
        active_connections -= 1
        duration = (datetime.now() - connection_start).total_seconds()
        print(f"[WebSocket] 连接关闭: {session_id}")
        print(f"  持续时间: {duration:.1f}秒")
        print(f"  当前活跃: {active_connections}")
```

## 🆘 仍然无法解决？

请提供以下信息：

1. **断开码**（从服务器日志）
2. **断开时间**（从连接建立到断开多久）
3. **浏览器**（Chrome/Firefox/Edge + 版本）
4. **网络环境**（本地/公司网络/云服务器）
5. **是否使用代理**（Nginx/Apache/Cloudflare）
6. **操作系统**（Windows/Linux/Mac）
7. **错误日志**（完整的 traceback）

## 📞 常见场景快速参考

| 场景 | 断开时间 | 最可能原因 | 解决方案 |
|------|----------|-----------|----------|
| 本地开发 | 60秒 | 默认超时未修改 | 确认 uvicorn 配置 |
| 生产环境 | 60秒 | Nginx 超时 | 修改 Nginx 配置 |
| 生产环境 | 100秒 | Cloudflare 超时 | 使用企业版或自建 |
| 不固定 | 随机 | 网络不稳定 | 增强重连机制 |
| 2小时 | 7200秒 | TCP KeepAlive | 修改系统配置 |
| 所有环境 | 立即 | 防火墙阻止 | 检查防火墙规则 |

---

**最后更新**: 2025-01-12
**版本**: 1.0.0
