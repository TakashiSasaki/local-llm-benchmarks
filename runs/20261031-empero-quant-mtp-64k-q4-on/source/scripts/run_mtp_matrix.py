"""Sequential single-GPU matrix collection, reusing only completed named cells."""
import argparse, json, os, pathlib, subprocess, sys, time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now

def run(a):
    parent=create_run('Empero 3bit / 4bit MTP matrix','quantization-mtp-matrix',run_id=a.prefix,config={'expected_cells':4,'expected_capability_conditions':16,'expected_capability_answers':800,'order':['iq3-off','iq3-on','q4-off','q4-on'],'context_tokens':65536,'cpu_moe_layers':34,'short_prompt_only':True})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now(),report='reports/'+a.prefix+'/index.html');save(parent/'manifest.json',m)
    def event(value):
        value={'at':now(),**value}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    def command(name,manifest,mtp,pilot=False):
        args=[sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',manifest,'--mtp',mtp,'--benchmark-python',str(a.benchmark_python)]
        if pilot:args+=['--pilot']
        with (parent/'logs'/(name+'.log')).open('w',encoding='utf-8') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:raise RuntimeError('Cell failed: '+name)
    try:
        children=[]
        for quant in ['iq3','q4']:
            metadata='configs/models/qwen38-35b-distill-'+('iq3-m' if quant=='iq3' else 'q4-k-m')+'.json'
            file=pathlib.Path(r'C:\LocalLLM\models')/load(ROOT/metadata)['filename']
            while not file.exists():event({'event':'waiting_for_model','quant':quant});time.sleep(30)
            if quant=='q4':
                pilot=a.prefix+'-q4-preflight';event({'event':'preflight_start','run':pilot});command(pilot,metadata,'on',True)
            for mtp in ['off','on']:
                name=a.prefix+'-'+quant+'-'+mtp;p=ROOT/'runs'/name;children.append(name)
                if p.exists():
                    while load(p/'manifest.json')['status']=='running':event({'event':'waiting_for_existing_cell','run':name});time.sleep(30)
                    assert load(p/'manifest.json')['status']=='complete','Existing cell is not complete: '+name
                else:event({'event':'cell_start','run':name});command(name,metadata,mtp)
                result=load(p/'summary.json');event({'event':'cell_complete','run':name,'summary':result})
                subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report_mtp_study.py'),'--prefix',a.prefix],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        save(parent/'summary.json',{'outcome':'passed','headline':'Four fresh matched-placement quantization/MTP cells collected','child_runs':children,'conditions':16,'answers':800,'scope':'Collection completed; individual capability pass counts remain separate.'});m.update(status='complete',completed_at=now())
    except BaseException as e:m.update(status='failed',error=repr(e));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='20261031-empero-quant-mtp-64k');p.add_argument('--benchmark-python',type=pathlib.Path,required=True);run(p.parse_args())
