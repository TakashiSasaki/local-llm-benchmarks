"""Synthetic controls for context-limit classification; no server calls."""
import json,pathlib,sys,types
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import httpx
from openai import BadRequestError
from bfcl_f7_context_limit import classify,install_capture,ContextOverflow,failure_result,run_case
ROOT=pathlib.Path(__file__).resolve().parents[1]

def make_error(status,message):
    request=httpx.Request('POST','http://127.0.0.1:8089/v1/chat/completions')
    response=httpx.Response(status,request=request,json={'error':{'message':message}})
    return BadRequestError(message,response=response,body={'message':message})

def main():
    message='request (70411 tokens) exceeds the available context size (65536 tokens), try increasing it'
    assert classify(400,message)==(70411,65536)
    for status,text in [(500,message),(400,'unrelated 400'),(400,message.replace('65536','4096')),
                        (400,message.replace('70411','65536'))]:assert classify(status,text) is None
    class Dummy:
        error=None
        def _query_prompting(self,data):
            data['inference_input_log']={'messages':[{'role':'user','content':'synthetic'}]}
            raise self.error
    adapter=types.SimpleNamespace(Gemma4LlamaChat=Dummy,CURRENT_CASE='synthetic_case_1')
    folder=ROOT/'.local/validation/bfcl-f7-context-limit-v2-20261113';folder.mkdir(parents=True,exist_ok=False)
    install_capture(adapter,folder);dummy=Dummy();dummy.error=make_error(400,message)
    try:dummy._query_prompting({})
    except ContextOverflow as exc:
        output=failure_result(adapter.CURRENT_CASE,exc)
        assert output['context_limit_failure']['input_tokens']==70411
    else:raise AssertionError('expected context case failure')
    saved=json.loads((folder/'synthetic_case_1.json').read_text(encoding='utf8'))
    assert saved['http_status']==400 and saved['context_tokens']==65536 and saved['request']
    adapter.CURRENT_CASE='synthetic_case_2';dummy.error=make_error(400,'unrelated 400')
    try:dummy._query_prompting({})
    except BadRequestError:pass
    else:raise AssertionError('unrelated 400 was incorrectly swallowed')
    assert not (folder/'synthetic_case_2.json').exists()
    class FakeHandler:
        def __init__(self):self.calls=[]
        def inference(self,entry,*args):
            self.calls.append(entry['id'])
            if entry['id']=='overflow':raise ContextOverflow('overflow',70411,65536,'overflow.json')
            return ([['synthetic response']],{'input_token_count':1})
    handler=FakeHandler()
    first=run_case(handler,{'id':'overflow'},True,False)
    second=run_case(handler,{'id':'next'},True,False)
    assert first['context_limit_failure']['retry'] is False and second['result']==[['synthetic response']]
    assert handler.calls==['overflow','next']
    print('PASS: overflow recorded once; next case runs; unrelated errors propagate')

if __name__=='__main__':main()
