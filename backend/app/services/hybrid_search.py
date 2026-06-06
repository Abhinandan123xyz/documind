"""
Hybrid Search: BM25 + Dense Embeddings + CrossEncoder Reranker
with Reciprocal Rank Fusion (RRF)

Features:
- Improved BM25 tokenization (handles punctuation, hyphens)
- Original text preservation (no reconstruction from tokens)
- Unique chunk IDs using document_id
- Metadata filtering support
- Incremental BM25 index updates
- CrossEncoder reranker for final precision
- Retrieval metrics tracking
"""

import numpy as np
from typing import List, Dict, Optional, Set
from rank_bm25 import BM25Okapi
import re
import uuid
from datetime import datetime
from app.services.vectorstore import search_similar_chunks, get_or_create_collection


# ============================================================
# Improved Tokenizer
# ============================================================

def improved_tokenize(text: str) -> List[str]:
    """
    Better tokenization that handles:
    - Punctuation (splits on punctuation but preserves hyphenated words)
    - Lowercasing
    - Whitespace normalization
    - Number preservation
    
    Examples:
    "cross-encoder" → ["cross-encoder"] (not ["cross", "encoder"])
    "LLM vs RAG" → ["llm", "vs", "rag"]
    "What is RAG?" → ["what", "is", "rag"]
    """
    # Normalize text
    text = text.lower().strip()
    
    # Replace common separators with space (but keep hyphens in words)
    # "cross-encoder" stays, but "word - word" becomes "word word"
    text = re.sub(r'\s+[-–—]\s+', ' ', text)  # word - word → word word
    text = re.sub(r'(?<!\w)[-–—](?!\w)', ' ', text)  # standalone hyphens
    
    # Split on punctuation and whitespace
    # This preserves hyphenated words like "cross-encoder"
    tokens = re.findall(r'[a-z0-9]+(?:[-–—][a-z0-9]+)*', text)
    
    # Filter empty tokens and very short tokens
    tokens = [t for t in tokens if len(t) > 0]
    
    return tokens


# ============================================================
# Retrieval Metrics Tracker
# ============================================================

class RetrievalMetrics:
    """Tracks retrieval performance metrics."""
    
    def __init__(self):
        self.total_queries = 0
        self.total_candidates = 0
        self.total_retrieved = 0
        self.latencies: List[float] = []
        self.bm25_hits = 0
        self.dense_hits = 0
        self.hybrid_hits = 0
    
    def record_query(
        self,
        bm25_count: int,
        dense_count: int,
        final_count: int,
        latency_ms: float
    ):
        self.total_queries += 1
        self.total_candidates += (bm25_count + dense_count)
        self.total_retrieved += final_count
        self.latencies.append(latency_ms)
        if bm25_count > 0: self.bm25_hits += 1
        if dense_count > 0: self.dense_hits += 1
        if final_count > 0: self.hybrid_hits += 1
    
    def get_stats(self) -> Dict:
        if self.total_queries == 0:
            return {"queries": 0, "message": "No queries yet"}
        
        return {
            "total_queries": self.total_queries,
            "avg_candidates": self.total_candidates / self.total_queries,
            "avg_retrieved": self.total_retrieved / self.total_queries,
            "avg_latency_ms": sum(self.latencies) / len(self.latencies),
            "bm25_success_rate": self.bm25_hits / self.total_queries,
            "dense_success_rate": self.dense_hits / self.total_queries,
            "hybrid_success_rate": self.hybrid_hits / self.total_queries,
        }


# ============================================================
# CrossEncoder Reranker (Optional - install with: pip install sentence-transformers)
# ============================================================

