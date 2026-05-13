import logging
import os

from openai import OpenAI

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a news assistant. Write a clear 2-3 sentence summary of the article in English. "
    "Include the key event, the main people/organizations involved, and the most important consequence or context. "
    "Use a neutral journalistic tone. Do not speculate or add facts not found in the article. "
    "Do not begin with phrases like 'The article is about' or 'This article discusses'."
)


class LLMService:
    def __init__(self):
        provider = os.environ.get("LLM_PROVIDER", "ollama").lower()

        if provider == "openai":
            self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        else:
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
            self.client = OpenAI(
                base_url=f"{base_url.rstrip('/')}/v1",
                api_key="ollama",
            )
            self.model = os.environ.get("OLLAMA_MODEL", "llama3.2")

    def summarize(self, text: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text[:4000]},
                ],
                max_tokens=200,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.warning("LLM summarization failed: %s", e)
            return ""
