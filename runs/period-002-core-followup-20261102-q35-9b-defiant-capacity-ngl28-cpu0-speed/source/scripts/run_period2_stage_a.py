"""Wait for verified stage A preparation, then own the two matched 200-answer cells."""
import argparse,json,msvcrt,os,pathlib,socket,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,sha,snapshot_sources,now
from local_llm_benchmarks.execution_window import require,ExecutionWindowDeferred

def ready_policy(validation,python):
    assert load(validation/'manifest.json')['status']=='complete'
    proof=load(validation/'summary.json')
    assert proof['outcome']=='passed' and proof['canonical_passed']==164
    command=[str(python),'-B','-X','utf8','-c',"import sys,json;sys.path.insert(0,'src');from local_llm_benchmarks.humaneval_standard_windows import provenance;print(json.dumps(provenance()))"]
    current=json.loads(subprocess.check_output(command,cwd=ROOT,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW))
    assert current==proof['policy'],'Validated grader or benchmark interpreter changed'
    return current

def run(a):
    preparation=ROOT/'runs'/a.preparation;validation=ROOT/'runs'/a.validation
    parent=create_run('Period 002 stage A ordinary versus Abliterix Q4_K_M','paired-capability-study',run_id=a.id,config={'preparation':a.preparation,'grader_validation':a.validation,'models':['q35-4b-base','q35-4b-abliterix'],'planned_capability_answers':400,'planned_conditions':8,'mtp':'off','thinking':['off','on'],'suites':{'bfcl':80,'humaneval':20},'waiting_does_not_count_as_measurement':True})
    snapshot_sources(parent);manifest=load(parent/'manifest.json');manifest.update(status='running',started_at=now(),owner_pid=os.getpid(),phase='waiting_for_preparation');save(parent/'manifest.json',manifest)
    children=[]
    def event(**data):
        row={'at':now(),**data}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    try:
        event(event='waiting',preparation=a.preparation)
        while True:
            status=load(preparation/'manifest.json')['status']
            if status=='failed':raise RuntimeError('Preparation failed; no automatic model retry or condition change')
            if status=='complete':break
            time.sleep(10)
        # Preparation publishes terminal status only after its owned server cleanup.
        assert load(preparation/'summary.json')['outcome']=='passed'
        policy=ready_policy(validation,a.benchmark_python);save(parent/'configs/grader-policy.json',policy)
        manifest.update(phase='collecting');save(parent/'manifest.json',manifest)
        for key in manifest['config']['models']:
            require(parent,'new model '+key,'model-benchmark')
            capacity=ROOT/'runs'/(a.preparation+'-capacity-'+key)
            assert load(capacity/'manifest.json')['status']=='complete'
            assert load(capacity/'configs/cleanup.json')['server_stopped']
            assert load(capacity/'summaries/tool-smoke.json')['transport_and_mode_checks_passed']
            memory=load(capacity/'summaries/memory.json')
            assert memory['peak_gpu_used_mib_system_total'] is not None and memory['peak_gpu_used_mib_system_total']<=7676
            assert memory['minimum_available_ram_bytes']>=3*1024**3
            profile=load(ROOT/'experiments/period-002/configs'/(key+'-preflight.json'))
            profile.update(tool_smoke=False,humaneval_grader_policy='standard-windows-v1')
            save(parent/'configs'/(key+'-profile.json'),profile)
            model=load(preparation/'configs'/(key+'-model.json'));save(parent/'configs'/(key+'-model.json'),model)
            with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Existing server must remain untouched'
            child_id=a.id+'-'+key;children.append(child_id)
            event(event='model_start',run=child_id,model=key)
            command=[sys.executable,'-B','-X','utf8',str(ROOT/'scripts/run_mtp_study.py'),'--id',child_id,'--model-manifest',(parent/'configs'/(key+'-model.json')).relative_to(ROOT).as_posix(),'--profile',(parent/'configs'/(key+'-profile.json')).relative_to(ROOT).as_posix(),'--mtp','off','--cpu-moe','0','--load-mode','none','--benchmark-python',str(a.benchmark_python)]
            with (parent/'logs'/(key+'.log')).open('w',encoding='utf-8') as log:
                process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
                event(event='owned_child',pid=process.pid,run=child_id)
                code=process.wait()
            if code:
                if (ROOT/'runs'/child_id/'manifest.json').exists() and load(ROOT/'runs'/child_id/'manifest.json').get('stop_reason')=='execution_window_deferred':raise ExecutionWindowDeferred('Model cell deferred: '+child_id)
                raise RuntimeError('Model cell failed; saved partial evidence retained: '+child_id)
            assert load(ROOT/'runs'/child_id/'configs/cleanup.json')['server_stopped']
            event(event='model_complete',run=child_id)
        summaries={}
        for child in children:
            for suite,count in [('bfcl',80),('humaneval',20)]:
                for thinking in ['off','on']:
                    name=child+'-'+suite+'-'+thinking;path=ROOT/'runs'/name
                    assert load(path/'manifest.json')['status']=='complete'
                    result=load(path/'summary.json');assert result['attempted']==count
                    summaries[name]=result
        assert len(summaries)==8 and sum(s['attempted'] for s in summaries.values())==400
        save(parent/'summary.json',{'outcome':'passed','capability_answers':400,'complete_conditions':8,'child_runs':children,'conditions':summaries,'scope':'Fresh direct API responses; speed probes and legacy grader replay excluded from answer count'})
        manifest.update(status='complete',completed_at=now(),phase='complete');event(event='stage_complete',capability_answers=400)
    except BaseException as error:
        if isinstance(error,ExecutionWindowDeferred):manifest.update(stop_reason='execution_window_deferred',model_failure=False)
        manifest.update(status='failed',completed_at=now(),error=repr(error));event(event='stage_failed',error=repr(error));raise
    finally:save(parent/'manifest.json',manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);parser.add_argument('--preparation',required=True);parser.add_argument('--validation',required=True);parser.add_argument('--benchmark-python',type=pathlib.Path,required=True);args=parser.parse_args()
    lockpath=ROOT/'.local/locks/period2-stage-a-main.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
    with lockpath.open('a+b') as lock:
        if lock.seek(0,2)==0:lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        run(args)
