from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Tuple, AsyncGenerator, Union
from datetime import datetime
from app.config import get_settings
from app.services.hybrid_search import get_hybrid_retriever
from app.services.web_search import search_web, search_wikipedia

settings = get_settings()
llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.GROQ_API_KEY, temperature=0.3, streaming=True)

# Prompt for the pre‑check (YES / NO)
CHECK_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are a helpful assistant. Given the following document context, can you answer the user's question accurately? Answer only YES or NO.

CONTEXT:
{context}

QUESTION:
{question}

CAN YOU ANSWER? (YES/NO):"""
)

# Full prompt when the document CAN answer
CITATION_PROMPT = PromptTemplate(
    input_variables=["context", "citations", "question", "current_date"],
    template="""You are DocuMind AI — a document analysis expert.
Current date: {current_date}

DOCUMENT CONTEXT (from user's uploaded files):
{context}

SOURCES AVAILABLE FOR CITATION:
{citations}

USER QUESTION: {question}

INSTRUCTIONS:
1. Answer using the document context above.
2. After factual statements, add citations like [1], [2].
3. Be comprehensive and well‑structured.

YOUR ANSWER:"""
)

WEB_PROMPT = PromptTemplate(
    input_variables=["web_results", "question", "current_date"],
    template="""You are DocuMind AI. Current date: {current_date}
WEB RESULTS: {web_results}
USER QUESTION: {question}
Answer accurately using the web results."""
)

GENERAL_PROMPT = PromptTemplate(
    input_variables=["question", "current_date"],
    template="""You are DocuMind AI. Current date: {current_date}
QUESTION: {question}
Answer thoroughly from your knowledge."""
)

def format_context_with_citations(chunks: List[Dict]) -> Tuple[str, str]:
    context_parts = []
    citation_parts = []
    for i, chunk in enumerate(chunks, 1):
        page = chunk["metadata"].get("page", "?")
        source = chunk["metadata"].get("source", "document")
        text = chunk["text"][:500]
        context_parts.append(f"[Source {i} | Page {page} | {source}]\n{text}")
        citation_parts.append(f"[{i}] {source}, Page {page}")
    return "\n\n---\n\n".join(context_parts), "\n".join(citation_parts)


# ---------- Pre‑check: can the document answer the question? ----------
async def document_can_answer(question: str, context: str) -> bool:
    """Quickly ask the LLM if the context contains the answer (YES/NO)."""
    prompt = CHECK_PROMPT.format(context=context[:3000], question=question)
    try:
        response = await llm.ainvoke(prompt)
        answer = response.content.strip().upper()
        return "YES" in answer
    except Exception as e:
        print(f"❌ Pre‑check error: {e}")
        return False  # if in doubt, fallback to web


# ---------- Non‑streaming RAG answer ----------
async def get_rag_answer(
    question: str,
    user_id: str,
    conversation_history: List[Dict] = None
) -> Tuple[str, str, List[Dict]]:
    if conversation_history is None:
        conversation_history = []
    current_date = datetime.now().strftime("%B %d, %Y")

    retriever = get_hybrid_retriever(user_id)
    chunks = retriever.search(question, n_results=5)

    # If we have chunks, check if they contain the answer
    if chunks:
        context, citation_text = format_context_with_citations(chunks)
        if await document_can_answer(question, context):
            citations = [{
                "number": i,
                "source": c["metadata"].get("source", "?"),
                "page": c["metadata"].get("page", "?"),
                "text": c["text"][:200] + "..."
            } for i, c in enumerate(chunks, 1)]

            prompt = CITATION_PROMPT.format(
                context=context,
                citations=citation_text,
                question=question,
                current_date=current_date
            )
            response = await llm.ainvoke(prompt)
            return response.content, "document", citations

    # Fallback to web / general
    web_results = await search_web(question) or await search_wikipedia(question)
    if web_results:
        prompt = WEB_PROMPT.format(web_results=web_results, question=question, current_date=current_date)
        source = "web"
    else:
        prompt = GENERAL_PROMPT.format(question=question, current_date=current_date)
        source = "general"

    response = await llm.ainvoke(prompt)
    return response.content, source, []


# ---------- Streaming RAG answer ----------
async def get_rag_answer_stream(
    question: str,
    user_id: str,
    conversation_history: List[Dict] = None
) -> AsyncGenerator[Union[Dict, str], None]:
    if conversation_history is None:
        conversation_history = []
    current_date = datetime.now().strftime("%B %d, %Y")

    retriever = get_hybrid_retriever(user_id)
    chunks = retriever.search(question, n_results=5)

    citations = []
    source = "general"
    prompt = None

    # ---------- 1. Try documents ----------
    if chunks:
        context, citation_text = format_context_with_citations(chunks)
        # Pre‑check: can the document answer?
        if await document_can_answer(question, context):
            print("📄 Document can answer – streaming from PDF")
            citations = [{
                "number": i,
                "source": c["metadata"].get("source", "?"),
                "page": c["metadata"].get("page", "?"),
                "text": c["text"][:200] + "..."
            } for i, c in enumerate(chunks, 1)]

            prompt = CITATION_PROMPT.format(
                context=context,
                citations=citation_text,
                question=question,
                current_date=current_date
            )
            source = "document"
        else:
            print("📄 Document cannot answer – falling back to web")

    # ---------- 2. Fallback to web ----------
    if prompt is None:
        print("🌐 Searching web...")
        web_results = await search_web(question) or await search_wikipedia(question)
        if web_results:
            prompt = WEB_PROMPT.format(web_results=web_results, question=question, current_date=current_date)
            source = "web"
        else:
            prompt = GENERAL_PROMPT.format(question=question, current_date=current_date)
            source = "general"

    # Send metadata to frontend
    yield {"source": source, "citations": citations}

    # Stream the final answer
    full_response = ""
    try:
        async for chunk in llm.astream(prompt):
            if hasattr(chunk, 'content'):
                full_response += chunk.content
                yield chunk.content
    except Exception as e:
        print(f"❌ Streaming error: {e}")
        yield f"[Error: {str(e)}]"