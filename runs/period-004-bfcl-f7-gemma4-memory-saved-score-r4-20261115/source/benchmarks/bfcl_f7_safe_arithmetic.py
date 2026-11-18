"""Bounded numeric AST evaluation for the BFCL f7 adapter; no Python eval."""
import ast,math,operator

class UnsafeArithmetic(BaseException):
    pass

_BINARY={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
         ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,
         ast.Pow:operator.pow,ast.LShift:operator.lshift,ast.RShift:operator.rshift,
         ast.BitOr:operator.or_,ast.BitXor:operator.xor,ast.BitAnd:operator.and_}
_UNARY={ast.UAdd:operator.pos,ast.USub:operator.neg,ast.Invert:operator.invert}

def safe_number(node,depth=0):
    if depth>32:raise UnsafeArithmetic('expression depth exceeds limit')
    if isinstance(node,ast.Constant):
        value=node.value
        if type(value) not in (int,float,bool):raise UnsafeArithmetic('non-numeric literal')
    elif isinstance(node,ast.UnaryOp) and type(node.op) in _UNARY:
        value=_UNARY[type(node.op)](safe_number(node.operand,depth+1))
    elif isinstance(node,ast.BinOp) and type(node.op) in _BINARY:
        a=safe_number(node.left,depth+1);b=safe_number(node.right,depth+1)
        if isinstance(node.op,ast.Pow):
            if type(b) not in (int,bool) or abs(b)>128:raise UnsafeArithmetic('power exceeds limit')
            if type(a) is int and b>0 and a.bit_length()*b>4096:raise UnsafeArithmetic('power size exceeds limit')
        if isinstance(node.op,(ast.LShift,ast.RShift)) and (type(b) not in (int,bool) or abs(b)>4096):
            raise UnsafeArithmetic('shift exceeds limit')
        if isinstance(node.op,ast.Mult) and type(a) is int and type(b) is int and a.bit_length()+b.bit_length()>4096:
            raise UnsafeArithmetic('product exceeds limit')
        value=_BINARY[type(node.op)](a,b)
    else:raise UnsafeArithmetic('expression contains unsupported or executable syntax')
    if type(value) is int and value.bit_length()>4096:raise UnsafeArithmetic('integer exceeds limit')
    if type(value) is float and not math.isfinite(value):raise UnsafeArithmetic('non-finite result')
    if type(value) not in (int,float,bool):raise UnsafeArithmetic('unsupported numeric result')
    return value
