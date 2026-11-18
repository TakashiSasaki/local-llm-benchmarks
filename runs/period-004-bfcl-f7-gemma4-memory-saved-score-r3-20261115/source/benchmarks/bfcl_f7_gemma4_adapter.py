"""Gemma 4 chat transport for pinned upstream BFCL prompt-mode handler.

Uses llama.cpp's GGUF chat template. Upstream generation and checker remain
unchanged. This is an adapter, not an upstream leaderboard model configuration.
"""
import copy
import json
import os
import pathlib
import time
from types import SimpleNamespace

from openai import OpenAI
from overrides import override
from bfcl_eval.model_handler.local_inference.base_oss_handler import OSSHandler
from bfcl_eval.model_handler.utils import combine_consecutive_user_prompts, format_execution_results_prompting

CURRENT_CASE = None

class Gemma4LlamaChat(OSSHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = OpenAI(base_url=self.base_url, api_key='EMPTY', max_retries=0, timeout=7200)

    @override
    def _query_prompting(self, inference_data: dict):
        messages = combine_consecutive_user_prompts(copy.deepcopy(inference_data['message']))
        assert all(m['role'] in ('system', 'user', 'assistant') for m in messages)
        payload = {'model': 'period4-bfcl-gemma4', 'messages': messages,
                   'temperature': self.temperature, 'max_tokens': 4096,
                   'seed': 42, 'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}}
        inference_data['inference_input_log'] = payload
        raw_dir = pathlib.Path(os.environ['BFCL_RAW_HTTP_DIR'])
        raw_dir.mkdir(parents=True, exist_ok=True)
        sequence = len(list(raw_dir.glob('*.json')))
        target = raw_dir / f'{sequence:08d}.json'
        assert not target.exists()
        started = time.monotonic()
        response = self.client.chat.completions.create(**payload)
        body = response.model_dump()
        with target.open('x', encoding='utf-8') as f:
            json.dump({'case_id':CURRENT_CASE, 'request': payload, 'response': body, 'seconds':time.monotonic()-started}, f, ensure_ascii=False, indent=2)
        choice = response.choices[0]
        return SimpleNamespace(choices=[SimpleNamespace(text=choice.message.content or '')], usage=response.usage), time.monotonic()-started

    @override
    def _add_execution_results_prompting(self, inference_data: dict, execution_results: list[str], model_response_data: dict) -> dict:
        text = format_execution_results_prompting(inference_data, execution_results, model_response_data)
        inference_data['message'].append({'role':'user', 'content':text})
        return inference_data

