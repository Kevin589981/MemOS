import os
import json
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class MemOSClient:
    """Thin HTTP client for MemOS APIs.

    Env vars used:
    - MEMOS_API_KEY
    - MEMOS_BASE_URL (default: https://memos.memtensor.cn/api/openmem/v1)
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("MEMOS_API_KEY")
        self.base_url = base_url or os.getenv("MEMOS_BASE_URL", "https://memos.memtensor.cn/api/openmem/v1")
        if not self.api_key:
            raise ValueError("MEMOS_API_KEY is not set")

        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

    def add_message(self, user_id: str, conversation_id: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "messages": messages,
        }
        url = f"{self.base_url}/add/message"
        res = requests.post(url, headers=self.headers, data=json.dumps(payload))
        res.raise_for_status()
        return res.json()

    def get_message(self, user_id: str, conversation_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "conversation_id": conversation_id,
        }
        if limit is not None:
            payload["message_limit_number"] = limit

        url = f"{self.base_url}/get/message"
        res = requests.post(url, headers=self.headers, data=json.dumps(payload))
        res.raise_for_status()
        return res.json()

    def search_memory(
        self,
        user_id: str,
        query: str,
        conversation_id: Optional[str] = None,
        memory_limit_number: Optional[int] = None,
        include_preference: Optional[bool] = None,
        preference_limit_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "query": query,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if memory_limit_number is not None:
            payload["memory_limit_number"] = memory_limit_number
        if include_preference is not None:
            payload["include_preference"] = include_preference
        if preference_limit_number is not None:
            payload["preference_limit_number"] = preference_limit_number

        url = f"{self.base_url}/search/memory"
        res = requests.post(url, headers=self.headers, data=json.dumps(payload))
        res.raise_for_status()
        return res.json()
