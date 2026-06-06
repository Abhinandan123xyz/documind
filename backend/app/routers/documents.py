from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.models import Document, User
from app.database import get_db
from app.services.file_parser import parse_file
from app.services.vectorstore import add_chunks_to_store
from app.services.hybrid_search import rebuild_user_index
from app.routers.auth import get_current_user
import os, shutil, uuid

router = APIRouter()
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    conversation_id: str = Form(default="default"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        allowed = {'.pdf','.docx','.pptx','.xlsx','.xls','.csv'}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed:
            raise HTTPException(400, f"Unsupported type: {ext}")
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        chunks = parse_file(file_path)
        if not chunks:
            raise HTTPException(400, "No text content found")
        doc = Document(id=file_id, user_id=current_user.id, filename=file.filename, file_path=file_path, chunk_count=str(len(chunks)), status="processing")
        db.add(doc)
        chunk_count = add_chunks_to_store(chunks=chunks, document_id=file_id, user_id=conversation_id)
        rebuild_user_index(conversation_id)
        doc.status = "ready"
        doc.chunk_count = str(chunk_count)
        await db.commit()
        return {"status": "success", "document_id": file_id, "filename": file.filename, "chunk_count": chunk_count, "message": f"Processed {file.filename}"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, str(e))

class URLRequest(BaseModel):
    url: str
    conversation_id: str = "default"

@router.post("/upload-url")
async def upload_url(
    request: URLRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.services.file_parser import parse_url
        chunks = parse_url(request.url)
        if not chunks:
            raise HTTPException(400, "No content found")
        file_id = str(uuid.uuid4())
        doc = Document(id=file_id, user_id=current_user.id, filename=request.url[:100], file_path=request.url, chunk_count=str(len(chunks)), status="processing")
        db.add(doc)
        chunk_count = add_chunks_to_store(chunks=chunks, document_id=file_id, user_id=request.conversation_id)
        rebuild_user_index(request.conversation_id)
        doc.status = "ready"
        doc.chunk_count = str(chunk_count)
        await db.commit()
        return {"status": "success", "document_id": file_id, "chunk_count": chunk_count, "message": "Scraped and indexed"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, str(e))

@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return {"documents": [], "message": "List endpoint ready"}