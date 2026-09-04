import os
from openai import AsyncOpenAI
import json

class QwenGateway:
    def __init__(self):
        # Uses standard OpenAI library with dashscope base URL
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY") or "MISSING_KEY"
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        self.model = "qwen-max"

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"Error calling Qwen API: {e}")
            raise
