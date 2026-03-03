import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI
from tqdm import tqdm

from .client import MemOSClient
from prompts import ANSWER_PROMPT,JUDGE_SYSTEM_PROMPT,AGENT_SYSTEM_PROMPT

from simple_rag.rag_workflow import ExternalKnowledgeBase

load_dotenv()


class MemOSSearch:
    def __init__(self, output_path: str = "results/memos_results.json", top_k: int = 10):
        self.enable_multiturn_rag=False 
        self.client = MemOSClient()
        self.top_k = top_k
        self.openai_client = OpenAI()
        self.results = defaultdict(list)
        self.output_path = output_path
        self.ANSWER_PROMPT = ANSWER_PROMPT
        self.model = os.getenv("MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

        if self.enable_multiturn_rag:
            print("🚀 Initializing External Knowledge Base for Agentic RAG...")
            self.kb = ExternalKnowledgeBase(
                documents=None, # 读取现有数据
                db_path="../../simple_rag/test_db_persistence", 
                embedding_api_base="http://localhost:8002/v1" 
              )

    def search_memory(
        self, user_id: str, query: str, conversation_id: str | None
    ) -> Tuple[List[Dict], List[Dict] | None, float]:
        start = time.time()
        
        # Detect temporal queries and adjust limits
        temporal_keywords = ["when", "date", "time", "last", "before", "after", "ago", "recent"]
        is_temporal_query = any(keyword in query.lower() for keyword in temporal_keywords)
        
        memory_limit = int(self.top_k * 1.3) if is_temporal_query else self.top_k
        
        resp = self.client.search_memory(
            user_id=user_id,
            query=query,
            conversation_id=conversation_id,
            memory_limit_number=memory_limit,
            include_preference=True,
            preference_limit_number=10,  # Increased from 6
        )
        end = time.time()

        data = resp.get("data", {})
        memory_detail_list = data.get("memory_detail_list", [])
        preference_detail_list = data.get("preference_detail_list", [])

        # Normalize to the shape used downstream (timestamp/memory)
        semantic_memories = [
            {
                "memory": m.get("memory_value", ""),
                "timestamp": str(m.get("create_time", "")),
                "score": float(m.get("relativity", 0.0)),
            }
            for m in memory_detail_list
        ]

        # Graph memories are optional; MemOS provides preference memories separately
        graph_memories = [
            {
                "preference": p.get("preference", ""),
                "type": p.get("preference_type", ""),
            }
            for p in preference_detail_list
        ] or None

        return semantic_memories, graph_memories, end - start

    def answer_question(self, speaker_1_user_id: str, speaker_2_user_id: str, question: str, conversation_id: str):
        if not self.enable_multiturn_rag:
            speaker_1_memories, speaker_1_graph_memories, speaker_1_memory_time = self.search_memory(
                speaker_1_user_id, question, conversation_id
            )
            speaker_2_memories, speaker_2_graph_memories, speaker_2_memory_time = self.search_memory(
                speaker_2_user_id, question, conversation_id
            )

            search_1_memory = [f"{item['timestamp']}: {item['memory']}" for item in speaker_1_memories]
            search_2_memory = [f"{item['timestamp']}: {item['memory']}" for item in speaker_2_memories]

            template = Template(self.ANSWER_PROMPT)
            answer_prompt = template.render(
                speaker_1_user_id=speaker_1_user_id.split("_")[0],
                speaker_2_user_id=speaker_2_user_id.split("_")[0],
                speaker_1_memories=json.dumps(search_1_memory, indent=4),
                speaker_2_memories=json.dumps(search_2_memory, indent=4),
                speaker_1_graph_memories=json.dumps(speaker_1_graph_memories, indent=4),
                speaker_2_graph_memories=json.dumps(speaker_2_graph_memories, indent=4),
                question=question,
            )

            t1 = time.time()
            response = self.openai_client.chat.completions.create(
                model=self.model, messages=[{"role": "system", "content": answer_prompt}], temperature=0.0
            )
            t2 = time.time()
            response_time = t2 - t1
            return (
                response.choices[0].message.content,
                speaker_1_memories,
                speaker_2_memories,
                speaker_1_memory_time,
                speaker_2_memory_time,
                speaker_1_graph_memories,
                speaker_2_graph_memories,
                response_time,
            )
        
        else:
            # 先执行 MemOS 检索
            speaker_1_memories, speaker_1_graph_memories, speaker_1_memory_time = self.search_memory(
                speaker_1_user_id, question, conversation_id
            )
            speaker_2_memories, speaker_2_graph_memories, speaker_2_memory_time = self.search_memory(
                speaker_2_user_id, question, conversation_id
            )
            
            t_start_gen = time.time()

            # 构造初始 Memory String (Context)
            spk1_lines = [f"[{item['timestamp']}]: {item['memory']}" for item in speaker_1_memories]
            spk2_lines = [f"[{item['timestamp']}]: {item['memory']}" for item in speaker_2_memories]
            
            memory_str = f"Memories for {speaker_1_user_id}:\n" + "\n".join(spk1_lines) + "\n\n"
            memory_str += f"Memories for {speaker_2_user_id}:\n" + "\n".join(spk2_lines)

            print(f"\n🔍 [Agent] Question: {question}")

            # Agentic Loop: Judge -> Hop -> Answer
            judge_prompt = f"""
    Question: {question}

    Retrieved Memories from Database:
    {memory_str}

    Now, begin to judge.
    """
            
            resp = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": judge_prompt}
                ],
                response_format={"type": "json_object"}
            )
            judgment = json.loads(resp.choices[0].message.content)

            if judgment.get('status') == "INSUFFICIENT":
                # 防御性获取 query，如果是 None，这就回退使用原始问题
                current_query = judgment.get('search_query')
                if not current_query:
                    current_query = question
                
                print(f"⚠️ [Agent] Insufficient info. Searching external KB for: {current_query}")
                
                MAX_HOPS = 2
                
                for hop in range(MAX_HOPS):
                    # 防止空 query 炸掉 BM25
                    if not current_query or not isinstance(current_query, str):
                        print("⚠️ [Agent] Invalid query detected, stopping hops.")
                        break

                    # 外部检索
                    external_docs = self.kb.search(current_query, top_k=3)
                    external_context = "\n".join(external_docs)
                    
                    print(f"🔎 [Hop {hop+1}] Found: {external_context[:100]}...")
                    
                    hop_prompt = f"""
    Original Question: {question}
    Current Known Info: {memory_str}
    Newly Found Info: {external_context}

    Do we have the full answer now?
    If yes, output "DONE".
    If no, output "CONTINUE" and a new search query based on the new info.

    Format: JSON {{ "status": "DONE" | "CONTINUE", "search_query": "..." }}
    """
                    hop_resp = self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "user", "content": JUDGE_SYSTEM_PROMPT},
                            {"role": "user", "content": hop_prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    hop_result = json.loads(hop_resp.choices[0].message.content)
                    
                    # 更新 Context
                    memory_str += f"\n\n[External Search Query]: {current_query}\n[External Evidence]: {external_context}\n"
                    
                    if hop_result.get('status') == "DONE":
                        break
                    else:
                        # 获取下一步的 query，如果 LLM 没给，就停止
                        next_query = hop_result.get('search_query')
                        if next_query:
                            current_query = next_query
                        else:
                            print("⚠️ [Agent] LLM did not provide next query. Stopping.")
                            break

            final_answer_resp = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {question}\n\nContext:\n{memory_str}"}
                ]
            )
            final_content = final_answer_resp.choices[0].message.content

            t_end_gen = time.time()
            response_time = t_end_gen - t_start_gen

            return (
                final_content,           # 最终回答
                speaker_1_memories,     
                speaker_2_memories,
                speaker_1_memory_time,
                speaker_2_memory_time,
                speaker_1_graph_memories, # 图记忆
                speaker_2_graph_memories,
                response_time            # 生成耗时 (包含了 Agent 思考的时间)
            )


    def process_question(self, val: Dict, speaker_a_user_id: str, speaker_b_user_id: str, conversation_id: str):
        question = val.get("question", "")
        answer = val.get("answer", "")
        category = val.get("category", -1)
        evidence = val.get("evidence", [])
        adversarial_answer = val.get("adversarial_answer", "")

        (
            response,
            speaker_1_memories,
            speaker_2_memories,
            speaker_1_memory_time,
            speaker_2_memory_time,
            speaker_1_graph_memories,
            speaker_2_graph_memories,
            response_time,
        ) = self.answer_question(speaker_a_user_id, speaker_b_user_id, question, conversation_id)

        result = {
            "question": question,
            "answer": answer,
            "category": category,
            "evidence": evidence,
            "response": response,
            "adversarial_answer": adversarial_answer,
            "speaker_1_memories": speaker_1_memories,
            "speaker_2_memories": speaker_2_memories,
            "num_speaker_1_memories": len(speaker_1_memories),
            "num_speaker_2_memories": len(speaker_2_memories),
            "speaker_1_memory_time": speaker_1_memory_time,
            "speaker_2_memory_time": speaker_2_memory_time,
            "speaker_1_graph_memories": speaker_1_graph_memories,
            "speaker_2_graph_memories": speaker_2_graph_memories,
            "response_time": response_time,
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=4, ensure_ascii=False)

        return result

    def process_questions_parallel(self, qa_list: List[Dict], speaker_a_user_id: str, speaker_b_user_id: str, conversation_id: str, max_workers: int = 10):
        """Process multiple questions in parallel."""
        def process_single_question(val):
            result = self.process_question(val, speaker_a_user_id, speaker_b_user_id, conversation_id)
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=4, ensure_ascii=False)
            return result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(
                tqdm(
                    executor.map(process_single_question, qa_list),
                    total=len(qa_list),
                    desc=f"Answering Questions",
                    leave=False,
                )
            )

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=4, ensure_ascii=False)

        return results

    def process_data_file(self, file_path: str, max_workers: int = 10):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        run_tag = os.getenv("MEMOS_RUN_TAG", "").strip()
        suffix = f"_{run_tag}" if run_tag else ""

        for idx, item in tqdm(enumerate(data), total=len(data), desc="Processing conversations"):
            qa = item["qa"]
            conversation = item["conversation"]
            speaker_a = conversation["speaker_a"]
            speaker_b = conversation["speaker_b"]

            speaker_a_user_id = f"{speaker_a}_{idx}{suffix}"
            speaker_b_user_id = f"{speaker_b}_{idx}{suffix}"
            conversation_id = f"conv_{idx}{suffix}"

            results = self.process_questions_parallel(
                qa, speaker_a_user_id, speaker_b_user_id, conversation_id, max_workers=max_workers
            )
            self.results[idx].extend(results)

            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=4, ensure_ascii=False)

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=4, ensure_ascii=False)
