from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy import TIMESTAMP, MetaData, Integer, String, Boolean, ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession

class Base(DeclarativeBase):
    metadata = MetaData()

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    chats: Mapped[List["Chat"]] = relationship(back_populates="user")

class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    user: Mapped[User] = relationship(back_populates="chats")
    messages: Mapped[List["Message"]] = relationship(back_populates="chat")

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chats.id"), nullable=False)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    chat: Mapped[Chat] = relationship(back_populates="messages")

