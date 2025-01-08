from typing import Sequence
from .schemas import PaginatedChats, PaginatedMessages, ChatBrief, Message
from db.models import Chat, Message as DBMessage

def convert_to_paginated_chats(
    chats: Sequence[Chat],
    total: int,
    limit: int,
    offset: int
) -> PaginatedChats:
    """Конвертирует список чатов из БД в пагинированный ответ API"""
    return PaginatedChats(
        items=[
            ChatBrief(
                id=chat.id,
                title=chat.title,
                updated_at=chat.updated_at
            ) for chat in chats
        ],
        total=total,
        limit=limit,
        offset=offset
    )

def convert_to_paginated_messages(
    messages: Sequence[DBMessage],
    total: int,
    limit: int,
    offset: int
) -> PaginatedMessages:
    """Конвертирует список сообщений из БД в пагинированный ответ API"""
    return PaginatedMessages(
        items=[
            Message(
                id=msg.id,
                chat_id=msg.chat_id,
                content=msg.content,
                created_at=msg.created_at,
                is_sent_by_bot=msg.is_sent_by_bot
            ) for msg in messages
        ],
        total=total,
        limit=limit,
        offset=offset
    )
