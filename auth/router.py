from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Optional

from db.session import get_async_session
from db.models import User
from auth.schemas import UserCreate, UserResponse, Token, EmailVerification, EmailVerificationResponse
from auth.convert import user_to_response
from auth.tools import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    generate_verification_code,
    send_email
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"description": "Не авторизован"}},
)

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
        
        await user.update_refresh_token(session, refresh_token)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
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
    refresh_token: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Обновление токенов доступа.
    
    - **refresh_token**: текущий refresh token
    
    Возвращает новую пару access_token и refresh_token.
    """
    try:
        user = await User.get_by_refresh_token(session, refresh_token)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh token"
            )
        
        new_access_token = create_access_token(data={"sub": user.username})
        new_refresh_token = create_refresh_token(data={"sub": user.username})
        
        await user.update_refresh_token(session, new_refresh_token)
        
        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении токена: {str(e)}"
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
