from pydantic import BaseModel
from datetime import datetime
from typing import List, Generic, TypeVar

# Базовые модели для пагинации
T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int

# Схемы для сообщений
class MessageBase(BaseModel):
    content: str
    created_at: datetime
    is_sent_by_bot: bool

class Message(MessageBase):
    id: int
    chat_id: int

    class Config:
        from_attributes = True

# Схемы для чатов
class ChatBase(BaseModel):
    title: str
    created_at: datetime
    updated_at: datetime

class Chat(ChatBase):
    id: int
    user_id: int
    thread_id: str | None
    messages: List[Message] = []

    class Config:
        from_attributes = True

class ChatBrief(BaseModel):
    """Краткая информация о чате для списка чатов"""
    id: int
    title: str
    updated_at: datetime

    class Config:
        from_attributes = True

# Ответы API с пагинацией
class PaginatedChats(PaginatedResponse[ChatBrief]):
    pass

class PaginatedMessages(PaginatedResponse[Message]):
    pass

# Схемы для запросов
class MessageCreate(BaseModel):
    content: str
    chat_id: int | None = None

class ChatResponse(BaseModel):
    chat_id: int
    response: str

class StatusResponse(BaseModel):
    """Базовый ответ об успешном выполнении операции"""
    status: str

class SendMessageResponse(BaseModel):
    """Ответ на отправку сообщения"""
    chat_id: int
    response: str
