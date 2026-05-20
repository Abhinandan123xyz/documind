from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Tuple
from datetime import datetime

from app.config import get_settings
from app.services.vectorstore import search_similar_chunks
from app.services.web_search import search_web, search_wikipedia

settings = get_settings()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3
)

HYBRID_PROMPT = PromptTemplate(
    input_variables=["context", "question", "current_date", "history"],
    template="""You are DocuMind AI — a professional research assistant.
Current date: {current_date}

CONVERSATION HISTORY:
{history}

RELEVANT DOCUMENT CONTEXT (from uploaded files):
{context}

USER QUESTION: {question}

INSTRUCTIONS:
- Use the document context as your PRIMARY source
- If the question is about current events or topics NOT in the documents, clearly state that and answer from your general knowledge
- Always cite page numbers when using document content like [Page X - filename]
- Be comprehensive, structured, and use bullet points for lists
- IMPORTANT: If the question is about current affairs (politics, news, recent events), acknowledge that document context may not be relevant and provide the best answer you can

YOUR ANSWER:"""
)

WEB_PROMPT = PromptTemplate(
    input_variables=["web_results", "question", "current_date", "history"],
    template="""You are DocuMind AI — a professional research assistant.
Current date: {current_date}

CONVERSATION HISTORY:
{history}

LIVE WEB SEARCH RESULTS (up-to-date information):
{web_results}

USER QUESTION: {question}

INSTRUCTIONS:
- Use the web search results as your PRIMARY source for current information
- Provide accurate, up-to-date answers based on the web results
- Be clear and structured
- Use bullet points for lists
- Cite sources mentioned in the web results

YOUR ANSWER:"""
)

GENERAL_PROMPT = PromptTemplate(
    input_variables=["question", "current_date", "history"],
    template="""You are DocuMind AI — a knowledgeable research assistant.
Current date: {current_date}

CONVERSATION HISTORY:
{history}

USER QUESTION: {question}

INSTRUCTIONS:
- Answer thoroughly from your knowledge
- Be accurate, clear, use bullet points
- If the question is about current events, acknowledge that your knowledge may be limited
- Suggest checking official sources for the most up-to-date information

YOUR ANSWER:"""
)

CONFIDENCE_THRESHOLD = 0.25  # Moderate threshold - if chunks are below this, they're likely unrelated
HIGH_CONFIDENCE_THRESHOLD = 0.45  # High confidence - definitely related

# Keywords that indicate current events/questions needing web search
CURRENT_EVENT_KEYWORDS = [
    "current", "latest", "today", "now", "recent", "present",
    "pm of", "prime minister", "president of", "election", "2024", "2025", "2026",
    "who is", "what is the current", "right now", "this year",
    "stock price", "news", "happening", "update", "new"
]

def is_current_event_question(question: str) -> bool:
    """Detect if a question is about current events"""
    question_lower = question.lower()
    for keyword in CURRENT_EVENT_KEYWORDS:
        if keyword in question_lower:
            return True
    return False

def format_context(chunks: List[Dict]) -> str:
    parts = []
    for chunk in chunks:
        page   = chunk["metadata"].get("page", "?")
        source = chunk["metadata"].get("source", "document")
        score  = chunk.get("score", 0)
        parts.append(f"[Page {page} - {source} | relevance: {score:.0%}]\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)

def format_history(history: List[Dict]) -> str:
    if not history:
        return "No previous conversation."
    lines = []
    for msg in history[-6:]:  # last 3 exchanges
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content'][:200]}...")
    return "\n".join(lines)

async def get_rag_answer(
    question: str,
    user_id: str,
    conversation_history: List[Dict] = None
) -> Tuple[str, str]:

    if conversation_history is None:
        conversation_history = []

    current_date = datetime.now().strftime("%B %d, %Y")
    history_text = format_history(conversation_history)

    # Step 1: search vector store
    try:
        chunks = search_similar_chunks(question, user_id, n_results=5)
    except Exception as e:
        print(f"Vector search error: {e}")
        chunks = []

    best_score = max((c["score"] for c in chunks), default=0)
    print(f"📊 Best chunk score: {best_score:.3f}")
    
    # Check if this is a current events question
    is_current = is_current_event_question(question)
    if is_current:
        print(f"🕒 Detected current event question: '{question[:100]}'")

    # Step 2: DECISION LOGIC
    should_use_web = False
    should_use_docs = False
    
    # HIGH confidence match - definitely use documents
    if chunks and best_score >= HIGH_CONFIDENCE_THRESHOLD:
        print("📄 HIGH confidence - using document context")
        should_use_docs = True
    
    # MODERATE confidence AND NOT a current event question
    elif chunks and best_score >= CONFIDENCE_THRESHOLD and not is_current:
        print("📄 MODERATE confidence - using document context")
        should_use_docs = True
    
    # LOW confidence OR current event question
    else:
        if is_current:
            print("🌐 Current event question - using web search")
        else:
            print("🌐 LOW confidence - using web search")
        should_use_web = True
    
    # Step 3: Generate answer
    if should_use_docs:
        context = format_context(chunks)
        prompt = HYBRID_PROMPT.format(
            context=context,
            question=question,
            current_date=current_date,
            history=history_text
        )
        source = "document"
        
    elif should_use_web:
        # Try web search
        print("🔍 Searching web for current information...")
        web_results = await search_web(question)

        if not web_results:
            print("🔄 Web search failed, trying Wikipedia...")
            web_results = await search_wikipedia(question)

        if web_results:
            print("✅ Using web search results")
            prompt = WEB_PROMPT.format(
                web_results=web_results,
                question=question,
                current_date=current_date,
                history=history_text
            )
            source = "web"
        else:
            print("⚠️ No web results, using general knowledge")
            prompt = GENERAL_PROMPT.format(
                question=question,
                current_date=current_date,
                history=history_text
            )
            source = "general"
    
    else:
        # Fallback
        print("⚠️ Fallback to general knowledge")
        prompt = GENERAL_PROMPT.format(
            question=question,
            current_date=current_date,
            history=history_text
        )
        source = "general"

    # Step 4: Call LLM
    try:
        print(f"🤖 Calling Groq with source: {source}")
        response = await llm.ainvoke(prompt)
        print(f"✅ Answer generated ({len(response.content)} chars)")
        return response.content, source
    except Exception as e:
        print(f"❌ LLM error: {e}")
        return "I encountered an error. Please try again.", "general"