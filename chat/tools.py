from openai import AsyncOpenAI
from core.openai import get_openai_client
from configs import TITLE_NAMER_ID
import logging

async def get_chat_title(user_message: str, assistant_response: str) -> str:
    """
    Генерирует название для чата на основе первого сообщения пользователя и ответа ассистента
    """
    client = get_openai_client()
    
    try:
        # Создаем временный тред для генерации названия
        thread = await client.beta.threads.create()
        
        # Отправляем контекст диалога
        message_content = f"""На основе этого диалога придумай короткое название для чата (не более 5 слов):
        
        Пользователь: {user_message}
        Ассистент: {assistant_response}
        
        Ответь только названием, без кавычек и дополнительного текста."""
        
        await client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message_content
        )
        
        # Запускаем генерацию названия
        await client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=TITLE_NAMER_ID,
            additional_instructions="Генерируй только название чата, без кавычек и пояснений. Максимум 5 слов."
        )
        
        # Получаем сгенерированное название
        messages_page = await client.beta.threads.messages.list(
            thread_id=thread.id,
            order="desc",
            limit=1
        )
        messages = messages_page.data
        
        if not messages:
            return "Новый чат"
            
        title = messages[0].content[0].text.value # type: ignore
        
        # Удаляем временный тред
        await client.beta.threads.delete(thread.id)
        
        return title.strip()
        
    except Exception as e:
        logging.error(f"Ошибка при генерации названия чата: {e}")
        return "Новый чат"  # Дефолтное название в случае ошибки


