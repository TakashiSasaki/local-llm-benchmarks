"""Experimental BFCL multi-turn adapter with a conservative call guard.

Guard rejection stops the run; it is never reported as a model failure.
This narrows accepted syntax and is not a general OS sandbox.
"""
from overrides import override
from bfcl_f7_gemma4_adapter import Gemma4LlamaChat
from bfcl_f7_call_guard_v5 import validate_call_text,validate_reconstructed_calls,set_case_allowed_names

class GuardedGemma4(Gemma4LlamaChat):
    @override
    def _pre_query_processing_prompting(self, test_entry: dict) -> dict:
        docs=list(test_entry['function'])
        for group in test_entry.get('missed_function',{}).values(): docs.extend(group)
        self.allowed_names={doc['name'] for doc in docs}
        return super()._pre_query_processing_prompting(test_entry)

    @override
    def decode_execute(self, result, has_tool_call_tag):
        set_case_allowed_names(self.allowed_names)
        validate_call_text(result,self.allowed_names,allow_unknown=True)
        calls=super().decode_execute(result,has_tool_call_tag)
        validate_reconstructed_calls(calls,self.allowed_names)
        return calls

