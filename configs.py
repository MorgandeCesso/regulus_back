from dotenv import load_dotenv
import os

load_dotenv()

PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")
PG_DATABASE = os.getenv("PG_DATABASE")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "maximsid2003@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "Maximsid2003")

PG_DSN = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}?async_fallback=True"

OPENAI_PROXY = os.getenv("OPENAI_PROXY")

