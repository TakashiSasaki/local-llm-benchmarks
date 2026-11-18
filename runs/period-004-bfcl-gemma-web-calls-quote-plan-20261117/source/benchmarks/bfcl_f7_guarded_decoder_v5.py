"""Replace f7's expression eval with bounded arithmetic before decoding."""
import ast,importlib
from bfcl_f7_call_guard_v5 import UnsupportedCall
from bfcl_f7_safe_arithmetic import safe_number,UnsafeArithmetic

def install_guarded_decoder():
    utils=importlib.import_module('bfcl_eval.model_handler.utils')
    original=utils.resolve_ast_by_type
    if getattr(original,'_guarded_decoder',False):raise RuntimeError('guarded decoder already installed')
    def resolve(value):
        if isinstance(value,ast.BinOp):
            try:return safe_number(value)
            except UnsafeArithmetic as exc:raise UnsupportedCall(str(exc))
        if isinstance(value,ast.Lambda):raise UnsupportedCall('lambda expression is not supported')
        return original(value)
    resolve._guarded_decoder=True
    utils.resolve_ast_by_type=resolve
