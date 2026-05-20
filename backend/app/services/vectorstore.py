import chromadb
from fastembed import TextEmbedding
from typing import List, Dict
from app.config import get_settings

settings = get_settings()

print("⏳ Loading embedding model...")
embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
print("✅ Embedding model ready!")

chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

def embed_texts(texts: List[str]) -> List[List[float]]:
    return [vec.tolist() for vec in embedding_model.embed(texts)]

def embed_query(text: str) -> List[float]:
    return list(embedding_model.embed([text]))[0].tolist()

def get_or_create_collection(user_id: str):
    name = f"user_{user_id.replace('-', '_')}"
    return chroma_client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )

def add_chunks_to_store(chunks: List[Dict], document_id: str, user_id: str):
    collection = get_or_create_collection(user_id)
    texts     = [c["text"] for c in chunks]
    metadatas = [{
        "page":        str(c["page"]),
        "chunk_index": str(c["chunk_index"]),
        "source":      c["source"],
        "document_id": document_id
    } for c in chunks]
    ids = [f"{document_id}_chunk_{c['chunk_index']}_page_{c['page']}"
           for c in chunks]

    batch_size = 50
    for i in range(0, len(texts), batch_size):
        vectors = embed_texts(texts[i:i+batch_size])
        collection.add(
            embeddings=vectors,
            documents=texts[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )
    return len(texts)

def search_similar_chunks(query: str, user_id: str, n_results: int = 5) -> List[Dict]:
    collection = get_or_create_collection(user_id)
    if collection.count() == 0:
        return []

    query_vector = embed_query(query)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    return [{
        "text":     doc,
        "metadata": results["metadatas"][0][i],
        "score":    1 - results["distances"][0][i]
    } for i, doc in enumerate(results["documents"][0])]

def delete_document_chunks(document_id: str, user_id: str):
    collection = get_or_create_collection(user_id)
    collection.delete(where={"document_id": document_id})