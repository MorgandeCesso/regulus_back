from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime

from db.session import get_async_session
from db.models import Chat, Message, User
from auth.tools import get_current_user
from gpt.gpt import GPT
from core.openai import get_openai_client
from .tools import get_chat_title
from .schemas import (
    PaginatedChats, PaginatedMessages, StatusResponse, 
    SendMessageResponse, MessageCreate
)
from .convert import convert_to_paginated_chats, convert_to_paginated_messages

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={401: {"description": "Не авторизован"}},
)

gpt = GPT()
client = get_openai_client()

@router.post("/send_message", response_model=SendMessageResponse)
async def send_message(
    message: MessageCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> SendMessageResponse:
    # Флаг для отслеживания нового чата
    is_new_chat = False
    
    # Если chat_id не предоставлен, создаем новый чат
    if not message.chat_id:
        is_new_chat = True
        chat = await Chat.create(
            session=session,
            user_id=current_user.id,
            title="Новый чат"  # Временное название
        )
        message.chat_id = chat.id
        
        # Создаем новый тред для чата
        thread_id = await gpt.create_thread(client)
        await Chat.update_thread_id(session, message.chat_id, thread_id)
    else:
        chat = await Chat.get_by_id(session, message.chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Чат не найден"
            )
        if chat.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому чату"
            )

    # Сохраняем сообщение пользователя
    await Message.create(
        session=session,
        chat_id=message.chat_id,
        content=message.content,
        is_sent_by_bot=False
    )

    # Отправляем сообщение в OpenAI
    await gpt.create_message(chat.thread_id, message.content, client)
    run = await gpt.create_and_poll_run(chat.thread_id, client, current_user.username)
    response = await gpt.get_gpt_response(chat.thread_id, client)

    # Если это новый чат, получаем для него название
    if is_new_chat:
        title = await get_chat_title(message.content, response)
        await Chat.update_title(session, message.chat_id, title)

    # Сохраняем ответ ассистента
    await Message.create(
        session=session,
        chat_id=message.chat_id,
        content=response,
        is_sent_by_bot=True
    )

    return SendMessageResponse(
        chat_id=message.chat_id,
        response=response
    )

@router.get("/list", response_model=PaginatedChats)
async def get_chats(
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> PaginatedChats:
    chats, total = await Chat.get_chats_paginated(
        session,
        current_user.id,
        limit=limit,
        offset=offset
    )
    return convert_to_paginated_chats(chats, total, limit, offset)

@router.get("/{chat_id}/messages", response_model=PaginatedMessages)
async def get_chat_messages(
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> PaginatedMessages:
    chat = await Chat.get_by_id(session, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден"
        )
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому чату"
        )

    messages, total = await Message.get_chat_messages_paginated(
        session, chat_id, limit, offset
    )
    return convert_to_paginated_messages(messages, total, limit, offset)

@router.delete("/{chat_id}", response_model=StatusResponse)
async def delete_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> StatusResponse:
    chat = await Chat.get_by_id(session, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден"
        )
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому чату"
        )

    # Удаляем тред в OpenAI
    if chat.thread_id:
        await gpt.delete_thread(chat.thread_id, client)

    # Удаляем чат из БД (сообщения удалятся каскадно)
    await Chat.delete(session, chat_id)
    return StatusResponse(status="success")

@router.post("/{chat_id}/reset", response_model=StatusResponse)
async def reset_chat_context(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> StatusResponse:
    chat = await Chat.get_by_id(session, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден"
        )
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому чату"
        )

    # Удаляем старый тред и создаем новый
    if chat.thread_id:
        await gpt.delete_thread(chat.thread_id, client)
    
    new_thread_id = await gpt.create_thread(client)
    await Chat.update_thread_id(session, chat_id, new_thread_id)

    return StatusResponse(status="success")

