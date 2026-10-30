"""Tool contract. SSH targets come only from a configured allowlist."""
import base64, hashlib, json, pathlib, shlex, subprocess, time, uuid
from executor_worker import check_cwd, launch, poll, stop
from bounded_windows import run_owned
from server import ROOT

def transport_cleanup_details(error):
    """Local client cleanup is independent of the state at the SSH peer."""
    return {'local_transport_cleanup_verified':getattr(error,'cleanup_verified',None),
            'local_transport_cleanup_error':getattr(error,'cleanup_error',None),
            'local_transport_pid':getattr(error,'pid',None)}

def annotate_interrupt(error,**details):
    error.transport_details={**transport_cleanup_details(error),**details}

def schema(name,description,properties,required):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}}
STR={'type':'string'}
RUN={'script':STR,'cwd':STR,'env':{'type':'object','additionalProperties':{'type':'string'}},'timeout':{'type':'number','minimum':0,'maximum':60}}

class RemotePreStartRejected(Exception):
    """A rejection backed by a verified protocol guarantee of no launch.

    The current worker does not emit such a guarantee. Ordinary RPC errors,
    including remote ValueError, do not establish that no process started.
    """

def validate_remote_envelope(result,job_id,alias,stdout_offset=0,stderr_offset=0,allow_unknown=False):
    """Validate a worker start/poll/stop envelope before trusting its state."""
    if not isinstance(result,dict) or result.get('job_id')!=job_id:
        raise RuntimeError('Remote start response has missing or mismatched job id')
    if result.get('host')!=alias or not isinstance(result.get('cwd'),str) or not result['cwd']:
        raise RuntimeError('Remote start response has invalid host or cwd')
    status=result.get('status')
    allowed=('running','completed','unknown') if allow_unknown else ('running','completed')
    if status not in allowed or result.get('real_execution') is not True:
        raise RuntimeError('Remote start response has invalid status or execution marker')
    if 'exit_code' not in result:
        raise RuntimeError('Remote start response has no exit code field')
    code=result['exit_code']
    if code is not None and (isinstance(code,bool) or not isinstance(code,int)):
        raise RuntimeError('Remote start response has invalid exit code')
    if (status in ('running','unknown') and code is not None) or (status=='completed' and code is None):
        raise RuntimeError('Remote start response has inconsistent exit status')
    if 'stop_verified' in result and not isinstance(result['stop_verified'],bool):
        raise RuntimeError('Remote response has invalid stop verification')
    if result.get('stop_verified') is True and (status!='completed' or result.get('stopped') is not True or result.get('process_group_exited') is not True or result.get('stop_scope')!='remote POSIX process group'):
        raise RuntimeError('Remote response does not prove verified group termination')
    for stream in ('stdout','stderr'):
        encoded=result.get(stream+'_base64')
        if not isinstance(encoded,str): raise RuntimeError('Remote start response has missing '+stream+' bytes')
        try: data=base64.b64decode(encoded,validate=True)
        except Exception as e: raise RuntimeError('Remote start response has invalid '+stream+' base64') from e
        offset=result.get(stream+'_offset'); next_offset=result.get(stream+'_next_offset'); size=result.get(stream+'_bytes')
        if any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in (offset,next_offset,size)):
            raise RuntimeError('Remote start response has invalid '+stream+' offsets')
        requested=stdout_offset if stream=='stdout' else stderr_offset
        if isinstance(requested,bool) or not isinstance(requested,int) or requested<0 or offset!=requested or next_offset!=offset+len(data) or next_offset>size:
            raise RuntimeError('Remote start response has inconsistent '+stream+' offsets')
        if not isinstance(result.get(stream+'_truncated'),bool) or result[stream+'_truncated']!=(next_offset<size):
            raise RuntimeError('Remote start response has inconsistent '+stream+' truncation')
        if not isinstance(result.get(stream+'_log'),str) or not result[stream+'_log']:
            raise RuntimeError('Remote start response has no '+stream+' log path')

