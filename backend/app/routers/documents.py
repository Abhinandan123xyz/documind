from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.models import Document
from app.database import get_db
from app.services.file_parser import parse_file
from app.services.vectorstore import add_chunks_to_store
import os
import shutil
import uuid

router = APIRouter()

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    conversation_id: str = Form(default="default"),
    user_id: str = Form(default="default_user"),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Validate file extension
        allowed_extensions = {'.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}"
            )
        
        # Save file
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse file into chunks
        chunks = parse_file(file_path)
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No text content found in file")
        
        # Store document record in database
        doc = Document(
            id=file_id,
            user_id=user_id,
            filename=file.filename,
            file_path=file_path,
            chunk_count=str(len(chunks)),
            status="processing"
        )
        db.add(doc)
        
        # Add chunks to vector store - ISOLATE by conversation_id
        chunk_count = add_chunks_to_store(
            chunks=chunks,
            document_id=file_id,
            user_id=conversation_id  # Use conversation_id to isolate documents
        )
        
        doc.status = "ready"
        doc.chunk_count = str(chunk_count)
        await db.commit()
        
        return {
            "status": "success",
            "document_id": file_id,
            "filename": file.filename,
            "chunk_count": chunk_count,
            "message": f"Successfully processed {file.filename}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

class URLRequest(BaseModel):
    url: str
    conversation_id: str = "default"
    user_id: str = "default_user"

@router.post("/upload-url")
async def upload_url(
    request: URLRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        from app.services.file_parser import parse_url
        
        chunks = parse_url(request.url)
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No content found at URL")
        
        file_id = str(uuid.uuid4())
        doc = Document(
            id=file_id,
            user_id=request.user_id,
            filename=request.url[:100],
            file_path=request.url,
            chunk_count=str(len(chunks)),
            status="processing"
        )
        db.add(doc)
        
        chunk_count = add_chunks_to_store(
            chunks=chunks,
            document_id=file_id,
            user_id=request.conversation_id  # Isolate by conversation
        )
        
        doc.status = "ready"
        doc.chunk_count = str(chunk_count)
        await db.commit()
        
        return {
            "status": "success",
            "document_id": file_id,
            "chunk_count": chunk_count,
            "message": "Successfully scraped and indexed URL"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))