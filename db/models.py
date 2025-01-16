from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Sequence
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy import TIMESTAMP, MetaData, Integer, String, Boolean, ForeignKey, select, and_, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

class Base(DeclarativeBase):
    metadata = MetaData()

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)
    chats: Mapped[List["Chat"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    vector_store: Mapped[Optional["VectorStore"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    @classmethod
    async def delete_refresh_token(cls, session: AsyncSession, username: str) -> Optional["User"]:
        query = update(cls).where(cls.username == username).values(refresh_token=None)
        await session.execute(query)
        await session.flush()
        
        # Получаем и возвращаем обновленного пользователя
        return await cls.get_by_username(session, username)

    @classmethod
    async def get_by_username(cls, session: AsyncSession, username: str) -> Optional["User"]:
        query = select(cls).where(cls.username == username)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_email(cls, session: AsyncSession, email: str) -> Optional["User"]:
        query = select(cls).where(cls.email == email)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_refresh_token(cls, session: AsyncSession, refresh_token: str) -> Optional["User"]:
        query = select(cls).where(cls.refresh_token == refresh_token)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def create(
        cls, 
        session: AsyncSession, 
        username: str, 
        hashed_password: str, 
        email: Optional[str] = None
    ) -> "User":
        # Проверяем существование пользователя
        existing_user = await cls.get_by_username(session, username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким именем уже существует"
            )
        
        # Проверяем email если он указан
        if email:
            existing_email = await cls.get_by_email(session, email)
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email уже используется"
                )

        # Создаем нового пользователя
        new_user = cls(
            username=username,
            email=email,
            hashed_password=hashed_password
        )
        session.add(new_user)
        await session.flush()
        return new_user

    async def update_refresh_token(self, session: AsyncSession, refresh_token: str) -> None:
        self.refresh_token = refresh_token
        await session.flush()

    async def verify_email_confirmation(self, session: AsyncSession) -> None:
        self.email_verified = True
        await session.flush()

class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(500), nullable=True)
    user: Mapped[User] = relationship(
        back_populates="chats",
        cascade="all"
    )
    messages: Mapped[List["Message"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan"
    )
    files: Mapped[List["File"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan"
    )

    @classmethod
    async def create(cls, session: AsyncSession, user_id: int, title: str, thread_id: str | None = None) -> "Chat":
        now = datetime.utcnow()
        chat = cls(
            user_id=user_id,
            title=title,
            thread_id=thread_id,
            created_at=now,
            updated_at=now
        )
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        return chat

    @classmethod
    async def get_by_id(cls, session: AsyncSession, chat_id: int) -> Optional["Chat"]:
        query = select(cls).where(cls.id == chat_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def delete(cls, session: AsyncSession, chat_id: int) -> None:
        query = delete(cls).where(cls.id == chat_id)
        await session.execute(query)
        await session.flush()

    @classmethod
    async def update_title(cls, session: AsyncSession, chat_id: int, new_title: str) -> None:
        query = update(cls).where(cls.id == chat_id).values(title=new_title)
        await session.execute(query)
        await session.flush()

    @classmethod
    async def update_thread_id(cls, session: AsyncSession, chat_id: int, thread_id: str) -> None:
        query = update(cls).where(cls.id == chat_id).values(thread_id=thread_id)
        await session.execute(query)
        await session.flush()

    @classmethod
    async def get_chats_paginated(
        cls,
        session: AsyncSession,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[Sequence["Chat"], int]:
        # Получаем общее количество чатов
        count_query = select(func.count()).select_from(cls).where(cls.user_id == user_id)
        total = await session.scalar(count_query) or 0  # Возвращаем 0 если None

        # Получаем чаты с пагинацией
        query = (
            select(cls)
            .where(cls.user_id == user_id)
            .order_by(cls.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        chats = result.scalars().all()
        
        return chats, total

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False
    )
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    is_sent_by_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    chat: Mapped[Chat] = relationship(
        back_populates="messages",
        cascade="all"
    )

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        chat_id: int,
        content: str,
        is_sent_by_bot: bool = False
    ) -> "Message":
        new_message = cls(
            chat_id=chat_id,
            content=content,
            created_at=datetime.utcnow(),
            is_sent_by_bot=is_sent_by_bot
        )
        session.add(new_message)
        await session.flush()
        
        # Обновляем время последнего сообщения в чате
        chat = await session.get(Chat, chat_id)
        if chat:
            chat.updated_at = datetime.utcnow()
            await session.flush()
        
        return new_message

    @classmethod
    async def get_by_id(
        cls,
        session: AsyncSession,
        message_id: int,
        chat_id: int
    ) -> Optional["Message"]:
        query = select(cls).where(
            and_(cls.id == message_id, cls.chat_id == chat_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_chat_messages_paginated(
        cls,
        session: AsyncSession,
        chat_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[Sequence["Message"], int]:
        # Получаем общее количество сообщений
        count_query = select(func.count()).select_from(cls).where(cls.chat_id == chat_id)
        total = await session.scalar(count_query) or 0

        # Получаем сообщения с пагинацией
        query = (
            select(cls)
            .where(cls.chat_id == chat_id)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        messages = result.scalars().all()
        
        return messages, total

class File(Base):
    __tablename__ = "files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    vector_store_id: Mapped[str] = mapped_column(
        String(500),
        ForeignKey("vector_stores.vector_store_id", ondelete="CASCADE"),
        nullable=False
    )
    chat_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False
    )
    chat: Mapped[Chat] = relationship(
        back_populates="files",
        cascade="all"
    )
    vector_store: Mapped["VectorStore"] = relationship(
        back_populates="files",
        cascade="all"
    )

    @classmethod
    async def create(cls, session: AsyncSession, file_id: str, chat_id: int, vector_store_id: str, filename: str) -> "File":
        new_file = cls(
            file_id=file_id, 
            chat_id=chat_id, 
            created_at=datetime.utcnow(),
            vector_store_id=vector_store_id,
            filename=filename
        )
        session.add(new_file)
        await session.flush()
        return new_file

    @classmethod
    async def get_by_id(cls, session: AsyncSession, file_id: str) -> Optional["File"]:
        query = select(cls).where(cls.file_id == file_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def delete(cls, session: AsyncSession, file_id: str) -> str:
        query = delete(cls).where(cls.file_id == file_id)
        await session.execute(query)
        await session.flush()
        return file_id

    @classmethod
    async def get_by_vector_store_id(cls, session: AsyncSession, vector_store_id: str) -> Sequence["File"]:
        query = select(cls).where(cls.vector_store_id == vector_store_id)
        result = await session.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def get_chat_files(cls, session: AsyncSession, chat_id: int) -> Sequence["File"]:
        query = select(cls).where(cls.chat_id == chat_id)
        result = await session.execute(query)
        return result.scalars().all()

class VectorStore(Base):
    __tablename__ = "vector_stores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id"), 
        nullable=False,
        unique=True
    )
    vector_store_id: Mapped[str] = mapped_column(
        String(500), 
        nullable=False,
        unique=True
    )
    user: Mapped[User] = relationship(
        back_populates="vector_store",
        cascade="all"
    )
    files: Mapped[List["File"]] = relationship(
        back_populates="vector_store",
        cascade="all, delete-orphan"
    )

    @classmethod
    async def create(cls, session: AsyncSession, user_id: int, vector_store_id: str) -> "VectorStore":
        new_vector_store = cls(user_id=user_id, vector_store_id=vector_store_id)
        session.add(new_vector_store)
        await session.flush()
        return new_vector_store

    @classmethod
    async def get_by_user_id(cls, session: AsyncSession, user_id: int) -> Optional["VectorStore"]:
        query = select(cls).where(cls.user_id == user_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def delete(cls, session: AsyncSession, vector_store_id: str) -> None:
        query = delete(cls).where(cls.vector_store_id == vector_store_id)
        await session.execute(query)
        await session.flush()
