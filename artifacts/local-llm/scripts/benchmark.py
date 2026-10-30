"""Fixed common texts, uncached requests and repeated-prefix measurements.

Run only after smoke tests pass. Results are configuration-specific observations.
"""
import argparse, datetime, json, urllib.request
from client import Client
from memory import Monitor
from server import ROOT,load_profile

def common_text(lines):
    return '\n'.join(f'entry={i:05d} status=OK subsystem=worker task=read latency_ms={10+i%19} note=fixed-fixture' for i in range(lines))

def tokens(profile,messages):
    def post(path,payload):
        req=urllib.request.Request(profile['base_url']+path,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=15) as r: return json.load(r)
    rendered=post('/apply-template',{'messages':messages,'chat_template_kwargs':profile['chat_template_kwargs']})
    return len(post('/tokenize',{'content':rendered['prompt'],'add_special':False})['tokens'])

def bench(name,repeats,purpose='performance',background_downloads=False):
    p=load_profile(name)
    state=json.loads((ROOT/'server-state.json').read_text())
    if state['profile']!=name or not state['ready']: raise RuntimeError('Matching server is not ready')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'); run_id=purpose+'-'+name+'-'+stamp
    c=Client(p,ROOT/'runs'/f'{run_id}.jsonl'); monitor=Monitor(state['pid'],ROOT/'runs'/f'{run_id}.memory.jsonl').start()
    c.record('benchmark_start',profile=p,purpose=purpose,background_downloads_active=background_downloads)
    results=[]
    try:
        for size,lines in [('short',22),('medium',166),('long',333)]:
            source=common_text(lines)
            text_path=ROOT/'docs'/f'benchmark-input-{size}.txt'
            if text_path.exists() and text_path.read_text(encoding='utf-8')!=source: raise RuntimeError('Common input fixture differs')
            text_path.write_text(source,encoding='utf-8')
            for repeat in range(repeats):
                messages=[{'role':'system','content':'ログを読み、指示された短い確認だけを返してください。'}, {'role':'user','content':source+'\nログを確認し、「確認済み」とだけ答えてください。'}]
                count=tokens(p,messages)
                if count+p['max_tokens']>p['context_tokens']: raise RuntimeError('Benchmark input plus output allowance exceeds context')
                cold=c.chat(messages,cache_prompt=False)
                results.append({'size':size,'repeat':repeat,'cache_condition':'prefix_not_reused','actual_rendered_input_tokens':count,**cold})
                messages.extend([cold['message'],{'role':'user','content':'同じログを再利用し、「再確認済み」とだけ答えてください。'}])
                count=tokens(p,messages)
                if count+p['max_tokens']>p['context_tokens']: raise RuntimeError('Follow-up exceeds context')
                warm=c.chat(messages,cache_prompt=True)
                results.append({'size':size,'repeat':repeat,'cache_condition':'same_prefix_appended','actual_rendered_input_tokens':count,**warm})
    finally: memory=monitor.stop()
    summary={'run_id':run_id,'purpose':purpose,'background_downloads_active':background_downloads,'profile':p,'load_measurement':state,'memory':memory,'measurements':results,'os_file_cache':'not forcibly cleared','prefix_cache':'actual reused tokens from server response/log only','gpu_expert_cache':'disabled','repeat_count':repeats}
    (ROOT/'runs'/f'{run_id}.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'run_id':run_id,'measurements':len(results),'memory':memory},ensure_ascii=False))
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('profile',choices=['qwen','lfm','glm']); ap.add_argument('--repeats',type=int,choices=[1,3],default=1); ap.add_argument('--purpose',choices=['performance','capacity-check'],default='performance'); ap.add_argument('--background-downloads',action='store_true'); a=ap.parse_args(); bench(a.profile,a.repeats,a.purpose,a.background_downloads)
