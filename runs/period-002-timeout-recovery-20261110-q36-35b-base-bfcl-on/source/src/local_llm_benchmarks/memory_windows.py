"""Sample Windows physical RAM, process working/private memory and GPU totals."""
import ctypes, json, subprocess, threading, time
from ctypes import wintypes

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_=[('dwLength',wintypes.DWORD),('dwMemoryLoad',wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in ['total_physical','available_physical','total_pagefile','available_pagefile','total_virtual','available_virtual','available_extended_virtual']]
class COUNTERS(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('page_fault_count',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ['peak_working_set','working_set','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile_usage','peak_pagefile_usage','private_usage']]

def snapshot(pid):
    m=MEMORYSTATUSEX(); m.dwLength=ctypes.sizeof(m); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    result={'monotonic':time.monotonic(),'available_ram_bytes':m.available_physical,'total_ram_bytes':m.total_physical,'process_working_set_bytes':None,'process_private_bytes':None,'process_page_fault_count':None,'gpu_used_mib':None,'gpu_temperature_c':None,'shared_gpu_memory_bytes':None}
    openprocess=ctypes.windll.kernel32.OpenProcess; openprocess.restype=wintypes.HANDLE
    openprocess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
    ctypes.windll.kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=openprocess(0x1000|0x10,False,pid)
    if handle:
        c=COUNTERS(); c.cb=ctypes.sizeof(c)
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb):
            result.update(process_working_set_bytes=c.working_set,process_private_bytes=c.private_usage,process_page_fault_count=c.page_fault_count)
        ctypes.windll.kernel32.CloseHandle(handle)
    try:
        p=subprocess.run(['nvidia-smi','--query-gpu=memory.used,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode==0:
            values=p.stdout.strip().splitlines()[0].split(','); result['gpu_used_mib']=float(values[0]); result['gpu_temperature_c']=float(values[1])
    except Exception: pass
    return result

class Monitor:
    def __init__(self,pid,path): self.pid=pid; self.path=path; self.samples=[]; self.event=threading.Event(); self.thread=None
    def loop(self):
        while not self.event.is_set():
            s=snapshot(self.pid); self.samples.append(s)
            with self.path.open('a',encoding='utf-8') as f: f.write(json.dumps(s)+'\n')
            self.event.wait(2)
    def start(self): self.thread=threading.Thread(target=self.loop,daemon=True); self.thread.start(); return self
    def stop(self):
        self.event.set(); self.thread.join(6)
        def extrema(key,fn):
            values=[s[key] for s in self.samples if s[key] is not None]; return fn(values) if values else None
        return {'peak_process_working_set_bytes':extrema('process_working_set_bytes',max),'peak_process_private_bytes':extrema('process_private_bytes',max),'minimum_available_ram_bytes':extrema('available_ram_bytes',min),'peak_gpu_used_mib_system_total':extrema('gpu_used_mib',max),'peak_gpu_temperature_c':extrema('gpu_temperature_c',max),'shared_gpu_memory_bytes':None,'sample_count':len(self.samples)}
