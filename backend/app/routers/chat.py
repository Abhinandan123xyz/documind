from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None

@router.post("/")
async def chat(request: ChatRequest):
    return {
        "reply": f"Echo: {request.message}",
        "source": "general",
        "status": "Phase 1 stub — RAG coming in Phase 2"
    }