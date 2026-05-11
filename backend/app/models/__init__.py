from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import uuid

Base = declarative_base()

def gen_id():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id           = Column(String, primary_key=True, default=gen_id)
    email        = Column(String, unique=True, nullable=False)
    username     = Column(String, unique=True, nullable=False)
    password_hash= Column(String, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)
    is_active    = Column(Boolean, default=True)
    
    documents    = relationship("Document", back_populates="owner")
    conversations= relationship("Conversation", back_populates="owner")

class Document(Base):
    __tablename__ = "documents"
    id          = Column(String, primary_key=True, default=gen_id)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False)
    filename    = Column(String, nullable=False)
    file_path   = Column(String, nullable=False)
    chunk_count = Column(String, default="0")
    status      = Column(String, default="processing")  # processing | ready | error
    created_at  = Column(DateTime, default=datetime.utcnow)
    
    owner       = relationship("User", back_populates="documents")

class Conversation(Base):
    __tablename__ = "conversations"
    id          = Column(String, primary_key=True, default=gen_id)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False)
    title       = Column(String, default="New conversation")
    created_at  = Column(DateTime, default=datetime.utcnow)
    
    owner       = relationship("User", back_populates="conversations")
    messages    = relationship("Message", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"
    id              = Column(String, primary_key=True, default=gen_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role            = Column(String, nullable=False)   # "user" | "assistant"
    content         = Column(Text, nullable=False)
    source          = Column(String, default="general") # "pdf" | "web" | "general"
    created_at      = Column(DateTime, default=datetime.utcnow)
    
    conversation    = relationship("Conversation", back_populates="messages")