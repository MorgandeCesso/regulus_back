from fastapi import FastAPI, Depends
from auth.router import router as auth_router
from auth.tools import get_current_user
from db.models import User
import logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Regulus")

app.include_router(auth_router)

@app.get("/public")
async def public_route():
    """Этот эндпоинт доступен всем пользователям"""
    return {"message": "Это публичный эндпоинт"}

@app.get("/private")
async def private_route(current_user: User = Depends(get_current_user)):
    """Этот эндпоинт доступен только авторизованным пользователям"""
    return {
        "message": "Это приватный эндпоинт",
        "user": current_user.username
    }


