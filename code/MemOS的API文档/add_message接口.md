# Add Message API 完整文档
## 一、API 概述
该 API 支持向特定会话中添加一条或多条消息，可用于实时同步用户与助手的交互消息、批量导入历史对话记录，或补充用户偏好及行为数据。所有添加的消息会被 MemOS 转化为记忆，可供未来对话检索使用，助力实现聊天历史管理、用户行为跟踪与个性化交互。

## 二、请求说明
### 基础信息
- 请求方式：POST
- 接口 URL：`https://memos.memtensor.cn/api/openmem/v1/add/message`
- 内容类型：application/json
- 授权方式：Token 认证（API Key）

### 授权要求
- 请求头需包含 `Authorization: Token YOUR_API_KEY`
- API Key 获取位置：API Console > API Keys

### 请求参数（Body）
| 参数名 | 类型 | 是否必填 | 描述 | 限制条件 |
| ---- | ---- | ---- | ---- | ---- |
| user_id | string | 是 | 与消息相关联的用户唯一标识 | - |
| conversation_id | string | 是 | 会话的唯一标识 | - |
| messages | MessageInput[] | 是 | 包含记忆内容的消息对象数组 | 消息数组总 Token 限制为 8k |

#### MessageInput 对象结构
| 字段名 | 类型 | 是否必填 | 描述 | 说明 |
| ---- | ---- | ---- | ---- | ---- |
| role | string | 是 | 发送者角色 | 支持 "user"（用户）、"assistant"（助手） |
| content | string | 是 | 消息内容 | 支持单行文本和多行文本，需以字符串格式传入 |
| chat_time | string | 否 | 对话时间 | 支持结构化时间戳（如 "2025-09-12 08:00:00"）或中文文本格式，用于丰富记忆的时间维度信息 |

## 三、请求示例
### 1. Python（HTTP）
```python
import os
import requests
import json

# 替换为你的 API Key
os.environ["MEMOS_API_KEY"] = "YOUR_API_KEY"
os.environ["MEMOS_BASE_URL"] = "https://memos.memtensor.cn/api/openmem/v1"

data = {
    "user_id": "memos_user_123",
    "conversation_id": "0610",
    "messages": [
        {"role": "user", "content": "I’ve planned to travel to Guangzhou this summer. What chain hotels are available for accommodation?"},
        {"role": "assistant", "content": "You can consider options like 7 Days Inn, All Seasons, Hilton, etc."},
        {"role": "user", "content": "I’ll choose 7 Days Inn."},
        {"role": "assistant", "content": "Alright, feel free to ask me if you have any other questions."}
    ]
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Token {os.environ['MEMOS_API_KEY']}"
}

url = f"{os.environ['MEMOS_BASE_URL']}/add/message"
res = requests.post(url=url, headers=headers, data=json.dumps(data))
print(f"result: {res.json()}")
```

### 2. Python（SDK）
```python
# 请确保已安装 MemoS（执行命令：pip install MemoryOS -U）
from memos.api.client import MemOSClient

# 使用 API Key 初始化 MemOS 客户端以开始发送请求
client = MemOSClient(api_key="YOUR_API_KEY")

messages = [
    {"role": "user", "content": "I’ve planned to travel to Guangzhou this summer. What chain hotels are available for accommodation?"},
    {"role": "assistant", "content": "You can consider options like 7 Days Inn, All Seasons, Hilton, etc."},
    {"role": "user", "content": "I’ll choose 7 Days Inn."},
    {"role": "assistant", "content": "Alright, feel free to ask me if you have any other questions."}
]
user_id = "memos_user_123"
conversation_id = "0610"

res = client.add_message(messages=messages, user_id=user_id, conversation_id=conversation_id)
print(f"result: {res}")
```

### 3. Curl
```curl
curl --request POST \
  --url https://memos.memtensor.cn/api/openmem/v1/add/message \
  --header 'Authorization: Token YOUR_API_KEY' \
  --header 'Content-Type: application/json' \
  --data '{
    "user_id": "memos_user_123",
    "conversation_id": "0610",
    "messages": [
      {"role": "user", "content": "I’ve planned to travel to Guangzhou this summer. What chain hotels are available for accommodation?"},
      {"role": "assistant", "content": "You can consider options like 7 Days Inn, All Seasons, Hilton, etc."},
      {"role": "user", "content": "I’ll choose 7 Days Inn."},
      {"role": "assistant", "content": "Alright, feel free to ask me if you have any other questions."}
    ]
  }'
```

## 四、响应说明
### 响应格式（application/json）
#### 成功响应
| 字段名 | 类型 | 是否必填 | 描述 | 示例 |
| ---- | ---- | ---- | ---- | ---- |
| code | number | 是 | API 状态码（详见错误码说明） | 0 |
| data | object | 是 | 添加消息的结果对象 | - |
| - success | boolean | 是 | 消息添加是否成功（true=成功，false=失败） | true |
| message | string | 是 | API 响应信息 | "ok"、"Message added successfully" |

### 响应示例
```json
{
  "code": 0,
  "data": {
    "success": true
  },
  "message": "ok"
}
```

## 五、使用场景示例
### 场景 1：实时对话同步
当用户收到模型响应时，实时调用该 API 追加消息，确保用户与助手的对话始终与 MemOS 同步。MemOS 会在后端随新消息添加持续更新用户记忆。

