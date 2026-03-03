# Search Memory API 完整文档
## 一、API 概述
该 API 用于查询用户的记忆数据，返回与输入内容最相关的记忆片段，为模型生成响应提供参考。支持实时检索对话中的用户记忆，或全局搜索用户完整记忆，助力创建用户画像、提供个性化推荐，同时提升对话连贯性与个性化程度。

### 核心特性
- 最新更新支持两种记忆类型：“事实记忆（Fact Memory）”和“偏好记忆（Preference Memory）”，让 LLM 更精准理解用户需求并作出响应。

## 二、请求说明
### 基础信息
- 请求方式：POST
- 接口 URL：`https://memos.memtensor.cn/api/openmem/v1/search/memory`
- 内容类型：application/json
- 授权方式：Token 认证（API Key）

### 授权要求
- 请求头需包含 `Authorization: Token YOUR_API_KEY`
- API Key 获取位置：API Console > API Keys

### 请求参数（Body）
| 参数名 | 类型 | 是否必填 | 描述 | 默认值 | 限制条件 |
| ---- | ---- | ---- | ---- | ---- | ---- |
| user_id | string | 是 | 与待查询记忆相关联的用户唯一标识 | - | - |
| conversation_id | string | 否 | 包含该记忆的会话唯一标识，提供后当前会话记忆优先级高于其他历史记忆 | - | - |
| query | string | 是 | 用于在记忆中搜索的文本内容 | - | 单次查询 Token 限制为 4k |
| memory_limit_number | number | 否 | 限制返回的事实记忆数量 | 6 | 最大值为 25 |
| include_preference | boolean | 否 | 是否启用偏好记忆召回，启用后系统将根据查询智能检索用户偏好记忆 | true | - |
| preference_limit_number | number | 否 | 限制返回的偏好记忆数量 | 6 | 最大值为 25 |

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
    "query": "I want to travel during the National Day holiday. Please recommend a city I haven’t been to and a hotel brand I haven’t stayed at.",
    "user_id": "memos_user_123",
    "conversation_id": "0928"
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Token {os.environ['MEMOS_API_KEY']}"
}

url = f"{os.environ['MEMOS_BASE_URL']}/search/memory"
res = requests.post(url=url, headers=headers, data=json.dumps(data))
print(f"result: {res.json()}")
```

### 2. Python（SDK）
```python
# 请确保已安装 MemoS（执行命令：pip install MemoryOS -U）
from memos.api.client import MemOSClient

# 使用 API Key 初始化 MemOS 客户端以开始发送请求
client = MemOSClient(api_key="YOUR_API_KEY")

query = "I want to travel during the National Day holiday. Please recommend a city I haven’t been to and a hotel brand I haven’t stayed at."
user_id = "memos_user_123"
conversation_id = "0928"

res = client.search_memory(query=query, user_id=user_id, conversation_id=conversation_id)
print(f"result: {res}")
```

### 3. Curl
```curl
curl --request POST \
  --url https://memos.memtensor.cn/api/openmem/v1/search/memory \
  --header 'Authorization: Token YOUR_API_KEY' \
  --header 'Content-Type: application/json' \
  --data '{
    "query": "I want to travel during the National Day holiday. Please recommend a city I haven’t been to and a hotel brand I haven’t stayed at.",
    "user_id": "memos_user_123",
    "conversation_id": "0928"
  }'
