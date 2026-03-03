import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from dotenv import load_dotenv
from tqdm import tqdm

from .client import MemOSClient
from .preprocessor import ConversationPreprocessor

load_dotenv()


class MemOSAdd:
    """Add conversation messages to MemOS as memories (per user/session)."""

    def __init__(self, data_path: str | None = None, batch_size: int = 4, overlap: int = 1, enable_preprocessing: bool = False):
        self.client = MemOSClient()
        self.batch_size = batch_size
        self.overlap = overlap  # Number of messages to overlap between batches
        self.data_path = data_path
        self.data: List[Dict] | None = None
        self.enable_preprocessing = enable_preprocessing
        self.preprocessor = ConversationPreprocessor() if enable_preprocessing else None
        if data_path:
            self.load_data()

    def load_data(self) -> List[Dict]:
        with open(self.data_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        return self.data

    def _send_messages(self, user_id: str, conversation_id: str, messages: List[Dict], desc: str):
        """Send messages with overlap sliding window to preserve context."""
        step = self.batch_size - self.overlap  # Step size for sliding window
        total_batches = max(1, (len(messages) - self.overlap + step - 1) // step)
        
        for i in tqdm(range(0, len(messages), step), desc=desc, total=total_batches):
            # Create overlapping batch
            batch = messages[i : i + self.batch_size]
            if not batch:
                break
                
            retries = 3
            for attempt in range(retries):
                try:
                    self.client.add_message(user_id=user_id, conversation_id=conversation_id, messages=batch)
                    break
                except Exception as e:
                    if attempt < retries - 1:
                        time.sleep(1)
                        continue
                    else:
                        raise e

    def process_conversation(self, item: Dict, idx: int):
        """Convert conversation structure to MemOS add_message payloads.

        We will create two logical users from speakers and one conversation_id per session.
        """
        conversation = item["conversation"]
        speaker_a = conversation["speaker_a"]
        speaker_b = conversation["speaker_b"]

        # MemOS uses user_id + conversation_id
        run_tag = os.getenv("MEMOS_RUN_TAG", "").strip()
        suffix = f"_{run_tag}" if run_tag else ""

        speaker_a_user_id = f"{speaker_a}_{idx}{suffix}"
        speaker_b_user_id = f"{speaker_b}_{idx}{suffix}"
        conversation_id = f"conv_{idx}{suffix}"

        # Iterate over keys that represent message lists with day tracking
        day_index = 0
        for key in sorted(conversation.keys()):
            if key in ["speaker_a", "speaker_b"] or "date" in key or "timestamp" in key:
                continue

            date_time_key = key + "_date_time"
            timestamp = conversation.get(date_time_key, "")
            chats = conversation[key]
            day_index += 1

            # 如果启用预处理且当前session尚未增强,则进行增强
            if self.enable_preprocessing and self.preprocessor:
                needs_enhance = True
                # 如果消息已包含增强内容,则跳过二次增强
                if isinstance(chats, list) and len(chats) > 0 and isinstance(chats[0], dict):
                    if 'enhanced_content' in chats[0] or 'enhanced_text' in chats[0]:
                        needs_enhance = False

                if needs_enhance:
                    enhanced_messages = self.preprocessor.preprocess_conversation(conversation, key)
                    # 用增强内容替换原始文本
                    for i, chat in enumerate(chats):
                        if i < len(enhanced_messages):
                            chat['enhanced_text'] = enhanced_messages[i]['enhanced_content']

            messages_a: List[Dict] = []
            messages_b: List[Dict] = []
            for chat in chats:
                # 使用增强内容(优先级: runtime增强 -> 预处理数据的enhanced_content -> 原始text)
                content_text = (
                    chat.get('enhanced_text')
                    or chat.get('enhanced_content')
                    or chat['text']
                )
                
                # Map to MemOS message schema with day boundary markers
                if chat["speaker"] == speaker_a:
                    messages_a.append(
                        {
                            "role": "user",
                            "content": f"[Day {day_index}] {speaker_a}: {content_text}",
                            "chat_time": str(timestamp),
                        }
                    )
                elif chat["speaker"] == speaker_b:
                    messages_b.append(
                        {
                            "role": "assistant",
                            "content": f"[Day {day_index}] {speaker_b}: {content_text}",
                            "chat_time": str(timestamp),
                        }
                    )
                else:
                    raise ValueError(f"Unknown speaker: {chat['speaker']}")

            # Upload for two users in parallel
            thread_a = threading.Thread(
                target=self._send_messages,
                args=(speaker_a_user_id, conversation_id, messages_a, "MemOS: Adding Speaker A"),
            )
            thread_b = threading.Thread(
                target=self._send_messages,
                args=(speaker_b_user_id, conversation_id, messages_b, "MemOS: Adding Speaker B"),
            )

            thread_a.start()
            thread_b.start()
            thread_a.join()
            thread_b.join()

    def process_all_conversations(self, max_workers: int = 10):
        if not self.data:
            raise ValueError("No data loaded. Please set data_path and call load_data() first.")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.process_conversation, item, idx) for idx, item in enumerate(self.data)]
            for f in futures:
                f.result()
