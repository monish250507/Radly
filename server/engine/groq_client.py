import json
import os
import re
from typing import Any

from groq import AsyncGroq

from .config import config
from .logger import radly_logger as logger


class UpstreamError(Exception):
    def __init__(self, message: str, status_code: int = 500, code: str = 'upstream_error'):
        super().__init__(message)
        self.status_code = status_code
        self.code = code

GROQ_MODELS = [
    m for m in [
        os.environ.get('RBR_LLM_MODEL', '').strip(),
        os.environ.get('GROQ_MODEL', '').strip(),
        'groq/compound-mini',
        'qwen/qwen3.8-27b',
        'openai/gpt-oss-120b',
        'openai/gpt-oss-20b',
        'groq/compound',
    ] if m
]

async def call_groq_api(messages: list[dict[str, str]], system_prompt: str = '', response_format_json: bool = True) -> dict[str, Any] | str:
    if not config.Groq.CONFIGURED:
        raise UpstreamError('GROQ_API_KEY is not configured; AI synthesis unavailable.', 503, 'ai_not_configured')

    client = AsyncGroq(api_key=config.Groq.API_KEY)

    full_messages = []
    if system_prompt:
        full_messages.append({'role': 'system', 'content': system_prompt})
    full_messages.extend(messages)

    last_error = None

    for model in GROQ_MODELS:
        try:
            kwargs = {
                "model": model,
                "messages": full_messages,
                "temperature": 0.0,
                "max_tokens": 4096
            }
            if response_format_json:
                kwargs["response_format"] = {"type": "json_object"}

            chat_completion = await client.chat.completions.create(**kwargs)
            content = chat_completion.choices[0].message.content
            
            if not content:
                raise Exception('Groq returned empty response body')

            if response_format_json:
                try:
                    return json.loads(content)
                except json.JSONDecodeError as json_err:
                    match = re.search(r'\{[\s\S]*\}', content)
                    if match:
                        return json.loads(match.group(0))
                    raise Exception(f'Groq response was not valid JSON: {json_err}')

            return content
        except Exception as err:
            logger.error(f'Failed with Groq model {model}', {'model': model, 'reason': str(err)})
            last_error = err

    raise last_error or UpstreamError('All Groq API models failed', 500, 'groq_all_models_failed')
