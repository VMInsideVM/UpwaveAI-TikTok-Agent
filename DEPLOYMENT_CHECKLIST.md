# 积分系统更新部署检查清单

## 更新概述
- 每个达人积分消耗: 30 → 100
- 最低使用门槛: 无 → 100积分
- 更新日期: 2025-12-19

---

## 部署前检查

### 1. 代码检查 ✅

- [x] 前端积分计算更新 (static/index.html)
- [x] 前端最低门槛检查 (static/index.html)
- [x] 后端报告生成积分扣除 (api/reports.py)
- [x] 后台任务积分扣除 (background_tasks.py)
- [x] 数据库模型注释更新 (database/models.py)
- [x] 迁移脚本注释更新 (migrations/001_quota_to_credits.sql)

### 2. 测试验证 ✅

```bash
python test_credits_update.py
```

期望结果: 所有5项测试通过
- [x] 积分计算公式测试通过
- [x] 最低积分门槛测试通过
- [x] 可承担达人数量测试通过
- [x] 积分扣除场景测试通过
- [x] 用户体验流程测试通过

### 3. 文档准备 ✅

- [x] 创建 CREDITS_SYSTEM_UPDATE.md（详细文档）
- [x] 创建 test_credits_update.py（测试脚本）
- [x] 创建 DEPLOYMENT_CHECKLIST.md（本检查清单）

---

## 部署步骤

### Step 1: 备份数据库

```bash
# SQLite 数据库备份
cp chatbot.db chatbot.db.backup_$(date +%Y%m%d_%H%M%S)
```

或者使用 SQLite dump:

```bash
sqlite3 chatbot.db .dump > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Step 2: 停止服务

```bash
# 停止聊天机器人服务
# Ctrl+C 或者
pkill -f chatbot_api.py

# 停止 Playwright API
pkill -f playwright_api.py
```

### Step 3: 更新代码

```bash
# 拉取最新代码
git pull

# 或者如果是本地修改
git add .
git commit -m "Update credits system: 30->100 credits per influencer, add minimum threshold"
```

### Step 4: 启动服务

```bash
# 终端 1: 启动 Playwright API
python start_api.py

# 终端 2: 启动聊天机器人
python start_chatbot.py
```

### Step 5: 验证服务状态

```bash
# 检查 Playwright API
curl http://127.0.0.1:8000/health

