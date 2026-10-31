"""Try declared CPU expert placements at unchanged 64K/F16 before capability tests."""
import argparse,json,os,pathlib,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now

def run(a):
    metadata=load(ROOT/a.model_manifest);placements=[int(x) for x in a.cpu_layers.split(',')]
    assert placements==sorted(set(placements)) and all(0<=x<=40 for x in placements)
    parent=create_run(metadata['model']+' '+metadata['quantization']+' MTP capacity placements','mtp-capacity-sweep',run_id=a.prefix,experiment_type='capacity',config={'model':metadata,'profile':a.profile,'cpu_moe_candidates':placements,'context_tokens':65536,'kv_type':'f16','load_mode':'none','capability_answers':0,'policy':'Short MTP ON probes only; first completed placement is not proof of a minimum or long-input capacity.'})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now());save(parent/'manifest.json',m)
    def event(value):
        value={'at':now(),**value}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    trials=[];selected=None
    try:
        target=pathlib.Path(r'C:\LocalLLM\models')/metadata['filename']
        while not target.exists():event({'event':'waiting_for_verified_model','filename':target.name});time.sleep(30)
        for n in placements:
            name=a.prefix+'-cpu'+str(n);event({'event':'placement_start','run':name,'cpu_moe':n})
            command=[sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',a.model_manifest,'--profile',a.profile,'--mtp','on','--cpu-moe',str(n),'--load-mode','none','--pilot']
            with (parent/'logs'/('cpu'+str(n)+'.log')).open('w',encoding='utf-8') as f:
                result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
            child=ROOT/'runs'/name;cm=load(child/'manifest.json');clean=load(child/'configs/cleanup.json');assert clean['server_stopped'],'Owned model did not stop'
            entry={'run':name,'cpu_moe':n,'status':cm['status'],'exit_code':result.returncode,'error':cm.get('error'),'resource_guard':clean['resource_guard']}
            if (child/'summaries/memory.json').exists():entry['memory']=load(child/'summaries/memory.json')
            trials.append(entry);event({'event':'placement_finished',**entry})
            if cm['status']=='complete' and result.returncode==0:selected=n;break
            if clean['resource_guard']:event({'event':'ram_guard_stop','reason':'Further CPU placement was not attempted after the RAM protective stop'});break
        save(parent/'summary.json',{'outcome':'passed' if selected is not None else 'failed','headline':'MTP short-probe placement search','selected_cpu_moe':selected,'trials':trials,'capability_answers':0,'scope':'Capacity evidence only; no BFCL or HumanEval score. All trials preserve 65536 context and F16 target/draft KV.'})
        m.update(status='complete',completed_at=now())
    except BaseException as e:m.update(status='failed',error=repr(e));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--model-manifest',required=True);p.add_argument('--profile',required=True);p.add_argument('--cpu-layers',default='34,35,36,37,38');run(p.parse_args())
