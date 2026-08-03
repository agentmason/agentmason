from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str = "user"


users: dict[str, dict[str, Any]] = {}


def _create_token(email: str) -> str:
    return f"token-{email}-{datetime.now(timezone.utc).timestamp():.0f}"


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> UserResponse:
    if payload.email in users:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = {
        "id": f"user-{len(users) + 1}",
        "email": str(payload.email),
        "name": payload.name,
        "role": "user",
        "password": payload.password,
    }
    users[str(payload.email)] = user
    return UserResponse(**{k: v for k, v in user.items() if k != "password"})


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = users.get(str(payload.email))
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(access_token=_create_token(str(payload.email)))
