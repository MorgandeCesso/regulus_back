from datetime import datetime
from typing import List, Optional, Tuple, Sequence
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy import TIMESTAMP, MetaData, Integer, String, Boolean, ForeignKey, select, and_, delete, update
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

    @classmethod
    async def create(cls, session: AsyncSession, user_id: int, title: str) -> "Chat":
        now = datetime.utcnow()
        new_chat = cls(
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now
        )
        session.add(new_chat)
        await session.flush()
        return new_chat

    @classmethod
    async def get_by_id(cls, session: AsyncSession, chat_id: int) -> Optional["Chat"]:
        query = select(cls).where(cls.id == chat_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_last_20_chats(cls, session: AsyncSession, user_id: int) -> Sequence["Chat"]:
        query = select(cls).where(cls.user_id == user_id).order_by(cls.updated_at.desc()).limit(20)
        result = await session.execute(query)
        return result.scalars().all()

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

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chats.id"), nullable=False)
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
    async def get_chat_messages(
        cls,
        session: AsyncSession,
        chat_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> Sequence["Message"]:
        query = (
            select(cls)
            .where(cls.chat_id == chat_id)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        return result.scalars().all()

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

