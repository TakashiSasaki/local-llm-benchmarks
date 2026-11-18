"""Synthetic equivalence and rejection controls for BFCL executor adapter."""
import builtins,importlib,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from bfcl_f7_call_guard_v5 import UnsupportedCall,set_case_allowed_names
from bfcl_f7_gemma4_guarded_adapter_v5 import GuardedGemma4
from bfcl_f7_guarded_executor_v5 import install_guarded_executor
from bfcl_f7_guarded_decoder_v5 import install_guarded_decoder

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
    missing='get_ticket_login_status'
    assert missing not in vars(utils) and missing not in vars(builtins)
    expected_missing,_=original([missing+'()'],*args)
    assert expected_missing==["Error during execution: name 'get_ticket_login_status' is not defined"]
    install_guarded_decoder();install_guarded_executor()
    set_case_allowed_names({'mean'})
    got_good,_=utils.execute_multi_turn_func_call(valid,*args)
    got_bad,_=utils.execute_multi_turn_func_call(malformed,*args)
    got_missing,_=utils.execute_multi_turn_func_call([missing+'()'],*args)
    assert got_good==expected_good and got_bad==expected_bad and got_missing==expected_missing
    handler=GuardedGemma4('synthetic',0.001,'synthetic-executor',False)
    handler.allowed_names={'mean'}
    unknown=handler.decode_execute('get_ticket_login_status()',False)
    assert utils.execute_multi_turn_func_call(unknown,*args)[0]==expected_missing
    nested='mean(numbers=[1,2,3])(file_name="README.md")'
    assert handler.decode_execute(nested,False)==malformed
    assert handler.decode_execute('mean([1,2,3])',False)==['mean()']
    handler.allowed_names={'cd','ls'}
    assert handler.decode_execute('[cd(folder="temporary"), ls(a=true)]',False)==["cd(folder='temporary')","ls(a='true')"]
    handler.allowed_names={'mean'}
    for bad in ('__import__(name="os")', 'open(file="x")', 'eval(source="1")',
                'importlib(name="os")', 'mean(numbers=__import__("os"))',
                'mean(numbers=[1])(file_name=__import__("os"))'):
        try:handler.decode_execute(bad,False)
        except UnsupportedCall:pass
        else:raise AssertionError('unsafe call accepted')
    try:utils.execute_multi_turn_func_call(['__import__(name="os")'],*args)
    except UnsupportedCall:pass
    else:raise AssertionError('executor accepted unknown function')
    print('PASS: upstream valid/invalid equivalence, nested callee, positional, unsafe rejection')

if __name__=='__main__':main()
