from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime

# Базовые схемы для пользователя
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    email_verified: bool
    model_config = ConfigDict(from_attributes=True)

# Схемы для токенов
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Схемы для верификации email
class EmailVerification(BaseModel):
    email: EmailStr
    code: str

class EmailVerificationResponse(BaseModel):
    """Ответ на верификацию email"""
    email: EmailStr
    email_verified: bool
    message: str
