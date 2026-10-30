"""Draft: bounded, owned Windows subprocess tree using a Job Object.

This is a prototype, not connected to the SSH/SCP executor.  It uses
temporary files for standard streams, starts the process suspended, assigns it
to a kill-on-close job, and resumes it only after assignment succeeds.
"""
import ctypes, math, os, subprocess, sys, tempfile, time
from ctypes import wintypes

if sys.platform!='win32': raise RuntimeError('Windows-only prototype')
import _winapi, msvcrt

class IO_COUNTERS(ctypes.Structure):
    _fields_=[(n,ctypes.c_ulonglong) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]

class BASIC_LIMIT(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),
              ('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),
              ('ActiveProcessLimit',wintypes.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]

class EXTENDED_LIMIT(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BASIC_LIMIT),('IoInfo',IO_COUNTERS),
              ('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),
              ('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]

class BASIC_ACCOUNTING(ctypes.Structure):
    _fields_=[('TotalUserTime',ctypes.c_longlong),('TotalKernelTime',ctypes.c_longlong),
              ('ThisPeriodTotalUserTime',ctypes.c_longlong),('ThisPeriodTotalKernelTime',ctypes.c_longlong),
              ('TotalPageFaultCount',wintypes.DWORD),('TotalProcesses',wintypes.DWORD),
              ('ActiveProcesses',wintypes.DWORD),('TotalTerminatedProcesses',wintypes.DWORD)]

kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]; kernel.CreateJobObjectW.restype=wintypes.HANDLE
kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]; kernel.SetInformationJobObject.restype=wintypes.BOOL
kernel.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p]; kernel.QueryInformationJobObject.restype=wintypes.BOOL
kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]; kernel.AssignProcessToJobObject.restype=wintypes.BOOL
kernel.TerminateJobObject.argtypes=[wintypes.HANDLE,wintypes.UINT]; kernel.TerminateJobObject.restype=wintypes.BOOL
kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]; kernel.TerminateProcess.restype=wintypes.BOOL
kernel.ResumeThread.argtypes=[wintypes.HANDLE]; kernel.ResumeThread.restype=wintypes.DWORD
kernel.CloseHandle.argtypes=[wintypes.HANDLE]; kernel.CloseHandle.restype=wintypes.BOOL

def _active(job):
    info=BASIC_ACCOUNTING()
    if not kernel.QueryInformationJobObject(job,1,ctypes.byref(info),ctypes.sizeof(info),None): raise ctypes.WinError(ctypes.get_last_error())
    return info.ActiveProcesses

class TransportOutputLimitError(RuntimeError):
    """A stream exceeded the capture cap; no truncated success is returned."""

def _read_limited(stream,limit,deadline):
    if time.monotonic()>=deadline: raise TimeoutError('deadline before output read')
    stream.seek(0,os.SEEK_END); size=stream.tell()
    if size>limit: raise TransportOutputLimitError('transport output exceeds byte limit')
    stream.seek(0); chunks=[]; remaining=size
    while remaining:
        if time.monotonic()>=deadline: raise TimeoutError('deadline during output read')
        chunk=stream.read(min(65536,remaining))
        if not chunk: raise OSError('transport output changed during read')
        chunks.append(chunk); remaining-=len(chunk)
    if time.monotonic()>=deadline: raise TimeoutError('deadline after output read')
    return b''.join(chunks)

