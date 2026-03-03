import os
import json
import requests
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
import bm25s
import Stemmer
from tqdm import tqdm

class LocalAPIEmbeddingFunction(EmbeddingFunction):
    """
    让 ChromaDB 调用你本地启动的 FastAPI Embedding 服务
    """
    def __init__(self, api_base: str, model_name: str = "Qwen3-Embedding-0.6B"):
        self.api_url = f"{api_base.rstrip('/')}/embeddings"
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        """
        ChromaDB 会自动调用这个函数把文本列表转成向量列表
        """
        # 构造 OpenAI 格式的请求
        payload = {
            "input": input,
            "model": self.model_name
        }
        
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # 提取向量 (OpenAI 格式: data['data'][i]['embedding'])
            embeddings = [item['embedding'] for item in data['data']]
            return embeddings
        except Exception as e:
            print(f"❌ Embedding API Error: {e}")
            # 如果失败返回空列表或报错，视情况而定
            raise e


class ExternalKnowledgeBase:
    def __init__(self, 
                 documents: list[str] = None, 
                 db_path: str = "./my_rag_db", 
                 collection_name: str = "locomo_knowledge",
                 embedding_api_base: str = "http://localhost:8002/v1"):
        
        self.db_path = db_path
        self.collection_name = collection_name
        
        print(f"📂 Loading Vector DB from {db_path}...")
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        
        self.embed_fn = LocalAPIEmbeddingFunction(api_base=embedding_api_base)

        self.vector_collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embed_fn, # 绑定你的 API
            metadata={"hnsw:space": "cosine"} # 使用余弦相似度
        )

        self.bm25_path = os.path.join(db_path, "bm25_index")
        self.bm25_retriever = None
        self.corpus_tokens = None

        if documents and len(documents) > 0:
            self._build_index(documents)
        else:
            self._load_bm25()

    def _build_index(self, documents):
        """构建索引（如果数据库里是空的）"""
        existing_count = self.vector_collection.count()
        if existing_count > 0:
            print(f"✅ Vector DB already contains {existing_count} docs. Skipping vector embedding.")
        else:
            print(f"🚀 Indexing {len(documents)} docs into Vector DB (this may take a while)...")
            
            ids = [str(i) for i in range(len(documents))]
            BATCH_SIZE = 2000
            
            total_docs = len(documents)
            
            # 使用 tqdm 显示进度条
            for i in tqdm(range(0, total_docs, BATCH_SIZE), desc="Vector Upserting"):
                end_i = min(i + BATCH_SIZE, total_docs)
                
                batch_docs = documents[i : end_i]
                batch_ids = ids[i : end_i]
                
                self.vector_collection.add(
                    documents=batch_docs,
                    ids=batch_ids
                )
            
            print("✅ Vector Indexing Complete.")

        print("🔠 Building BM25 Index (English)...")
        # bm25s.tokenize 默认支持英文分词和词干提取 (stemmer=True)
        # stopwords="en" 会自动去除 the, is, at 等停用词
        stemmer = Stemmer.Stemmer("english")
        
        self.corpus_tokens = bm25s.tokenize(
            documents, 
            stopwords="en", 
            stemmer=stemmer  
        )
        
        self.bm25_retriever = bm25s.BM25(corpus=documents) 
        self.bm25_retriever.index(self.corpus_tokens)
        

        print(f"💾 Saving BM25 index to {self.bm25_path}...")
        self.bm25_retriever.save(self.bm25_path)

        with open(os.path.join(self.db_path, "documents.json"), "w", encoding="utf-8") as f:
            json.dump(documents, f)

    def _load_bm25(self):
            """尝试从磁盘加载 BM25"""
            try:
                print(f"📂 Loading BM25 index from {self.bm25_path}...")
                
                # 加载原始文本到 self.documents
                with open(os.path.join(self.db_path, "documents.json"), "r", encoding="utf-8") as f:
                    self.documents = json.load(f)

                # 加载 BM25 索引
                self.bm25_retriever = bm25s.BM25.load(self.bm25_path, load_corpus=True)
                
                if not hasattr(self.bm25_retriever, "corpus") or not self.bm25_retriever.corpus:
                    self.bm25_retriever.corpus = self.documents

            except Exception as e:
                print(f"⚠️ Failed to load BM25 index: {e}. Please initialize with documents first.")

    def _min_max_normalize(self, scores, invert=False):
            """
            辅助函数：Min-Max 归一化
            :param scores: 分数列表 (可能来自 NumPy 数组)
            :param invert: 是否反转
            """
            # --- 修复点：处理 NumPy 数组 ---
            # 如果是 NumPy 数组，先转成普通 list
            if hasattr(scores, 'tolist'):
                scores = scores.tolist()
            
            # 现在这是一个普通的 list，可以使用 if not scores 判断是否为空
            if not scores:
                return []
            
            # 转换为 float 避免类型问题
            scores = [float(s) for s in scores]
            
            min_s = min(scores)
            max_s = max(scores)
            
            # 避免除以零（如果所有分数都一样，或者只有一个结果）
            if max_s == min_s:
                # 如果只有一个结果，或者所有分数一样，归一化默认为 1.0 (或者 0.5，看策略)
                return [1.0] * len(scores)
            
            norm_scores = []
            for s in scores:
                # 标准 Min-Max: (x - min) / (max - min)
                normalized = (s - min_s) / (max_s - min_s)
                
                # 如果是距离（越小越好），需要反转：1 - normalized
                if invert:
                    normalized = 1.0 - normalized
                
                norm_scores.append(normalized)
                
            return norm_scores

    def search(self, query, top_k=5):
        # 用字典存储最终融合分数: {doc_content: final_score}
        fusion_scores = {}

        bm25_docs_list = []
        bm25_norm_scores = []
        
        if self.bm25_retriever:
            # 分词
            stemmer = Stemmer.Stemmer("english")
            query_tokens = bm25s.tokenize([query], stopwords="en", stemmer=stemmer)
            
            # 这里的 k 可以稍微取大一点，给融合留空间，比如 top_k * 2
            # 返回的是 batch，所以取 [0]
            bm25_res_docs, bm25_res_scores = self.bm25_retriever.retrieve(query_tokens, k=top_k * 2)
            
            raw_docs = bm25_res_docs[0]
            raw_scores = bm25_res_scores[0]
            
            # 归一化 BM25 分数 (Score 越大越好，不需要 invert)
            bm25_norm_scores = self._min_max_normalize(raw_scores, invert=False)

            # 处理文档格式并暂存
            for doc, norm_score in zip(raw_docs, bm25_norm_scores):
                doc_content = doc['text'] if isinstance(doc, dict) else str(doc)
                # 初始化分数，加权 0.5 (可调整)
                if doc_content not in fusion_scores:
                    fusion_scores[doc_content] = 0.0
                fusion_scores[doc_content] += norm_score * 0.5



        vector_results = self.vector_collection.query(
            query_texts=[query],
            n_results=top_k * 2 
        )

        vec_docs_list = []
        vec_norm_scores = []

        if vector_results['documents']:
            raw_vec_docs = vector_results['documents'][0]
            # ChromaDB 默认返回 distances (L2 或 Cosine Distance)
            # 注意：distances 越小越相似
            raw_vec_distances = vector_results['distances'][0]
            
            # 归一化 Vector 分数 (Distance 越小越好，需要 invert=True)
            # 归一化后变成 [0, 1] 的相似度，1 代表距离最小(最相似)
            vec_norm_scores = self._min_max_normalize(raw_vec_distances, invert=True)
            
            for doc, norm_score in zip(raw_vec_docs, vec_norm_scores):
                if doc not in fusion_scores:
                    fusion_scores[doc] = 0.0
                # 加权 0.5 并累加
                fusion_scores[doc] += norm_score * 0.5

        sorted_results = sorted(
            fusion_scores.items(), 
            key=lambda item: item[1], 
            reverse=True
        )
        
        final_docs = [item[0] for item in sorted_results[:top_k]]
        
        return final_docs


if __name__ == "__main__":
    # 假设这是你的原始数据（可以是几千条 list）

    # raw_docs = [
    #     "Elon Musk founded SpaceX in 2002.",
    #     "The headquarters of SpaceX is in Hawthorne, California.",
    #     "DeepSeek is an AI company based in China.",
    #     "Python is a great programming language for RAG."
    # ]

    with open("/home/zengyuqi/memos/raw_data.json","r") as f:
        raw_docs=json.load(f)

    kb = ExternalKnowledgeBase(
        documents=raw_docs,
        db_path="./test_db_persistence",
        embedding_api_base="http://localhost:8002/v1"
    )

    print("\n--- Testing Search ---")
    results = kb.search("When did Caroline go to the LGBTQ support group?", top_k=10)
    for r in results:
        print(f"- {r}")

    print("\n--- Testing Persistence ---")

    kb_loaded = ExternalKnowledgeBase(
        documents=[], # 空列表表示只读
        db_path="./test_db_persistence",
        embedding_api_base="http://localhost:8002/v1"
    )
    results_2 = kb_loaded.search("When did Caroline go to the LGBTQ support group?", top_k=3)
    for r in results_2:
        print(f"- {r}")