# Get Message API 完整文档
## 一、API 概述
该 API 用于获取指定会话中用户与助手的历史对话记录，支持限制返回结果数量。

### 核心用途
1. 为模型生成响应提供近期消息参考，维持对话连贯性与上下文理解能力；
2. 当用户刷新或重新打开应用时，恢复聊天上下文，保障无缝用户体验并支持个性化交互。

## 二、请求说明
### 基础信息
- 请求方式：POST
- 接口 URL：`https://memos.memtensor.cn/api/openmem/v1/get/message`
- 内容类型：application/json
- 授权方式：Token 认证（API Key）

### 授权要求
- 请求头需包含 `Authorization: Token YOUR_API_KEY`
- API Key 获取位置：API Console > API Keys

### 请求参数（Body）
| 参数名 | 类型 | 是否必填 | 描述 | 默认值 | 限制条件 |
| ---- | ---- | ---- | ---- | ---- | ---- |
| user_id | string | 是 | 与待获取消息相关联的用户唯一标识 | - | - |
| conversation_id | string | 是 | 与待获取消息相关联的会话唯一标识 | - | - |
| message_limit_number | number | 否 | 限制返回的消息数量，控制消息列表长度 | 6 | 最大值为 50 |

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
    "conversation_id": "0610"
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Token {os.environ['MEMOS_API_KEY']}"
}

url = f"{os.environ['MEMOS_BASE_URL']}/get/message"
res = requests.post(url=url, headers=headers, data=json.dumps(data))
print(f"result: {res.json()}")
```

### 2. Python（SDK）
```python
# 请确保已安装 MemoS（执行命令：pip install MemoryOS -U）
from memos.api.client import MemOSClient

# 使用 API Key 初始化 MemOS 客户端以开始发送请求
client = MemOSClient(api_key="YOUR_API_KEY")

user_id = "memos_user_123"
conversation_id = "0610"

res = client.get_message(user_id=user_id, conversation_id=conversation_id)
print(f"result: {res}")
```

### 3. Curl
```curl
curl --request POST \
  --url https://memos.memtensor.cn/api/openmem/v1/get/message \
  --header 'Authorization: Token YOUR_API_KEY' \
  --header 'Content-Type: application/json' \
  --data '{
    "user_id": "memos_user_123",
    "conversation_id": "0610"
  }'
```

## 四、响应说明
### 响应格式（application/json）
#### 成功响应
| 字段名 | 类型 | 是否必填 | 描述 | 示例 |
| ---- | ---- | ---- | ---- | ---- |
| code | number | 是 | API 状态码（详见错误码说明） | 0 |
| data | object | 是 | 包含获取到的消息的对象 | - |
| - message_detail_list | MessageDetail[] | 是 | 获取到的消息详情列表 | - |
| message | string | 是 | API 响应信息 | - |

#### MessageDetail 对象结构
| 字段名 | 类型 | 描述 | 枚举值/说明 |
| ---- | ---- | ---- | ---- |
| role | string | 消息发送者角色 | "user"、"assistant" |
| content | string | 消息文本内容 | - |
| create_time | string | 消息创建时间 | - |
| update_time | string | 消息最后更新时间 | - |

### 响应示例
```json
{
  "code": 0,
  "data": {
    "message_detail_list": [
      {
        "role": "user",
        "content": "<string>",
        "create_time": "<string>",
        "update_time": "<string>"
      }
    ]
  },
  "message": "<string>"
}
```

## 五、使用场景示例
### 场景 1：为 LLM Prompt 补充上下文
当需要模型参考用户近期对话历史生成响应时，可通过该 API 获取历史消息并拼接至 Prompt 中，确保无状态场景下的对话连续性。

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

BASE_URL = os.environ["MEMOS_BASE_URL"]

def get_message(user_id: str, conversation_id: str, limit: int):
    data = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_limit_number": limit
    }
    res = requests.post(f"{BASE_URL}/get/message", headers=headers, data=json.dumps(data))
    result = res.json()
    if result.get("code") == 0:
        return result.get("data", {}).get("message_detail_list", [])
    else:
        print(f"❌ Failed to get message: {result.get('message')}")
        return []

# ---------------------------
# 获取历史消息
model_context = get_message("memos_user_345", "memos_conversation_345", 4)

# 移除时间字段，生成模型可用格式并打印
model_context_simple = [{"role": m["role"], "content": m["content"]} for m in model_context]
print(json.dumps(model_context_simple, ensure_ascii=False, indent=2))
```

#### 输出示例
```json
[
  {
    "role": "user",
    "content": "I like spicy food."
  },
  {
    "role": "assistant",
    "content": "Got it — I’ll remember that you like spicy food."
  },
  {
    "role": "user",
    "content": "But I don’t really like heavy or oily dishes, like hotpot or spicy beef soup."
  },
  {
    "role": "assistant",
    "content": "So you prefer light but spicy dishes. I can recommend some that might suit your taste!"
  }
]
```

### 场景 2：恢复聊天上下文
在 AI 应用初期未搭建本地或数据库存储用户聊天记录时，可在用户刷新页面或重新打开应用时，通过该 API 获取最近活跃会话并在聊天窗口中恢复。

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

BASE_URL = os.environ["MEMOS_BASE_URL"]

def get_messages(user_id: str, conversation_id: str):
    data = {
        "user_id": user_id,
        "conversation_id": conversation_id,
    }
    res = requests.post(f"{BASE_URL}/get/message", headers=headers, data=json.dumps(data))
    result = res.json()
    if result.get("code") == 0:
        return result.get("data", {}).get("message_detail_list", [])
    else:
        print(f"❌ Failed to get message: {result.get('message')}")
        return []

# 假设：用户打开应用
user_id = "memos_user_345"
conversation_id = "memos_conversation_345"
messages = get_messages(user_id, conversation_id)

# 打印角色、内容和时间
for m in messages:
    print(f"[{m['role']}] {m['content']} (time={m.get('create_time', 'unknown')})")
```

#### 输出示例
```
[user] I like spicy food. (time=2025-09-12 08:00:00)
[assistant] Got it — I’ll remember that you like spicy food. (time=2025-09-12 08:01:00)
[user] But I don’t really like heavy or oily dishes, like hotpot or spicy beef soup. (time=2025-09-25 12:00:00)
[assistant] So you prefer light but spicy dishes. I can recommend some that might suit your taste! (time=2025-09-25 12:01:00)
```

## 六、关联 API 简介
### 1. Add Message API
- 功能：向特定会话添加一条或多条消息；
- 用途：实时添加用户-助手交互消息、批量导入历史消息、补充用户偏好和行为数据；
- 特性：添加的消息会被 MemOS 转化为记忆，可在未来对话中检索，支持聊天历史管理、用户行为跟踪和个性化交互。

### 2. Search Memory API
- 功能：查询用户的记忆并返回与输入最相关的片段，为模型生成响应提供参考；
- 用途：实时检索用户对话记忆、全局搜索用户完整记忆以创建用户画像或支持个性化推荐，提升对话连贯性和个性化程度；
- 最新特性：除“事实记忆（Fact Memory）”外，新增支持“偏好记忆（Preference Memory）”，让 LLM 更理解用户需求。

