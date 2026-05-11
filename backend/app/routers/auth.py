from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register")
async def register(data: RegisterRequest):
    # Full implementation in Phase 4
    return {"message": "Registration endpoint ready", "username": data.username}

@router.post("/login")
async def login(data: LoginRequest):
    # Full implementation in Phase 4
    return {"message": "Login endpoint ready"}