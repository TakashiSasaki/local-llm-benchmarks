"""SSE transport checks without a model; never included in model results."""
import http.server, json, pathlib, tempfile, threading
from client import Client
from memory import snapshot
from server import ROOT

class Handler(http.server.BaseHTTPRequestHandler):
    packets=[]; payload=None
    def log_message(self,*args): pass
    def do_POST(self):
        Handler.payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
        for packet in self.packets:
            self.wfile.write(('data: '+json.dumps(packet,ensure_ascii=False)+'\n\n').encode()); self.wfile.flush()
        self.wfile.write(b'data: [DONE]\n\n')

def run():
    server=http.server.HTTPServer(('127.0.0.1',0),Handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    p={'profile_id':'synthetic-transport-only','model_hash':'not-a-model','runtime_build':'not-a-runtime','sampling':{'temperature':.1},'chat_template_kwargs':{},'max_tokens':512,'seed':42,'base_url':f'http://127.0.0.1:{server.server_port}'}
    results=[]
    def check(name,ok):
        results.append({'name':name,'passed':bool(ok)})
        if not ok: raise AssertionError(name)
    try:
        with tempfile.TemporaryDirectory(prefix='client-',dir=ROOT/'validation') as temp:
            client=Client(p,pathlib.Path(temp)/'test.jsonl')
            Handler.packets=[{'choices':[{'delta':{'role':'assistant'}}]},
                {'choices':[{'delta':{'reasoning_content':'確認中'}}]},
                {'choices':[{'delta':{'tool_calls':[{'index':0,'id':'call_test','function':{'name':'inspect_fixture','arguments':'{"path":"資料 '}}]}}]},
                {'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'arguments':'[日本語].txt"}'}}]}}]},
                {'choices':[{'delta':{},'finish_reason':'tool_calls'}],'usage':{'prompt_tokens':40,'completion_tokens':12,'total_tokens':52},'timings':{'prompt_n':40,'predicted_n':12}}]
            r=client.chat([{'role':'user','content':'transport test'}],request_timeout=5)
            check('streamed_unicode_tool_json',json.loads(r['message']['tool_calls'][0]['function']['arguments'])=={'path':'資料 [日本語].txt'})
            check('reasoning_separate',r['message']['reasoning_content']=='確認中' and r['ttft_kind']=='reasoning_content')
            check('actual_usage_and_timings',r['usage']['completion_tokens']==12 and r['timings']['prompt_n']==40)
            check('valid_tool_timestamp',r['first_valid_tool_call_seconds'] is not None)
            check('transport_timeout_not_sent_as_model_argument','request_timeout' not in Handler.payload)
            Handler.packets=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'bad','function':{'name':'inspect_fixture','arguments':'not JSON'}}]}}]}, {'choices':[{'delta':{},'finish_reason':'stop'}]}]
            r=client.chat([{'role':'user','content':'invalid tool test'}])
            check('malformed_tool_not_valid',r['first_valid_tool_call_seconds'] is None)
            Handler.packets=[{'choices':[{'delta':{'content':'完了'}}]},{'choices':[{'delta':{},'finish_reason':'stop'}]}]
            r=client.chat([{'role':'user','content':'plain response'}])
            check('plain_text_is_not_tool',r['message']['content']=='完了' and r['first_valid_tool_call_seconds'] is None)
        import os
        memory=snapshot(os.getpid())
        check('actual_process_memory_available',memory['process_working_set_bytes']>0 and memory['available_ram_bytes']>0)
    finally: server.shutdown(); server.server_close()
    (ROOT/'runs/client-selftest.json').write_text(json.dumps({'type':'synthetic_transport_and_local_memory','results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(results),'model_trials':0}))

if __name__=='__main__': run()
