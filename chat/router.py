from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime
import tempfile
import os
import logging

from db.session import get_async_session
from db.models import Chat, Message, User, VectorStore, File as DBFile
from auth.tools import get_current_user
from gpt.gpt import GPT
from core.openai import get_openai_client
from .tools import get_chat_title
from .schemas import (
    PaginatedChats, PaginatedMessages, StatusResponse, 
    SendMessageResponse, MessageCreate, ChatResponse, UploadFileResponse, Filenames
)
from .convert import convert_to_paginated_chats, convert_to_paginated_messages, convert_to_filenames

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={401: {"description": "Не авторизован"}},
)

gpt = GPT()
client = get_openai_client()

@router.post("/create_chat", response_model=ChatResponse)
async def create_chat(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> ChatResponse:
    thread_id = await gpt.create_thread(client)
    chat = await Chat.create(session, current_user.id, title="Новый чат", thread_id=thread_id)
    return ChatResponse(chat_id=chat.id, response="Чат создан")

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
        # Сначала создаем thread в OpenAI
        thread_id = await gpt.create_thread(client)
        
        # Затем создаем чат с thread_id
        chat = await Chat.create(
            session=session,
            user_id=current_user.id,
            title="Новый чат",  # Временное название
            thread_id=thread_id  # Добавляем thread_id при создании
        )
        message.chat_id = chat.id
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
    response = await gpt.get_gpt_response(chat.thread_id, run.id, client)

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
    vector_store = await VectorStore.get_by_user_id(session, current_user.id)
    if vector_store:
        files = await DBFile.get_by_vector_store_id(session, vector_store.vector_store_id)
        for file in files:
            await gpt.unattach_file_from_vector_store(file.file_id, vector_store.vector_store_id, client)
            await gpt.delete_file(file.file_id, client)
            file_id = await DBFile.delete(session, file.file_id)
            logging.info(f"File deleted from database: {file_id}")
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

@router.post("/{chat_id}/upload_file", response_model=UploadFileResponse)
async def upload_file(
    chat_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> UploadFileResponse:
    try:
        if not file.filename or not file.filename.lower().endswith(('.pdf', '.docx', '.txt')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Поддерживаются только TXT, PDF и DOCX файлы"
            )
        vector_store = await VectorStore.get_by_user_id(session, current_user.id)
        content = await file.read()
        if not vector_store:
            vector_store_id = await gpt.create_vector_store(current_user.id, client)
            vector_store = await VectorStore.create(session, current_user.id, vector_store_id)
        file_id = await gpt.upload_file_to_vector_store(
            content,
            vector_store.vector_store_id,
            file.filename,
            client
        )
        
        # Сохраняем информацию о файле в БД
        result = await DBFile.create(session, file_id=file_id, chat_id=chat_id, vector_store_id=vector_store.vector_store_id, filename=file.filename)
        logging.info(f"File created: {result}")
        return UploadFileResponse(status="success", file_id=result.file_id)
                
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке файла: {str(e)}"
        )

@router.get("/{chat_id}/files", response_model=Filenames)
async def get_chat_files(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Filenames:
    files = await DBFile.get_chat_files(session, chat_id)
    return convert_to_filenames(files)