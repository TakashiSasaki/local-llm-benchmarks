"""Collect declared MTP/thinking grids and retain explicit matched references."""
import argparse,json,os,pathlib,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now,resolve_run,validate_run

def run(a):
    config=load(ROOT/a.definition);groups=config['groups'];assert len({g['key'] for g in groups})==len(groups)
    cell_runs={g['key']+'-'+mtp:g.get('reference_runs',{}).get(mtp,a.prefix+'-'+g['key']+'-'+mtp) for g in groups for mtp in g.get('states',['off','on'])}
    assert len(set(cell_runs.values()))==len(cell_runs),'A measured cell cannot be counted twice'
    fresh=[name for g in groups for mtp in g.get('states',['off','on']) if (name:=cell_runs[g['key']+'-'+mtp]) not in g.get('reference_runs',{}).values()]
    config.update(study_type='mtp-grid',cell_runs=cell_runs,expected_cells=len(cell_runs),context_tokens=65536,max_output_tokens=64000,expected_new_answers=len(fresh)*200)
    parent=create_run(config['title'],'quantization-mtp-grid',run_id=a.prefix,config=config)
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now(),report='reports/'+a.prefix+'/index.html');save(parent/'manifest.json',m)
    def event(value):
        value={'at':now(),**value}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    def execute(command,logfile):
        with (parent/'logs'/logfile).open('w',encoding='utf-8') as f:
            r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        if r.returncode:raise RuntimeError('Driver failed: '+logfile)
    try:
        for g in groups:
            metadata=load(ROOT/g['model_manifest'])
            for mtp in g.get('states',['off','on']):
                name=cell_runs[g['key']+'-'+mtp]
                if name not in fresh:
                    reference=validate_run(resolve_run(name));assert reference['status']=='complete'
                    rc=reference['config'];args=rc['profile']['server_args']
                    assert rc['model']['sha256']==metadata['sha256'] and args[args.index('--n-cpu-moe')+1]==str(g['cpu_moe_layers'])
                    assert rc['profile']['mtp']==mtp and rc['profile']['context_tokens']==65536
                    event({'event':'referenced_complete_cell','run':name,'fresh_inference':False});continue
                event({'event':'cell_start','run':name,'group':g['key']})
                execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',g['model_manifest'],'--profile',g['profile'],'--mtp',mtp,'--cpu-moe',str(g['cpu_moe_layers']),'--load-mode',g.get('load_mode','none'),'--benchmark-python',str(a.benchmark_python)],name+'.log')
                event({'event':'cell_complete','run':name})
                subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report_mtp_grid.py'),'--prefix',a.prefix],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        for name in fresh:
            event({'event':'policy_audit_start','source':name})
            execute([str(a.benchmark_python),'-B',str(ROOT/'scripts/audit_humaneval_policy.py'),'--study',name],'audit-'+name+'.log')
        unavailable=config.get('unavailable',[])
        save(parent/'summary.json',{'outcome':'partial' if unavailable else 'passed','headline':config['title'],'child_runs':list(cell_runs.values()),'conditions':len(cell_runs)*4,'answers':len(cell_runs)*200,'new_answers':len(fresh)*200,'referenced_answers':(len(cell_runs)-len(fresh))*200,'unavailable':unavailable,'scope':'Collection and capacity availability are distinct from capability pass counts. References preserve their original IDs; audits are separate replays.'})
        m.update(status='complete',completed_at=now());save(parent/'manifest.json',m)
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/report_mtp_grid.py'),'--prefix',a.prefix],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        execute([sys.executable,'-B',str(ROOT/'tools/verify_mtp_study.py'),'--prefix',a.prefix,'--report',str(ROOT/'publication'/(a.prefix+'-evidence-validation.json'))],'evidence-validation.log')
    except BaseException as e:m.update(status='failed',error=repr(e));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--definition',required=True);p.add_argument('--benchmark-python',type=pathlib.Path,required=True);run(p.parse_args())
