# 邮件服务配置说明

## 当前问题

阿里云企业邮箱认证失败(错误码526)。可能的原因:

1. 密码不正确
2. 需要在阿里云企业邮箱管理后台开启SMTP权限
3. 可能需要使用授权码而不是密码
4. 某些特殊字符需要转义

## 解决方案

### 方案1: 检查阿里云企业邮箱设置

1. 登录阿里云企业邮箱管理后台
2. 进入"安全设置"或"客户端设置"
3. 确认已开启"SMTP服务"
4. 查看是否需要生成"授权码"或"应用专用密码"
5. 确认SMTP服务器地址和端口正确:
   - 服务器: `smtp.qiye.aliyun.com`
   - 端口: `465` (SSL) 或 `587` (TLS)

### 方案2: 临时使用QQ邮箱测试

QQ邮箱配置更简单,可以先用来测试功能:

#### 步骤1: 获取QQ邮箱授权码

1. 登录 [QQ邮箱网页版](https://mail.qq.com)
2. 点击"设置" → "账户"
3. 找到"POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务"
4. 开启"IMAP/SMTP服务"
5. 点击"生成授权码"(需要手机验证)
6. 保存生成的授权码

#### 步骤2: 修改.env配置

```env
# 邮件服务配置（使用QQ邮箱）
SMTP_SERVER="smtp.qq.com"
SMTP_PORT=465
SMTP_USERNAME="your_qq_number@qq.com"
SMTP_PASSWORD="生成的16位授权码"
EMAIL_FROM_NAME="TikTok 达人推荐系统"
EMAIL_FROM_ADDRESS="your_qq_number@qq.com"
```

#### 步骤3: 运行测试

```bash
python test_email.py
```

### 方案3: 使用163邮箱

#### 步骤1: 获取163邮箱授权码

1. 登录 [163邮箱](https://mail.163.com)
2. 点击"设置" → "POP3/SMTP/IMAP"
3. 开启"IMAP/SMTP服务"
4. 点击"授权密码管理"生成授权码

#### 步骤2: 修改.env配置

```env
# 邮件服务配置（使用163邮箱）
SMTP_SERVER="smtp.163.com"
SMTP_PORT=465
SMTP_USERNAME="your_email@163.com"
SMTP_PASSWORD="生成的授权码"
EMAIL_FROM_NAME="TikTok 达人推荐系统"
EMAIL_FROM_ADDRESS="your_email@163.com"
```

## 测试命令

### 测试SMTP连接
```bash
python test_smtp_connection.py
```

### 测试邮件发送
```bash
python test_email.py
```

## 常见端口说明

- **25**: 标准SMTP端口(明文,不推荐)
- **465**: SMTP over SSL (推荐)
- **587**: SMTP with STARTTLS (推荐)

## 注意事项

1. **授权码不是邮箱密码**,需要在邮箱设置中单独生成
2. **首次发送可能被识别为垃圾邮件**,请检查收件箱的垃圾邮件文件夹
3. **部分邮箱对发送频率有限制**,避免短时间内大量发送
4. **环境变量中的密码不要包含特殊符号**,如果有请用引号包裹

## 当前状态

- ✅ 代码已支持SSL(465)和STARTTLS(587)两种连接方式
- ✅ 已创建测试脚本
- ❌ 阿里云企业邮箱认证失败,需要检查配置
- 💡 建议先使用QQ邮箱或163邮箱测试功能
