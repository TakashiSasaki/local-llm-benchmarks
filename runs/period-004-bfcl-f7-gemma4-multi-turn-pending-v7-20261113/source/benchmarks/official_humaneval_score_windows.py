"""Score collected HumanEval completions with upstream execution, adapted for Windows.

This executes model-generated Python on the host. The user explicitly authorized it.
The JobObject is a resource limit and is not an isolation sandbox.
"""
import ctypes,gzip,hashlib,json,pathlib,subprocess,sys,time
from ctypes import wintypes as w
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now
from local_llm_benchmarks.humaneval_standard_windows import ExtendedLimits

COLLECTION=ROOT/'runs/period-004-gemma-humaneval-prefix-20261112'
RUN=ROOT/'runs/period-004-gemma-humaneval-score-20261112'
WORKER=ROOT/'benchmarks/official_humaneval_windows_worker.py'
DATA=ROOT/'.local/official-humaneval-b9453e8/data/HumanEval.jsonl.gz'
SOURCE=ROOT/'.local/official-humaneval-b9453e8/human_eval/execution.py'

def score(problem,completion):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.CloseHandle.argtypes=[w.HANDLE]
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise ctypes.WinError(ctypes.get_last_error())
    child=None
    try:
        limits=ExtendedLimits();limits.Basic.Flags=0x2000|0x100|0x8;limits.Basic.ActiveProcesses=1;limits.ProcessMemory=256*1024**2
        if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):raise ctypes.WinError(ctypes.get_last_error())
        child=subprocess.Popen([sys.executable,'-I','-B','-X','utf8',str(WORKER)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        if not kernel.AssignProcessToJobObject(job,w.HANDLE(int(child._handle))):raise ctypes.WinError(ctypes.get_last_error())
        try:out,err=child.communicate(json.dumps({'problem':problem,'completion':completion}),timeout=4.0)
        except subprocess.TimeoutExpired:
            child.kill();child.communicate();return {'passed':False,'result':'timed out'}
        if child.returncode:raise RuntimeError('Official worker infrastructure failed: '+err[-300:])
        result=json.loads(out)['result'];return {'passed':result=='passed','result':result}
    finally:
        if child and child.poll() is None:child.kill();child.wait()
        kernel.CloseHandle(job)

def main():
    manifest=load(RUN/'manifest.json')
    try:
        manifest.update(status='running',started_at=now());save(RUN/'manifest.json',manifest)
        while True:
            collection=load(COLLECTION/'manifest.json')
            if collection['status']=='complete':break
            if collection['status']=='failed':raise RuntimeError('Collection failed; scoring not started')
            time.sleep(5)
        assert hashlib.sha256(DATA.read_bytes()).hexdigest()=='b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef'
        problems=[json.loads(x) for x in gzip.decompress(DATA.read_bytes()).decode().splitlines()]
        samples=[json.loads(x) for x in (COLLECTION/'summaries/samples.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(problems)==len(samples)==164 and [p['task_id'] for p in problems]==[s['task_id'] for s in samples]
        proof={'upstream_execution_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'worker_sha256':hashlib.sha256(WORKER.read_bytes()).hexdigest(),'dataset_sha256':hashlib.sha256(DATA.read_bytes()).hexdigest(),'python':sys.version,'upstream_timeout_seconds':3,'parent_watchdog_seconds':4,'memory_limit_bytes':256*1024**2,'process_limit':1,'workers':1,'difference':'Official unsafe_execute and prompt+completion+test+check; Windows parent replaces SIGALRM/multiprocessing; one worker and explicit limits. Host execution, not isolated.'}
        save(RUN/'configs/scoring-policy.json',proof)
        # Discrimination controls use synthetic, non-model code only.
        control={'task_id':'control','prompt':'def f(x):\n','test':'def check(candidate):\n    assert candidate(2)==3','entry_point':'f'}
        assert score(control,'    return x+1\n')['passed']
        assert not score(control,'    return 0\n')['passed']
        assert score(control,'    while True: pass\n')['result']=='timed out'
        for problem,sample in zip(problems,samples):
            result={'task_id':sample['task_id'],**score(problem,sample['completion'])}
            save(RUN/'raw'/(sample['task_id'].replace('/','_')+'.json'),result)
            print(json.dumps(result),flush=True)
        results=[load(p) for p in (RUN/'raw').glob('*.json')];assert len(results)==164
        passed=sum(x['passed'] for x in results)
        save(RUN/'summary.json',{'outcome':'scored','passed':passed,'attempted':164,'pass_at_1':passed/164,'source_run':COLLECTION.name,'generated_code_executed':True,'policy':'Windows adapter of official HumanEval execution; see configs/scoring-policy.json'})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:manifest.update(status='failed',error=repr(e),failed_at=now());raise
    finally:save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
