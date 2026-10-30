"""Standard-library streaming chat client; records actual SSE and server timings."""
import copy, datetime, json, pathlib, time, urllib.request

def utcnow(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

class Client:
    def __init__(self,profile,log): self.profile=profile; self.log=log
    def record(self,event,**data):
        with self.log.open('a',encoding='utf-8') as f:
            f.write(json.dumps({'event':event,'utc':utcnow(),**data},ensure_ascii=False)+'\n')
    def chat(self,messages,tools=None,**overrides):
        p=self.profile
        request_timeout=overrides.pop('request_timeout',600)
        payload={'model':p['profile_id'],'messages':messages,'stream':True,
                 'stream_options':{'include_usage':True},'max_tokens':p['max_tokens'],
                 'seed':p['seed'],'cache_prompt':True,**p['sampling'],
                 'chat_template_kwargs':p['chat_template_kwargs']}
        if tools: payload.update(tools=tools,parallel_tool_calls=False)
        payload.update(overrides)
        self.record('request',payload=payload,profile_id=p['profile_id'],model_hash=p['model_hash'],runtime_build=p['runtime_build'])
        req=urllib.request.Request(p['base_url']+'/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'})
        start=time.perf_counter(); ttft=None; first_kind=None; first_tool_delta=None
        message={'role':'assistant','content':''}; calls={}; usage=None; timings=None; finish=None
        with urllib.request.urlopen(req,timeout=request_timeout) as response:
            for raw in response:
                line=raw.decode('utf-8').strip()
                if not line.startswith('data: '): continue
                data=line[6:]
                if data=='[DONE]': break
                chunk=json.loads(data); elapsed=time.perf_counter()-start
                if elapsed>request_timeout: raise TimeoutError('Request exceeded remaining task wall time')
                self.record('sse',elapsed=elapsed,chunk=chunk)
                if chunk.get('usage'): usage=chunk['usage']
                if chunk.get('timings'): timings=chunk['timings']
                for choice in chunk.get('choices',[]):
                    delta=choice.get('delta',{})
                    if ttft is None and any(delta.get(k) for k in ['content','reasoning_content','tool_calls']):
                        ttft=elapsed; first_kind=next(k for k in ['reasoning_content','content','tool_calls'] if delta.get(k))
                    for k in ['content','reasoning_content']:
                        if delta.get(k): message[k]=message.get(k,'')+delta[k]
                    for tool in delta.get('tool_calls',[]):
                        if first_tool_delta is None: first_tool_delta=elapsed
                        index=tool['index']; call=calls.setdefault(index,{'id':'','type':'function','function':{'name':'','arguments':''}})
                        if tool.get('id'): call['id']=tool['id']
                        for k in ['name','arguments']:
                            if tool.get('function',{}).get(k): call['function'][k]+=tool['function'][k]
                    if choice.get('finish_reason'): finish=choice['finish_reason']
        if calls: message['tool_calls']=[calls[i] for i in sorted(calls)]
        elapsed=time.perf_counter()-start
        valid=bool(calls)
        try:
            for call in calls.values():
                if not call['id'] or not call['function']['name']: valid=False
                if not isinstance(json.loads(call['function']['arguments']),dict): valid=False
        except (ValueError,TypeError): valid=False
        result={'message':message,'finish_reason':finish,'usage':usage,'timings':timings,
                'wall_seconds':elapsed,'ttft_seconds':ttft,'ttft_kind':first_kind,
                'first_tool_delta_seconds':first_tool_delta,
                'first_valid_tool_call_seconds':elapsed if valid else None}
        self.record('response',**result)
        return result
