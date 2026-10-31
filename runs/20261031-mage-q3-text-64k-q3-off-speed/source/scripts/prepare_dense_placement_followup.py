"""Probe higher dense-model GPU placement after the matched comparison has stopped."""
import argparse,html,json,os,pathlib,socket,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,create_run,snapshot_sources,resolve_run

def admissible(result,limit):
    peak=result.get('memory',{}).get('peak_gpu_used_mib_system_total')
    return result['status']=='complete' and result['exit_code']==0 and not result['resource_guard'] and peak is not None and peak<=limit

def run(a):
    plan=load(ROOT/a.plan);meta=load(ROOT/plan['model_manifest']);candidates=plan['gpu_layer_candidates']
    assert candidates==sorted(set(candidates)) and all(20<n<=meta['decoder_layers']+1 for n in candidates)
    parent=create_run(meta['model']+' Q3 higher GPU placement','dense-gpu-placement',run_id=plan['prefix'],experiment_type='capacity',config={'plan':plan,'capability_answers':0})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now(),report='reports/'+parent.name+'/index.html');save(parent/'manifest.json',m)
    def event(**v):
        v={'at':now(),**v}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(v)+'\n')
        print(json.dumps(v),flush=True)
    def trial(n,pilot):
        profile=load(ROOT/plan['profile']);args=profile['server_args'];args[args.index('-ngl')+1]=str(n)
        profile['placement_note']=f'Explicit dense placement experiment: -ngl {n} including output; {meta["decoder_layers"]+1-n} CPU decoder layers, {n-1} GPU decoder layers plus output. Same 64K/F16, MTP OFF.'
        if pilot:args+=['-lv','4']
        rel=parent.relative_to(ROOT)/'configs'/('ngl'+str(n)+('-probe' if pilot else '-speed')+'.json');save(ROOT/rel,profile)
        name=parent.name+'-ngl'+str(n)+('-probe' if pilot else '-throughput')
        command=[sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',plan['model_manifest'],'--profile',rel.as_posix(),'--mtp','off','--cpu-moe','0','--load-mode','none','--pilot' if pilot else '--speed-only']
        event(event='trial_start',run=name,ngl=n,pilot=pilot)
        with (parent/'logs'/(name+'.log')).open('w',encoding='utf-8') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        child=resolve_run(name);cm=load(child/'manifest.json');cleanup=load(child/'configs/cleanup.json');assert cleanup['server_stopped']
        result={'run':name,'ngl_including_output':n,'cpu_decoder_layers':meta['decoder_layers']+1-n,'gpu_decoder_layers':n-1,'status':cm['status'],'exit_code':r.returncode,'error':cm.get('error'),'resource_guard':cleanup['resource_guard'],'memory':load(child/'summaries/memory.json') if (child/'summaries/memory.json').exists() else {}}
        speed=resolve_run(name+'-speed')/'summary.json'
        if speed.exists():result['speed']=load(speed)
        event(event='trial_finished',**result);return result
    try:
        waiting=resolve_run(plan['wait_for_run']);event(event='waiting_for_matched_q3',run=waiting.name)
        while load(waiting/'manifest.json')['status'] not in ['complete','failed']:time.sleep(30)
        # A preceding failure remains evidence; do not restart it or take over an occupied port.
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Port occupied; no process is replaced'
        assert (pathlib.Path(r'C:\LocalLLM\models')/meta['filename']).exists(),'Q3 model unavailable after preceding trial'
        trials=[];selected=None
        for n in candidates:
            result=trial(n,True);result['admissible']=admissible(result,plan['maximum_peak_gpu_mib']);trials.append(result)
            if not result['admissible']:break
            selected=n
        baseline=resolve_run(plan['baseline_speed_run']);baseline_data=None
        if (baseline/'manifest.json').exists() and load(baseline/'manifest.json')['status']=='complete':baseline_data={'run':baseline.name,'summary':load(baseline/'summary.json')}
        if baseline_data is None:
            fallback=trial(20,False)
            if fallback['status']=='complete':baseline_data={'run':fallback['run']+'-speed','summary':fallback['speed']}
        throughput=trial(selected,False) if selected is not None else None
        ratio=None
        if baseline_data and throughput and throughput['status']=='complete':ratio=throughput['speed']['median_decode_tokens_per_second']/baseline_data['summary']['median_decode_tokens_per_second']
        summary={'outcome':'passed' if throughput and throughput['status']=='complete' else 'partial','headline':'Q3 GPU layer capacity and separate fixed-length throughput','selected_ngl_including_output':selected,'selected_cpu_decoder_layers':meta['decoder_layers']+1-selected if selected else None,'trials':trials,'baseline':baseline_data,'selected_throughput':throughput,'fixed_length_speedup':ratio,'capability_answers':0,'scope':plan['policy']}
        save(parent/'summary.json',summary);m.update(status='complete',completed_at=now())
    except BaseException as error:m.update(status='failed',error=repr(error));raise
    finally:
        save(parent/'manifest.json',m);out=ROOT/'reports'/parent.name;out.mkdir(parents=True,exist_ok=True)
        result=load(parent/'summary.json') if (parent/'summary.json').exists() else {'status':m['status'],'error':m.get('error')}
        (out/'index.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><title>Q3 GPU配置の容量・速度</title><h1>Q3 GPU配置の容量・速度</h1><p>能力得点の測定とは別です。最大は試した候補内の値で、長い生成時の速度・安定性を保証しません。</p><pre>'+html.escape(json.dumps(result,ensure_ascii=False,indent=2))+'</pre><a href="../../runs/'+parent.name+'/manifest.json">起動条件と証拠</a></html>',encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);run(p.parse_args())
