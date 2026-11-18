"""Conservative preflight guard for BFCL model-generated Python calls.

This is an experiment adapter, not a general Python sandbox. Unsupported but
otherwise legitimate calls halt the run rather than becoming scored failures.
"""
import ast

class UnsupportedCall(BaseException):
    pass

def validate_call_text(text, allowed_names, *, strict=False):
    """Reject executable expressions before upstream decoder/eval sees them."""
    cleaned=text.strip('`\n ')
    if not cleaned.startswith('['):cleaned='['+cleaned
    if not cleaned.endswith(']'):cleaned+=']'
    try: expression=ast.parse(cleaned,mode='eval').body
    except SyntaxError:
        if strict: raise UnsupportedCall('reconstructed call is not valid Python')
        # Upstream decoder will report the original syntax/format error.
        return
    calls=expression.elts if isinstance(expression,(ast.List,ast.Tuple)) else [expression]
    for call in calls:
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name):
            raise UnsupportedCall('only direct named calls are permitted')
        if call.func.id not in allowed_names or call.args:
            raise UnsupportedCall('unknown function or positional argument')
        for keyword in call.keywords:
            if keyword.arg is None or not keyword.arg.isidentifier():
                raise UnsupportedCall('invalid keyword')
            try:ast.literal_eval(keyword.value)
            except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError):
                raise UnsupportedCall('argument is not a literal')

def validate_reconstructed_calls(calls, allowed_names):
    for call in calls:
        validate_call_text(call,allowed_names,strict=True)

