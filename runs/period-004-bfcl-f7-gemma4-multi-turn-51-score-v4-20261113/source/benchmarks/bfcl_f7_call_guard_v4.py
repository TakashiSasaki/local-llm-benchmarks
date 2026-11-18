"""Conservative preflight guard for BFCL model-generated Python calls.

This is an experiment adapter, not a general Python sandbox. Unsupported but
otherwise legitimate calls halt the run rather than becoming scored failures.
"""
import ast,builtins,sys

class UnsupportedCall(BaseException):
    pass

MALFORMED_EXECUTOR_INSTALLED = False
CASE_ALLOWED_NAMES = None

def set_case_allowed_names(names):
    global CASE_ALLOWED_NAMES
    CASE_ALLOWED_NAMES = None if names is None else frozenset(names)

def enable_malformed_executor():
    global MALFORMED_EXECUTOR_INSTALLED
    MALFORMED_EXECUTOR_INSTALLED = True

def _validate_value(value, *, allow_names):
    try:
        ast.literal_eval(value)
        return
    except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError):
        pass
    # The pinned decoder converts bare names to their string spelling. It also
    # recursively converts list, tuple and dictionary elements.
    if allow_names and isinstance(value,ast.Name):return
    if allow_names and isinstance(value,(ast.List,ast.Tuple)):
        for item in value.elts:_validate_value(item,allow_names=True)
        return
    if allow_names and isinstance(value,ast.Dict):
        for item in value.keys+value.values:
            if item is None:raise UnsupportedCall('dictionary unpacking is not permitted')
            _validate_value(item,allow_names=True)
        return
    raise UnsupportedCall('argument is neither a literal nor an upstream name')

def _validate_call(call, allowed_names, *, strict=False, allow_unknown=False):
    if not isinstance(call,ast.Call):
        raise UnsupportedCall('only function calls are permitted')
    if isinstance(call.func,ast.Call):
        _validate_call(call.func,allowed_names,strict=strict,allow_unknown=allow_unknown)
    elif not isinstance(call.func,ast.Name):
        raise UnsupportedCall('unknown or indirect function')
    elif call.func.id not in allowed_names:
        if not allow_unknown or not MALFORMED_EXECUTOR_INSTALLED:
            raise UnsupportedCall('unknown function without guarded executor')
        module=sys.modules.get('bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils')
        forbidden={'kill','exit','quit','remove','unlink','popen','Popen','run'}
        if module is None or call.func.id in forbidden or call.func.id in vars(builtins) or call.func.id in vars(module):
            raise UnsupportedCall('unknown name is a builtin, global or denied')
    for argument in call.args:_validate_value(argument,allow_names=not strict)
    for keyword in call.keywords:
        if keyword.arg is None or not keyword.arg.isidentifier():
            raise UnsupportedCall('invalid keyword')
        _validate_value(keyword.value,allow_names=not strict)

def validate_call_text(text, allowed_names, *, strict=False, allow_unknown=False):
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
        _validate_call(call,allowed_names,strict=strict,allow_unknown=allow_unknown)

def validate_reconstructed_calls(calls, allowed_names):
    for call in calls:
        try:validate_call_text(call,allowed_names,strict=True,allow_unknown=MALFORMED_EXECUTOR_INSTALLED)
        except UnsupportedCall:
            if not MALFORMED_EXECUTOR_INSTALLED or not call.startswith('('):raise
            try:compile(call,'<string>','eval')
            except SyntaxError:continue
            raise