def validate_remote_start(result,job_id,alias):
    validate_remote_envelope(result,job_id,alias)

TOOLS=[schema('run_powershell','Windowsの新しいPowerShell 7プロセスで実行。cwdとenvは毎回明示。timeoutは最大60秒の待機時間で、超過してもjobは続く。',RUN,['script','cwd']),
       schema('run_ssh_bash','許可済みSSH hostで新しいBashプロセスを実行。状態は毎回リセット。待機超過時はjob_idをpollする。',{**RUN,'host_alias':STR},['host_alias','script','cwd']),
       schema('poll_process','管理jobの完了と追記出力を確認。offsetは前回のnext_offsetを指定。',{'job_id':STR,'stdout_offset':{'type':'integer','minimum':0},'stderr_offset':{'type':'integer','minimum':0}},['job_id']),
       schema('stop_process','管理jobのプロセスグループを停止し、実際の終了を確認。',{'job_id':STR},['job_id']),
       schema('transfer_file','許可済みSSH hostとのファイル転送。local_pathとremote_pathは絶対パス。',{'host_alias':STR,'direction':{'type':'string','enum':['upload','download']},'local_path':STR,'remote_path':STR},['host_alias','direction','local_path','remote_path'])]

class Executor:
    def __init__(self,workspace=None):
        self.workspace=str(pathlib.Path(workspace or ROOT/'workspace').resolve())
        pathlib.Path(self.workspace).mkdir(parents=True,exist_ok=True)
        self.config=json.loads((ROOT/'executor-config.json').read_text(encoding='utf-8-sig'))
        self.registry=ROOT/'jobs-registry.json'
        self.index=ROOT/'jobs-index'; self.index.mkdir(exist_ok=True)
        self.started_jobs=set()
        self.deadline=None
    def jobs(self): return json.loads(self.registry.read_text()) if self.registry.exists() else {}
    def remember(self,job_id,alias):
        self.started_jobs.add(job_id)
        path=self.index/(job_id+'.json')
        if not path.exists(): path.write_text(json.dumps({'host_alias':alias}),encoding='utf-8')
    def job_info(self,job_id):
        if len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id): raise ValueError('Invalid managed job id')
        path=self.index/(job_id+'.json')
        return json.loads(path.read_text()) if path.exists() else self.jobs().get(job_id)
    def not_started(self,job_id,alias):
        self.started_jobs.discard(job_id)
        (self.index/(job_id+'.json')).write_text(json.dumps({'host_alias':alias,'state':'not_started'}),encoding='utf-8')
    def set_stop_unverified(self,job_id,unverified):
        # Persist uncertainty across later polls and fresh Executor instances.
        record=dict(self.job_info(job_id))
        if unverified: record['stop_unverified']=True
        else: record.pop('stop_unverified',None)
        path=self.index/(job_id+'.json'); tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps(record),encoding='utf-8'); tmp.replace(path)
    def register(self,result,alias):
        self.remember(result['job_id'],alias)
        return self.decode(result)
    def transport_timeout(self,maximum):
        deadline=getattr(self,'deadline',None)
        if deadline is None: return maximum
        remaining=deadline-time.perf_counter()
        if remaining<=0: raise TimeoutError('Task deadline reached before transport started')
        return min(maximum,remaining)
    def remote(self,alias,payload):
        host=self.config['ssh_hosts'].get(alias)
        if host is None: raise ValueError('host_alias is not configured')
        command='python3 '+shlex.quote(host['worker_path'])
        p=run_owned([self.config['ssh'],'-T','-o','BatchMode=yes','-o','ConnectTimeout=10',alias,command],input_bytes=json.dumps(payload,ensure_ascii=False).encode('utf-8'),timeout=self.transport_timeout(90))
        if p.returncode:
            try: error=json.loads(p.stdout)
            except ValueError: error={}
            # Even a structured ValueError may have happened after Popen.
            if not isinstance(error,dict): error={}
            detail=error.get('error') or p.stderr.decode('utf-8',errors='replace') or p.stdout.decode('utf-8',errors='replace')
            raise RuntimeError('Remote worker error: '+str(detail))
        result=json.loads(p.stdout)
        if not isinstance(result,dict): raise RuntimeError('Remote worker response must be an object')
        if result.get('error'): raise RuntimeError(result['error'])
        return result
    def decode(self,result):
        for name in ['stdout','stderr']:
            data=base64.b64decode(result.pop(name+'_base64',''))
            result[name]=data.decode('utf-8',errors='replace')
        return result
    def execute(self,name,args):
        if name=='run_powershell':
            check_cwd(args['cwd'],self.workspace)
            job_id=uuid.uuid4().hex; self.remember(job_id,None)
            try: result=launch({**args,'job_id':job_id,'state_root':str(ROOT/'jobs'),'workspace_root':self.workspace,'host':'windows-local','powershell':self.config['powershell']})
            except KeyboardInterrupt: raise
            except Exception as e:
                # Popen may already have succeeded even if writing worker.json
                # failed. Missing metadata is not proof that nothing started.
                return {'job_id':job_id,'status':'unknown','exit_code':None,'host':'windows-local','error':str(e),'may_be_running':True}
            return self.register(result,None)
        if name=='run_ssh_bash':
            a=dict(args); alias=a.pop('host_alias'); h=self.config['ssh_hosts'].get(alias)
            if h is None: raise ValueError('host_alias is not configured')
            job_id=uuid.uuid4().hex; self.remember(job_id,alias)
            try:
                result=self.remote(alias,{'action':'start',**a,'job_id':job_id,'state_root':h['state_root'],'workspace_root':h['workspace_root'],'host':alias})
                validate_remote_start(result,job_id,alias)
                return self.register(result,alias)
            except RemotePreStartRejected: self.not_started(job_id,alias); raise
            except KeyboardInterrupt as e:
                annotate_interrupt(e,host=alias,job_id=job_id,remote_status='unknown',may_be_running=True)
                raise
            except Exception as e: return {'job_id':job_id,'status':'unknown','exit_code':None,'host':alias,'error':str(e),'may_be_running':True,**transport_cleanup_details(e)}
        if name in ['poll_process','stop_process']:
            job=self.job_info(args['job_id'])
            if job is None: raise ValueError('unknown managed job')
            alias=job['host_alias']; action='poll' if name=='poll_process' else 'stop'
            if job.get('state')=='not_started': return {'job_id':args['job_id'],'status':'not_started','exit_code':None,'host':alias or 'windows-local'}
            if alias:
                h=self.config['ssh_hosts'][alias]
                try:
                    response=self.remote(alias,{'action':action,**args,'state_root':h['state_root']})
                    stdout_offset=args.get('stdout_offset',0) if action=='poll' else 0
                    stderr_offset=args.get('stderr_offset',0) if action=='poll' else 0
                    validate_remote_envelope(response,args['job_id'],alias,stdout_offset,stderr_offset,allow_unknown=True)
                    result=self.decode(response)
                    if result['status']=='unknown': result['may_be_running']=True
                    verified=result.get('stop_verified') is True
                    if verified and job.get('stop_unverified'):
                        self.set_stop_unverified(args['job_id'],False)
                    uncertain_stop=(action=='stop' and not verified) or result.get('stop_verified') is False
                    if uncertain_stop: self.set_stop_unverified(args['job_id'],True)
                    if uncertain_stop or (action=='poll' and job.get('stop_unverified') and not verified and result['status']=='completed'):
                        # A completed shell alone does not prove its remote group
                        # and descendants are gone. Preserve that uncertainty.
                        result['worker_status']=result['status']; result['worker_exit_code']=result['exit_code']
                        result['status']='unknown'; result['exit_code']=None
                        result['stop_verified']=False; result['may_be_running']=True
                    return result
                except KeyboardInterrupt as e:
                    if action=='stop': self.set_stop_unverified(args['job_id'],True)
                    annotate_interrupt(e,host=alias,job_id=args['job_id'],remote_status='unknown',may_be_running=True)
                    raise
                except Exception as e:
                    if action=='stop': self.set_stop_unverified(args['job_id'],True)
                    return {'job_id':args['job_id'],'status':'unknown','exit_code':None,'host':alias,
                            'error':str(e),'may_be_running':True,**transport_cleanup_details(e)}
            if not (ROOT/'jobs'/args['job_id']/'request.json').exists():
                self.not_started(args['job_id'],None)
                return {'job_id':args['job_id'],'status':'not_started','exit_code':None,'host':'windows-local'}
            result=poll(str(ROOT/'jobs'),**args) if action=='poll' else stop(str(ROOT/'jobs'),args['job_id'])
            return self.decode(result)
        if name=='transfer_file':
            alias=args['host_alias']; h=self.config['ssh_hosts'].get(alias)
            if h is None: raise ValueError('host_alias is not configured')
            local=pathlib.Path(args['local_path']).resolve(); remote=args['remote_path']
            if not local.is_relative_to(pathlib.Path(self.workspace)): raise ValueError('local_path outside workspace')
            if not remote.startswith(h['workspace_root'].rstrip('/')+'/') or '..' in pathlib.PurePosixPath(remote).parts: raise ValueError('remote_path outside workspace')
            target=f'{alias}:{remote}'
            if args['direction']=='upload': src,dst=str(local),target
            elif args['direction']=='download': src,dst=target,str(local)
            else: raise ValueError('invalid transfer direction')
            try:
                p=run_owned([self.config['scp'],'-B','-o','ConnectTimeout=10',src,dst],timeout=self.transport_timeout(120))
            except KeyboardInterrupt as e:
                annotate_interrupt(e,host=alias,remote_status='unknown',may_be_partial=True,local_path=str(local),remote_path=remote)
                raise
            except Exception as e:
                return {'host':alias,'status':'unknown','exit_code':None,'may_be_partial':True,
                        'error':'SCP transport failed; transfer may be partial: '+str(e),**transport_cleanup_details(e),
                        'local_path':str(local),'remote_path':remote,'bytes':None,'local_sha256':None,
                        'remote_sha256':None,'real_execution':None}
            if p.returncode:
                return {'host':alias,'status':'unknown','exit_code':p.returncode,'may_be_partial':True,
                        'stderr':p.stderr.decode('utf-8',errors='replace'),'local_path':str(local),'remote_path':remote,
                        'bytes':None,'local_sha256':None,'remote_sha256':None,'real_execution':True}
            try:
                size=local.stat().st_size
                if not local.is_file(): raise OSError('Transfer path is not a regular file')
                digest=hashlib.sha256(local.read_bytes()).hexdigest()
            except KeyboardInterrupt as e:
                annotate_interrupt(e,host=alias,remote_status='unknown',may_be_partial=True,
                                   verification_status='incomplete',transfer_client_exit_code=0,
                                   local_transport_cleanup_verified=True,local_path=str(local),remote_path=remote)
                raise
            except Exception as e:
                return {'host':alias,'status':'unknown','exit_code':0,'transfer_client_exit_code':0,
                        'verification_status':'incomplete','may_be_partial':True,'error':str(e),
                        'local_transport_cleanup_verified':True,'local_path':str(local),'remote_path':remote,
                        'bytes':None,'local_sha256':None,'remote_sha256':None,'real_execution':True}
            return {'host':alias,'status':'completed','exit_code':p.returncode,'stderr':p.stderr.decode('utf-8',errors='replace'),'local_path':str(local),'remote_path':remote,'bytes':size,'local_sha256':digest,'remote_sha256':None,'real_execution':True}
        raise ValueError('unknown tool')