#### 示例代码
```python
import os
import json
import requests

# 设置 API Key 和基础 URL
os.environ["MEMOS_API_KEY"] = "YOUR_API_KEY"
os.environ["MEMOS_BASE_URL"] = "https://memos.memtensor.cn/api/openmem/v1"

headers = {
    "Authorization": f"Token {os.environ['MEMOS_API_KEY']}",
    "Content-Type": "application/json"
}

BASE_URL = os.environ['MEMOS_BASE_URL']

def add_message(user_id, conversation_id, role, content):
    data = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "messages": [{"role": role, "content": content}]
    }
    res = requests.post(f"{BASE_URL}/add/message", headers=headers, data=json.dumps(data))
    result = res.json()
    if result.get('code') == 0:
        print(f"✅ Message added successfully")
    else:
        print(f"❌ Failed to add message: {result.get('message')}")

# === 示例调用 ===
# 用户发送消息
add_message("memos_user_123", "memos_conversation_123", "user", """I ran 5 kilometers this morning and my knees feel a bit sore.""")
# 助手回复消息
add_message("memos_user_123", "memos_conversation_123", "assistant", """You ran 5 kilometers this morning and your knees feel sore. That means your joints and muscles are still adjusting to the intensity. Tomorrow, try keeping the distance to around 3 kilometers and focus on proper warm-up and cool-down. This will help you stay consistent while giving your knees time to recover.""")
```

### 场景 2：导入历史对话
若应用已存在历史聊天记录，可通过该 API 批量导入 MemOS，让助手立即获取过往上下文，提供更个性化、连贯的响应。

#### 技巧
`chat_time` 字段支持结构化时间戳和纯中文文本格式，MemOS 会利用该字段提升记忆检索准确性。

#### 示例代码
```python
import os
import json
import requests

# 设置 API Key 和基础 URL
os.environ["MEMOS_API_KEY"] = "YOUR_API_KEY"
os.environ["MEMOS_BASE_URL"] = "https://memos.memtensor.cn/api/openmem/v1"

headers = {
    "Authorization": f"Token {os.environ['MEMOS_API_KEY']}",
    "Content-Type": "application/json"
}

BASE_URL = os.environ['MEMOS_BASE_URL']

# 示例：历史对话数据
history_messages = [
    # 第一天 - 用户与助手对话
    {"role": "user", "content": "I like spicy food.", "chat_time": "2025-09-12 08:00:00"},
    {"role": "assistant", "content": "Got it — I’ll remember that you like spicy food.", "chat_time": "2025-09-12 08:01:00"},
    # 几天后 - 新的对话
    {"role": "user", "content": "But I don’t really like heavy or oily dishes, like hotpot or spicy beef soup.", "chat_time": "2025-09-25 12:00:00"},
    {"role": "assistant", "content": "So you prefer light but spicy dishes. I can recommend some that might suit your taste!", "chat_time": "2025-09-25 12:01:00"}
]

def add_message(user_id, conversation_id, messages):
    data = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "messages": messages
    }
    res = requests.post(f"{BASE_URL}/add/message", headers=headers, data=json.dumps(data))
    result = res.json()
    if result.get('code') == 0:
        print("✅ Message added successfully")
    else:
        print(f"❌ Failed to add message: {result.get('message')}")

# === 示例调用 ===
# 导入历史对话
add_message("memos_user_345", "memos_conversation_345", history_messages)
```

### 场景 3：存储用户偏好与行为
除对话数据外，还可将用户偏好、行为信息（如注册时收集的兴趣调查）导入 MemOS，作为用户记忆的一部分。

#### 技巧
`content` 字段必须为字符串类型，支持单行和多行文本，系统会自动正确解析。

#### 示例代码
```python
import os
import json
import requests

# 设置 API Key 和基础 URL
os.environ["MEMOS_API_KEY"] = "YOUR_API_KEY"
os.environ["MEMOS_BASE_URL"] = "https://memos.memtensor.cn/api/openmem/v1"

headers = {
    "Authorization": f"Token {os.environ['MEMOS_API_KEY']}",
    "Content-Type": "application/json"
}

BASE_URL = os.environ['MEMOS_BASE_URL']

# 示例：用户画像与兴趣数据
user_profile_info = [
    {
        "role": "user",
        "content": """
Favorite movie genres: Sci-fi, Action, Comedy
Favorite TV genres: Mystery, Historical dramas
Favorite book genres: Popular science, Technology, Personal growth
Preferred learning formats: Articles, Videos, Podcasts
Exercise habits: Running, Fitness
Dietary preferences: Spicy food, Healthy eating
Travel interests: Nature, Urban culture, Adventure
Preferred conversation style: Humorous, Warm, Casual
Types of support I want from AI: Suggestions, Information lookup, Inspiration
Topics I’m most interested in: Artificial intelligence, Future tech, Film reviews
I’d like AI to help me with: Daily study planning, Movie and book recommendations, Emotional companionship
"""
    }
]

def add_message(user_id, conversation_id, messages):
    data = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "messages": messages
    }
    res = requests.post(f"{BASE_URL}/add/message", headers=headers, data=json.dumps(data))
    result = res.json()
    if result.get('code') == 0:
        print("✅ Message added successfully")
    else:
        print(f"❌ Failed to add message: {result.get('message')}")

# === 示例调用 ===
# 导入用户兴趣与偏好数据
add_message("memos_user_567", "memos_conversation_id_567", user_profile_info)
```