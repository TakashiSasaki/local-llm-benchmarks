"""Intercept malformed BFCL calls without evaluating syntactically invalid code.

Valid calls are restricted to direct documented method names and literal
arguments before the pinned upstream executor is invoked. This adapter is not
an OS sandbox. A guard stop leaves the evaluation incomplete.
"""
import importlib,inspect
from bfcl_f7_call_guard import UnsupportedCall,enable_malformed_executor,validate_call_text

def install_guarded_executor():
    utils=importlib.import_module('bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils')
    base=importlib.import_module('bfcl_eval.model_handler.base_handler')
    checker=importlib.import_module('bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker')
    original=utils.execute_multi_turn_func_call
    if getattr(original,'_guarded_executor',False):raise RuntimeError('guarded executor already installed')

    def guarded(func_call_list,initial_config,involved_classes,model_name,test_entry_id,
                long_context=False,is_evaL_run=False):
        args=(initial_config,involved_classes,model_name,test_entry_id)
        opts={'long_context':long_context,'is_evaL_run':is_evaL_run}
        _,instances=original([], *args, **opts)
        method_names=set()
        for obj in instances.values():
            for name,_ in inspect.getmembers(obj,predicate=inspect.ismethod):
                if not name.startswith('_'):method_names.add(name)
        output=[]
        for call in func_call_list:
            try:compile(call,'<string>','eval')
            except SyntaxError as exc:
                # The exact observed upstream malformed form has no named
                # callee. Reject quoted nested-call spellings because upstream's
                # regex could rewrite inside strings before it compiles them.
                mapping={name:'guard_marker' for name in method_names}
                rewritten=utils._process_method_calls(call,mapping)
                if not call.startswith('(') or rewritten != call:
                    raise UnsupportedCall('malformed reconstructed call requires review')
                output.append('Error during execution: '+str(exc))
                continue
            validate_call_text(call,method_names,strict=True)
            result,instances=original([call],*args,**opts)
            output.extend(result)
        return output,instances

    guarded._guarded_executor=True
    utils.execute_multi_turn_func_call=guarded
    base.execute_multi_turn_func_call=guarded
    checker.execute_multi_turn_func_call=guarded
    enable_malformed_executor()