# 检查聊天机器人 API
curl http://127.0.0.1:8001/api/health
```

---

## 部署后测试

### 测试 1: 积分充足用户（推荐）

1. **创建测试用户** (300积分)
   ```sql
   -- 查看测试用户
   SELECT user_id, username, email FROM users WHERE username = 'test_user';

   -- 查看积分
   SELECT
       u.username,
       uu.total_credits,
       uu.used_credits,
       (uu.total_credits - uu.used_credits) as remaining_credits
   FROM users u
   JOIN user_usage uu ON u.user_id = uu.user_id
   WHERE u.username = 'test_user';
   ```

2. **登录测试**
   - [ ] 访问 http://127.0.0.1:8001
   - [ ] 使用测试账号登录
   - [ ] 验证右上角显示: "剩余积分: 300"

3. **聊天功能测试**
   - [ ] 输入框状态: 启用 ✅
   - [ ] 发送按钮状态: 启用 ✅
   - [ ] 占位符文字: "请告诉我您的需求..."
   - [ ] 无黄色警告框

4. **请求测试**
   - [ ] 输入: "美国的口红，2个达人"
   - [ ] Agent正常响应并收集参数
   - [ ] 出现确认弹窗

5. **确认弹窗验证**
   - [ ] 达人数量显示: 2
   - [ ] 消耗积分显示: 200
   - [ ] 当前积分显示: 300
   - [ ] 确认后剩余: 100
   - [ ] 确认按钮: 启用
   - [ ] 按钮文字: "确认生成"

6. **提交并验证**
   - [ ] 点击"确认生成"
   - [ ] 任务成功提交
   - [ ] 检查数据库积分变化:
   ```sql
   SELECT
       total_credits,
       used_credits,
       (total_credits - used_credits) as remaining_credits
   FROM user_usage
   WHERE user_id = (SELECT user_id FROM users WHERE username = 'test_user');
   ```
   - [ ] 期望: total_credits=300, used_credits=200, remaining_credits=100

7. **刷新页面验证**
   - [ ] 刷新浏览器
   - [ ] 右上角显示: "剩余积分: 100"
   - [ ] 输入框仍然启用（100 ≥ 100）

### 测试 2: 积分不足用户（必须）

1. **修改测试用户积分**
   ```sql
   UPDATE user_usage
   SET total_credits = 50, used_credits = 0
   WHERE user_id = (SELECT user_id FROM users WHERE username = 'test_user');

   -- 验证修改
   SELECT total_credits, used_credits, (total_credits - used_credits) as remaining_credits
   FROM user_usage
   WHERE user_id = (SELECT user_id FROM users WHERE username = 'test_user');
   ```

2. **登录测试**
   - [ ] 登出后重新登录（或刷新页面）
   - [ ] 右上角显示: "剩余积分: 50"

3. **输入框状态验证**
   - [ ] 输入框状态: 禁用（灰色）❌
   - [ ] 发送按钮状态: 禁用 ❌
   - [ ] 占位符文字: "积分不足（剩余50），至少需要100积分才能使用"

4. **警告框验证**
   - [ ] 聊天区域显示黄色警告框
   - [ ] 警告文字包含:
     - "⚠️ 积分不足"
     - "您当前剩余 50 积分"
     - "至少需要 100 积分才能使用达人推荐服务"
     - "每个达人消耗100积分"

5. **功能限制验证**
   - [ ] 无法在输入框中输入任何文字
   - [ ] 无法点击发送按钮
   - [ ] 可以查看历史聊天记录
   - [ ] 可以查看报告库

6. **控制台日志验证**
   - [ ] 打开浏览器开发者工具 (F12)
   - [ ] Console 标签页显示: `⚠️ 积分不足: 50 < 100`

### 测试 3: 临界状态用户（推荐）

1. **修改测试用户积分**
   ```sql
   UPDATE user_usage
   SET total_credits = 100, used_credits = 0
   WHERE user_id = (SELECT user_id FROM users WHERE username = 'test_user');
   ```

2. **登录测试**
   - [ ] 刷新页面
   - [ ] 右上角显示: "剩余积分: 100"
   - [ ] 输入框: 启用 ✅（刚好达到门槛）

3. **请求1个达人**
   - [ ] 输入: "美国的口红，1个达人"
   - [ ] 确认弹窗显示:
     - 达人数量: 1
     - 消耗积分: 100
     - 确认后剩余: 0
   - [ ] 确认按钮: 启用 ✅

4. **提交验证**
   - [ ] 点击确认
   - [ ] 任务成功提交
   - [ ] 积分扣除为0

5. **扣除后状态**
   - [ ] 刷新页面
   - [ ] 右上角显示: "剩余积分: 0"
   - [ ] 输入框: 禁用 ❌
   - [ ] 显示警告框

### 测试 4: 积分不足请求多个达人（必须）

1. **修改测试用户积分**
   ```sql
   UPDATE user_usage
   SET total_credits = 150, used_credits = 0
   WHERE user_id = (SELECT user_id FROM users WHERE username = 'test_user');
   ```

2. **请求2个达人**
   - [ ] 输入: "美国的口红，2个达人"
   - [ ] 确认弹窗显示:
     - 达人数量: 2
     - 消耗积分: 200
     - 当前积分: 150
     - 确认后剩余: 不足

3. **确认按钮验证**
   - [ ] 确认按钮: 禁用 ❌
   - [ ] 按钮文字: "积分不足，需要 200 积分"
   - [ ] 按钮样式: 灰色，不可点击

4. **错误提示（如果尝试点击）**
   - [ ] 无法点击按钮
   - [ ] 用户无法提交请求

---

## 回滚方案（如果出现问题）

### 快速回滚步骤

1. **停止服务**
   ```bash
   pkill -f chatbot_api.py
   pkill -f playwright_api.py
   ```

2. **恢复代码**
   ```bash
   # 如果使用 Git
   git revert HEAD

   # 或手动修改
   # 将所有 100 改回 30
   # 移除前端的 MIN_CREDITS_REQUIRED 检查
   ```

3. **恢复数据库（如果需要）**
   ```bash
   # 恢复备份
   cp chatbot.db.backup_YYYYMMDD_HHMMSS chatbot.db

   # 或从 SQL dump 恢复
   sqlite3 chatbot.db < backup_YYYYMMDD_HHMMSS.sql
   ```

4. **重启服务**
   ```bash
   python start_api.py
   python start_chatbot.py
   ```

---

## 监控指标

### 需要关注的日志

**后端日志**:
```
📊 从 Agent 获取目标达人数: X
💰 使用目标达人数量计算积分: X 个
📊 用户 XXX 扣除积分: XXX (剩余: XXX)
```

**前端控制台**:
```
📊 确认弹窗 - 达人数量: X, 扣除积分: XXX
⚠️ 积分不足: XX < 100
```

### 数据库查询

**查看所有用户积分状态**:
```sql
SELECT
    u.username,
    u.email,
    uu.total_credits,
    uu.used_credits,
    (uu.total_credits - uu.used_credits) as remaining_credits,
    CASE
        WHEN (uu.total_credits - uu.used_credits) < 100 THEN '❌ 无法使用'
        ELSE '✅ 正常'
    END as status
