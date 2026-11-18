"""After the primary matrix stops, collect deployment speed and pinned grader replays."""
import argparse, json, os, pathlib, subprocess, sys, time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now,resolve_run

def run(a):
    main=resolve_run(a.prefix)
    parent=create_run('Empero MTP deployment speed and grader sensitivity','mtp-speed-and-policy-audit',run_id=a.prefix+'-extras',config={'primary_matrix':a.prefix,'capability_answers':0,'expected_speed_cases':18,'cpu_moe_layers':30,'additional_audits':a.additional_audit})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now());save(parent/'manifest.json',m)
    def event(data):
        data={'at':now(),**data}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(data)+'\n')
        print(json.dumps(data),flush=True)
    def execute(command,logfile):
        with (parent/'logs'/logfile).open('w',encoding='utf-8') as log:
            return subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8')).returncode
    try:
        while load(main/'manifest.json')['status']=='running':time.sleep(30)
        assert load(main/'manifest.json')['status']=='complete','Primary collection did not complete'
        speed_runs=[]
        for mtp in ['off','on']:
            name=a.prefix+'-iq3-cpu30-'+mtp;event({'event':'deployment_speed_start','run':name})
            code=execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest','configs/models/qwen38-35b-distill-iq3-m.json','--mtp',mtp,'--cpu-moe','30','--speed-only'],'speed-'+mtp+'.log')
            assert load(ROOT/'runs'/name/'configs/cleanup.json')['server_stopped']
            speed_runs.append(name);event({'event':'deployment_speed_finished','run':name,'exit_code':code})
        config=load(main/'manifest.json')['config'];audits=list(config['cell_runs'].values())+a.additional_audit
        for name in dict.fromkeys(audits):
            resolve_run(name);event({'event':'policy_audit_start','source':name})
            code=execute([str(a.benchmark_python),'-B',str(ROOT/'scripts/audit_humaneval_policy.py'),'--study',name],'policy-'+name+'.log')
            assert code==0,'Policy audit driver failed: '+name
        for prefix in dict.fromkeys([a.prefix,config.get('reference_iq3_prefix')]):
            if prefix:subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report_mtp_study.py'),'--prefix',prefix],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        complete=all(load(ROOT/'runs'/name/'manifest.json')['status']=='complete' for name in speed_runs)
        save(parent/'summary.json',{'outcome':'passed' if complete else 'partial','headline':'CPU30 deployment speed and existing HumanEval secondary-policy replays','speed_runs':speed_runs,'audit_runs':[n+'-he-policy-audit' for n in dict.fromkeys(audits)],'new_capability_answers':0,'scope':'New model inference is limited to fixed-length speed probes. Grader audits replay saved failures; primary scores are unchanged.'})
        m.update(status='complete',completed_at=now())
    except BaseException as e:m.update(status='failed',error=repr(e));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--benchmark-python',type=pathlib.Path,required=True);p.add_argument('--additional-audit',action='append',default=[]);run(p.parse_args())
