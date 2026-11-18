"""Synthetic upstream BFCL generation controls with no model or network."""
import json, pathlib, sys, types
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from bfcl_f7_gemma4_guarded_adapter_v3 import GuardedGemma4
from bfcl_f7_call_guard_v3 import UnsupportedCall
from bfcl_f7_guarded_executor_v3 import install_guarded_executor
import bfcl_eval

def main():
    install_guarded_executor()
    docs=pathlib.Path(bfcl_eval.__file__).parent/'data/multi_turn_func_doc/math_api.json'
    functions=[json.loads(x) for x in docs.read_text(encoding='utf8').splitlines()]
    mean=next(f for f in functions if f['name']=='mean')
    def entry():
        return {'id':'multi_turn_base_999','function':[mean],
                'question':[[{'role':'user','content':'Calculate the mean.'}]],
                'involved_classes':['MathAPI'],'initial_config':{}}
    h=GuardedGemma4('synthetic',0.001,'synthetic-generation',False)
    responses=iter(['mean(numbers=[1,2,3])','The mean is 2.'])
    def fake(self,data):
        return SimpleNamespace(choices=[SimpleNamespace(text=next(responses))],
            usage=SimpleNamespace(prompt_tokens=1,completion_tokens=1)),0.01
    h._query_prompting=types.MethodType(fake,h)
    result,metadata=h.inference(entry(),True,False)
    assert result==[['mean(numbers=[1,2,3])','The mean is 2.']]
    assert '2' in repr(metadata['inference_log'])
    responses=iter(['mean(numbers=[1,2,3])(file_name="README.md")','Cannot complete.'])
    result,metadata=h.inference(entry(),True,False)
    assert len(result[0])==2 and 'Error during execution:' in repr(metadata['inference_log'])
    responses=iter(['__import__(name="os")'])
    try:h.inference(entry(),True,False)
    except UnsupportedCall:pass
    else:raise AssertionError('unsafe model call was not stopped')
    print('PASS: upstream generation, tool response, and guard-stop controls')

if __name__=='__main__':main()
