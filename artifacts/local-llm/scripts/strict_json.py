"""Parse and compare JSON without confusing booleans, numbers or non-finite values."""
import json
from decimal import Decimal, InvalidOperation

def reject_constant(value):
    raise ValueError('Non-standard JSON constant: '+value)

def loads(text):
    return json.loads(text,parse_float=Decimal,parse_constant=reject_constant)

def equal(actual,expected):
    if isinstance(actual,bool) or isinstance(expected,bool):
        return type(actual) is bool and type(expected) is bool and actual==expected
    if isinstance(actual,dict) or isinstance(expected,dict):
        return isinstance(actual,dict) and isinstance(expected,dict) and actual.keys()==expected.keys() and all(equal(actual[k],expected[k]) for k in actual)
    if isinstance(actual,list) or isinstance(expected,list):
        return isinstance(actual,list) and isinstance(expected,list) and len(actual)==len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
    numbers=(int,float,Decimal)
    if isinstance(actual,numbers) or isinstance(expected,numbers):
        if not isinstance(actual,numbers) or not isinstance(expected,numbers): return False
        try:
            a,b=Decimal(str(actual)),Decimal(str(expected))
            return a.is_finite() and b.is_finite() and a==b
        except (InvalidOperation,ValueError): return False
    return type(actual) is type(expected) and actual==expected
