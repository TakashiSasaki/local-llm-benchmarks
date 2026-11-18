"""Decode the tagged WebSearchAPI calls observed in Gemma 4 chat replies."""

import ast
import json

from overrides import override

from bfcl_f7_call_guard_v5 import validate_call_text
from bfcl_f7_gemma4_guarded_adapter_v5 import GuardedGemma4


PREFIX = '<|tool_call>call:'
SUFFIX = '<tool_call|>'
WEB_CALLS = frozenset(('search_engine_query', 'fetch_url_content'))


class Gemma4WebToolCalls(GuardedGemma4):
    @override
    def decode_execute(self, result, has_tool_call_tag):
        text = result.strip()
        if text.startswith(PREFIX):
            text = text[len(PREFIX):].removesuffix(SUFFIX).strip()
            if text.startswith('{'):
                # In these two tool schemas, keywords uniquely identifies search.
                arguments = json.loads(text)
                if (not isinstance(arguments, dict)
                        or set(arguments) - {'keywords', 'max_results', 'region'}
                        or not isinstance(arguments.get('keywords'), str)
                        or not arguments['keywords'].strip()):
                    raise ValueError('Cannot identify a web tool from the tagged arguments')
                text = 'search_engine_query(' + ', '.join(
                    f'{name}={value!r}' for name, value in arguments.items()) + ')'
            elif text.startswith('"') and text.endswith('"'):
                try:
                    text = json.loads(text)
                except json.JSONDecodeError:
                    # Some replies wrap a Python call without escaping its inner quotes.
                    text = text[1:-1]

            call = ast.parse(text, mode='eval').body
            allowed = WEB_CALLS & self.allowed_names
            if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name)
                    or call.func.id not in allowed):
                raise ValueError('Expected one allowed web tool in the tagged reply')
            text = ast.unparse(call)
            validate_call_text(text, allowed, strict=True)
            result = text
        return super().decode_execute(result, has_tool_call_tag)