FROM users u
JOIN user_usage uu ON u.user_id = uu.user_id
ORDER BY remaining_credits ASC;
```

**查看积分不足的用户**:
```sql
SELECT
    u.username,
    u.email,
    (uu.total_credits - uu.used_credits) as remaining_credits
FROM users u
JOIN user_usage uu ON u.user_id = uu.user_id
WHERE (uu.total_credits - uu.used_credits) < 100
ORDER BY remaining_credits ASC;
```

---

## 常见问题

### Q1: 用户抱怨无法使用聊天功能

**检查步骤**:
1. 查询用户积分: `SELECT * FROM user_usage WHERE user_id = 'XXX'`
2. 如果积分 < 100，这是正常的限制
3. 如果积分 ≥ 100 但仍被禁用，检查前端代码是否正确部署

**解决方案**:
- 为用户充值积分
- 或临时降低 MIN_CREDITS_REQUIRED（需要修改代码）

### Q2: 积分扣除不正确

**检查步骤**:
1. 检查后端日志中的积分计算
2. 验证 CREDITS_PER_INFLUENCER = 100
3. 检查数据库中的 used_credits 增量

**解决方案**:
- 如果发现使用了旧的30积分，需要重启服务确保新代码生效

### Q3: 确认弹窗显示错误的积分

**检查步骤**:
1. 打开浏览器控制台
2. 查看 `📊 确认弹窗` 日志
3. 验证 `creditsPerInfluencer = 100`

**解决方案**:
- 清除浏览器缓存
- 强制刷新 (Ctrl+F5)

---

## 完成标记

部署完成后，请勾选以下项目:

- [ ] 所有代码文件已更新
- [ ] 测试脚本通过
- [ ] 数据库已备份
- [ ] 服务已重启
- [ ] 积分充足用户测试通过
- [ ] 积分不足用户测试通过
- [ ] 临界状态用户测试通过
- [ ] 积分不足请求多个达人测试通过
- [ ] 监控日志正常
- [ ] 用户已收到通知（如果需要）

---

## 附录: SQL 快速命令

### 为所有现有用户补偿积分

```sql
-- 为所有用户增加200积分补偿
UPDATE user_usage
SET total_credits = total_credits + 200;

-- 验证
SELECT
    u.username,
    uu.total_credits,
    (uu.total_credits - uu.used_credits) as remaining_credits
FROM users u
JOIN user_usage uu ON u.user_id = uu.user_id;
```

### 为特定用户充值

```sql
-- 为特定用户增加积分
UPDATE user_usage
SET total_credits = total_credits + 500
WHERE user_id = (SELECT user_id FROM users WHERE email = 'user@example.com');
```

### 查看最近的积分使用情况

```sql
SELECT
    r.created_at,
    u.username,
    r.title,
    s.meta_data
FROM reports r
JOIN users u ON r.user_id = u.user_id
LEFT JOIN chat_sessions s ON r.session_id = s.session_id
ORDER BY r.created_at DESC
LIMIT 10;
```

---

**部署人员**: _________________
**部署日期**: _________________
**部署时间**: _________________
**验证人员**: _________________
