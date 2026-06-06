from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from app.services.rag import get_rag_answer, get_rag_answer_stream
from app.database import get_db
from app.models import Conversation, Message, User
from app.routers.auth import get_current_user   # JWT dependency
import uuid
import json

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    stream: bool = True

class ConversationCreate(BaseModel):
    title: str = "New Conversation"

class RenameRequest(BaseModel):
    title: str

# ─────────────── Conversations ───────────────
@router.post("/conversations")
async def create_conversation(
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conversation_id = str(uuid.uuid4())
    conversation = Conversation(
        id=conversation_id,
        user_id=current_user.id,
        title=request.title
    )
    db.add(conversation)
    await db.commit()
    return {"conversation_id": conversation_id, "title": request.title, "message": "New conversation created"}

@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(desc(Conversation.created_at))
    )
    conversations = result.scalars().all()
    return {"conversations": [{"id": c.id, "title": c.title, "created_at": str(c.created_at)} for c in conversations]}

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "Conversation not found")
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return {"messages": [{"id": m.id, "role": m.role, "content": m.content, "source": m.source, "citations": json.loads(m.citations) if m.citations else [], "created_at": str(m.created_at)} for m in messages]}

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "Conversation not found")
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.delete(conv)
    await db.commit()
    return {"message": "Conversation deleted"}

@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    request: RenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "Conversation not found")
    conv.title = request.title
    await db.commit()
    return {"message": "Conversation renamed"}

# ─────────────── Chat (streaming) ───────────────
@router.post("/")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not request.conversation_id:
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(id=conversation_id, user_id=current_user.id, title=request.message[:50] + ("..." if len(request.message) > 50 else ""))
        db.add(conversation)
        await db.commit()
    else:
        conversation_id = request.conversation_id
        conv = await db.get(Conversation, conversation_id)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(404, "Conversation not found")

    user_message = Message(id=str(uuid.uuid4()), conversation_id=conversation_id, role="user", content=request.message)
    db.add(user_message)
    await db.commit()

    result = await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at))
    history_msgs = result.scalars().all()
    conversation_history = [{"role": m.role, "content": m.content} for m in history_msgs[:-1]]

    if request.stream:
        return StreamingResponse(
            stream_response(question=request.message, user_id=conversation_id, conversation_history=conversation_history, conversation_id=conversation_id, db=db),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
        )
    else:
        reply, source, citations = await get_rag_answer(question=request.message, user_id=conversation_id, conversation_history=conversation_history)
        assistant_message = Message(id=str(uuid.uuid4()), conversation_id=conversation_id, role="assistant", content=reply, source=source, citations=json.dumps(citations) if citations else None)
        db.add(assistant_message)
        await db.commit()
        return {"reply": reply, "source": source, "citations": citations, "conversation_id": conversation_id, "status": "success"}

async def stream_response(question: str, user_id: str, conversation_history: list, conversation_id: str, db: AsyncSession):
    full_response = ""
    source = "general"
    citations = []
    sources_sent = False
    try:
        async for chunk_data in get_rag_answer_stream(question=question, user_id=user_id, conversation_history=conversation_history):
            if isinstance(chunk_data, dict):
                source = chunk_data.get("source", source)
                citations = chunk_data.get("citations", citations)
                if not sources_sent:
                    yield f"data: {json.dumps({'type': 'metadata', 'source': source, 'citations': citations})}\n\n"
                    sources_sent = True
            else:
                full_response += str(chunk_data)
                yield f"data: {json.dumps({'type': 'token', 'content': str(chunk_data)})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"
        assistant_message = Message(id=str(uuid.uuid4()), conversation_id=conversation_id, role="assistant", content=full_response, source=source, citations=json.dumps(citations) if citations else None)
        db.add(assistant_message)
        await db.commit()
    except Exception as e:
        print(f"❌ Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"