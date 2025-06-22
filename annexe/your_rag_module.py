#!/usr/bin/env python3
import os
import json
import logging
from typing import List, Dict, Optional, Tuple

import time
import numpy as np
import faiss
import h5py
from sentence_transformers import SentenceTransformer, CrossEncoder
import google.generativeai as genai
from dotenv import load_dotenv
from whoosh import index as whoosh_index
from whoosh.analysis import RegexTokenizer, LowercaseFilter
from whoosh import scoring 
from whoosh.fields import Schema, TEXT, ID
from whoosh.analysis import StandardAnalyzer
from whoosh.qparser import QueryParser

FR_ANALYZER = RegexTokenizer(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+") \
              | LowercaseFilter()
load_dotenv()

# ---------------------------
# 📦 Vector Store HDF5 + FAISS
# ---------------------------
class VectorStoreHDF5:
    def __init__(self, path: str):
        self.path = path
        self.faiss_path = f"{path}.faiss"
        self.index: Optional[faiss.Index] = None
        self.vectors: Optional[np.ndarray] = None
        self.meta: List[Dict] = []
        self.id_map: Dict[str, Dict] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_store(self):
        # Load HDF5 vectors and metadata
        with h5py.File(self.path, 'r') as hf:
            self.vectors = hf['vectors'][:]
            raw = hf['metadata'][:]
            # decode byte-encoded JSON metadata
            self.meta = []
            for r in raw:
                m = json.loads(r.decode('utf-8'))
                # ensure each metadata entry has an 'id'
                if 'id' not in m:
                    # generate a unique id based on index
                    m['id'] = str(len(self.meta))
                self.meta.append(m)
        # Build id->meta map
        self.id_map = {m['id']: m for m in self.meta}
        # Load FAISS index
        if os.path.exists(self.faiss_path):
            self.index = faiss.read_index(self.faiss_path)
            self.logger.info(f"Loaded FAISS index from {self.faiss_path}")
        else:
            raise FileNotFoundError(f"FAISS index not found at {self.faiss_path}")

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        if self.index is None:
            raise RuntimeError("FAISS index not loaded")
        vec = query_vec.reshape(1, -1) if query_vec.ndim == 1 else query_vec
        faiss.normalize_L2(vec)
        scores, ids = self.index.search(vec, top_k)
        return list(zip(ids[0].tolist(), scores[0].tolist()))

    def get_metadata(self, indices: List[int]) -> List[Dict]:
        return [self.meta[i] for i in indices]

# ---------------------------
# 🤖 Embedding Generator
# ---------------------------
class EmbeddingGenerator:
    def __init__(self, model_name: str = 'all-mpnet-base-v2'):
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> np.ndarray:
        return self.model.encode(text, convert_to_numpy=True)

# ---------------------------
# 🗃️ BM25 Initialization
# ---------------------------

def init_bm25_index(index_dir: str):
    if not whoosh_index:
        raise ImportError("Whoosh required for BM25. Install via 'pip install whoosh'.")
    if not os.path.exists(index_dir):
        os.makedirs(index_dir)
        

        schema = Schema(id=ID(stored=True), content=TEXT(analyzer=FR_ANALYZER))
        idx = whoosh_index.create_in(index_dir, schema)
    else:
        idx = whoosh_index.open_dir(index_dir)
    return idx

# ---------------------------
# 🔎 Simple Retriever (dense-only)
# ---------------------------
class Retriever:
    def __init__(self, store: VectorStoreHDF5, embedder: EmbeddingGenerator):
        self.store = store
        self.embedder = embedder

    def retrieve(self, question: str, top_k: int = 5) -> List[Dict]:
        q_vec = self.embedder.embed_text(question)
        hits = self.store.search(q_vec, top_k)
        results = []
        for idx, score in hits:
            meta = self.store.meta[idx].copy()
            meta['score'] = float(score)
            results.append(meta)
        return results

# ---------------------------
# 🔄 Hybrid Retriever (dense + BM25 + optional reranking)
# ---------------------------
class HybridRetriever:
    def __init__(
        self,
        store: VectorStoreHDF5,
        embedder: EmbeddingGenerator,
        bm25_index_dir: Optional[str] = None
    ):
        self.store = store
        self.embedder = embedder
        self.bm25_idx = init_bm25_index(bm25_index_dir) if bm25_index_dir else None
        self.qp = QueryParser("content", schema=self.bm25_idx.schema)
        self.cross_encoder: Optional[CrossEncoder] = None

    def _build_query(self, question: str):
        toks = [t.text for t in FR_ANALYZER(question)]
        return None if not toks else self.qp.parse(" ".join(toks))

    def enable_reranking(self, model_name: str):
        self.cross_encoder = CrossEncoder(model_name)
        logging.getLogger(self.__class__.__name__).info(f"Loaded CrossEncoder '{model_name}' for reranking")

    def retrieve(self,
                 question: str,
                 top_k: int = 5,
                 alpha: float = 0.5,
                 dense_k: int = 10,
                 bm25_k: int = 10) -> List[Dict]:
        # ↓ Dense retrieval first (works even when bm25 disabled)
        q_vec = self.embedder.embed_text(question)
        dense_hits = self.store.search(q_vec, dense_k)

        # BM-25 retrieval (optional)
        bm25_hits = []
        if self.bm25_idx:
            print("⇢ BM25 docs in index:", self.bm25_idx.doc_count())
            query = self._build_query(question)
            if query is not None:
                with self.bm25_idx.searcher(weighting=scoring.BM25F()) as searcher:
                    res = searcher.search(query, limit=bm25_k)
                    bm25_hits = [(hit["id"], hit.score) for hit in res]
                    for mid, _ in bm25_hits:
                        if mid not in self.store.id_map:
                            print("⚠️  ID mismatch →", mid[:80])
        # BM25 retrieval
        bm25_hits = []
        if self.bm25_idx:
            query = self._build_query(question)
            if query is not None:
                bm25_hits = []
                if query is not None:
                    with self.bm25_idx.searcher(weighting=scoring.BM25F()) as searcher:
                        res = searcher.search(query, limit=bm25_k)
                        bm25_hits = [(hit['id'], hit.score) for hit in res]
        # Combine
        combined = {}
        for idx, score in dense_hits:
            meta = self.store.meta[idx]
            mid = meta['id']
            combined[mid] = {'meta': meta.copy(), 'dense': score, 'bm25': 0.0}
        for mid, score in bm25_hits:
            if mid in combined:
                combined[mid]['bm25'] = score
            elif mid in self.store.id_map:
                combined[mid] = {'meta': self.store.id_map[mid].copy(), 'dense': 0.0, 'bm25': score}
        max_d = max((v['dense'] for v in combined.values()), default=1.0)
        if max_d == 0.0:
            logging.warning("All dense scores are zero → skipping dense normalization")
            max_d = 1.0

        max_b = max((v['bm25'] for v in combined.values()), default=1.0)
        if max_b == 0.0:
            logging.warning("All BM25 scores are zero → skipping BM25 normalization")
            max_b = 1.0
        for v in combined.values():
            v['score'] = alpha*(v['dense']/max_d) + (1-alpha)*(v['bm25']/max_b)
        items = sorted(combined.values(), key=lambda x: x['score'], reverse=True)
        # Rerank
        if self.cross_encoder:
            pairs = [(question, item['meta'].get('text','')) for item in items[:top_k*2]]
            rerank_scores = self.cross_encoder.predict(pairs)
            for item, rs in zip(items[:top_k*2], rerank_scores):
                item['score'] = float(rs)
            items = sorted(items, key=lambda x: x['score'], reverse=True)
        # Top-k
        results = []
        for item in items[:top_k]:
            m = item['meta']
            if 'type' not in m:          # garantit la clé attendue
                m['type'] = 'text'
            m['score'] = float(item['score'])
            results.append(m)
        return results

# ---------------------------
# ✨ Gemini LLM
# ---------------------------
class GeminiLLM:
    def __init__(self, model_name: str = 'gemini-1.5-flash-latest'):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY non défini")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.config = genai.types.GenerationConfig(temperature=0.0)

    def generate(self, prompt: str) -> str:
        # Respect API rate limits
        time.sleep(1)
        resp = self.model.generate_content(prompt, generation_config=self.config)
        return resp.text if resp.parts else ''

# ---------------------------
# 🔁 RAG Pipeline
# ---------------------------
class RAG:
    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.llm = llm

    def answer(self, question: str, top_k: int = 3) -> str:
        contexts = self.retriever.retrieve(question, top_k)
        prompt = (
            "Tu es un assistant spécialisé en données statistiques. "
            "Utilise les extraits suivants pour répondre à la question.\n"
            "Inclue des données numériques si pertinent.\n\n"
            "Contexte :\n"
        )
        for ctx in contexts:
            text = ctx.get('original_text',
                        ctx.get('text',
                                ctx.get('text_representation','')))
            prompt += f"- ({ctx.get('type','text')} p.{ctx.get('page','?')}): {text}\n"
        prompt += f"\nQuestion : {question}\nRéponse :"
        # Respect API rate limits
        time.sleep(0.5)
        return self.llm.generate(prompt)
