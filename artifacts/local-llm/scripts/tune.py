"""Bounded placement then generation-thread exploration, one setting at a time.

Raw fixed-length completions measure hardware throughput only. Normal chat,
tool correctness and final timing repeats are checked separately afterward.
"""
import argparse, copy, datetime, json, pathlib, time, urllib.request
from benchmark import common_text
from memory import Monitor, snapshot
from server import ROOT, get_json, load_profile, start, stop

GPU_LIMIT_MIB=7168
def save(name,p): (ROOT/'profiles'/f'{name}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
def setarg(args,key,value):
    if key in args: args[args.index(key)+1]=str(value)
    else: args.extend([key,str(value)])

def probe(p):
    outputs=[]; prefix=common_text(22)+'\nentry='
    for reuse in [False,True]:
        payload={'prompt':prefix+('00023' if reuse else ''),'n_predict':256,'ignore_eos':True,'stream':False,'cache_prompt':reuse,'seed':p['seed'],**p['sampling']}
        request=urllib.request.Request(p['base_url']+'/completion',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        t=time.perf_counter()
        with urllib.request.urlopen(request,timeout=180) as response: result=json.load(response)
        outputs.append({'cache_reuse_requested':reuse,'wall_seconds':time.perf_counter()-t,'payload':payload,'response':result})
    return outputs

def tune(model,background_downloads):
    baseline=load_profile(model)
    if baseline.get('diagnostic_cpu_only'): raise ValueError('CUDA baseline required')
    inspected=json.loads((ROOT/'docs'/f'gguf-inspection-{model}.json').read_text(encoding='utf-8'))
    arch=inspected['metadata']['general.architecture']; blocks=inspected['metadata'][arch+'.block_count']
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'); experiments=[]
    def test(cpu_layers,threads,label):
        p=copy.deepcopy(baseline); args=p['server_args']
        if '--cpu-moe' in args: args.remove('--cpu-moe')
        setarg(args,'--n-cpu-moe',cpu_layers); setarg(args,'-t',threads)
        p.update(profile_id=f'{model}-explore-ncpu{cpu_layers}-t{threads}-{stamp}',status='exploration-only')
        key=f'{model}-explore'; save(key,p)
        record={'cpu_moe_layers':cpu_layers,'threads':threads,'label':label,'profile':p,'background_downloads_active':background_downloads,'passed':False}
        mon=None
        try:
            start(key); state=json.loads((ROOT/'server-state.json').read_text())
            initial=snapshot(state['pid']); record['after_load_memory']=initial
            if initial['gpu_used_mib'] is None: raise RuntimeError('GPU telemetry unavailable')
            if initial['gpu_used_mib']>GPU_LIMIT_MIB:
                record['failure']='gpu_margin'; return record
            mon=Monitor(state['pid'],ROOT/'runs'/f"tune-{p['profile_id']}.memory.jsonl").start()
            record['probes']=probe(p)
            record['memory']=mon.stop(); mon=None
            record['gpu_margin_ok']=record['memory']['peak_gpu_used_mib_system_total']<=GPU_LIMIT_MIB
            record['passed']=record['gpu_margin_ok'] and all(x['response'].get('tokens_predicted')==256 for x in record['probes'])
            record['total_probe_seconds']=sum(x['wall_seconds'] for x in record['probes'])
        except Exception as e: record['failure']=str(e)
        finally:
            if mon: record['memory']=mon.stop()
            stop()
            experiments.append(record)
            (ROOT/'runs'/f'tuning-{model}-{stamp}.json').write_text(json.dumps({'model':model,'baseline':baseline,'experiments':experiments,'status':'exploring'},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'model':model,'label':label,'cpu_layers':cpu_layers,'threads':threads,'passed':record['passed'],'seconds':record.get('total_probe_seconds'),'gpu_peak':record.get('memory',{}).get('peak_gpu_used_mib_system_total'),'failure':record.get('failure')},ensure_ascii=False),flush=True)
        return record
    # Stop only the current managed server. Downloads and unrelated applications continue.
    stop(); base=test(blocks,8,'all-experts-cpu'); last_safe=base; failed_layers=None
    if not base['passed']: raise RuntimeError('Starting placement failed; inspect tuning log')
    no_gain=0
    for offloaded in range(4,blocks+1,4):
        candidate=test(blocks-offloaded,8,'placement')
        if not candidate['passed']:
            failed_layers=blocks-offloaded; break
        if candidate['total_probe_seconds']>=last_safe['total_probe_seconds']*.98: no_gain+=1
        else: no_gain=0
        last_safe=candidate
        if no_gain>=2: break
    if failed_layers is not None and last_safe['cpu_moe_layers']-failed_layers>=4:
        test(failed_layers+2,8,'placement-memory-boundary')
    placements=[r for r in experiments if r['passed']]
    best=min(placements,key=lambda r:r['total_probe_seconds'])
    for threads in [6,12,16]: test(best['cpu_moe_layers'],threads,'threads')
    safe=[r for r in experiments if r['passed']]
    winner=min(safe,key=lambda r:r['total_probe_seconds'])
    # Retain eight threads unless the best alternative improves total probe time by 5%.
    eight=min((r for r in safe if r['threads']==8),key=lambda r:r['total_probe_seconds'])
    if winner['threads']!=8 and winner['total_probe_seconds']>eight['total_probe_seconds']*.95: winner=eight
    adopted=copy.deepcopy(winner['profile']); adopted.update(profile_id=model+'-eval-v1',status='tuned-provisional; chat smoke and idle timing repeats required')
    save(model+'-baseline',baseline); save(model,adopted)
    report={'model':model,'baseline':baseline,'experiments':experiments,'status':'selected-provisionally','selected':adopted,'gpu_limit_mib':GPU_LIMIT_MIB,'background_downloads_active':background_downloads,'selection_rule':'lowest cold+warm fixed-256-token wall time among safe configurations; keep t8 within 5%; normal-chat repeats still required'}
    (ROOT/'runs'/f'tuning-{model}-{stamp}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'model':model,'selected_cpu_layers':winner['cpu_moe_layers'],'selected_threads':winner['threads'],'profile_id':adopted['profile_id']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('model',choices=['qwen','lfm','glm']); ap.add_argument('--background-downloads',action='store_true'); a=ap.parse_args(); tune(a.model,a.background_downloads)
