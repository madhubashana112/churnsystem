import json
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class QwenGateway:
    def __init__(self, model: str = "qwen-max"):
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")
        if not api_key or not api_key.strip():
            # Failing here beats a placeholder key: a silent "MISSING_KEY"
            # surfaces much later as an opaque 401 from the provider.
            raise EnvironmentError(
                "No Qwen API key configured. Set DASHSCOPE_API_KEY or ALIBABA_API_KEY, "
                "or run with CHURN_ENGINE=local to use the offline engine."
            )

        self.client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
        self.model = model

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            return json.loads(completion.choices[0].message.content)
        except Exception:
            logger.exception("Qwen request failed")
            raise
