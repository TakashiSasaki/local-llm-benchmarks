"""Record only verified llama.cpp context overflow as a case-level failure."""
import json,pathlib,re
from openai import BadRequestError

_PATTERN=re.compile(r'request \((\d+) tokens\) exceeds the available context size \((\d+) tokens\)')

class ContextOverflow(Exception):
    def __init__(self,case_id,input_tokens,context_tokens,evidence):
        super().__init__(f'input {input_tokens} exceeds context {context_tokens}')
        self.case_id=case_id;self.input_tokens=input_tokens
        self.context_tokens=context_tokens;self.evidence=evidence

def classify(status,message):
    if status!=400:return None
    match=_PATTERN.search(message)
    if not match:return None
    size,limit=map(int,match.groups())
    if limit!=65536 or size<=limit:return None
    return size,limit

def install_capture(adapter,raw_dir):
    """Wrap verified chat adapter; every non-context error is re-raised."""
    cls=adapter.Gemma4LlamaChat;original=cls._query_prompting
    if getattr(original,'_context_capture',False):raise RuntimeError('capture already installed')
    def wrapped(self,inference_data):
        try:return original(self,inference_data)
        except BadRequestError as exc:
            response=exc.response
            size=classify(response.status_code,str(exc))
            if size is None:raise
            case=adapter.CURRENT_CASE
            if not isinstance(case,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',case):raise RuntimeError('invalid case id')
            folder=pathlib.Path(raw_dir);folder.mkdir(parents=True,exist_ok=True)
            path=folder/(case+'.json')
            record={'case_id':case,'http_status':response.status_code,'input_tokens':size[0],
                    'context_tokens':size[1],'outcome':'failed_context_limit',
                    'request':inference_data.get('inference_input_log'),
                    'response_body':response.text}
            if record['request'] is None:raise RuntimeError('missing failed request')
            with path.open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
            raise ContextOverflow(case,*size,path.name) from exc
    wrapped._context_capture=True
    cls._query_prompting=wrapped

def failure_result(case,exc):
    if exc.case_id!=case:raise RuntimeError('context failure case id mismatch')
    return {'id':case,'result':f'Error during inference: input {exc.input_tokens} exceeds context {exc.context_tokens}',
            'context_limit_failure':{'input_tokens':exc.input_tokens,'context_tokens':exc.context_tokens,
                                     'evidence':exc.evidence,'retry':False}}

def run_case(handler,test_case,include_input_log,exclude_state_log):
    try:
        result,metadata=handler.inference(test_case,include_input_log,exclude_state_log)
        return {'id':test_case['id'],'result':result,**metadata}
    except ContextOverflow as exc:
        return failure_result(test_case['id'],exc)
