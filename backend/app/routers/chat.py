from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.services.rag import get_rag_answer
from app.database import get_db
from app.models import Conversation, Message
import uuid

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    user_id: str = "default_user"

class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    user_id: str = "default_user"

@router.post("/conversations")
async def create_conversation(
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation"""
    conversation_id = str(uuid.uuid4())
    
    conversation = Conversation(
        id=conversation_id,
        user_id=request.user_id,
        title=request.title
    )
    db.add(conversation)
    await db.commit()
    
    return {
        "conversation_id": conversation_id,
        "title": request.title,
        "user_id": request.user_id,
        "message": "New conversation created"
    }

@router.get("/conversations")
async def list_conversations(
    user_id: str = "default_user",
    db: AsyncSession = Depends(get_db)
):
    """List all conversations for a user"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.created_at))
    )
    conversations = result.scalars().all()
    
    return {
        "conversations": [
            {
                "id": conv.id,
                "title": conv.title,
                "created_at": str(conv.created_at)
            }
            for conv in conversations
        ]
    }

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all messages for a conversation"""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    
    return {
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "source": msg.source,
                "created_at": str(msg.created_at)
            }
            for msg in messages
        ]
    }

@router.post("/")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    print(f"\n📨 Received question: {request.message}")
    print(f"📝 Conversation ID: {request.conversation_id}")
    
    # Create conversation if not exists
    if not request.conversation_id:
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            id=conversation_id,
            user_id=request.user_id,
            title=request.message[:50] + "..."
        )
        db.add(conversation)
        await db.commit()
    else:
        conversation_id = request.conversation_id
    
    # Save user message
    user_message = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    await db.commit()
    
    try:
        # Get conversation history
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        history_msgs = result.scalars().all()
        
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_msgs[:-1]  # Exclude the just-added user message
        ]
        
        # Get RAG answer - use conversation_id as user_id to isolate vector stores
        reply, source = await get_rag_answer(
            question=request.message,
            user_id=conversation_id,  # Use conversation_id instead of fixed user_id
            conversation_history=conversation_history
        )
        
        # Save assistant message
        assistant_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
            source=source
        )
        db.add(assistant_message)
        await db.commit()
        
        print(f"📤 Response source: {source}")
        
        return {
            "reply": reply,
            "source": source,
            "conversation_id": conversation_id,
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        await db.rollback()
        return {
            "reply": f"I apologize, but I encountered an error. Please try again.",
            "source": "general",
            "conversation_id": conversation_id,
            "status": "error"
        }