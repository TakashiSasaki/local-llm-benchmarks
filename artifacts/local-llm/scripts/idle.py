"""Same explicit AC/CPU/GPU/temperature condition before measured model groups."""
import ctypes, datetime, json, subprocess, time
from ctypes import wintypes
from server import ROOT

class Power(ctypes.Structure):
    _fields_=[('ac',wintypes.BYTE),('flags',wintypes.BYTE),('percent',wintypes.BYTE),('status',wintypes.BYTE),('life',wintypes.DWORD),('full_life',wintypes.DWORD)]
def cpu_times():
    idle=ctypes.c_ulonglong(); kernel=ctypes.c_ulonglong(); user=ctypes.c_ulonglong()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kernel),ctypes.byref(user)): raise OSError('GetSystemTimes failed')
    return idle.value,kernel.value+user.value
def wait_idle(max_seconds=120):
    started=time.monotonic(); previous=cpu_times(); consecutive=0; samples=[]
    while time.monotonic()-started<max_seconds:
        time.sleep(2); current=cpu_times(); total=current[1]-previous[1]
        cpu=100*(1-(current[0]-previous[0])/total) if total else None; previous=current
        power=Power(); ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power))
        p=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,temperature.gpu,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        values=p.stdout.strip().split(',') if p.returncode==0 else []
        gpu=float(values[0]) if len(values)==3 else None; temp=float(values[1]) if len(values)==3 else None
        ok=power.ac==1 and cpu is not None and cpu<=15 and gpu is not None and gpu<=15 and temp<=55
        samples.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cpu_percent':cpu,'gpu_percent':gpu,'gpu_temperature_c':temp,'gpu_used_mib':float(values[2]) if len(values)==3 else None,'ac_online':power.ac==1,'condition_met':ok})
        consecutive=consecutive+1 if ok else 0
        if consecutive>=3: break
    report={'ready':consecutive>=3,'condition':'AC online, CPU<=15%, GPU<=15%, GPU temperature<=55C for 3 samples at 2-second intervals','samples':samples}
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    (ROOT/'runs'/f'idle-{stamp}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'ready':report['ready'],'last_sample':samples[-1] if samples else None},ensure_ascii=False),flush=True)
    return report['ready']
if __name__=='__main__': raise SystemExit(0 if wait_idle() else 1)
