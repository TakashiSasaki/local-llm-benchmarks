"""Sequential single-GPU matrix collection, reusing only completed named cells."""
import argparse, json, os, pathlib, subprocess, sys, time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now,resolve_run

def run(a):
    if a.reference_iq3_prefix:resolve_run(a.reference_iq3_prefix)
    cell_runs={q+'-'+m:(a.reference_iq3_prefix if q=='iq3' and a.reference_iq3_prefix else a.prefix)+'-'+q+'-'+m for q in ['iq3','q4'] for m in ['off','on']}
    parent=create_run('Empero 3bit / 4bit MTP matrix'+(' / Q4 load '+a.q4_load_mode if a.q4_load_mode else ''),'quantization-mtp-matrix',run_id=a.prefix,config={'expected_cells':4,'expected_capability_conditions':16,'expected_capability_answers':800,'expected_new_answers':400 if a.reference_iq3_prefix else 800,'referenced_answers':400 if a.reference_iq3_prefix else 0,'reference_iq3_prefix':a.reference_iq3_prefix,'q4_load_mode':a.q4_load_mode,'cell_runs':cell_runs,'order':['iq3-off','iq3-on','q4-off','q4-on'],'context_tokens':65536,'cpu_moe_layers':34,'short_prompt_only':True})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now(),report='reports/'+a.prefix+'/index.html');save(parent/'manifest.json',m)
    def event(value):
        value={'at':now(),**value}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    def command(name,manifest,mtp,pilot=False,load_mode=None):
        args=[sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',manifest,'--mtp',mtp,'--benchmark-python',str(a.benchmark_python)]
        if pilot:args+=['--pilot']
        if load_mode:args+=['--load-mode',load_mode]
        with (parent/'logs'/(name+'.log')).open('w',encoding='utf-8') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:raise RuntimeError('Cell failed: '+name)
    try:
        children=[]
        for quant in ['iq3','q4']:
            metadata='configs/models/qwen38-35b-distill-'+('iq3-m' if quant=='iq3' else 'q4-k-m')+'.json'
            file=pathlib.Path(r'C:\LocalLLM\models')/load(ROOT/metadata)['filename']
            while not file.exists() and not (quant=='iq3' and a.reference_iq3_prefix):event({'event':'waiting_for_model','quant':quant});time.sleep(30)
            if quant=='q4':
                pilot=a.prefix+'-q4-preflight';event({'event':'preflight_start','run':pilot});command(pilot,metadata,'on',True,a.q4_load_mode)
            for mtp in ['off','on']:
                name=cell_runs[quant+'-'+mtp];p=ROOT/'runs'/name;children.append(name)
                if p.exists():
                    while load(p/'manifest.json')['status']=='running':event({'event':'waiting_for_existing_cell','run':name});time.sleep(30)
                    assert load(p/'manifest.json')['status']=='complete','Existing cell is not complete: '+name
                    cfg=load(p/'manifest.json')['config'];pa=cfg['profile']['server_args']
                    assert cfg['model']['sha256']==load(ROOT/metadata)['sha256'] and pa[pa.index('--n-cpu-moe')+1]=='34' and cfg['profile']['context_tokens']==65536
                    event({'event':'referenced_complete_cell','run':name,'fresh_inference':False})
                else:event({'event':'cell_start','run':name});command(name,metadata,mtp,load_mode=a.q4_load_mode if quant=='q4' else None)
                result=load(p/'summary.json');event({'event':'cell_complete','run':name,'summary':result})
                subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report_mtp_study.py'),'--prefix',a.prefix],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        save(parent/'summary.json',{'outcome':'passed','headline':'Four matched-placement quantization/MTP cells assembled','child_runs':children,'conditions':16,'answers':800,'new_answers':400 if a.reference_iq3_prefix else 800,'referenced_answers':400 if a.reference_iq3_prefix else 0,'scope':'Collection completed; original referenced run IDs are preserved. Individual capability pass counts remain separate.'});m.update(status='complete',completed_at=now())
    except BaseException as e:m.update(status='failed',error=repr(e));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='20261031-empero-quant-mtp-64k');p.add_argument('--benchmark-python',type=pathlib.Path,required=True);p.add_argument('--reference-iq3-prefix');p.add_argument('--q4-load-mode',choices=['none','mmap']);run(p.parse_args())
