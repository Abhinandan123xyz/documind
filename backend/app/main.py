from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from app.config import get_settings
from app.models import Base
from app.routers import chat, documents, auth

settings = get_settings()

# Create DB engine
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# DB dependency — used in every route
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database ready")
    yield
    # On shutdown: cleanup
    await engine.dispose()

app = FastAPI(
    title="DocuMind AI",
    description="AI assistant with RAG and web search",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allows your React frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router,      prefix="/api/auth",      tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["chat"])

@app.get("/")
async def root():
    return {"status": "running", "app": settings.APP_NAME}

@app.get("/health")
async def health():
    return {"status": "healthy"}