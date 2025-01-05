import secrets
import smtplib
from email.mime.text import MIMEText
from configs import SENDER_EMAIL, SENDER_PASSWORD, ACCESS_TOKEN_SECRET_KEY, REFRESH_TOKEN_SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_async_session
from db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def generate_verification_code():
    return secrets.token_hex(4)  # 8-значный код

def send_email(email: str, code: str):
    sender = SENDER_EMAIL
    password = SENDER_PASSWORD
    
    message = MIMEText(f"Ваш код подтверждения: {code}")
    message['Subject'] = "Подтверждение регистрации"
    message['From'] = sender
    message['To'] = email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(message)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, str(ACCESS_TOKEN_SECRET_KEY), algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, str(REFRESH_TOKEN_SECRET_KEY), algorithm=ALGORITHM)
    return encoded_jwt

def verify_refresh_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, str(REFRESH_TOKEN_SECRET_KEY), algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        return username if username else None
    except JWTError:
        return None

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, str(ACCESS_TOKEN_SECRET_KEY), algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not isinstance(username, str):
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await User.get_by_username(session, username)
    if user is None:
        raise credentials_exception
    return user