```

## 四、响应说明
### 响应格式（application/json）
#### 成功响应（状态码 200）
| 字段名 | 类型 | 是否必填 | 描述 | 示例 |
| ---- | ---- | ---- | ---- | ---- |
| code | number | 是 | API 状态码（详见错误码说明） | 0 |
| data | object | 是 | 包含查询结果的对象 | - |
| - memory_detail_list | MemoryDetail[] | 是 | 返回的事实记忆片段详情列表 | - |
| - preference_detail_list | MemoryDetail[] | 是 | 返回的偏好记忆详情列表 | - |
| - preference_note | string | 是 | 检索到偏好记忆时的使用说明 | - |
| message | string | 是 | API 响应信息 | - |

#### MemoryDetail（事实记忆）对象结构
| 字段名 | 类型 | 描述 | 枚举值/说明 |
| ---- | ---- | ---- | ---- |
| id | string | 事实记忆唯一标识（系统内部使用） | - |
| memory_key | string | 事实记忆的标题或关键词摘要 | - |
| memory_value | string | 事实记忆的详细内容 | - |
| memory_type | string | 记忆类型 | "WorkingMemory"（短期工作记忆，临时存储）、"LongTermMemory"（长期记忆，持久化存储重要信息）、"UserMemory"（用户专属记忆，个性化相关信息） |
| create_time | string | 事实记忆创建时间（通常为 ISO 8601 格式） | - |
| conversation_id | string | 关联的会话唯一标识 | - |
| status | string | 事实记忆状态（检索到的记忆均为激活状态） | "activated"（激活状态，可检索使用） |
| confidence | number | 事实记忆可信度评分（0-1 之间，越接近 1 可信度越高） | 评分可能随时间或重复模型推理逐渐衰减，反映不确定性 |
| tags | string[] | 事实记忆关联的标签（用于分类或检索） | 示例：["person", "event", "work"] |
| update_time | string | 事实记忆最后修改/更新时间（通常为 ISO 8601 格式） | - |
| relativity | number | 事实记忆与查询的相关性评分（0-1 之间，值越高相关性越强） | - |

#### MemoryDetail（偏好记忆）对象结构
| 字段名 | 类型 | 描述 | 枚举值/说明 |
| ---- | ---- | ---- | ---- |
| id | string | 偏好记忆唯一标识（系统内部使用） | - |
| preference | string | 偏好记忆的详细内容 | - |
| preference_type | string | 偏好类型 | "explicit_preference"（显式偏好记忆）、"implicit_preference"（隐式偏好记忆） |
| reasoning | string | 偏好记忆的提取依据 | - |
| create_time | string | 偏好记忆创建时间（通常为 ISO 8601 格式） | - |
| conversation_id | string | 关联的会话唯一标识 | - |
| status | string | 偏好记忆状态（检索到的记忆均为激活状态） | "activated"（激活状态，可检索使用） |
| update_time | string | 偏好记忆最后修改/更新时间（通常为 ISO 8601 格式） | - |

### 响应示例
```json
{
  "code": 0,
  "data": {
    "memory_detail_list": [
      {
        "id": "<string>",
        "memory_key": "<string>",
        "memory_value": "<string>",
        "memory_type": "LongTermMemory",
        "create_time": "<string>",
        "conversation_id": "<string>",
        "status": "activated",
        "confidence": 0.95,
        "tags": [
          "<string>"
        ],
        "update_time": "<string>",
        "relativity": 0.87
      }
    ],
    "preference_detail_list": [
      {
        "id": "<string>",
        "preference": "<string>",
        "preference_type": "explicit_preference",
        "reasoning": "<string>",
        "create_time": "<string>",
        "conversation_id": "<string>",
        "status": "activated",
        "update_time": "<string>"
      }
    ],
    "preference_note": "<string>"
  },
  "message": "<string>"
}
```

## 五、使用场景示例
### 场景 1：对话过程中检索用户记忆
在用户与 AI 对话时，可通过该 API 检索与用户当前消息最相关的记忆，并导入 LLM 的 Prompt 中，让响应更贴合用户背景与偏好。

#### 技巧
填写 `conversation_id` 有助于 MemOS 更好理解当前会话上下文，提高会话相关记忆的权重，使模型响应更连贯、贴合场景。

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

# 将用户当前消息作为查询文本
query_text = "I'm going to Yunnan for National Day. Any food recommendations?"
data = {
    "user_id": "memos_user_345",
    "conversation_id": "memos_conversation_789",  # 新建会话 ID
    "query": query_text,
}

# 调用 /search/memory 接口检索相关记忆
res = requests.post(f"{BASE_URL}/search/memory", headers=headers, data=json.dumps(data))
print(f"result: {res.json()}")
```

#### 输出示例
```json
{
  "memory_detail_list": [
    {
      "id": "a8aec934-756b-4f7e-afdf-da4f567b2f85",
      "memory_key": "Dislike for heavy or oily dishes",
      "memory_value": "On September 25, 2025, the user clarified that while they enjoy spicy food, they do not like heavy or oily dishes, such as hotpot or spicy beef soup.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675057192,
      "conversation_id": "memos_conversation_345",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "food preference",
        "dietary restrictions",
        "heavy dishes"
      ],
      "update_time": 1762675059740,
      "relativity": 0.00003117323
    },
    {
      "id": "4dfefe7b-9593-4924-be9b-efe6d15bfaf0",
      "memory_key": "Preference for spicy food",
      "memory_value": "On September 12, 2025, the user expressed a liking for spicy food.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675029246,
      "conversation_id": "memos_conversation_345",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "food preference",
        "spicy food"
      ],
      "update_time": 1762675058836,
      "relativity": 0.000027298927
    }
  ],
  "preference_detail_list": [
    {
      "id": "e3ea3b4e-5a9a-4deb-a11c-1502d4a996ce",
      "preference_type": "explicit_preference",
      "preference": "The user likes spicy food but does not like heavy or oily dishes like hotpot or spicy beef soup.",
      "reasoning": "The user explicitly stated a liking for spicy food and a dislike for heavy or oily dishes. The dislike was specified by examples, indicating a clear preference for lighter dishes even if they are spicy.",
      "create_time": 1762675319726,
      "conversation_id": "memos_conversation_345",
      "status": "activated",
      "update_time": 1762674876250
    },
    {
      "id": "b306d189-99fc-42a4-b870-07ea00ffc1ca",
      "preference_type": "implicit_preference",
      "preference": "Preference for balance between flavor intensity and dish lightness",
      "reasoning": "The user explicitly states a preference for spicy food but dislikes heavy or oily dishes, suggesting a desire for a balance between intense flavors and the lightness of the dish. This implies a hidden motivation to enjoy the taste without the heaviness associated with certain spicy dishes, pointing to a preference for dishes that are both flavorful and light.",
      "create_time": 1762674876398,
      "conversation_id": "memos_conversation_345",
      "status": "activated",
      "update_time": 1762674885918
    }
  ],
  "preference_note": "\n# Note:\nFact memory are summaries of facts, while preference memory are summaries of user preferences.\nYour response must not violate any of the user's preferences, whether explicit or implicit, and briefly explain why you answer this way to avoid conflicts.\n"
}
```

