"""Pinned HumanEval test execution with a documented Windows process adapter."""
import ctypes,json,pathlib,subprocess,sys
from ctypes import wintypes as w
from .study import ROOT,load,sha

POLICY='humaneval-b9453e8-windows-full-module-v1'
VENDOR=ROOT/'vendor/humaneval/b9453e8'
WORKER=ROOT/'benchmarks/humaneval_standard_worker.py'
TIMEOUT=6
MEMORY_BYTES=256*1024**2

class BasicLimits(ctypes.Structure):
    _fields_=[('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',w.DWORD),('MinWS',ctypes.c_size_t),('MaxWS',ctypes.c_size_t),('ActiveProcesses',w.DWORD),('Affinity',ctypes.c_size_t),('Priority',w.DWORD),('Scheduling',w.DWORD)]
class IO(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint64) for n in ['ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes']]
class ExtendedLimits(ctypes.Structure):
    _fields_=[('Basic',BasicLimits),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]

def provenance():
    meta=load(VENDOR/'manifest.json')
    for name,digest in meta['files'].items():
        assert sha(VENDOR/name)==digest,'Pinned HumanEval vendor changed'
    return {'policy':POLICY,'upstream':meta,'worker_sha256':sha(WORKER),'adapter_sha256':sha(pathlib.Path(__file__)),'python':sys.version,'timeout_seconds':TIMEOUT,'process_memory_bytes':MEMORY_BYTES,'active_process_limit':1,'platform_adaptation':'Full module plus unchanged official tests/check; upstream reliability_guard and IO capture. Parent Windows JobObject/wall watchdog replaces POSIX SIGALRM and multiprocessing manager. No AST, builtin, or math/import whitelist. Not EvalPlus and not an exact official Linux execution environment.','security_scope':'JobObject limits resources and descendants; upstream reliability_guard is not an OS security sandbox.'}

def grade(code,problem):
    provenance()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.CloseHandle.argtypes=[w.HANDLE]
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise ctypes.WinError(ctypes.get_last_error())
    child=None
    try:
        limits=ExtendedLimits();limits.Basic.Flags=0x2000|0x100|0x8;limits.Basic.ActiveProcesses=1;limits.ProcessMemory=MEMORY_BYTES
        if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):raise ctypes.WinError(ctypes.get_last_error())
        child=subprocess.Popen([sys.executable,'-I','-B','-X','utf8',str(WORKER)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        if not kernel.AssignProcessToJobObject(job,w.HANDLE(int(child._handle))):raise ctypes.WinError(ctypes.get_last_error())
        try:out,err=child.communicate(json.dumps({'code':code,'problem':problem}),timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            child.kill();child.communicate();return {'passed':False,'status':'timeout'}
        if child.returncode:return {'passed':False,'status':'worker_error','returncode':child.returncode,'detail':err[-300:]}
        result=json.loads(out)
        if result.get('status')=='adapter_error':raise RuntimeError(result['detail'])
        return result
    finally:
        if child and child.poll() is None:child.kill();child.wait()
        kernel.CloseHandle(job)
