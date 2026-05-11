from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

def hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register")
async def register(data: RegisterRequest):
    return {"message": "Registration endpoint ready", "username": data.username}

@router.post("/login")
async def login(data: LoginRequest):
    return {"message": "Login endpoint ready"}