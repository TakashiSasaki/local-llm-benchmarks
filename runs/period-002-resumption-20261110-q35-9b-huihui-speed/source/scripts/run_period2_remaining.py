"""Sequential approved 9B/35B cohorts, with shared placement and finish-by admission."""
import argparse,gzip,importlib.util,json,msvcrt,os,pathlib,random,re,shutil,socket,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now,validate_run,resolve_run,sha
from local_llm_benchmarks.execution_window import require,ExecutionWindowDeferred

MODELS={'q35-9b-base':'Qwen3.5-9B ordinary','q35-9b-huihui':'Qwen3.5-9B Huihui','q35-9b-heretic':'Qwen3.5-9B Heretic','q35-9b-defiant':'Qwen3.5-9B Defiant','q36-35b-base':'Qwen3.6-35B-A3B ordinary','q36-35b-huihui':'Qwen3.6-35B-A3B Huihui'}
COHORTS=[('b',list(MODELS)[:4],[('all',0),('32',0),('31',0),('30',0),('28',0),('24',0)]),('c',list(MODELS)[4:],[('all',n) for n in range(34,41)])]
CONTINUATION='experiments/period-002/configs/q35-9b-he-on-continuation.json'

def script_module(name,file):
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def validate_stage_a(prefix):
    parent=ROOT/'runs'/prefix;assert validate_run(parent)['status']=='complete'
    assert load(parent/'summary.json')['capability_answers']==400
    conditions=[]
    for key in ['q35-4b-base','q35-4b-abliterix']:
        for suite,count in [('bfcl',80),('humaneval',20)]:
            for mode in ['off','on']:
                path=ROOT/'runs'/(prefix+'-'+key+'-'+suite+'-'+mode)
                assert validate_run(path)['status']=='complete'
                summary=load(path/'summary.json');assert summary['attempted']==count
                cases=load(path/'summaries'/('bfcl-cases.json' if suite=='bfcl' else 'cases.json'))
                assert len(cases)==count and len(list((path/'raw').glob('*.json')))==count
                assert sum(e['passed'] for e in cases)==summary['passed']
                conditions.append({'run':path.name,'saved':count,'passed':summary['passed']})
        assert load(ROOT/'runs'/(prefix+'-'+key)/'configs/cleanup.json')['server_stopped']
    return {'scope':'Source hashes, saved-record counts and score aggregation; not new inference or independent code execution','referenced_capability_answers':400,'conditions':conditions}

def checkpoint(previous, continuation_path=None):
    """Validate the saved 9B checkpoint before starting any new collection."""
    manifest=validate_run(previous)
    assert manifest['period']=='period-002' and manifest['stop_reason']=='execution_window_deferred' and not manifest['model_failure']
    plan=load(continuation_path or ROOT/CONTINUATION)
    assert plan['source_run']==previous.name+'-q35-9b-base-humaneval-on'
    profile=load(previous/'configs/cohort-b-matched-profile.json')
    args=profile['server_args']
    assert args[args.index('-ngl')+1]=='24' and args[args.index('--n-cpu-moe')+1]=='0'
    proofs=[]
    for key in COHORTS[0][1]:
        run=resolve_run(previous.name+'-'+key+'-capacity-ngl24-cpu0')
        assert validate_run(run)['status']=='complete'
        assert load(run/'configs/cleanup.json')['server_stopped']
        assert load(run/'summaries/tool-smoke.json')['transport_and_mode_checks_passed']
        observed=load(run/'summaries/memory.json')
        assert observed['peak_gpu_used_mib_system_total']<=7676 and observed['minimum_available_ram_bytes']>=3*1024**3
        model=load(previous/'configs'/(key+'-model.json'))
        pin=load(ROOT/'experiments/period-002/models'/(key+'.json'))
        assert all(model[field]==pin[field] for field in ('filename','bytes','sha256','revision','url'))
        proofs.append(run.name)
    for suffix,count in [('bfcl-off',80),('bfcl-on',80),('humaneval-off',20)]:
        run=resolve_run(previous.name+'-q35-9b-base-'+suffix)
        assert validate_run(run)['status']=='complete' and load(run/'summary.json')['attempted']==count
        assert len(list((run/'raw').glob('*.json')))==count
    return profile,plan,proofs