### 场景 2：获取用户画像
若需分析应用用户或向用户实时展示“个人核心洞察”摘要，可通过该 API 检索用户的整体记忆，帮助模型生成个性化用户画像。

#### 技巧
此种场景下无需指定 `conversation_id`。收到响应后，可筛选 `memory_type` 为 `UserMemory` 的记忆，这类记忆汇总了用户的个性化信息，最适合生成用户画像或内容推荐。

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

# 用于检索用户画像的查询文本
query_text = "What are my key personal traits?"
data = {
    "user_id": "memos_user_567",
    "query": query_text,
}

# 调用 /search/memory 接口检索相关记忆
res = requests.post(f"{BASE_URL}/search/memory", headers=headers, data=json.dumps(data))
print(f"result: {res.json()}")
```

#### 输出示例
```json
{
  "memory_detail_list": [
    {
      "id": "d8ccc6b1-ca92-49d6-8f3c-beea6fa00e1e",
      "memory_key": "Preferred conversation style",
      "memory_value": "The user prefers a humorous, warm, and casual style in conversations.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675887693,
      "conversation_id": "memos_conversation_id_567",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "conversation",
        "style",
        "preferences"
      ],
      "update_time": 1762675961289,
      "relativity": 0.0007798947
    },
    {
      "id": "a5c99814-f69d-448d-87f9-28836244dad8",
      "memory_key": "Dietary preferences",
      "memory_value": "The user enjoys spicy food and maintains a healthy eating lifestyle.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675848775,
      "conversation_id": "memos_conversation_id_567",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "diet",
        "preferences",
        "healthy eating"
      ],
      "update_time": 1762675968743,
      "relativity": 0.000111509864
    },
    {
      "id": "7300e222-d526-4f59-bf30-b60952e9e508",
      "memory_key": "Travel interests",
      "memory_value": "The user is interested in nature, urban culture, and adventure when it comes to travel.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675868195,
      "conversation_id": "memos_conversation_id_567",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "travel",
        "interests",
        "adventure"
      ],
      "update_time": 1762675960296,
      "relativity": 0.00010057839
    },
    {
      "id": "61a4aa7d-3532-4ee7-902f-4798a82f92ab",
      "memory_key": "Favorite book genres",
      "memory_value": "The user is interested in popular science, technology, and personal growth as their favorite book genres.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675781163,
      "conversation_id": "memos_conversation_id_567",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "books",
        "genres",
        "preferences"
      ],
      "update_time": 1762675952467,
      "relativity": 0.00009639777
    },
    {
      "id": "10583713-7bdb-42ed-a01a-e5b54aeb34dd",
      "memory_key": "AI assistance goals",
      "memory_value": "The user would like AI to help with daily study planning, movie and book recommendations, and providing emotional companionship.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675948115,
      "conversation_id": "memos_conversation_id_567",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "AI",
        "assistance",
        "goals"
      ],
      "update_time": 1762675969747,
      "relativity": 0.000017721624
    },
    {
      "id": "1b736daf-73aa-4c04-aae8-8b308c9a6b8a",
      "memory_key": "Topics of interest",
      "memory_value": "The user is most interested in artificial intelligence, future tech, and film reviews.",
      "memory_type": "WorkingMemory",
      "create_time": 1762675925831,
      "conversation_id": "memos_conversation_id_567",
      "status": "activated",
      "confidence": 0.99,
      "tags": [
        "interests",
        "topics",
        "AI"
      ],
      "update_time": 1762675967351,
      "relativity": 0.00001625416
    }
  ],
  "preference_detail_list": [],
  "preference_note": ""
}
```