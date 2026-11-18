"""Collect one pinned Q4_K_M model's MTP controls, retaining earlier references."""
import argparse,json,os,pathlib,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now,resolve_run

def run(a):
    definition=load(ROOT/a.definition);metadata=load(ROOT/definition['model_manifest'])
    assert metadata['quantization']=='Q4_K_M','This pair protocol is for Q4_K_M'
    cells={'q4-'+mtp:a.prefix+'-q4-'+mtp for mtp in ['off','on']}
    config={**definition,'study_type':'mtp-pair','cell_runs':cells,'q4_load_mode':definition['load_mode'],'expected_new_answers':400,'referenced_answers':0}
    parent=create_run(metadata['model']+' '+metadata['quantization']+' MTP comparison','quantization-mtp-pair',run_id=a.prefix,config=config)
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now(),report='reports/'+a.prefix+'/index.html');save(parent/'manifest.json',m)
    def event(value):
        value={'at':now(),**value}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    def execute(command,filename):
        with (parent/'logs'/filename).open('w',encoding='utf-8') as f:
            result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        if result.returncode:raise RuntimeError('Driver failed: '+filename)
    def collect(name,mtp,pilot=False):
        command=[sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',definition['model_manifest'],'--profile',definition['profile'],'--mtp',mtp,'--cpu-moe',str(definition['cpu_moe_layers']),'--load-mode',definition['load_mode'],'--benchmark-python',str(a.benchmark_python)]
        if pilot:command.append('--pilot')
        execute(command,name+'.log')
    def report():
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report_mtp_pair.py'),'--prefix',a.prefix],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        target=pathlib.Path(r'C:\LocalLLM\models')/metadata['filename']
        while not target.exists():event({'event':'waiting_for_verified_model','filename':target.name});time.sleep(30)
        pilot=a.prefix+'-preflight';event({'event':'preflight_start','run':pilot});collect(pilot,'on',True)
        for mtp,name in cells.items():
            event({'event':'cell_start','run':name});collect(name,mtp.rsplit('-',1)[1]);event({'event':'cell_complete','run':name});report()
        audits=[]
        for name in cells.values():
            event({'event':'policy_audit_start','source':name})
            execute([str(a.benchmark_python),'-B',str(ROOT/'scripts/audit_humaneval_policy.py'),'--study',name],'audit-'+name+'.log');audits.append(name+'-he-policy-audit')
        save(parent/'summary.json',{'outcome':'passed','headline':metadata['model']+' Q4_K_M matched MTP controls complete','child_runs':list(cells.values()),'audit_runs':audits,'conditions':8,'answers':400,'new_answers':400,'referenced_answers':0,'scope':'400 new capability answers. Earlier models are linked separately and are not fresh inference.'})
        m.update(status='complete',completed_at=now());save(parent/'manifest.json',m);report()
    except BaseException as e:m.update(status='failed',error=repr(e));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--definition',default='configs/qwen36-q4-mtp-64k.json');p.add_argument('--benchmark-python',type=pathlib.Path,required=True);run(p.parse_args())
