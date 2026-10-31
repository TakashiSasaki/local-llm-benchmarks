"""Queue a matched quantization after terminal predecessors, retaining partial failures."""
import argparse,json,os,pathlib,socket,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,create_run,snapshot_sources,resolve_run

def definition(plan,mtp_passed,probe,root=ROOT):
    groups=[{'key':'q3','model_manifest':plan['model_manifest'],'profile':plan['profile'],'cpu_moe_layers':0,'load_mode':'none','states':['off','on'] if mtp_passed else ['off'],'role':'fresh Q3 matched placement'}]
    unavailable=[] if mtp_passed else [{'model_manifest':plan['model_manifest'],'mtp':['on'],'thinking':['off','on'],'benchmarks':['bfcl','humaneval'],'capacity_run':probe,'reason':'Native MTP probe failed; no positive draft count. No ON capability score is assigned.'}]
    references={}
    for state in ['off','on']:
        name=plan['reference_'+state];path=root/'runs'/name/'manifest.json'
        if path.exists() and load(path)['status']=='complete':references[state]=name
    if references:groups.append({'key':'q4-reference','model_manifest':plan['reference_manifest'],'profile':plan['reference_profile'],'cpu_moe_layers':0,'load_mode':'none','states':list(references),'reference_runs':references,'role':'completed Q4 reference; no new inference'})
    if 'off' not in references:unavailable.append({'model_manifest':plan['reference_manifest'],'mtp':['off'],'run':plan['reference_off'],'reason':'Q4 did not finish all 200 answers; its partial evidence is retained, not counted as a complete comparison cell.'})
    return {'title':'Mage-VL-Cowork Q3_K_M / Q4_K_M テキスト比較・64K','groups':groups,'unavailable':unavailable,'reference_report':plan['reference_report'],'context_note':'同じ-ngl20（CPU17 decoder層・GPU19層＋出力層）、64K/F16、画像なし。公式32K active windowを超える拡張条件。Q4は完了runのみ参照し、未完了分を正答率比較に含めません。形式エラーの統計は不明です。','scope':'Fresh Q3 HumanEval20/BFCL80 x thinking OFF/ON; native MTP ON only after a positive real probe. Exact completed Q4 references are separately labelled. Same 7200-second API request timeout as Q4.'}

def run(a):
    plan=load(ROOT/a.plan);parent=create_run('Mage Q3_K_M follow-up preparation','quantization-followup-preparation',run_id=plan['prefix']+'-preparation',experiment_type='capacity',config={'plan':plan,'capability_answers':0})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now());save(parent/'manifest.json',m)
    def event(**v):
        v={'at':now(),**v}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(v)+'\n')
        print(json.dumps(v),flush=True)
    def execute(command,name):
        event(event='step_start',step=name)
        with (parent/'logs'/(name+'.log')).open('w',encoding='utf-8') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        event(event='step_finished',step=name,exit_code=r.returncode);return r.returncode
    def pilot(state):
        name=plan['prefix']+'-capacity-'+state
        code=execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',plan['model_manifest'],'--profile',plan['probe_profile'],'--mtp',state,'--cpu-moe','0','--load-mode','none','--pilot'],'capacity-'+state)
        path=resolve_run(name);assert load(path/'configs/cleanup.json')['server_stopped']
        passed=code==0 and load(path/'manifest.json')['status']=='complete'
        if passed and state=='on':assert load(resolve_run(name+'-speed')/'summary.json')['draft_tokens']>0
        return name,passed
    try:
        previous=None
        while True:
            states={name:load(resolve_run(name)/'manifest.json')['status'] for name in plan['wait_for_runs']}
            if all(status in ['complete','failed'] for status in states.values()):break
            if states!=previous:event(event='waiting_for_predecessors',states=states);previous=states
            time.sleep(30)
        clean=load(resolve_run(plan['preceding_server_run'])/'configs/cleanup.json');assert clean['server_stopped'],'Preceding owned server still running'
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Port occupied; no existing process is replaced'
        event(event='predecessors_terminal',states=states)
        code=execute([sys.executable,'-B',str(ROOT/'scripts/download_model_managed.py'),'--manifest',plan['model_manifest'],'--model-dir',str(a.model_dir),'--connections','1','--min-free-gib','32','--report','publication/'+plan['prefix']+'-download.json'],'download')
        if code:raise RuntimeError('Q3 pinned download failed; no inference started')
        code=execute([sys.executable,'-B',str(ROOT/'tools/inspect_gguf_header.py'),str(a.model_dir/load(ROOT/plan['model_manifest'])['filename']),'--report','publication/'+plan['prefix']+'-structure.json'],'structure')
        if code:raise RuntimeError('Q3 header inspection failed')
        off,passed=pilot('off')
        if not passed:raise RuntimeError('Q3 unchanged placement capacity probe failed: '+off)
        probe,mtp_passed=pilot('on');config=definition(plan,mtp_passed,probe);relative='configs/'+plan['prefix']+'.json';assert not (ROOT/relative).exists();save(ROOT/relative,config)
        code=execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_grid.py'),'--prefix',plan['prefix'],'--definition',relative,'--benchmark-python',str(a.benchmark_python)],'full-grid')
        if code:raise RuntimeError('Q3 benchmark or evidence verification failed')
        save(parent/'summary.json',{'outcome':'partial' if config['unavailable'] else 'passed','headline':'Q3 follow-up collection completed','benchmark_run':plan['prefix'],'predecessor_statuses':states,'mtp_probe_passed':mtp_passed,'capability_answers':0,'scope':'Answers belong only to benchmark runs; prior failures and capacity probes are separate evidence.'})
        m.update(status='complete',completed_at=now())
    except BaseException as error:m.update(status='failed',error=repr(error));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--model-dir',type=pathlib.Path,required=True);p.add_argument('--benchmark-python',type=pathlib.Path,required=True);run(p.parse_args())
