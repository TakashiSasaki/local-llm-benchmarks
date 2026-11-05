"""One-shot shutdown only after the selected response and its owned process tree exit."""
import argparse,ctypes,datetime,json,msvcrt,pathlib,subprocess,time
from ctypes import wintypes as w

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def evidence_ready(root,cfg):
    paths=[root/'runs'/cfg[key] for key in ['condition','model_run','orchestrator']]
    if any(not (p/'manifest.json').exists() or read(p/'manifest.json')['status'] not in ['complete','failed'] for p in paths):return False,'Waiting for terminal run records'
    cleanup=paths[1]/'configs/cleanup.json'
    if not cleanup.exists() or not read(cleanup)['server_stopped']:return False,'Waiting for owned server cleanup'
    casesfile=paths[0]/'summaries/cases.json';cases=read(casesfile) if casesfile.exists() else []
    if len(cases)>cfg['maximum_saved_cases']:raise RuntimeError('Unexpected later question evidence; do not shut down unreviewed work')
    graded=any(c['task_id']==cfg['question'] for c in cases)
    if graded and not (paths[0]/'raw'/cfg['raw_filename']).exists():raise RuntimeError('Graded target has no saved raw response')
    if not graded and read(paths[0]/'manifest.json')['status']!='failed':return False,'Waiting for selected question result or recorded failure'
    return True,'Selected response saved and graded' if graded else 'Selected request ended with recorded failure; earlier evidence retained'

def watch(configpath):
    cfg=read(configpath);root=pathlib.Path(cfg['repository']);state=pathlib.Path(cfg['state_file'])
    # A consumed one-shot request must never be rearmed from old saved evidence.
    # Check before opening process handles or overwriting the historical state.
    if state.exists():
        previous=read(state)
        if previous.get('shutdown_started') or previous.get('status')=='shutdown_requested':
            raise RuntimeError('Consumed shutdown request; preserve the old config/state and use a newly authorized request')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.GetProcessTimes.argtypes=[w.HANDLE,ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME)]
    kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.CloseHandle.argtypes=[w.HANDLE]
    handles=[];proof=[]
    try:
        for item in cfg['owned_processes']:
            handle=kernel.OpenProcess(0x100000|0x1000,False,item['pid'])
            if not handle:
                error=ctypes.get_last_error()
                if error!=87:raise ctypes.WinError(error)
                proof.append({'pid':item['pid'],'original_already_exited':True});continue
            created=w.FILETIME();exited=w.FILETIME();user=w.FILETIME();system=w.FILETIME()
            if not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(system),ctypes.byref(user)):kernel.CloseHandle(handle);raise ctypes.WinError(ctypes.get_last_error())
            seconds=((created.dwHighDateTime<<32)|created.dwLowDateTime)/10000000-11644473600
            expected=datetime.datetime.fromisoformat(item['created_at']).timestamp()
            if abs(seconds-expected)>0.05:
                kernel.CloseHandle(handle);proof.append({'pid':item['pid'],'pid_reused_original_exited':True});continue
            handles.append(handle);proof.append({'pid':item['pid'],'original_process_handle_captured':True})
        write(state,{'status':'armed','at':now(),'watched_processes':proof,'question':cfg['question'],'shutdown_started':False})
        while True:
            if not read(configpath).get('enabled'):
                write(state,{'status':'cancelled','at':now(),'shutdown_started':False});return
            statuses=[kernel.WaitForSingleObject(handle,0) for handle in handles]
            if any(s not in [0,258] for s in statuses):raise RuntimeError('Process wait failed; do not infer owned process exit')
            ready,reason=evidence_ready(root,cfg)
            if ready and all(s==0 for s in statuses):break
            time.sleep(5)
        # Save the decision before shutdown can close this watcher.
        write(state,{'status':'shutdown_requested','at':now(),'reason':reason,'question':cfg['question'],'all_original_owned_processes_exited':True,'shutdown_started':True})
        result=subprocess.run([cfg['shutdown_executable'],'/s','/t','0','/d','p:0:0','/c','User requested shutdown after current benchmark response and evidence saving'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:raise RuntimeError('Windows rejected shutdown: '+result.stderr)
    except BaseException as error:
        write(state,{'status':'failed','at':now(),'error':repr(error),'shutdown_started':False});raise
    finally:
        for handle in handles:kernel.CloseHandle(handle)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=pathlib.Path,required=True);args=parser.parse_args()
    lockpath=args.config.with_suffix('.lock')
    with lockpath.open('a+b') as lock:
        if lock.seek(0,2)==0:lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);watch(args.config)
