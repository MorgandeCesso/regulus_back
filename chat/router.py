from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI
from typing import List

from db.session import get_async_session
from db.models import Chat, Message, User
from auth.tools import get_current_user
from gpt.gpt import GPT
from configs import OPENAI_API_KEY

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={401: {"description": "Не авторизован"}},
)

gpt = GPT()
client = OpenAI(api_key=OPENAI_API_KEY)

