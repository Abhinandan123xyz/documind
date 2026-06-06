from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select

from app.config import get_settings
from app.models import Base, User
from app.database import engine, AsyncSessionLocal
from app.routers import chat, documents, auth

settings = get_settings()


async def create_default_user():
    """Ensure a default user exists (dev only – remove after first real user)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "default@documind.ai")
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id="default_user",
                email="default@documind.ai",
                username="default_user",
                password_hash="not-used-yet",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            print("✅ Default user created (id='default_user')")
        else:
            print("ℹ️  Default user already exists")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database ready")

    # Seed default user (safe to remove in production after real auth is live)
    await create_default_user()

    yield

    await engine.dispose()


app = FastAPI(
    title="DocuMind AI",
    description="AI assistant with RAG and web search",
    version="2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://documind-puce-eta.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["chat"])


@app.get("/")
async def root():
    return {"status": "running", "app": settings.APP_NAME}


@app.get("/health")
async def health():
    return {"status": "healthy"}
