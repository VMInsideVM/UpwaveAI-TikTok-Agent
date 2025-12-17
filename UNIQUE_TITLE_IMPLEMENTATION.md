# 会话标题自动区分功能

## 概述

实现了智能会话标题生成时的自动去重机制，当多个对话生成相同的标题时，系统会自动添加序号进行区分。

## 功能特点

### 1. 智能标题生成
- 基于对话前6条消息，使用LLM生成5-15字的简洁标题
- 自动突出商品名称或核心需求
- 过滤掉"对话"、"聊天"等冗余词语

### 2. 自动去重机制
当检测到标题重复时，自动添加序号：
- 第一个会话：`女士香水推荐`
- 第二个会话：`女士香水推荐 (2)`
- 第三个会话：`女士香水推荐 (3)`
- ...以此类推

### 3. 智能序号分配
- 自动检测已存在的序号，分配下一个可用序号
- 正则匹配识别现有的序号模式
- 确保序号连续且唯一

## 实现细节

### 核心方法

#### `generate_smart_title(session_id: str)`
生成智能标题的主方法，流程：
1. 获取会话的前10条消息
2. 构建对话摘要（前6条）
3. 使用LLM生成基础标题
4. 调用 `_make_title_unique()` 确保唯一性

#### `_make_title_unique(current_session_id: str, base_title: str)`
确保标题唯一性的辅助方法：

```python
def _make_title_unique(self, current_session_id: str, base_title: str) -> str:
    """
    确保标题唯一，如果有重复则添加序号

    工作流程:
    1. 获取当前用户的所有会话标题（排除当前会话）
    2. 检查基础标题是否已存在
    3. 如果不重复，直接返回基础标题
    4. 如果重复，使用正则表达式检测已有序号
    5. 分配下一个可用序号
    6. 返回 "标题 (序号)" 格式
    """
```

### 关键逻辑

#### 1. 重复检测
```python
# 查找该用户的所有会话标题（排除当前会话）
existing_sessions = db.query(ChatSession).filter(
    ChatSession.user_id == user_id,
    ChatSession.session_id != current_session_id
).all()

existing_titles = [s.title for s in existing_sessions]

# 如果没有重复，直接返回
if base_title not in existing_titles:
    return base_title
```

#### 2. 序号识别与分配
```python
import re
pattern = re.compile(rf"^{re.escape(base_title)}\s*\((\d+)\)$")

max_number = 1
for title in existing_titles:
    match = pattern.match(title)
    if match:
        num = int(match.group(1))
        max_number = max(max_number, num + 1)
    elif title == base_title:
        # 原始标题已存在，从(2)开始
        max_number = max(max_number, 2)

# 生成新标题
unique_title = f"{base_title} ({max_number})"
```

#### 3. 后备方案
如果去重失败，使用时间戳：
```python
from datetime import datetime
timestamp = datetime.now().strftime("%H:%M")
return f"{base_title} {timestamp}"
```

## 使用示例

### 场景1：首次使用某个标题
```
用户A创建会话 → LLM生成 "口红推荐"
系统检测：无重复
最终标题：口红推荐
```

### 场景2：重复标题（同一用户）
```
用户A创建第二个会话 → LLM生成 "口红推荐"
系统检测：已存在 "口红推荐"
最终标题：口红推荐 (2)

用户A创建第三个会话 → LLM生成 "口红推荐"
系统检测：已存在 "口红推荐"、"口红推荐 (2)"
最终标题：口红推荐 (3)
```

### 场景3：跳号处理
```
已存在标题：
- 口红推荐
- 口红推荐 (2)
- 口红推荐 (5)  (手动修改或删除了3、4)

新会话 → LLM生成 "口红推荐"
系统检测：最大序号是5
最终标题：口红推荐 (6)
```

### 场景4：不同用户可以有相同标题
```
用户A的会话：口红推荐
用户B的会话：口红推荐  (互不影响)
```

## 触发时机

标题自动生成在以下情况触发：

1. **自动触发**（`auto_update_title_if_needed`）：
   - 会话标题为"新对话"（默认值）
   - 消息数量达到4条（2轮对话）
   - 每次保存消息后检查

2. **手动触发**（API调用）：
   - 前端可以手动请求重新生成标题

## 配置说明

### LLM设置
```python
llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
    temperature=0.3,  # 较低温度确保一致性
    max_tokens=50     # 限制标题长度
)
```

### 标题生成规则
```python
要求：
1. 标题要简洁明了，5-15个字
2. 突出商品名称或核心需求
3. 不要包含"对话"、"聊天"等词语
4. 只返回标题文本，不要任何其他内容
```

## 优势

✅ **用户体验**：
- 相同需求的多次对话能够清晰区分
- 自动化处理，无需手动干预
- 序号递增，一目了然

✅ **数据一致性**：
- 只在同一用户范围内去重
- 不会影响其他用户的标题
- 确保标题的唯一性

✅ **智能容错**：
- 正则匹配识别多种序号格式
- 后备方案使用时间戳
- 异常情况下也能正常工作

## 测试建议

1. **基本功能测试**：
   - 创建3个关于同一商品的对话
   - 验证标题分别为：`商品名`、`商品名 (2)`、`商品名 (3)`

2. **跳号测试**：
   - 删除中间的某个会话
   - 创建新会话，验证序号是否正确递增

3. **并发测试**：
   - 同一用户快速创建多个会话
   - 验证序号分配不会冲突

4. **跨用户测试**：
   - 不同用户创建相同主题的对话
   - 验证标题互不影响

## 文件修改

✅ [session_manager_db.py](session_manager_db.py#L353-L492)
- 修改 `generate_smart_title()` 方法，添加去重逻辑
- 新增 `_make_title_unique()` 辅助方法

## 注意事项

⚠️ **性能考虑**：
- 每次生成标题需要查询数据库获取所有会话标题
- 如果用户会话数量很大（>1000），可能需要优化查询

⚠️ **手动修改标题**：
- 用户可以手动修改标题，不影响自动去重机制
- 手动修改的标题也会被纳入去重检测

⚠️ **标题长度**：
- 基础标题限制30字
- 加上序号后可能略长，前端需要适当处理显示
