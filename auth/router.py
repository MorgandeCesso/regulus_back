from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta, datetime
from typing import Optional
from jose import JWTError, jwt

from core.openai import get_openai_client
from db.session import get_async_session
from db.models import User, VectorStore
from auth.schemas import UserCreate, UserResponse, Token, EmailVerification, EmailVerificationResponse, LogoutResponse
from auth.convert import user_to_response
from auth.tools import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    get_current_user,
    generate_verification_code,
    send_email,
    ACCESS_TOKEN_SECRET_KEY,
    REFRESH_TOKEN_SECRET_KEY,
    ALGORITHM
)
from gpt.gpt import GPT

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Не авторизован"}},
)
gpt = GPT()
client = get_openai_client()

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Регистрация нового пользователя.
    
    - **username**: уникальное имя пользователя
    - **password**: пароль пользователя
    - **email**: опциональный email для верификации
    
    Возвращает данные созданного пользователя.
    """
    try:
        hashed_password = get_password_hash(user_data.password)
        user = await User.create(
            session=session,
            username=user_data.username,
            hashed_password=hashed_password,
            email=user_data.email
        )
        vector_store_id = await gpt.create_vector_store(user.id, client)
        await VectorStore.create(session, user.id, vector_store_id)
        return user_to_response(user)
    except HTTPException as e:
        # Пробрасываем HTTPException дальше
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при регистрации пользователя: {str(e)}"
        )

@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Получение токенов доступа.
    
    - **username**: имя пользователя
    - **password**: пароль
    
    Возвращает access_token и refresh_token для авторизации.
    """
    try:
        user = await User.get_by_username(session, form_data.username)
        
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(data={"sub": user.username})
        refresh_token = create_refresh_token(data={"sub": user.username})
        
        # Сохраняем refresh token в БД, но не отправляем клиенту
        await user.update_refresh_token(session, refresh_token)
        
        return Token(
            access_token=access_token,
            token_type="bearer"
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при авторизации: {str(e)}"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    access_token: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Обновление токенов доступа.
    
    - **access_token**: текущий (возможно истекший) access token
    
    Возвращает новую пару access_token и refresh_token.
    """
    try:
        if not ACCESS_TOKEN_SECRET_KEY or not REFRESH_TOKEN_SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка конфигурации токенов"
            )

        # Получаем username из access token (даже если он истек)
        payload = jwt.decode(access_token, ACCESS_TOKEN_SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный access token"
            )
            
        # Находим пользователя и его refresh token
        user = await User.get_by_username(session, username)
        if not user or not user.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Сессия истекла, требуется повторная авторизация"
            )

        # Проверяем refresh token на валидность и срок действия
        try:
            jwt.decode(user.refresh_token, REFRESH_TOKEN_SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            # Если refresh token истек или невалиден
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Сессия истекла, требуется повторная авторизация"
            )
        
        # Создаем только новый access token
        new_access_token = create_access_token(data={"sub": user.username})
        
        # Возвращаем тот же refresh token
        return Token(
            access_token=new_access_token,
            token_type="bearer"
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный access token"
        )

@router.post("/verify-email", response_model=EmailVerificationResponse)
async def verify_email(
    verification_data: EmailVerification,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Подтверждение email адреса пользователя.
    
    - **email**: email адрес для подтверждения
    - **code**: код подтверждения, отправленный на email
    
    Возвращает статус верификации email.
    """
    try:
        user = await User.get_by_email(session, verification_data.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        # Здесь будет проверка кода верификации
        
        await user.verify_email_confirmation(session)
        
        return EmailVerificationResponse(
            email=user.email,
            email_verified=user.email_verified,
            message="Email успешно подтвержден"
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при верификации email: {str(e)}"
        )

@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Выход из системы.
    Очищает refresh token пользователя в БД.
    """
    try:
        await User.delete_refresh_token(session, current_user.username)
        return LogoutResponse(
            status="success",
            message="Успешный выход из системы"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при выходе из системы: {str(e)}"
        )
