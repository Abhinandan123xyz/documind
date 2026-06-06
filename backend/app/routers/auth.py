import re
import uuid
import secrets
import bcrypt  # ← use bcrypt directly

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from app.database import get_db
from app.models import User
from app.config import get_settings

router   = APIRouter()
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    # bcrypt expects bytes, encode and generate salt
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.JWT_SECRET, algorithm="HS256")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


class RegisterRequest(BaseModel):
    email:    str
    username: str
    password: str


@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Validation
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', data.email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not data.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    # Check existing
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Create user (unverified)
    verification_token = secrets.token_urlsafe(32)
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
        is_active=True,
        is_verified=False,
        verification_token=verification_token
    )
    db.add(user)
    await db.commit()

    # Fake email send (print to console)
    verify_url = f"http://localhost:8000/api/auth/verify-email?token={verification_token}"
    print(f"\n📧 Verification email for {data.email}:\n{verify_url}\n")

    return {
        "message": "Registration successful. Check your email (or console) to verify your account.",
        "user_id": user.id,
        "username": user.username,
        "email": user.email
    }


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user.is_verified = True
    user.verification_token = None
    await db.commit()
    return {"message": "Email verified successfully! You can now log in."}


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(
            (User.email == form_data.username) | (User.username == form_data.username)
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in")

    token = create_token(user.id)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      user.id,
        "username":     user.username,
        "email":        user.email
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id":  current_user.id,
        "username": current_user.username,
        "email":    current_user.email
    }
