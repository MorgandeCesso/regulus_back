import logging
from openai import OpenAI
from configs import OPENAI_ASSISTANT_ID

class GPT:
    def __init__(self):
        self.assistant_id = OPENAI_ASSISTANT_ID

    def create_thread(self, client: OpenAI):
        thread = client.beta.threads.create()
        logging.info(f"Thread created: {thread.id}")
        return thread.id

    def create_message(self, thread_id: str, content: str, client: OpenAI):
        message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=content)
        logging.info(f"Message created: {message.id}")
        return message

    def create_and_poll_run(self, thread_id: str, client: OpenAI, user_name: str):
        run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=str(self.assistant_id), additional_instructions=f"Обращайся к пользователю как {user_name}")
        logging.info(f"Run created: {run.id}")
        return run

    def get_gpt_response(self, thread_id: str, client: OpenAI):
        messages = list(client.beta.threads.messages.list(thread_id=thread_id))
        logging.info(f"Received {len(messages)} messages from OpenAI")

        gpt_response = messages[-1].content[0]
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
                                cited_file = client.files.retrieve(file_citation.file_id)
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

    def delete_thread(self, thread_id: str, client: OpenAI):
        client.beta.threads.delete(thread_id=thread_id)
        logging.info(f"Thread deleted: {thread_id}")
        return {"status": "success",
                "deleted_thread_id": f"{thread_id}"}

    def cancel_run(self, run_id: str, thread_id: str, client: OpenAI):
        client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
        logging.info(f"Run cancelled: {run_id}")
        return {"status": "success",
                "cancelled_run_id": f"{run_id}"}

