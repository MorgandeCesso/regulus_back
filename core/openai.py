from openai import AsyncOpenAI
from configs import OPENAI_API_KEY, OPENAI_PROXY
import httpx

class OpenAIClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = AsyncOpenAI(
                api_key=OPENAI_API_KEY, 
                http_client=httpx.AsyncClient(proxy=OPENAI_PROXY)
            )
        return cls._instance

def get_openai_client() -> AsyncOpenAI:
    return OpenAIClient() 