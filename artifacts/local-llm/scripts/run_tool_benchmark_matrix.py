"""Wait for the already-running Qwen35 job, then fill the seven remaining BFCL ON cells."""
import datetime,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(r'C:\LocalLLM');OUT=Path(sys.argv[1]);QWEN=Path(sys.argv[2]);OUT.mkdir(exist_ok=True)
order=['lfm3','lfm3-q8','lfm3-vl-q4','lfm3-vl-q8','qwen-daily','lfm','glm']
state={'directory':str(OUT),'qwen35_directory':str(QWEN),'started_at':datetime.datetime.now().astimezone().isoformat(),'order':order,'status':'waiting_for_qwen35','models':{}}
if (OUT/'orchestration.json').exists():
    state=json.loads((OUT/'orchestration.json').read_text(encoding='utf-8'))
    state.setdefault('resume_history',[]).append({'resumed_at':datetime.datetime.now().astimezone().isoformat(),'previous_status':state['status'],'previous_error':state.pop('error',None)})
    state['status']='waiting_for_qwen35'
def persist():
    path=OUT/'orchestration.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
def build():
    script=ROOT/'scripts/build_benchmark_matrix.py'
    if script.exists():subprocess.run([sys.executable,'-X','utf8',str(script),str(OUT)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
def audit(path):subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/audit_qwen_tool_thinking.py'),str(path)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
persist();print(json.dumps({'event':'waiting_for_qwen35','directory':str(OUT)}),flush=True)
try:
    while not (QWEN/'summary.json').exists():
        qr=json.loads((QWEN/'results.json').read_text(encoding='utf-8'))
        if qr.get('error'):raise RuntimeError('Qwen35 run failed: '+qr['error'])
        build();time.sleep(15)
    audit(QWEN);state['models']['qwen-large']={'directory':str(QWEN),'status':'complete'};persist();build()
    for key in order:
        run=OUT/key
        if (run/'independent-audit.json').exists():
            state['models'][key]={'directory':str(run),'status':'complete'};persist();continue
        state['status']='running';state['active_model']=key;state['models'][key]={'directory':str(run),'status':'running'};persist()
        print(json.dumps({'event':'model_start','model':key,'directory':str(run)}),flush=True)
        cmd=[sys.executable,'-X','utf8',str(ROOT/'scripts/benchmark_model_tool_thinking.py'),str(run),key]
        with (OUT/(key+'-runner.log')).open('a',encoding='utf-8') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            while proc.poll() is None:build();time.sleep(15)
        if proc.returncode:raise RuntimeError('Model runner failed: '+key+'; see '+str(OUT/(key+'-runner.log')))
        audit(run);state['models'][key]['status']='complete';persist();build()
        print(json.dumps({'event':'model_complete','model':key}),flush=True)
    state['status']='complete';state.pop('active_model',None);state['finished_at']=datetime.datetime.now().astimezone().isoformat();persist();build()
    print(json.dumps({'event':'complete','directory':str(OUT)}),flush=True)
except Exception as exc:
    state['status']='error';state['error']=repr(exc);persist();build();raise