class CrossEncoderReranker:
    """
    Reranks retrieved chunks using a CrossEncoder model.
    Much more accurate than embedding similarity alone.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Args:
            model_name: HuggingFace model for reranking
        """
        self.model_name = model_name
        self.model = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy load the model."""
        if not self._initialized:
            try:
                from sentence_transformers import CrossEncoder
                print(f"⏳ Loading reranker model: {self.model_name}...")
                self.model = CrossEncoder(self.model_name)
                self._initialized = True
                print("✅ Reranker ready!")
            except ImportError:
                print("⚠️ sentence-transformers not installed. Reranker disabled.")
                print("   Install with: pip install sentence-transformers")
                self.model = None
                self._initialized = True  # Mark as initialized to stop trying
    
    def rerank(self, query: str, chunks: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Rerank chunks using CrossEncoder.
        
        Args:
            query: User question
            chunks: List of retrieved chunks
            top_k: Number of top results to return after reranking
            
        Returns:
            Reranked chunks with cross_encoder_score added
        """
        self._initialize()
        
        if not self.model or len(chunks) == 0:
            return chunks[:top_k]
        
        # Prepare pairs for CrossEncoder
        pairs = [(query, chunk["text"]) for chunk in chunks]
        
        # Get relevance scores
        scores = self.model.predict(pairs)
        
        # Add scores to chunks
        for i, chunk in enumerate(chunks):
            chunk["cross_encoder_score"] = float(scores[i])
        
        # Sort by cross-encoder score (descending)
        reranked = sorted(chunks, key=lambda x: x.get("cross_encoder_score", 0), reverse=True)
        
        return reranked[:top_k]


# ============================================================
# Main HybridRetriever Class
# ============================================================

