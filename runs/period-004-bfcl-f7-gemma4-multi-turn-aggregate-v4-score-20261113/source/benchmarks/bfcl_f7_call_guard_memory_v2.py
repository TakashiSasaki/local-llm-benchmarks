"""Conservative preflight guard for BFCL model-generated Python calls.

This is an experiment adapter, not a general Python sandbox. Unsupported but
otherwise legitimate calls halt the run rather than becoming scored failures.
"""
import ast

class UnsupportedCall(BaseException):
    pass

MALFORMED_EXECUTOR_INSTALLED = False

def enable_malformed_executor():
    global MALFORMED_EXECUTOR_INSTALLED
    MALFORMED_EXECUTOR_INSTALLED = True

def _validate_call(call, allowed_names):
    if not isinstance(call,ast.Call):
        raise UnsupportedCall('only function calls are permitted')
    if isinstance(call.func,ast.Call):
        # f7 drops the nested callee when reconstructing this shape.
        _validate_call(call.func,allowed_names)
    elif not isinstance(call.func,ast.Name) or call.func.id not in allowed_names:
        raise UnsupportedCall('unknown or indirect function')
    for argument in call.args:
        try:ast.literal_eval(argument)
        except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError):
            raise UnsupportedCall('positional argument is not a literal')
    for keyword in call.keywords:
        if keyword.arg is None or not keyword.arg.isidentifier():
            raise UnsupportedCall('invalid keyword')
        try:ast.literal_eval(keyword.value)
        except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError):
            raise UnsupportedCall('argument is not a literal')

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
        if not isinstance(call,ast.Call):
            if strict: raise UnsupportedCall('reconstructed expression is not a function call')
            continue  # f7 decoder handles non-call expressions as ordinary parse failures
        _validate_call(call,allowed_names)

def validate_reconstructed_calls(calls, allowed_names):
    for call in calls:
        try:validate_call_text(call,allowed_names,strict=True)
        except UnsupportedCall:
            if not MALFORMED_EXECUTOR_INSTALLED or not call.startswith('('):raise
            try:compile(call,'<string>','eval')
            except SyntaxError:continue
            raise

