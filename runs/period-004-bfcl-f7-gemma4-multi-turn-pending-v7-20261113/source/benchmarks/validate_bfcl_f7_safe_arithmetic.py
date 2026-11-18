"""Compare bounded arithmetic to f7 for safe fixed expressions; reject hazards."""
import ast,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from bfcl_eval.model_handler import utils
from bfcl_f7_safe_arithmetic import safe_number,UnsafeArithmetic
from bfcl_f7_guarded_decoder_v5 import install_guarded_decoder
from bfcl_f7_guarded_executor_v5 import install_guarded_executor
from bfcl_f7_gemma4_guarded_adapter_v5 import GuardedGemma4
from bfcl_f7_call_guard_v5 import UnsupportedCall

def main():
    # Only these fixed, independently reviewed numeric expressions reach upstream eval.
    expressions=['150/3.78541','1+2','5-9','-2*4','17//3','17%3','2**8',
                 '8<<2','8>>2','5|2','5&2','5^2','(3+4)*2','1.0/2']
    expected=[]
    for text in expressions:
        node=ast.parse(text,mode='eval').body
        expected.append(utils.resolve_ast_by_type(node))
        assert safe_number(node)==expected[-1]
    # Exhaust a small fixed numeric boundary grid, including zero divisors.
    checked=0
    for a in (-2,-1,0,1,2,5):
        for b in (-2,-1,0,1,2,5):
            for op in ('+','-','*','/','//','%','**','|','&','^'):
                node=ast.parse(f'({a}){op}({b})',mode='eval').body
                try:original=('value',utils.resolve_ast_by_type(node))
                except Exception as exc:original=('exception',type(exc))
                try:bounded=('value',safe_number(node))
                except Exception as exc:bounded=('exception',type(exc))
                assert original==bounded,(a,op,b,original,bounded)
                checked+=1
    install_guarded_decoder();install_guarded_executor()
    for text,value in zip(expressions,expected):
        assert utils.resolve_ast_by_type(ast.parse(text,mode='eval').body)==value
    h=GuardedGemma4('synthetic',0.001,'synthetic-arithmetic',False)
    h.allowed_names={'fillFuelTank'}
    assert h.decode_execute('fillFuelTank(fuelAmount=150/3.78541)',False)==[f'fillFuelTank(fuelAmount={150/3.78541!r})']
    for expression in ('1+__import__("os")','1+open("x")','1+(lambda: 1)()',
                       '1+x.y','1+x[0]','2**1000000','"x"*99999999'):
        node=ast.parse(expression,mode='eval').body
        try:safe_number(node)
        except UnsafeArithmetic:pass
        else:raise AssertionError('unsafe arithmetic accepted: '+expression)
    try:h.decode_execute('fillFuelTank(fuelAmount=1/0)',False)
    except ZeroDivisionError:pass
    else:raise AssertionError('arithmetic exception was not preserved')
    print('PASS: fixed numeric oracle,',checked,'boundary cases, arithmetic errors and executable-syntax rejection')

if __name__=='__main__':main()