def validate_reconciled_continuations(previous, plan):
    """Never skip a partial attempt unless every raw answer is pinned in this plan."""
    from local_llm_benchmarks.humaneval_subset import select
    rows=[json.loads(s) for s in gzip.decompress((ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
    problems=[rows[i] for i in sorted(random.Random(42).sample(range(164),20))]
    select(problems,plan)
    reconciled=plan.get('reconciled_parent_runs',{})
    seen=set()
    references={r['source_run'] for r in plan.get('references',[])}
    for path in (ROOT/'runs').glob('period-002-*/manifest.json'):
        record=load(path)
        if record.get('config',{}).get('resume_from')!=previous.name:
            continue
        raw_files=list((ROOT/'runs').glob(path.parent.name+'-*/raw/*.json'))
        if record['status']=='running':
            raise ValueError(f'Existing continuation {path.parent.name} is still marked running')
        if not raw_files:
            continue
        proof=reconciled.get(path.parent.name)
        if not proof:
            raise ValueError(f'Existing continuation {path.parent.name} must be reconciled before starting another')
        assert record['status']=='failed' and sha(path)==proof['manifest_sha256']
        actual_sources={p.parent.parent.name for p in raw_files}
        assert actual_sources==set(proof['source_runs'])
        assert actual_sources.issubset(references)
        for name in actual_sources:
            assert name.startswith(path.parent.name+'-')
        seen.add(path.parent.name)
    assert seen==set(reconciled),'Missing or empty reconciled continuation'
    return plan

def run(a):
    previous=resolve_run(a.resume_from) if getattr(a,'resume_from',None) else None
    continuation_path=getattr(a,'continuation_plan',None)
    if continuation_path and not previous:
        raise ValueError('An explicit continuation plan requires --resume-from')
    plan=load(continuation_path or ROOT/CONTINUATION) if previous else None
    if previous:
        validate_reconciled_continuations(previous,plan)
    planned=1000+plan['new_answer_count'] if previous else 1200
    referenced=1600-planned
    parent=create_run('Period 002 remaining 9B and 35B core cohorts','staged-capability-study',run_id=a.id,config={'source_stage_a':a.stage_a,'resume_from':previous.name if previous else None,'new_models':list(MODELS),'planned_new_answers':planned,'referenced_answers':referenced,'execution_window':'experiments/period-002/configs/execution-window.json','fixed_protocol':'64K/F16, MTP OFF, same BFCL80/HE20 and OFF/ON requests; matched placement within cohort','placement_scope':'First shared safe candidate in declared descending candidates, not proof of an untested global maximum'})
    snapshot_sources(parent);manifest=load(parent/'manifest.json');manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(parent/'manifest.json',manifest)
    completed=[];children=[]
    def event(**data):
        row={'at':now(),**data}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    def execute(command,name,guard_disk=False):
        logpath=parent/'logs'/(name+'.log')
        with logpath.open('w',encoding='utf-8') as log:
            child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
            event(event='owned_child',step=name,pid=child.pid)
            try:
                while child.poll() is None:
                    if guard_disk and shutil.disk_usage('C:/LocalLLM/models').free<32*1024**3:raise RuntimeError('Disk reserve reached; retain weight fragment')
                    time.sleep(2)
            finally:
                if child.poll() is None:
                    subprocess.run(['taskkill.exe','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);child.wait()
        return child.returncode,logpath
    def cell(key,profile,run_id,pilot,continuation=None):
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Existing server must remain untouched'
        require(parent,run_id,'model-preflight' if pilot else 'model-benchmark')
        profilepath=parent/'configs'/(run_id+'-profile.json');save(profilepath,profile)
        command=[sys.executable,'-B','-X','utf8',str(ROOT/'scripts/run_mtp_study.py'),'--id',run_id,'--model-manifest',(parent/'configs'/(key+'-model.json')).relative_to(ROOT).as_posix(),'--profile',profilepath.relative_to(ROOT).as_posix(),'--mtp','off','--cpu-moe',str(profile['server_args'][profile['server_args'].index('--n-cpu-moe')+1]),'--load-mode','none','--benchmark-python',str(a.benchmark_python)]
        if pilot:command+=['--pilot']
        if continuation:command+=['--continuation-plan',str(continuation)]
        children.append(run_id);event(event='cell_start',run=run_id,pilot=pilot)
        code,log=execute(command,run_id)
        path=ROOT/'runs'/run_id;m=load(path/'manifest.json') if (path/'manifest.json').exists() else {}
        if m.get('stop_reason')=='execution_window_deferred':raise ExecutionWindowDeferred('Child admission deferred: '+run_id)
        if (path/'configs/cleanup.json').exists():assert load(path/'configs/cleanup.json')['server_stopped']
        if code:
            serverlog=path/'logs/llama-server.log';text=serverlog.read_text(encoding='utf-8',errors='replace') if serverlog.exists() else ''
            if pilot and re.search(r'(cudaMalloc.*failed|CUDA.*out of memory|CUDA error: out of memory)',text,re.I):
                event(event='capacity_rejected',run=run_id,reason='Explicit CUDA allocation failure');return False
            raise RuntimeError('Owned cell failed; inspect preserved evidence, no automatic inference retry: '+run_id)
        memory=load(path/'summaries/memory.json')
        if memory['peak_gpu_used_mib_system_total'] is None:raise RuntimeError('GPU observation unavailable; do not infer capacity success')
        if memory['minimum_available_ram_bytes']<3*1024**3:raise RuntimeError('RAM reserve not met; do not continue placement search')
        if memory['peak_gpu_used_mib_system_total']>7676:
            if not pilot:raise RuntimeError('Main measurement exceeded GPU reserve; preserve scores and flag placement for review')
            event(event='capacity_rejected',run=run_id,reason='Observed system GPU exceeds 7676 MiB',memory=memory);return False
        if pilot:assert load(path/'summaries/tool-smoke.json')['transport_and_mode_checks_passed']
        event(event='cell_complete',run=run_id,pilot=pilot,memory=memory);return True
    try:
        while load(ROOT/'runs'/a.stage_a/'manifest.json')['status']=='running':time.sleep(10)
        save(parent/'configs/stage-a-validation.json',validate_stage_a(a.stage_a))
        module=script_module('stage_a_control',ROOT/'scripts/run_period2_stage_a.py')
        save(parent/'configs/grader-policy.json',module.ready_policy(ROOT/'runs'/a.validation,a.benchmark_python))
        template=load(ROOT/'experiments/period-002/configs/q35-4b-base-preflight.json')
        if previous:
            require(parent,'validate resumed 9B cohort','model-preflight')
            save(parent/'configs/execution-window-at-start.json',load(ROOT/'experiments/period-002/configs/execution-window.json'))
            matched,plan,proofs=checkpoint(previous,continuation_path)
            save(parent/'configs/continuation-plan.json',plan)
            save(parent/'configs/9b-checkpoint.json',{'source':previous.name,'capacity_runs':proofs,'referenced_answers':180+plan['referenced_answer_count']})
            runtime_dir=pathlib.Path(matched['runtime_executable']).parent
            runtime=load(ROOT/'experiments/period-002/environment/handoff-20261106.json')['runtime']
            digest=script_module('pinned_downloader',ROOT/'scripts/download_pinned_model.py').digest
            for artifact in runtime['installed_files_verified']:
                file=runtime_dir/artifact['filename']
                assert file.stat().st_size==artifact['bytes'] and digest(file)==artifact['sha256'],file.name
            save(parent/'configs/runtime-verification.json',runtime)
        for cohort,keys,candidates in COHORTS:
            event(event='cohort_start',cohort=cohort,models=keys)
            for key in keys:
                original=ROOT/'experiments/period-002/models'/(key+'.json');metadata=load(original)
                if previous and cohort=='b':
                    # The owned cell rehashes the installed GGUF before each model load.
                    save(parent/'configs'/(key+'-model.json'),load(previous/'configs'/(key+'-model.json')))
                    continue
                require(parent,'download '+key,'download',int(metadata['bytes']/(5*1024**2))+300)
                assert shutil.disk_usage('C:/LocalLLM/models').free>metadata['bytes']+32*1024**3,'Insufficient reserved disk capacity'
                code,log=execute([sys.executable,'-B','-X','utf8',str(ROOT/'scripts/download_pinned_model.py'),'--manifest',str(original),'--model-dir','C:/LocalLLM/models','--connections','1','--download-query','download=true'],key+'-download',True)
                if code:raise RuntimeError('Pinned download failed; preserve fragment and stop: '+key)
                metadata.update(model=MODELS[key],status='Downloaded with full-file SHA validation; served behavior verified separately')
                save(parent/'configs'/(key+'-model.json'),metadata);event(event='download_complete',model=key,bytes=metadata['bytes'],sha256=metadata['sha256'])
            chosen=matched if previous and cohort=='b' else None
            for ngl,cpu in candidates if chosen is None else []:
                profile=json.loads(json.dumps(template));args=profile['server_args'];args[args.index('-ngl')+1]=ngl;args[args.index('--n-cpu-moe')+1]=str(cpu)
                profile.update(profile_id='period2-cohort-'+cohort+'-ngl'+ngl+'-cpu'+str(cpu),tool_smoke=True)
                accepted=True
                for key in keys:
                    name=a.id+'-'+key+'-capacity-ngl'+ngl+'-cpu'+str(cpu)
                    if not cell(key,profile,name,True):accepted=False;break
                if accepted:chosen=profile;break
            if chosen is None:raise RuntimeError('No shared safe placement among declared candidates; no capability collection')
            save(parent/'configs'/('cohort-'+cohort+'-matched-profile.json'),chosen)
            event(event='common_placement_selected',cohort=cohort,ngl=chosen['server_args'][chosen['server_args'].index('-ngl')+1],cpu_moe=chosen['server_args'][chosen['server_args'].index('--n-cpu-moe')+1])
            for key in keys:
                profile=json.loads(json.dumps(chosen));profile.update(tool_smoke=False,humaneval_grader_policy='standard-windows-v1')
                run_id=a.id+'-'+key
                continuation=parent/'configs/continuation-plan.json' if previous and key=='q35-9b-base' else None
                if previous:profile['maximum_gpu_used_mib']=7676
                cell(key,profile,run_id,False,continuation)
                if continuation:
                    path=resolve_run(run_id+'-humaneval-on')
                    assert validate_run(path)['status']=='complete'
                    summary=load(path/'summary.json')
                    assert summary['attempted']==plan['new_answer_count'] and summary['combined_reference_score']['expected']==20
                    completed.append({'model':key,'run':run_id,'new_answers':plan['new_answer_count'],'conditions':{'humaneval-on':summary}})
                    save(parent/'summaries/completed-models.json',completed)
                    continue
                summaries={}
                for suite,count in [('bfcl',80),('humaneval',20)]:
                    for mode in ['off','on']:
                        p=ROOT/'runs'/(run_id+'-'+suite+'-'+mode);assert validate_run(p)['status']=='complete'
                        s=load(p/'summary.json');assert s['attempted']==count;summaries[suite+'-'+mode]=s
                completed.append({'model':key,'run':run_id,'new_answers':200,'conditions':summaries});save(parent/'summaries/completed-models.json',completed)
        assert sum(entry['new_answers'] for entry in completed)==planned
        save(parent/'summary.json',{'outcome':'passed','new_answers':planned,'referenced_stage_a_answers':400,'referenced_answers':referenced,'completed_models':completed,'child_runs':children,'scope':'Approved six remaining core artifacts only; no optional models, MTP ON or extension datasets'})
        manifest.update(status='complete',completed_at=now());event(event='remaining_core_complete',new_answers=planned)
    except BaseException as error:
        deferred=isinstance(error,ExecutionWindowDeferred)
        manifest.update(status='failed',completed_at=now(),error=repr(error),stop_reason='execution_window_deferred' if deferred else 'owned_step_failed',model_failure=False if deferred else None)
        save(parent/'summary.json',{'outcome':'deferred' if deferred else 'partial','completed_models':completed,'completed_model_answers':sum(x['new_answers'] for x in completed),'partial_responses':'Inspect child raw directories; not included in completed-model count','child_runs':children,'pending_models':[k for k in MODELS if k not in [x['model'] for x in completed]],'reason':str(error)})
        event(event='followup_deferred' if deferred else 'followup_failed',reason=str(error));raise
    finally:save(parent/'manifest.json',manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);parser.add_argument('--stage-a',required=True);parser.add_argument('--validation',required=True);parser.add_argument('--benchmark-python',type=pathlib.Path,required=True);parser.add_argument('--resume-from',help='Resume the saved period-002 9B checkpoint with a new run ID');parser.add_argument('--continuation-plan',type=pathlib.Path,help='Pinned multi-run continuation definition');args=parser.parse_args()
    lockpath=ROOT/'.local/locks/period2-remaining.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
    with lockpath.open('a+b') as lock:
        if lock.seek(0,2)==0:lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);run(args)
