import json
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ConversationPreprocessor:
    """预处理对话,提取和增强逻辑信息"""
    
    def __init__(self, model: str = "qwen-plus", enable_image_processing: bool = False, image_cache_path: str = "image_descriptions_cache.json"):
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.enable_image_processing = enable_image_processing
        
        # 图片描述缓存（仅在启用图片处理时加载）
        self.image_cache = {}
        if self.enable_image_processing:
            if os.path.exists(image_cache_path):
                with open(image_cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # 构建 dia_id -> description 的映射
                    for filename, info in cache_data.items():
                        if 'dia_id' in info and 'ai_description' in info:
                            self.image_cache[info['dia_id']] = info['ai_description']
                print(f"✓ Loaded {len(self.image_cache)} image descriptions from cache")
            else:
                print(f"⚠ Image cache not found: {image_cache_path}")
        else:
            print("ℹ Image processing is disabled")
    
    def extract_facts_with_llm(self, conversation_chunk: List[Dict], session_date: str) -> List[str]:
        """
        使用LLM从对话片段中提取显式事实
        
        Args:
            conversation_chunk: 对话消息列表 [{"speaker": "Caroline", "text": "...", "dia_id": "D1:5", "img_url": "..."}]
            session_date: 对话发生的日期 "1:56 pm on 8 May, 2023"
        
        Returns:
            事实列表 ["Caroline attended LGBTQ support group on 7 May 2023", ...]
        """
        # 构建对话上下文
        conversation_lines = []
        for msg in conversation_chunk:
            text_line = f"{msg['speaker']}: {msg['text']}"
            
            # 如果启用图片处理，添加图片描述
            if self.enable_image_processing:
                img_desc = None
                if 'dia_id' in msg and msg['dia_id'] in self.image_cache:
                    img_desc = self.image_cache[msg['dia_id']]
                elif 'blip_caption' in msg and msg['blip_caption']:
                    img_desc = msg['blip_caption']
                
                if img_desc:
                    text_line += f"\n  [Image description: {img_desc}]"
            
            conversation_lines.append(text_line)
        
        conversation_text = "\n".join(conversation_lines)
        
        # 根据是否启用图片处理使用不同的prompt
        if self.enable_image_processing:
            prompt = f"""You are a fact extraction assistant. Extract explicit factual statements from the conversation below.

Conversation Date: {session_date}

Conversation:
{conversation_text}

Rules:
1. Extract ONLY verifiable facts (events, dates, relationships, preferences, activities)
2. Convert relative time references to absolute dates based on conversation date
   - "yesterday" → calculate actual date
   - "last week" → calculate date range
   - "last Friday" → calculate specific date
3. Include WHO, WHAT, WHEN, WHERE information
4. **IMPORTANT: If there are image descriptions, extract key information from them (book titles, visible text, objects, activities shown in images)**
5. Each fact should be a complete, standalone sentence
6. Use format: "[Person] [verb] [object/activity] on/in [date/time]"

Examples:
- Caroline attended LGBTQ support group on 7 May 2023
- Melanie shared a photo of the book "Nothing is Impossible" on 12 July 2023
- Caroline showed a painting of a sunset over a lake on 8 May 2023
- Melanie plays clarinet and violin

Extract facts (one per line):"""
        else:
            prompt = f"""You are a fact extraction assistant. Extract explicit factual statements from the conversation below.

Conversation Date: {session_date}

Conversation:
{conversation_text}

Rules:
1. Extract ONLY facts explicitly stated in the conversation (events, dates, relationships, preferences, activities). Do not guess.
2. Handle time carefully.
   - If the conversation uses "yesterday", "today", or "tomorrow", convert it into an absolute date using the Conversation Date.
   - If the conversation uses "last week" / "last weekend", convert it into "The week before <Conversation Date>" / "The weekend before <Conversation Date>".
   - If the conversation uses "last <weekday>", convert it into "The <weekday> before <Conversation Date>".
   - If the conversation uses "this month" / "next month" / "last month", convert it into "<Month> <Year>".
   - If the conversation uses "last year", convert it into the year number (e.g., "2022") using the Conversation Date.
   - For other relative time phrases (e.g., "two months ago", "a few weeks ago"), KEEP the original phrase exactly as stated.
   - Only output an absolute date if (a) it appears in the conversation, or (b) it is a conversion from yesterday/today/tomorrow.
3. Include WHO, WHAT, WHEN, WHERE only when they are explicitly present.
4. Each fact should be a complete, standalone sentence.
5. Prefer copying exact wording from the conversation.
6. Use simple format: "[Person] [fact]". If a time is mentioned, keep it as-is (absolute or relative).

Examples:
- Caroline attended LGBTQ support group on 7 May 2023
- Caroline attended LGBTQ support group on 7 May 2023  (if the conversation says "yesterday" and Conversation Date is 8 May 2023)
- Caroline attended an LGBTQ support group last week
- Melanie has been married for 5 years
- Caroline is interested in a counseling career for transgender people
- Melanie plays clarinet and violin

Extract facts (one per line):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500,
            )
            
            facts_text = response.choices[0].message.content.strip()
            facts = [f.strip() for f in facts_text.split("\n") if f.strip() and not f.strip().startswith("#")]
            
            # 只有在不启用图片处理时才进行时间规范化（原始逻辑）
            if not self.enable_image_processing:
                return [self._normalize_fact_time(f, session_date) for f in facts]
            return facts
        
        except Exception as e:
            print(f"LLM fact extraction failed: {e}")
            return []

    def _normalize_fact_time(self, fact: str, session_date: str) -> str:
        base_dt = self._parse_session_date(session_date)
        if not base_dt:
            return fact

        def format_day_month_year(dt: datetime) -> str:
            return f"{dt.day} {dt.strftime('%B %Y')}"

        base_date_str = format_day_month_year(base_dt)

        def shift_month(dt: datetime, delta_months: int) -> datetime:
            y = dt.year
            m = dt.month + delta_months
            while m <= 0:
                m += 12
                y -= 1
            while m > 12:
                m -= 12
                y += 1
            return datetime(y, m, 1)

        lower = fact.lower()
        if "yesterday" in lower:
            target = base_dt - timedelta(days=1)
            return re.sub(r"\byesterday\b", format_day_month_year(target), fact, flags=re.IGNORECASE)
        if "today" in lower:
            target = base_dt
            return re.sub(r"\btoday\b", format_day_month_year(target), fact, flags=re.IGNORECASE)
        if "tomorrow" in lower:
            target = base_dt + timedelta(days=1)
            return re.sub(r"\btomorrow\b", format_day_month_year(target), fact, flags=re.IGNORECASE)

        if re.search(r"\blast\s+week\b", lower):
            return re.sub(r"\blast\s+week\b", f"The week before {base_date_str}", fact, flags=re.IGNORECASE)

        if re.search(r"\blast\s+weekend\b", lower):
            return re.sub(r"\blast\s+weekend\b", f"The weekend before {base_date_str}", fact, flags=re.IGNORECASE)

        m = re.search(r"\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lower)
        if m:
            weekday = m.group(1).capitalize()
            return re.sub(
                r"\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                f"The {weekday} before {base_date_str}",
                fact,
                flags=re.IGNORECASE,
            )

        if re.search(r"\bthis\s+month\b", lower):
            target = shift_month(base_dt, 0)
            return re.sub(r"\bthis\s+month\b", target.strftime("%B %Y"), fact, flags=re.IGNORECASE)

        if re.search(r"\bnext\s+month\b", lower):
            target = shift_month(base_dt, 1)
            return re.sub(r"\bnext\s+month\b", target.strftime("%B %Y"), fact, flags=re.IGNORECASE)

        if re.search(r"\blast\s+month\b", lower):
            target = shift_month(base_dt, -1)
            return re.sub(r"\blast\s+month\b", target.strftime("%B %Y"), fact, flags=re.IGNORECASE)

        if re.search(r"\blast\s+year\b", lower):
            return re.sub(r"\blast\s+year\b", str(base_dt.year - 1), fact, flags=re.IGNORECASE)

        if re.search(r"\btwo\s+days\s+ago\b", lower):
            target = base_dt - timedelta(days=2)
            return re.sub(r"\btwo\s+days\s+ago\b", format_day_month_year(target), fact, flags=re.IGNORECASE)

        if re.search(r"\bthree\s+days\s+ago\b", lower):
            target = base_dt - timedelta(days=3)
            return re.sub(r"\bthree\s+days\s+ago\b", format_day_month_year(target), fact, flags=re.IGNORECASE)

        return fact
    
    def parse_relative_date(self, text: str, base_date: str) -> str:
        """
        解析相对时间引用为绝对日期
        
        Args:
            text: 包含相对时间的文本 "I went there yesterday"
            base_date: 基准日期 "1:56 pm on 8 May, 2023"
        
        Returns:
            绝对日期 "7 May 2023"
        """
        try:
            # 解析基准日期
            base_dt = self._parse_session_date(base_date)
            if not base_dt:
                return ""

            def format_day_month_year(dt: datetime) -> str:
                return f"{dt.day} {dt.strftime('%B %Y')}"
            
            text_lower = text.lower()
            
            # 相对时间模式
            patterns = {
                r'yesterday': -1,
                r'last week': -7,
                r'last month': -30,
                r'two days ago': -2,
                r'three days ago': -3,
                r'last friday': None,  # 需要特殊处理
                r'last saturday': None,
                r'last sunday': None,
            }
            
            for pattern, days_offset in patterns.items():
                if re.search(pattern, text_lower):
                    if days_offset is not None:
                        target_date = base_dt + timedelta(days=days_offset)
                        return format_day_month_year(target_date)
                    else:
                        # 处理"last Friday"这类
                        weekday_name = pattern.split()[-1]
                        weekday_map = {
                            'monday': 0, 'tuesday': 1, 'wednesday': 2,
                            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
                        }
                        target_weekday = weekday_map.get(weekday_name)
                        if target_weekday is not None:
                            days_back = (base_dt.weekday() - target_weekday) % 7
                            if days_back == 0:
                                days_back = 7
                            target_date = base_dt - timedelta(days=days_back)
                            return format_day_month_year(target_date)
            
            return ""
        
        except Exception as e:
            print(f"Date parsing error: {e}")
            return ""
    
    def _parse_session_date(self, session_date: str) -> datetime:
        """解析session日期字符串为datetime对象"""
        try:
            # "1:56 pm on 8 May, 2023" → datetime
            date_part = session_date.split(" on ")[-1]  # "8 May, 2023"
            dt = datetime.strptime(date_part, "%d %B, %Y")
            return dt
        except Exception as e:
            print(f"Session date parse error: {e}")
            return None
    
    def extract_entities(self, conversation_chunk: List[Dict]) -> Dict[str, List[str]]:
        """
        提取实体(人物、地点、组织、事件)
        
        Returns:
            {
                "people": ["Caroline", "Melanie"],
                "events": ["LGBTQ support group", "pride parade"],
                "locations": ["beach", "museum"],
                "activities": ["pottery", "painting", "camping"]
            }
        """
        entities = {
            "people": set(),
            "events": set(),
            "locations": set(),
            "activities": set(),
        }
        
        for msg in conversation_chunk:
            text = msg['text']
            speaker = msg['speaker']
            entities["people"].add(speaker)
            
            # 简单规则提取(实际应该用NER模型)
            # 事件关键词
            event_keywords = [
                'support group', 'conference', 'parade', 'workshop', 
                'meeting', 'event', 'festival', 'show', 'concert'
            ]
            for kw in event_keywords:
                if kw in text.lower():
                    entities["events"].add(kw)
            
            # 活动关键词
            activity_keywords = [
                'pottery', 'painting', 'camping', 'hiking', 'running',
                'swimming', 'reading', 'playing', 'volunteering'
            ]
            for kw in activity_keywords:
                if kw in text.lower():
                    entities["activities"].add(kw)
        
        return {k: list(v) for k, v in entities.items()}
    
    def enhance_message(self, message: Dict, facts: List[str], entities: Dict) -> str:
        """
        增强单条消息,附加提取的事实和实体信息
        
        Args:
            message: {"speaker": "Caroline", "text": "I went to...", "dia_id": "D1:5"}
            facts: 从该消息所在chunk提取的事实列表
            entities: 提取的实体
        
        Returns:
            增强后的消息内容
        """
        original_content = f"{message['speaker']}: {message['text']}"
        
        # 如果有相关事实,附加到消息后
        if facts:
            # 过滤出与该消息speaker相关的事实
            speaker_facts = [f for f in facts if message['speaker'] in f]
            if speaker_facts:
                fact_section = "\n[Facts extracted: " + "; ".join(speaker_facts) + "]"
                return original_content + fact_section
        
        return original_content
    
    def preprocess_conversation(self, conversation: Dict, session_key: str) -> List[Dict]:
        """
        预处理单个session的对话
        
        Args:
            conversation: 完整对话数据
            session_key: "session_1", "session_2" etc.
        
        Returns:
            增强后的消息列表 [{"speaker": "...", "text": "...", "enhanced_content": "..."}]
        """
        date_key = session_key + "_date_time"
        session_date = conversation.get(date_key, "")
        chats = conversation.get(session_key, [])
        
        if not chats:
            return []
        
        # 分批处理(每batch_size条消息提取一次事实)
        batch_size = 6
        enhanced_messages = []
        
        for i in range(0, len(chats), batch_size):
            chunk = chats[i:i+batch_size]
            
            # 提取事实
            facts = self.extract_facts_with_llm(chunk, session_date)
            
            # 提取实体
            entities = self.extract_entities(chunk)
            
            # 增强每条消息
            for msg in chunk:
                enhanced_content = self.enhance_message(msg, facts, entities)
                enhanced_messages.append({
                    "speaker": msg["speaker"],
                    "text": msg["text"],
                    "enhanced_content": enhanced_content,
                    "facts": facts,  # 保存提取的事实供后续使用
                    "entities": entities,
                })
        
        return enhanced_messages
    
    def preprocess_dataset(self, data_path: str, output_path: str):
        """
        预处理整个数据集
        
        Args:
            data_path: 原始数据集路径
            output_path: 增强后数据集保存路径
        """
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        enhanced_data = []
        
        for idx, item in enumerate(data):
            print(f"\n=== Processing conversation {idx+1}/{len(data)} ===")
            conversation = item["conversation"]
            
            # 预处理每个session
            enhanced_conversation = {"speaker_a": conversation["speaker_a"], "speaker_b": conversation["speaker_b"]}
            
            for key in sorted(conversation.keys()):
                if key in ["speaker_a", "speaker_b"] or "date" in key or "timestamp" in key:
                    enhanced_conversation[key] = conversation[key]
                    continue
                
                if key.startswith("session_"):
                    enhanced_messages = self.preprocess_conversation(conversation, key)
                    enhanced_conversation[key] = enhanced_messages
                    print(f"  {key}: {len(enhanced_messages)} messages processed")
            
            enhanced_item = {
                "qa": item["qa"],
                "conversation": enhanced_conversation
            }
            enhanced_data.append(enhanced_item)
        
        # 保存增强数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Enhanced dataset saved to {output_path}")


if __name__ == "__main__":
    # 默认关闭图片处理
    preprocessor = ConversationPreprocessor(model="qwen-plus", enable_image_processing=False)
    
    # 如果需要启用图片处理，使用:
    # preprocessor = ConversationPreprocessor(
    #     model="qwen-plus", 
    #     enable_image_processing=True, 
    #     image_cache_path="image_descriptions_cache.json"
    # )
    
    # 预处理测试数据集
    preprocessor.preprocess_dataset(
        data_path="dataset/locomo10_test2.json",
        output_path="dataset/locomo10_test2_enhanced.json"
    )