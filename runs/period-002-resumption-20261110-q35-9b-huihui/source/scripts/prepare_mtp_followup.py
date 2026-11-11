"""Wait for an owned study to stop, probe native MTP, then collect only supported cells."""
import argparse,json,os,pathlib,socket,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,create_run,snapshot_sources,resolve_run

def definition(plan,passed,probe):
    group={'key':'mage-text','model_manifest':plan['model_manifest'],'profile':plan['benchmark_profile'],'cpu_moe_layers':0,'load_mode':'none','states':['off','on'] if passed else ['off'],'reference_runs':{'off':plan['reference_off']},'role':'text-only native MTP comparison','placement_label':'-ngl 20（出力層込み）'}
    unavailable=[] if passed else [{'model_manifest':plan['model_manifest'],'mtp':['on'],'thinking':['off','on'],'benchmarks':['bfcl','humaneval'],'capacity_run':probe,'reason':'Native MTP startup/generation probe did not complete with observed draft tokens. No MTP ON capability score or speedup is assigned; inspect the saved failure log and structure evidence.'}]
    return {'title':'Mage-VL-Cowork Q4_K_M・MTP ON/OFFの利用可否とテキスト比較','groups':[group],'unavailable':unavailable,'context_note':'64K/F16、画像入力なし。OFFは先行runの参照で再測定ではありません。ONは実際のdraft tokensが確認できた場合だけ実測します。形式エラー時の統計は不明です。','reference_report':'reports/'+plan['wait_for_study']+'/index.html','structure_evidence':'publication/mage-vl-cowork-q4-structure.json','scope':'Reference OFF preserves its original run; fresh ON is conditional on a real native-MTP probe. Unsupported conditions have no capability score.'}

def run(a):
    plan=load(ROOT/a.plan);parent=create_run('Mage native MTP follow-up preparation','mtp-followup-preparation',run_id=plan['prefix']+'-preparation',experiment_type='capacity',config={'plan':plan,'capability_answers':0})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now());save(parent/'manifest.json',m)
    def event(**v):
        v={'at':now(),**v}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(v)+'\n')
        print(json.dumps(v),flush=True)
    def execute(command,name):
        event(event='step_start',step=name)
        with (parent/'logs'/(name+'.log')).open('w',encoding='utf-8') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        event(event='step_finished',step=name,exit_code=r.returncode);return r.returncode
    try:
        waiting=resolve_run(plan['wait_for_study']);last=None
        while True:
            status=load(waiting/'manifest.json')['status']
            if status=='failed':raise RuntimeError('Preceding study failed; follow-up did not start')
            verification=ROOT/'publication'/(waiting.name+'-evidence-validation.json')
            if status=='complete' and verification.exists() and load(verification).get('passed') is True:break
            if status=='complete':status='waiting-for-evidence-verification'
            if status!=last:event(event='waiting_for_preceding_study',run=waiting.name,status=status);last=status
            time.sleep(30)
        off=resolve_run(plan['reference_off']);assert load(off/'manifest.json')['status']=='complete'
        assert load(off/'configs/cleanup.json')['server_stopped'],'Preceding owned server has not stopped'
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Port occupied; no process is replaced'
        probe=plan['prefix']+'-preflight'
        code=execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',probe,'--model-manifest',plan['model_manifest'],'--profile',plan['probe_profile'],'--mtp','on','--cpu-moe','0','--load-mode','none','--pilot'],'mtp-preflight')
        p=resolve_run(probe);pm=load(p/'manifest.json');assert load(p/'configs/cleanup.json')['server_stopped']
        passed=code==0 and pm['status']=='complete'
        if passed:assert load(resolve_run(probe+'-speed')/'summary.json')['draft_tokens']>0
        config=definition(plan,passed,probe);relative='configs/'+plan['prefix']+'.json';assert not (ROOT/relative).exists();save(ROOT/relative,config)
        event(event='mtp_probe_result',supported_probe=passed,probe=probe,error=pm.get('error'))
        code=execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_grid.py'),'--prefix',plan['prefix'],'--definition',relative,'--benchmark-python',str(a.benchmark_python)],'comparison-grid')
        if code:raise RuntimeError('Follow-up grid or evidence verification failed')
        save(parent/'summary.json',{'outcome':'passed' if passed else 'partial','headline':'Native MTP probe and conditional comparison finished','probe_run':probe,'mtp_probe_passed':passed,'benchmark_run':plan['prefix'],'capability_answers':0,'scope':'Capability answers are stored only in benchmark runs. Failed probe is unavailable, not zero accuracy.'})
        m.update(status='complete',completed_at=now())
    except BaseException as error:m.update(status='failed',error=repr(error));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--benchmark-python',type=pathlib.Path,required=True);run(p.parse_args())
