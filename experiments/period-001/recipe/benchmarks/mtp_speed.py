"""Fixed-length greedy decoding probes, separate from capability scoring."""
import argparse, hashlib, json, pathlib, statistics, sys, time, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.study import ROOT, load, save, snapshot_sources, now, resolve_run

DATASET=ROOT/'datasets/mtp-speed/v1'
PROMPTS=[(p['id'],p['prompt']) for p in load(DATASET/'prompts.json')]

def collect(path, endpoint, model, count=256, repeats=3):
    manifest=load(DATASET/'manifest.json')
    assert hashlib.sha256((DATASET/'prompts.json').read_bytes()).hexdigest()==manifest['files']['prompts.json']
    save(path/'configs/speed-dataset.json',manifest)
    def api(route, payload=None):
        req = urllib.request.Request(endpoint + route, data=json.dumps(payload).encode() if payload is not None else None, headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=600) as f: return json.load(f)
    props = api('/props')
    assert props['model_alias'] == model and props['default_generation_settings']['n_ctx'] == 65536
    results = []
    for index in range(-1, repeats * len(PROMPTS)):
        name, prompt = PROMPTS[index % len(PROMPTS)]
        rendered = api('/apply-template', {'messages':[{'role':'user','content':prompt}], 'chat_template_kwargs':{'enable_thinking':False}})['prompt']
        payload = {'prompt':rendered, 'n_predict':64 if index == -1 else count, 'temperature':0, 'top_p':1, 'top_k':0, 'min_p':0, 'repeat_penalty':1, 'seed':42, 'cache_prompt':False, 'ignore_eos':True, 'stream':False, 'return_tokens':True}
        start = time.monotonic(); response = api('/completion', payload); seconds = time.monotonic() - start
        raw = {'prompt_id':name, 'repeat':index // len(PROMPTS), 'warmup':index == -1, 'request':payload, 'response':response, 'seconds':seconds}
        save(path / 'raw' / ('warmup.json' if index == -1 else f'{index:02d}-{name}.json'), raw)
        if index == -1: continue
        assert response['timings']['predicted_n'] == count, 'Fixed-length probe did not produce the requested count'
        timings = response['timings']
        results.append({'prompt_id':name, 'repeat':raw['repeat'], 'seconds':seconds, 'timings':timings, 'content_sha256':hashlib.sha256(response['content'].encode()).hexdigest(), 'tokens':response.get('tokens')})
        save(path / 'summaries' / 'speed-cases.json', results)
    summary = {'benchmark':'fixed-length-speed', 'outcome':'passed', 'attempted':len(results), 'tokens_per_case':count, 'median_decode_tokens_per_second':statistics.median(r['timings']['predicted_per_second'] for r in results), 'aggregate_decode_tokens_per_second':sum(r['timings']['predicted_n'] for r in results) / (sum(r['timings']['predicted_ms'] for r in results)/1000), 'median_request_seconds':statistics.median(r['seconds'] for r in results), 'draft_tokens':sum(r['timings'].get('draft_n',0) for r in results), 'accepted_draft_tokens':sum(r['timings'].get('draft_n_accepted',0) for r in results), 'scope':'Short prompts, greedy, thinking OFF, fixed output count with ignore_eos; throughput probe, not a quality score. Warmup excluded.'}
    save(path / 'summary.json', summary)
    return summary

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--run',required=True); p.add_argument('--model',required=True); p.add_argument('--endpoint',default='http://127.0.0.1:8089'); a=p.parse_args()
    path=resolve_run(a.run); m=load(path/'manifest.json'); assert m['status']=='planned'; snapshot_sources(path); m.update(status='running',started_at=now()); save(path/'manifest.json',m)
    try:
        collect(path,a.endpoint,a.model); m.update(status='complete',completed_at=now())
    except BaseException as e: m.update(status='failed',error=repr(e)); raise
    finally: save(path/'manifest.json',m)
