"""Vector Store & RAG Search Engine

Multi-strategy retrieval: vector search, BM25, keyword, hybrid + rerank
"""

import os
import json
import hashlib
from typing import List, Dict, Optional, Any
from datetime import datetime


class VectorStore:
    """Simple vector store with embedding-based and BM25 retrieval"""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self.documents: Dict[str, Dict] = {}
        self.embeddings: Dict[str, List[float]] = {}
        self.index_ready = False
        self._load_index()

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding using sentence-transformers or fallback"""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            emb = model.encode(text)
            return emb.tolist()
        except Exception:
            # Fallback: hash-based pseudo-embedding
            return self._pseudo_embedding(text)

    def _pseudo_embedding(self, text: str, dim: int = 128) -> List[float]:
        """Generate a deterministic pseudo-embedding based on text hash"""
        h = hashlib.md5(text.encode()).hexdigest()
        import random
        random.seed(h)
        return [random.gauss(0, 1) for _ in range(dim)]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def add_documents(self, chunks: List[Dict]):
        """Add document chunks to the index"""
        for chunk in chunks:
            chunk_id = chunk.get("id", hashlib.md5(chunk["content"].encode()).hexdigest())
            self.documents[chunk_id] = chunk
            self.embeddings[chunk_id] = self._get_embedding(chunk["content"])

        self.index_ready = len(self.documents) > 0
        self._save_index()

    def remove_documents(self, doc_id: str):
        """Remove all chunks for a given document"""
        to_remove = [cid for cid, doc in self.documents.items()
                     if doc.get("metadata", {}).get("document_id") == doc_id]
        for cid in to_remove:
            del self.documents[cid]
            if cid in self.embeddings:
                del self.embeddings[cid]
        self._save_index()

    def clear(self):
        """Clear all documents from index"""
        self.documents.clear()
        self.embeddings.clear()
        self.index_ready = False
        self._save_index()

    def _filter_docs(self, document_ids: Optional[List[str]] = None,
                     chunk_type: Optional[str] = None) -> Dict[str, Dict]:
        """Return a filtered copy of self.documents."""
        if not document_ids and not chunk_type:
            return self.documents
        return {
            cid: doc for cid, doc in self.documents.items()
            if (not document_ids
                or doc.get("metadata", {}).get("document_id") in document_ids)
            and (not chunk_type or doc.get("chunk_type") == chunk_type)
        }

    def search_vector(self, query: str, top_k: int = 5,
                      document_ids: Optional[List[str]] = None,
                      chunk_type: Optional[str] = None) -> List[Dict]:
        """Vector similarity search"""
        docs = self._filter_docs(document_ids, chunk_type)
        if not docs:
            return []

        query_emb = self._get_embedding(query)
        scored = []
        for cid, doc in docs.items():
            if cid in self.embeddings:
                score = self._cosine_similarity(query_emb, self.embeddings[cid])
                scored.append((score, cid, doc))

        scored.sort(key=lambda x: -x[0])
        return [
            {
                "chunk_id": cid,
                "document_id": doc.get("metadata", {}).get("document_id", ""),
                "document_name": doc.get("metadata", {}).get("filename", ""),
                "content": doc["content"],
                "chunk_type": doc.get("chunk_type", "text"),
                "page_number": doc.get("page_number"),
                "score": round(score, 4),
                "evidence": {
                    "document_id": doc.get("metadata", {}).get("document_id", ""),
                    "filename": doc.get("metadata", {}).get("filename", ""),
                    "file_type": doc.get("metadata", {}).get("file_type", ""),
                    "page_number": doc.get("page_number"),
                    "chunk_type": doc.get("chunk_type", "text")
                }
            }
            for score, cid, doc in scored[:top_k]
        ]

    def search_bm25(self, query: str, top_k: int = 5,
                    document_ids: Optional[List[str]] = None,
                    chunk_type: Optional[str] = None) -> List[Dict]:
        """BM25 keyword search"""
        import math
        docs = self._filter_docs(document_ids, chunk_type)
        if not docs:
            return []

        # Simple BM25 implementation
        k1, b = 1.5, 0.75
        query_terms = set(query.lower().split())
        avg_doc_len = sum(len(d["content"].split()) for d in docs.values()) / max(len(docs), 1)

        scored = []
        for cid, doc in docs.items():
            doc_text = doc["content"]
            doc_len = len(doc_text.split())
            idf_scores = []

            for term in query_terms:
                tf = doc_text.lower().count(term)
                if tf == 0:
                    continue
                df = sum(1 for d in docs.values() if term in d["content"].lower())
                idf = math.log((len(docs) - df + 0.5) / (df + 0.5) + 1.0)
                score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
                idf_scores.append(score)

            total_score = sum(idf_scores)
            if total_score > 0:
                scored.append((total_score, cid, doc))

        scored.sort(key=lambda x: -x[0])
        return [
            {
                "chunk_id": cid,
                "document_id": doc.get("metadata", {}).get("document_id", ""),
                "document_name": doc.get("metadata", {}).get("filename", ""),
                "content": doc["content"],
                "chunk_type": doc.get("chunk_type", "text"),
                "page_number": doc.get("page_number"),
                "score": round(score, 4),
                "evidence": {
                    "document_id": doc.get("metadata", {}).get("document_id", ""),
                    "filename": doc.get("metadata", {}).get("filename", ""),
                    "page_number": doc.get("page_number"),
                    "chunk_type": doc.get("chunk_type", "text")
                }
            }
            for score, cid, doc in scored[:top_k]
        ]

    def search_hybrid(self, query: str, top_k: int = 5, alpha: float = 0.5,
                      document_ids: Optional[List[str]] = None,
                      chunk_type: Optional[str] = None) -> List[Dict]:
        """Hybrid search combining vector and BM25 scores"""
        vec_results = self.search_vector(query, top_k * 2, document_ids, chunk_type)
        bm25_results = self.search_bm25(query, top_k * 2, document_ids, chunk_type)

        # Normalize and combine scores
        combined = {}
        for r in vec_results:
            combined[r["chunk_id"]] = {"result": r, "vec_score": r["score"], "bm25_score": 0.0}
        for r in bm25_results:
            if r["chunk_id"] in combined:
                combined[r["chunk_id"]]["bm25_score"] = r["score"]
            else:
                combined[r["chunk_id"]] = {"result": r, "vec_score": 0.0, "bm25_score": r["score"]}

        # Normalize scores within each method
        vec_scores = [v["vec_score"] for v in combined.values()]
        bm25_scores = [v["bm25_score"] for v in combined.values()]
        max_vec = max(vec_scores) if vec_scores else 1
        max_bm25 = max(bm25_scores) if bm25_scores else 1

        results = []
        for cid, data in combined.items():
            norm_vec = data["vec_score"] / max_vec if max_vec > 0 else 0
            norm_bm25 = data["bm25_score"] / max_bm25 if max_bm25 > 0 else 0
            hybrid_score = alpha * norm_vec + (1 - alpha) * norm_bm25
            result = data["result"]
            result["score"] = round(hybrid_score, 4)
            result["vec_score"] = round(data["vec_score"], 4)
            result["bm25_score"] = round(data["bm25_score"], 4)
            results.append((hybrid_score, result))

        results.sort(key=lambda x: -x[0])
        return [r for _, r in results[:top_k]]

    def rerank(self, query: str, results: List[Dict], top_k: int = 3) -> List[Dict]:
        """Simple reranking based on keyword overlap with original query"""
        query_terms = set(query.lower().split())
        query_words = query.lower().split()

        scored = []
        for r in results:
            content = r["content"].lower()
            # Term overlap score
            term_overlap = sum(1 for t in query_terms if t in content) / max(len(query_terms), 1)
            # Proximity score (rough): check if query words appear close together
            proximity = 0
            for i, w in enumerate(query_words[:-1]):
                next_w = query_words[i + 1]
                if w in content and next_w in content:
                    proximity += 1
            prox_score = proximity / max(len(query_words) - 1, 1)

            # Combine original score with rerank signals
            original_score = r.get("score", 0.5)
            combined = 0.4 * original_score + 0.4 * term_overlap + 0.2 * prox_score
            scored.append((combined, r))

        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top_k]]

    def search(self, query: str, top_k: int = 5, method: str = "hybrid",
               use_rerank: bool = True,
               document_ids: Optional[List[str]] = None,
               chunk_type: Optional[str] = None) -> Dict:
        """Unified search entry point"""
        docs = self._filter_docs(document_ids, chunk_type)
        if not docs:
            return {"results": [], "total": 0, "method": method, "query": query}

        if method == "vector":
            results = self.search_vector(query, top_k * 2, document_ids, chunk_type)
        elif method == "bm25":
            results = self.search_bm25(query, top_k * 2, document_ids, chunk_type)
        else:
            results = self.search_hybrid(query, top_k * 2, 0.5, document_ids, chunk_type)

        if use_rerank and len(results) > top_k:
            results = self.rerank(query, results, top_k)
        else:
            results = results[:top_k]

        return {
            "results": results,
            "total": len(results),
            "method": method,
            "query": query
        }

    def get_document_chunks(self, document_ids: List[str],
                            chunk_type: Optional[str] = None) -> List[Dict]:
        """Return full chunks for the given documents (in-memory store)."""
        return [
            dict(doc) for cid, doc in self.documents.items()
            if doc.get("metadata", {}).get("document_id") in document_ids
            and (not chunk_type or doc.get("chunk_type") == chunk_type)
        ]

    def get_stats(self) -> Dict:
        return {
            "total_chunks": len(self.documents),
            "index_ready": self.index_ready,
            "types": {
                t: sum(1 for d in self.documents.values() if d.get("chunk_type") == t)
                for t in set(d.get("chunk_type", "text") for d in self.documents.values())
            }
        }

    def _save_index(self):
        """Save index metadata to disk"""
        try:
            meta = {
                "doc_count": len(self.documents),
                "updated_at": datetime.now().isoformat(),
                "documents": {
                    k: {
                        "id": k,
                        "content": v["content"][:100],
                        "chunk_type": v.get("chunk_type", "text"),
                        "metadata": v.get("metadata", {}),
                        "page_number": v.get("page_number")
                    }
                    for k, v in self.documents.items()
                }
            }
            with open(os.path.join(self.persist_dir, "index_meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_index(self):
        """Load index metadata from disk"""
        meta_path = os.path.join(self.persist_dir, "index_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                for k, v in meta.get("documents", {}).items():
                    self.documents[k] = v
                self.index_ready = len(self.documents) > 0
            except Exception:
                pass