def run_owned(argv,*,input_bytes=None,timeout,cleanup_wait=2,max_output_bytes=64*1024*1024):
    """Return CompletedProcess or raise TimeoutExpired; no shell or network implied.

    timeout governs launch + work.  On timeout cleanup may take at most the
    additional cleanup_wait; failure to verify termination is explicit on the
    raised exception as cleanup_verified=False.  OS call delays themselves are
    not provably hard-bounded by Python.
    """
    if not argv or not math.isfinite(timeout) or timeout<=0 or not math.isfinite(cleanup_wait) or cleanup_wait<0 or isinstance(max_output_bytes,bool) or not isinstance(max_output_bytes,int) or max_output_bytes<0: raise ValueError('invalid args/timeout')
    start=time.monotonic(); deadline=start+timeout
    job=kernel.CreateJobObjectW(None,None)
    if not job: raise ctypes.WinError(ctypes.get_last_error())
    process=thread=None; pid=None; assigned=False
    def stop_owned():
        cleanup_error=None; verified=False
        if not kernel.TerminateJobObject(job,1): cleanup_error='TerminateJobObject failed: '+str(ctypes.get_last_error())
        cleanup_deadline=time.monotonic()+cleanup_wait
        try:
            while _active(job) and time.monotonic()<cleanup_deadline: time.sleep(min(.01,max(0,cleanup_deadline-time.monotonic())))
            verified=_active(job)==0
        except OSError as exc: cleanup_error=str(exc)
        return verified,cleanup_error
    def timeout_error(pid=None):
        verified,cleanup_error=stop_owned()
        # Do not read outputs on timeout: writers could survive and files can be
        # arbitrarily large. This also bounds Python-side output handling.
        exc=subprocess.TimeoutExpired(argv,timeout,output=None,stderr=None)
        exc.cleanup_verified=verified; exc.cleanup_error=cleanup_error; exc.pid=pid
        raise exc
    def limit_error(pid,stream,size):
        verified,cleanup_error=stop_owned()
        exc=TransportOutputLimitError(f'{stream} exceeded byte limit ({size} > {max_output_bytes})')
        exc.cleanup_verified=verified; exc.cleanup_error=cleanup_error; exc.pid=pid
        exc.stream=stream; exc.observed_bytes=size; exc.limit=max_output_bytes
        raise exc
    try:
        info=EXTENDED_LIMIT(); info.BasicLimitInformation.LimitFlags=0x00002000  # KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)): raise ctypes.WinError(ctypes.get_last_error())
        with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            if input_bytes is not None: stdin.write(input_bytes)
            stdin.seek(0)
            handles=[msvcrt.get_osfhandle(f.fileno()) for f in (stdin,stdout,stderr)]
            for h in handles: os.set_handle_inheritable(h,True)
            si=subprocess.STARTUPINFO(); si.dwFlags|=_winapi.STARTF_USESTDHANDLES
            si.hStdInput,si.hStdOutput,si.hStdError=handles
            si.lpAttributeList={'handle_list':handles}
            try:
                process,thread,pid,tid=_winapi.CreateProcess(str(argv[0]),subprocess.list2cmdline(list(argv)),None,None,True,
                    0x00000004|_winapi.CREATE_NO_WINDOW,None,None,si)  # CREATE_SUSPENDED
            finally:
                for h in handles: os.set_handle_inheritable(h,False)
            if not kernel.AssignProcessToJobObject(job,process):
                error=ctypes.WinError(ctypes.get_last_error())
                killed=bool(kernel.TerminateProcess(process,1))
                waited=_winapi.WaitForSingleObject(process,1000)
                if not killed or waited!=_winapi.WAIT_OBJECT_0: raise RuntimeError('Job assignment failed; suspended-process cleanup unverified') from error
                raise error
            assigned=True
            if time.monotonic()>=deadline: timeout_error(pid)
            if kernel.ResumeThread(thread)==0xffffffff: raise ctypes.WinError(ctypes.get_last_error())
            _winapi.CloseHandle(thread); thread=None
            while True:
                if time.monotonic()>=deadline: timeout_error(pid)
                active=_active(job)
                if time.monotonic()>=deadline: timeout_error(pid)
                # Polling reduces, but cannot eliminate, output overshoot: a
                # writer can produce data between checks or during an OS call.
                for name,stream in (('stdout',stdout),('stderr',stderr)):
                    size=os.fstat(stream.fileno()).st_size
                    if size>max_output_bytes: limit_error(pid,name,size)
                if active==0:
                    code=_winapi.GetExitCodeProcess(process)
                    try:
                        out=_read_limited(stdout,max_output_bytes,deadline)
                        err=_read_limited(stderr,max_output_bytes,deadline)
                    except TimeoutError: timeout_error(pid)
                    return subprocess.CompletedProcess(argv,code,out,err)
                remaining=deadline-time.monotonic()
                if remaining<=0: timeout_error(pid)
                time.sleep(min(.01,remaining))
    except BaseException as exc:
        # Preserve the original failure (including KeyboardInterrupt), but
        # expose whether our own process group was observed stopped. A local
        # result says nothing about a remote SSH command or transfer.
        if not hasattr(exc,'pid'): exc.pid=pid
        if not hasattr(exc,'cleanup_verified'):
            cleanup_verified=False; cleanup_error=None
            try:
                if assigned:
                    cleanup_verified,cleanup_error=stop_owned()
                elif process:
                    signalled=_winapi.WaitForSingleObject(process,0)==_winapi.WAIT_OBJECT_0
                    if not signalled and not kernel.TerminateProcess(process,1):
                        cleanup_error='TerminateProcess failed: '+str(ctypes.get_last_error())
                    cleanup_verified=(_winapi.WaitForSingleObject(process,int(cleanup_wait*1000))==_winapi.WAIT_OBJECT_0)
                else:
                    cleanup_verified=True
            except BaseException as cleanup_exc:
                cleanup_error='cleanup could not be verified: '+str(cleanup_exc)
            exc.cleanup_verified=cleanup_verified
            exc.cleanup_error=cleanup_error
        raise
    finally:
        if assigned:
            # Also kills a still-running owned tree on KeyboardInterrupt/errors.
            kernel.TerminateJobObject(job,1)
        elif process:
            kernel.TerminateProcess(process,1)
        if thread: _winapi.CloseHandle(thread)
        if process: _winapi.CloseHandle(process)
        kernel.CloseHandle(job)
