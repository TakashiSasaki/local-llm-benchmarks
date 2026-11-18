"""Synthetic controls for the pinned BFCL guard and evaluator integration."""
import copy, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bfcl_eval.eval_checker import eval_runner
from bfcl_f7_gemma4_guarded_adapter_v4 import GuardedGemma4
from bfcl_f7_guarded_scoring_v4 import install_case_allowlists
from bfcl_f7_call_guard_v4 import UnsupportedCall
from bfcl_f7_guarded_executor_v4 import install_guarded_executor

def main():
    install_guarded_executor();install_case_allowlists(eval_runner)
    h=GuardedGemma4('synthetic',0.001,'synthetic-guard-test',False)
    entry={'id':'multi_turn_base_999','function':[{'name':'mean'}],
           'question':[[{'role':'user','content':'synthetic'}]],
           'involved_classes':['MathAPI'],'initial_config':{}}
    def multi(response,truth="mean(numbers=[1,2,3])"):
        return eval_runner._evaluate_single_multi_turn_entry(
            h,'multi_turn_base_999',[[response]],[[truth]],copy.deepcopy(entry),
            'synthetic-guard-test','multi_turn_base')
    assert multi('mean(numbers=[1,2,3])')['valid']
    assert not multi('mean(numbers=[4,5,6])')['valid']
    assert not multi('mean(numbers=[1,2,3])(file_name="README.md")')['valid']
    # A genuinely undefined function receives the upstream NameError result;
    # it is not a guard rejection or arbitrary evaluated code.
    assert not multi('get_ticket_login_status()')['valid']
    assert not hasattr(h,'allowed_names')
    # The upstream f7 parser discards literal positional arguments. The guard
    # must not reject them before upstream applies that behavior.
    h.allowed_names={'mean'}
    assert h.decode_execute('mean([1,2,3])',False)==['mean()']
    try: h.decode_execute('mean(__import__("os"))',False)
    except UnsupportedCall: pass
    else: raise AssertionError('unsafe positional argument was not stopped')
    del h.allowed_names
    try: multi('__import__(name="os")')
    except UnsupportedCall: pass
    else: raise AssertionError('unsafe call was not stopped')
    assert not hasattr(h,'allowed_names')
    other=copy.deepcopy(entry);other['function']=[{'name':'logarithm'}]
    try:
        eval_runner._evaluate_single_multi_turn_entry(h,'multi_turn_base_998',
            [['mean(numbers=[1,2,3])']],[["mean(numbers=[1,2,3])"]],other,
            'synthetic-guard-test','multi_turn_base')
    except UnsupportedCall: pass
    else: raise AssertionError('allowlist leaked between cases')
    assert not hasattr(h,'allowed_names')
    agent={'function':[{'name':'mean'}],'question':[[{'role':'user','content':'synthetic'}]]}
    result=eval_runner._evaluate_single_agentic_entry(h,'memory_kv_999',
        [['mean(numbers=[1,2,3])','The answer is 2.']],['2'],agent,
        'synthetic-guard-test','memory_kv')
    assert result['valid'] and not hasattr(h,'allowed_names')
    print('PASS: correct/wrong, blocked call, case isolation and agentic scoring controls')

if __name__=='__main__': main()
