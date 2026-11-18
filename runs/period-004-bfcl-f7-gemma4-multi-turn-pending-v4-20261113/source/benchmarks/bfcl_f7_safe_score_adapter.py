"""Stop offline BFCL scoring before upstream Python AST eval expressions.

This is a conservative experimental guard, not an OS sandbox. Ordinary
unparseable answers are still passed to the upstream checker unchanged.
"""
import ast,re
from overrides import override
from bfcl_eval.constants.enums import ReturnFormat
from bfcl_f7_call_guard import UnsupportedCall
from bfcl_f7_gemma4_adapter import Gemma4LlamaChat

class GuardedScoringGemma4(Gemma4LlamaChat):
    @override
    def decode_ast(self, result, language, has_tool_call_tag):
        if language == ReturnFormat.PYTHON:
            text=result.strip('`\n ')
            if not text.startswith('['):text='['+text
            if not text.endswith(']'):text+=']'
            if has_tool_call_tag:
                match=re.search(r'<TOOLCALL>(.*?)</TOOLCALL>',text,re.DOTALL)
                if match:text=match.group(1).strip()
            try:tree=ast.parse(text.strip().strip("'"),mode='eval')
            except SyntaxError:tree=None
            if tree is not None and any(isinstance(n,(ast.BinOp,ast.Lambda)) for n in ast.walk(tree)):
                raise UnsupportedCall('upstream Python AST decoder would evaluate an expression; scoring stopped for review')
        return super().decode_ast(result,language,has_tool_call_tag)
