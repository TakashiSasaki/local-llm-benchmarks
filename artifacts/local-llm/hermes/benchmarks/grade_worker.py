"""Restricted pure-Python grading worker; parent adds Windows memory/process limits."""
import ast
import builtins
import contextlib
import io
import json
import sys

MODULES={'math','typing','collections','itertools','functools','re','heapq','bisect','statistics','string'}
ATTRS=set('append extend pop remove sort reverse index count join split splitlines strip lstrip rstrip lower upper isalpha isalnum isdigit isspace startswith endswith replace find rfind capitalize title swapcase zfill keys values items get setdefault add update discard union intersection difference copy clear popleft appendleft Counter defaultdict deque reduce lru_cache cache combinations permutations product chain accumulate repeat cycle islice groupby heappush heappop heapify nsmallest nlargest bisect bisect_left bisect_right insort digits ascii_lowercase ascii_uppercase ascii_letters punctuation'.split())
import math
ATTRS.update(name for name in dir(math) if not name.startswith('_'))
SAFE=set('abs all any bin bool bytearray bytes chr complex dict divmod enumerate filter float frozenset hash hex int isinstance iter len list map max min next oct ord pow print range reversed round set slice sorted str sum tuple zip Exception ValueError AssertionError IndexError KeyError TypeError ZeroDivisionError StopIteration NotImplementedError'.split())
def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name not in MODULES: raise ValueError('Unsupported import: '+name)
    if name=='typing' and any(n not in {'List','Tuple','Dict','Set','Optional','Any','Union','Iterable','Sequence','Callable'} for n in fromlist):
        raise ValueError('Unsupported typing import')
    return builtins.__import__(name,globals,locals,fromlist,level)
def validate(code):
    tree=ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node,(ast.ClassDef,ast.Global,ast.Nonlocal,ast.AsyncFunctionDef,ast.Await)):
            raise ValueError('Unsupported syntax: '+type(node).__name__)
        if isinstance(node,ast.Name) and node.id.startswith('__'): raise ValueError('Private name')
        if isinstance(node,ast.Attribute) and node.attr not in ATTRS: raise ValueError('Unsupported attribute: '+node.attr)
        if isinstance(node,ast.Import):
            if any(a.name not in MODULES or (a.asname or '').startswith('__') for a in node.names): raise ValueError('Unsupported import')
        if isinstance(node,ast.ImportFrom):
            if node.level or node.module not in MODULES: raise ValueError('Unsupported import')
            if node.module=='typing' and any(a.name not in {'List','Tuple','Dict','Set','Optional','Any','Union','Iterable','Sequence','Callable'} for a in node.names): raise ValueError('Unsupported typing import')
    return tree
payload=json.loads(sys.stdin.read())
try:
    tree=validate(payload['code'])
except Exception as exc:
    print(json.dumps({'passed':False,'status':'guard_rejected','detail':str(exc)})); sys.exit(0)
namespace={'__builtins__':{n:getattr(builtins,n) for n in SAFE}}
namespace['__builtins__']['__import__']=guarded_import
try:
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        exec(compile(tree,'candidate.py','exec'),namespace)
        exec(payload['test'],namespace)
        namespace['check'](namespace[payload['entry_point']])
    outcome={'passed':True,'status':'passed'}
except BaseException as exc:
    outcome={'passed':False,'status':'failed','detail':type(exc).__name__+': '+str(exc)[:300]}
print(json.dumps(outcome))
