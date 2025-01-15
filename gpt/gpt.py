import logging
from openai import AsyncOpenAI
from configs import OPENAI_ASSISTANT_ID
from io import BytesIO

class GPT:
    def __init__(self):
        self.assistant_id = OPENAI_ASSISTANT_ID

    async def create_thread(self, client: AsyncOpenAI):
        """Создает новый тред"""
        thread = await client.beta.threads.create()
        logging.info(f"Thread created: {thread.id}")
        return thread.id

    async def create_message(self, thread_id: str, content: str, client: AsyncOpenAI):
        """Создает новое сообщение в тред"""
        message = await client.beta.threads.messages.create(
            thread_id=thread_id, 
            role="user", 
            content=content
        )
        logging.info(f"Message created: {message.id}")
        return message

    async def create_and_poll_run(self, thread_id: str, client: AsyncOpenAI, user_name: str):
        """Создает и запускает новый тред"""
        run = await client.beta.threads.runs.create_and_poll(
            thread_id=thread_id, 
            assistant_id=str(self.assistant_id), 
            additional_instructions=f"Обращайся к пользователю как {user_name}"
        )
        logging.info(f"Run created: {run.id}")
        return run

    async def get_gpt_response(self, thread_id: str, run_id: str, client: AsyncOpenAI):
        """Получает ответ от GPT"""
        messages_page = await client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=1,
            run_id=run_id
        )
        messages = messages_page.data
        
        if not messages:
            return "Нет сообщений"
            
        gpt_response = messages[0].content[0]
        logging.info(f"First message content: {gpt_response}")

        if hasattr(gpt_response, "text"):
            text_content = gpt_response.text # type: ignore
            response = getattr(text_content, 'value', '')
            annotations = getattr(text_content, 'annotations', [])
            citations = []
            if response:
                for index, annotation in enumerate(annotations):
                    if hasattr(annotation, 'text') and annotation.text in response:
                        response = response.replace(annotation.text, f"[{index}]")
                        if file_citation := getattr(annotation, "file_citation", None):
                            try:
                                cited_file = await client.files.retrieve(file_citation.file_id)
                                citations.append(f"[{index}] {cited_file.filename}")
                            except Exception as e:
                                logging.error(f"Ошибка при получении цитируемого файла: {e}")

                if citations:
                    response += "\n\nИсточники:\n" + "\n".join(citations)
            else:
                response = "Извините, не удалось получить текст ответа"
        else:
            response = getattr(gpt_response, 'value', "Извините, но я не могу обработать этот тип контента")

        logging.info(f"GPT response: {response}")
        return response

    async def delete_thread(self, thread_id: str, client: AsyncOpenAI):
        """Удаляет тред"""
        await client.beta.threads.delete(thread_id=thread_id)
        logging.info(f"Thread deleted: {thread_id}")
        return {"status": "success", "deleted_thread_id": f"{thread_id}"}

    async def cancel_run(self, run_id: str, thread_id: str, client: AsyncOpenAI):
        """Отменяет выполнение задания"""
        await client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
        logging.info(f"Run cancelled: {run_id}")
        return {"status": "success", "cancelled_run_id": f"{run_id}"}

    async def upload_file_to_vector_store(self, file_content: bytes, vector_store_id: str, filename: str, client: AsyncOpenAI) -> str:
        """
        Загружает файл и привязывает его к векторному хранилищу.
        
        Args:
            file_content: Содержимое файла в байтах
            vector_store_id: ID векторного хранилища
            filename: Оригинальное имя файла с расширением
            client: OpenAI клиент
        
        Returns:
            str: ID файла в OpenAI
        """
        # Создаем BytesIO объект
        file_obj = BytesIO(file_content)
        file_obj.name = filename  # Используем оригинальное имя файла
        
        # Загружаем файл
        file = await client.files.create(
            file=file_obj,
            purpose="assistants"
        )
        logging.info(f"File uploaded: {file.id}")
        
        # Получаем текущие файлы ассистента
        file_batch = await client.beta.vector_stores.file_batches.create_and_poll(
            vector_store_id=vector_store_id,
            file_ids=[file.id]
        )
        
        return file.id

    async def create_vector_store(self, user_id: int, client: AsyncOpenAI):
        """Создает векторное хранилище"""
        vector_store = await client.beta.vector_stores.create(name=f"User_{user_id} vector store")
        logging.info(f"Vector store created: {vector_store.id}")
        return vector_store.id
    
    async def unattach_file_from_vector_store(self, file_id: str, vector_store_id: str, client: AsyncOpenAI):
        result = await client.beta.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
        logging.info(f"File unattached from vector store: {result.id}")
        return result.id
    
    async def delete_file(self, file_id: str, client: AsyncOpenAI):
        result = await client.files.delete(file_id=file_id)
        logging.info(f"File deleted from OpenAI: {result.id}")
        return result.id
