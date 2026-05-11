from fastapi import APIRouter, UploadFile, File

router = APIRouter()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    return {
        "filename": file.filename,
        "status": "received",
        "message": "Full RAG processing coming in Phase 2"
    }

@router.get("/")
async def list_documents():
    return {"documents": []}