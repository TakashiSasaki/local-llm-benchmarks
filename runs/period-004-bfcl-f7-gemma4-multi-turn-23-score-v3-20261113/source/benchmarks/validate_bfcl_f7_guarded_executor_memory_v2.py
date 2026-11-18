"""Synthetic equivalence and rejection controls for BFCL executor adapter."""
import importlib,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from bfcl_f7_call_guard_memory_v2 import UnsupportedCall
from bfcl_f7_gemma4_guarded_adapter_memory_v2 import GuardedGemma4
from bfcl_f7_guarded_executor_memory_v2 import install_guarded_executor

def main():
    utils=importlib.import_module('bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils')
    original=utils.execute_multi_turn_func_call
    args=({},['MathAPI'],'synthetic-executor','multi_turn_base_998')
    valid=['mean(numbers=[1,2,3])','mean()','mean(numbers=[])']
    malformed=["(file_name='README.md')"]
    # This exact static expression cannot execute: it is a SyntaxError.
    try:compile(malformed[0],'<string>','eval')
    except SyntaxError:pass
    else:raise AssertionError('synthetic malformed input unexpectedly compiled')
    expected_good,_=original(valid,*args)
    expected_bad,_=original(malformed,*args)
    install_guarded_executor()
    got_good,_=utils.execute_multi_turn_func_call(valid,*args)
    got_bad,_=utils.execute_multi_turn_func_call(malformed,*args)
    assert got_good==expected_good and got_bad==expected_bad
    handler=GuardedGemma4('synthetic',0.001,'synthetic-executor',False)
    handler.allowed_names={'mean'}
    nested='mean(numbers=[1,2,3])(file_name="README.md")'
    assert handler.decode_execute(nested,False)==malformed
    assert handler.decode_execute('mean([1,2,3])',False)==['mean()']
    for bad in ('__import__(name="os")', 'mean(numbers=__import__("os"))',
                'mean(numbers=[1])(file_name=__import__("os"))'):
        try:handler.decode_execute(bad,False)
        except UnsupportedCall:pass
        else:raise AssertionError('unsafe call accepted')
    try:utils.execute_multi_turn_func_call(['__import__(name="os")'],*args)
    except UnsupportedCall:pass
    else:raise AssertionError('executor accepted unknown function')
    print('PASS: upstream valid/invalid equivalence, nested callee, positional, unsafe rejection')

if __name__=='__main__':main()