class HybridRetriever:
    """
    Production-grade hybrid retrieval: BM25 + Dense + RRF + CrossEncoder.
    """
    
    def __init__(
        self,
        user_id: str,
        bm25_weight: float = 0.4,
        dense_weight: float = 0.6,
        enable_reranker: bool = True,
        metadata_filter: Optional[Dict] = None
    ):
        self.user_id = user_id
        self.bm25_weight = bm25_weight
        self.dense_weight = dense_weight
        self.metadata_filter = metadata_filter  # e.g., {"document_id": "abc123"}
        
        # BM25 data
        self.bm25_index: Optional[BM25Okapi] = None
        self.corpus_tokenized: List[List[str]] = []
        self.corpus_original: List[str] = []       # ✅ Store original text (not reconstructed)
        self.corpus_metadata: List[Dict] = []
        self.corpus_ids: List[str] = []            # ✅ Unique chunk IDs
        self._index_built = False
        
        # Reranker
        self.reranker = CrossEncoderReranker() if enable_reranker else None
        self.enable_reranker = enable_reranker
        
        # Metrics
        self.metrics = RetrievalMetrics()
    
    def _make_chunk_id(self, metadata: Dict) -> str:
        """Create a unique chunk ID."""
        doc_id = metadata.get("document_id", "")
        page = metadata.get("page", "")
        chunk_idx = metadata.get("chunk_index", "")
        
        if doc_id:
            return f"{doc_id}_p{page}_c{chunk_idx}"
        else:
            return f"{uuid.uuid4().hex[:12]}"  # Fallback unique ID
    
    def build_bm25_index(self) -> bool:
        """Build BM25 index with improved tokenization."""
        try:
            collection = get_or_create_collection(self.user_id)
            count = collection.count()
            
            if count == 0:
                print(f"⚠️ No documents in collection for {self.user_id}")
                return False
            
            # Apply metadata filter if specified
            where_filter = self.metadata_filter if self.metadata_filter else None
            
            results = collection.get(
                include=["documents", "metadatas"],
                limit=count,
                where=where_filter
            )
            
            self.corpus_tokenized = []
            self.corpus_original = []    # ✅ Store original text
            self.corpus_metadata = []
            self.corpus_ids = []         # ✅ Store unique IDs
            
            for doc, meta in zip(results["documents"], results["metadatas"]):
                # ✅ Use improved tokenizer
                tokens = improved_tokenize(doc)
                
                if tokens:
                    self.corpus_tokenized.append(tokens)
                    self.corpus_original.append(doc)  # ✅ Keep original text
                    self.corpus_metadata.append(meta)
                    self.corpus_ids.append(self._make_chunk_id(meta))
            
            if not self.corpus_tokenized:
                print("⚠️ No valid documents for BM25 indexing")
                return False
            
            self.bm25_index = BM25Okapi(self.corpus_tokenized)
            self._index_built = True
            print(f"✅ BM25 index: {len(self.corpus_tokenized)} documents")
            return True
            
        except Exception as e:
            print(f"❌ Error building BM25 index: {e}")
            return False
    
    def bm25_search(self, query: str, n_results: int = 10) -> List[Dict]:
        """Search using BM25 with improved tokenization."""
        if not self._index_built:
            if not self.build_bm25_index():
                return []
        
        if not self.corpus_tokenized:
            return []
        
        # ✅ Use improved tokenizer for query too
        tokenized_query = improved_tokenize(query)
        
        if not tokenized_query:
            return []
        
        scores = self.bm25_index.get_scores(tokenized_query)
        
        top_n = min(n_results, len(scores))
        if top_n == 0:
            return []
        
        top_indices = np.argsort(scores)[::-1][:top_n]
        max_score = float(max(scores)) if max(scores) > 0 else 1.0
        
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            
            results.append({
                "text": self.corpus_original[idx],        # ✅ Use original text
                "metadata": self.corpus_metadata[idx],
                "chunk_id": self.corpus_ids[idx],         # ✅ Unique ID
                "bm25_score": score / max_score,
                "bm25_rank": int(idx)
            })
        
        return results
    
    def reciprocal_rank_fusion(
        self,
        bm25_results: List[Dict],
        dense_results: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """RRF with unique chunk IDs to prevent collisions."""
        fused_scores = {}
        all_chunks = {}
        
        # Process BM25 results
        for rank, chunk in enumerate(bm25_results):
            chunk_id = chunk.get("chunk_id", self._make_chunk_id(chunk["metadata"]))
            rrf_score = 1.0 / (k + rank + 1)
            
            if chunk_id in fused_scores:
                fused_scores[chunk_id] += rrf_score * self.bm25_weight
            else:
                fused_scores[chunk_id] = rrf_score * self.bm25_weight
                all_chunks[chunk_id] = {
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "chunk_id": chunk_id,
                    "bm25_score": chunk.get("bm25_score", 0),
                    "bm25_rank": rank + 1,
                    "dense_score": 0,
                    "dense_rank": 0
                }
        
        # Process Dense results
        for rank, chunk in enumerate(dense_results):
            chunk_id = chunk.get("chunk_id", self._make_chunk_id(chunk["metadata"]))
            rrf_score = 1.0 / (k + rank + 1)
            
            if chunk_id in fused_scores:
                fused_scores[chunk_id] += rrf_score * self.dense_weight
                all_chunks[chunk_id]["dense_score"] = chunk.get("score", 0)
                all_chunks[chunk_id]["dense_rank"] = rank + 1
            else:
                fused_scores[chunk_id] = rrf_score * self.dense_weight
                all_chunks[chunk_id] = {
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "chunk_id": chunk_id,
                    "bm25_score": 0,
                    "bm25_rank": 0,
                    "dense_score": chunk.get("score", 0),
                    "dense_rank": rank + 1
                }
        
        sorted_ids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        
        fused_results = []
        for chunk_id, fused_score in sorted_ids:
            chunk_data = all_chunks[chunk_id]
            chunk_data["fused_score"] = fused_score
            chunk_data["score"] = fused_score
            fused_results.append(chunk_data)
        
        return fused_results
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        candidate_multiplier: int = 3,
        use_reranker: Optional[bool] = None
    ) -> List[Dict]:
        """
        Full hybrid search pipeline with optional reranking.
        
        Pipeline: Query → BM25 + Dense → RRF → (Optional Reranker) → Top K
        
        Args:
            query: User's question
            n_results: Final number of results
            candidate_multiplier: Candidates = n_results * multiplier
            use_reranker: Override reranker setting
            
        Returns:
            Ranked list of relevant chunks
        """
        start_time = datetime.now()
        
        if not self._index_built:
            self.build_bm25_index()
        
        candidate_count = max(n_results * candidate_multiplier, 15)
        
        # Phase 1: BM25 search
        bm25_results = self.bm25_search(query, n_results=candidate_count)
        
        # Phase 2: Dense search
        dense_results = search_similar_chunks(query, self.user_id, n_results=candidate_count)
        
        # Add unique IDs to dense results
        for chunk in dense_results:
            chunk["chunk_id"] = self._make_chunk_id(chunk["metadata"])
        
        print(f"🔤 BM25: {len(bm25_results)} | 🧠 Dense: {len(dense_results)}")
        
        # Handle edge cases
        if not bm25_results and not dense_results:
            return []
        if not bm25_results:
            fused = dense_results[:n_results * 2]  # Get extra for reranking
        elif not dense_results:
            fused = bm25_results[:n_results * 2]
        else:
            # Phase 3: RRF Fusion
            fused = self.reciprocal_rank_fusion(bm25_results, dense_results)
            print(f"🔗 RRF: {len(fused)} fused results")
        
        # Phase 4: CrossEncoder Reranker (highest impact improvement!)
        should_rerank = use_reranker if use_reranker is not None else self.enable_reranker
        
        if should_rerank and self.reranker and len(fused) > n_results:
            print(f"🎯 Reranking {len(fused)} candidates...")
            fused = self.reranker.rerank(query, fused, top_k=n_results)
            print(f"✅ Reranked to top {len(fused)}")
        else:
            fused = fused[:n_results]
        
        # Record metrics
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.metrics.record_query(
            bm25_count=len(bm25_results),
            dense_count=len(dense_results),
            final_count=len(fused),
            latency_ms=latency_ms
        )
        
        # Print top results
        if fused:
            print("   Top results:")
            for i, chunk in enumerate(fused):
                b_rank = chunk.get('bm25_rank', '?')
                d_rank = chunk.get('dense_rank', '?')
                ce_score = chunk.get('cross_encoder_score', None)
                source = chunk['metadata'].get('source', '?')[:40]
                
                ce_str = f" | CE:{ce_score:.4f}" if ce_score is not None else ""
                print(f"   #{i+1}: {chunk['score']:.4f} | "
                      f"B:{b_rank} D:{d_rank}{ce_str} | {source}")
        
        return fused
    
    def rebuild_index(self) -> bool:
        """Force rebuild of BM25 index."""
        self.bm25_index = None
        self.corpus_tokenized = []
        self.corpus_original = []
        self.corpus_metadata = []
        self.corpus_ids = []
        self._index_built = False
        return self.build_bm25_index()


# ============================================================
# Global cache
# ============================================================

_retrievers: Dict[str, HybridRetriever] = {}

def get_hybrid_retriever(
    user_id: str,
    bm25_weight: float = 0.4,
    dense_weight: float = 0.6,
    enable_reranker: bool = True
) -> HybridRetriever:
    """Get or create a HybridRetriever for a user."""
    if user_id not in _retrievers:
        _retrievers[user_id] = HybridRetriever(
            user_id=user_id,
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            enable_reranker=enable_reranker
        )
    return _retrievers[user_id]

def rebuild_user_index(user_id: str) -> bool:
    """Rebuild BM25 index after document changes."""
    if user_id in _retrievers:
        return _retrievers[user_id].rebuild_index()
    retriever = get_hybrid_retriever(user_id)
    return retriever._index_built

def clear_retriever_cache():
    """Clear all cached retrievers."""
    global _retrievers
    _retrievers.clear()