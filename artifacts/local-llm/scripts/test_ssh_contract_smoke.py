"""Synthetic tests for the SSH smoke harness; no SSH or subprocess is used."""
import base64, hashlib, json, pathlib, tempfile, unittest
import smoke_ssh_contract as smoke_module

ALIAS='fixture-peer'
TOKEN='1'*32

class Clock:
    def __init__(self): self.now=0
    def monotonic(self): return self.now
    def sleep(self,seconds): self.now+=seconds

class World:
    def __init__(self,mode='ok'):
        self.mode=mode; self.calls=[]; self.remote=None; self.files={}; self.executor=None
        self.host={'worker_path':'/home/tester/llm-test/executor_worker.py',
                   'workspace_root':'/home/tester/llm-test/workspace',
                   'state_root':'/home/tester/llm-test/jobs'}
    def bridge_factory(self,alias):
        if alias!=ALIAS: raise KeyError(alias)
        world=self
        class FakeBridge:
            host=world.host
            def preflight(self):
                world.calls.append('preflight')
                if world.mode=='preflight_error': raise RuntimeError('simulated preflight failure')
                return {'hostname':'linux-fixture','bash':'/bin/bash','worker_sha256':'a'*64}
            def __call__(self,payload):
                world.calls.append(payload['action'])
                if payload['action']=='seed':
                    world.remote=payload['directory']
                    return {'seeded':True,'host':'linux-fixture','directory':world.remote}
                if payload['action']=='snapshot':
                    if world.mode=='snapshot_nonobject': return None
                    files={}
                    for name,data in world.files.items():
                        digest=hashlib.sha256(data).hexdigest()
                        if world.mode=='bad_remote_hash' and name.startswith('転送 '): digest='0'*64
                        files[name]={'base64':base64.b64encode(data).decode(),'sha256':digest,'executable':False}
                    host='wrong-host' if world.mode=='snapshot_wrong_host' else 'linux-fixture'
                    return {'host':host,'directory':world.remote,'files':files}
                raise AssertionError(payload['action'])
        return FakeBridge()
    def executor_factory(self,workspace):
        self.calls.append('executor')
        self.executor=FakeExecutor(self,workspace)
        return self.executor

class FakeExecutor:
    def __init__(self,world,workspace):
        self.world=world; self.workspace=pathlib.Path(workspace); self.started_jobs=set(); self.jobs={}; self.count=0
    def packet(self,job,status,out='',err='',offset=0,err_offset=0,exit_code=None,**extra):
        raw=out.encode('utf-8'); eraw=err.encode('utf-8')
        return {'job_id':job,'status':status,'exit_code':exit_code,'host':ALIAS,'cwd':self.world.remote,
                'stdout':out,'stderr':err,'stdout_offset':offset,'stderr_offset':err_offset,
                'stdout_next_offset':offset+len(raw),'stderr_next_offset':err_offset+len(eraw),**extra}
    def execute(self,name,args):
        self.world.calls.append(name)
        if name=='run_ssh_bash':
            self.count+=1; job=f'{self.count:032x}'; self.started_jobs.add(job)
            script=args['script']; self.jobs[job]={'status':'completed','kind':'other'}
            if self.world.mode=='start_unknown' and '# smoke:stdio' in script:
                self.jobs[job]={'status':'unknown','kind':'unknown'}
                return {'job_id':job,'status':'unknown','may_be_running':True,'error':'simulated timeout'}
            if self.world.mode in ('interrupt','interrupt_unresolved') and '# smoke:stdio' in script:
                self.jobs[job]={'status':'unknown' if self.world.mode=='interrupt_unresolved' else 'running',
                                'kind':'unknown' if self.world.mode=='interrupt_unresolved' else 'other'}
                raise KeyboardInterrupt()
            if '# smoke:stdio' in script:
                return self.packet(job,'completed',smoke_module.STDOUT+'\n',smoke_module.STDERR+'\n',exit_code=7)
            if '# smoke:environment' in script:
                value=next(iter(args.get('env',{}).values()),None)
                out=json.dumps({'hostname':'linux-fixture','cwd':self.world.remote,'value':value},ensure_ascii=False)+'\n'
                return self.packet(job,'completed',out,exit_code=0)
            if '# smoke:async' in script:
                self.jobs[job]={'status':'running','kind':'async'}
                initial='開始 α\n'
                response=self.packet(job,'running',initial)
                if self.world.mode=='bad_offsets': response['stdout_next_offset']+=1
                return response
            if '# smoke:stubborn' in script:
                self.jobs[job]={'status':'running','kind':'stubborn'}
                self.world.files['child-identity.json']=json.dumps({'pid':123,'start':'456'}).encode()
                return self.packet(job,'running',smoke_module.CHILD_READY+'\n')
            if '# smoke:stop-proof' in script:
                proof={'same_process_alive':False,'late_marker_exists':self.world.mode=='late_marker'}
                return self.packet(job,'completed',json.dumps(proof)+'\n',exit_code=0)
            raise AssertionError('unexpected script')
        if name=='poll_process':
            job=args['job_id']; state=self.jobs[job]
            if state['kind']=='unknown': return {'job_id':job,'status':'unknown','error':'simulated unreachable'}
            if state['kind']=='async' and state['status']=='running':
                state['status']='completed'
                result=self.packet(job,'completed','完了 β\n',offset=args.get('stdout_offset',0),
                                   err_offset=args.get('stderr_offset',0),exit_code=0)
                if self.world.mode=='poll_wrong_job': result['job_id']='f'*32
                if self.world.mode=='poll_wrong_host': result['host']='wrong-host'
                if self.world.mode=='poll_wrong_offset': result['stdout_offset']=0
                return result
            return self.packet(job,state['status'],offset=args.get('stdout_offset',0),
                               err_offset=args.get('stderr_offset',0),exit_code=0 if state['status']=='completed' else None)
        if name=='stop_process':
            job=args['job_id']; self.jobs[job]['status']='completed'
            verified=self.world.mode!='stop_unverified'
            result=self.packet(job,'completed',exit_code=-9,stop_verified=verified,process_group_exited=verified)
            if self.world.mode=='stop_wrong_job': result['job_id']='f'*32
            if self.world.mode=='stop_wrong_host': result['host']='wrong-host'
            return result
        if name=='transfer_file':
            path=pathlib.Path(args['local_path']); remote=pathlib.PurePosixPath(args['remote_path']).name
            if args['direction']=='upload': self.world.files[remote]=path.read_bytes()
            else: path.write_bytes(self.world.files[remote])
            return {'host':ALIAS,'status':'completed','exit_code':0,'local_path':str(path),
                    'remote_path':args['remote_path'],'local_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'remote_sha256':None,'bytes':path.stat().st_size}
        raise AssertionError(name)

class SSHContractSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ssh-contract-test-'); self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
    def run_world(self,mode='ok',alias=ALIAS):
        world=World(mode); result=smoke_module.smoke(alias,root=self.root,bridge_factory=world.bridge_factory,
            executor_factory=world.executor_factory,clock=Clock(),run_token=TOKEN)
        return result,world
    def test_success_requires_all_checks_and_preflight_before_seed(self):
        report,world=self.run_world()
        self.assertTrue(report['passed']); self.assertEqual(report['status'],'completed')
        self.assertEqual(world.calls[:3],['preflight','seed','executor'])
        self.assertEqual(report['unresolved_jobs'],[])
        self.assertTrue(all(c['passed'] for c in report['checks']))
        self.assertIn('stop_independent_process_and_marker',[c['name'] for c in report['checks']])
        self.assertIn('転送 \'見本\' "日本語".txt',world.files)
        self.assertEqual((pathlib.Path(report['local_directory'])/'回収 日本語.txt').read_bytes(),smoke_module.PAYLOAD)
        saved=json.loads((self.root/'runs'/('ssh-contract-'+TOKEN+'.json')).read_text(encoding='utf-8'))
        self.assertTrue(saved['passed'])
    def test_unconfigured_host_never_attempts_ssh(self):
        report,world=self.run_world(alias='not-configured')
        self.assertFalse(report['passed']); self.assertFalse(report['ssh_attempted']); self.assertEqual(world.calls,[])
    def test_preflight_failure_records_attempt_without_claiming_connection_success(self):
        report,world=self.run_world('preflight_error')
        self.assertFalse(report['passed']); self.assertTrue(report['ssh_attempted']); self.assertFalse(report['ssh_executed'])
        self.assertEqual(world.calls,['preflight'])
    def test_unknown_start_is_not_passed_and_id_remains_unresolved(self):
        report,_=self.run_world('start_unknown')
        self.assertFalse(report['passed']); self.assertEqual(len(report['unresolved_jobs']),1)
        self.assertEqual(report['cleanup'][0]['status'],'unknown')
    def test_bad_byte_offsets_fail(self):
        report,_=self.run_world('bad_offsets')
        self.assertFalse(report['passed']); self.assertIn('byte offset',report['error']['message'])
    def test_poll_job_host_and_requested_offset_mismatch_fail(self):
        for mode in ('poll_wrong_job','poll_wrong_host','poll_wrong_offset'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp:
                world=World(mode)
                report=smoke_module.smoke(ALIAS,root=pathlib.Path(temp),bridge_factory=world.bridge_factory,
                    executor_factory=world.executor_factory,clock=Clock(),run_token=TOKEN)
                self.assertFalse(report['passed'])
                self.assertTrue('mismatch' in report['error']['message'])
    def test_stop_job_and_host_mismatch_leave_unresolved(self):
        for mode in ('stop_wrong_job','stop_wrong_host'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp:
                world=World(mode)
                report=smoke_module.smoke(ALIAS,root=pathlib.Path(temp),bridge_factory=world.bridge_factory,
                    executor_factory=world.executor_factory,clock=Clock(),run_token=TOKEN)
                self.assertFalse(report['passed']); self.assertEqual(report['error']['message'],'stop_verified_group')
                self.assertTrue(report['unresolved_jobs'])
    def test_snapshot_host_mismatch_is_not_passed(self):
        report,_=self.run_world('snapshot_wrong_host')
        self.assertFalse(report['passed']); self.assertEqual(report['error']['message'],'child_snapshot_host')
        self.assertTrue(report['unresolved_jobs'])
    def test_nonobject_snapshot_is_explicitly_rejected(self):
        report,_=self.run_world('snapshot_nonobject')
        self.assertFalse(report['passed']); self.assertEqual(report['error']['message'],'child_snapshot_host')
        self.assertTrue(report['unresolved_jobs'])
    def test_unverified_stop_remains_unresolved_even_if_shell_completed(self):
        report,_=self.run_world('stop_unverified')
        self.assertFalse(report['passed']); self.assertEqual(len(report['unresolved_jobs']),1)
        self.assertEqual(report['error']['message'],'stop_verified_group')
    def test_late_marker_fails_independent_stop_proof(self):
        report,_=self.run_world('late_marker')
        self.assertFalse(report['passed']); self.assertEqual(len(report['unresolved_jobs']),1)
        self.assertEqual(report['error']['message'],'stop_independent_process_and_marker')
    def test_remote_hash_mismatch_is_not_passed(self):
        report,_=self.run_world('bad_remote_hash')
        self.assertFalse(report['passed']); self.assertEqual(report['error']['message'],'remote_content_and_hash')
    def test_existing_report_is_never_overwritten(self):
        report,world=self.run_world(); path=self.root/'runs'/('ssh-contract-'+TOKEN+'.json')
        original=path.read_bytes(); calls=list(world.calls)
        with self.assertRaises(FileExistsError):
            smoke_module.smoke(ALIAS,root=self.root,bridge_factory=world.bridge_factory,
                executor_factory=world.executor_factory,clock=Clock(),run_token=TOKEN)
        self.assertEqual(path.read_bytes(),original); self.assertEqual(world.calls,calls)
    def test_interrupt_is_saved_and_reraised_after_cleanup(self):
        for mode in ('interrupt','interrupt_unresolved'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp:
                root=pathlib.Path(temp); world=World(mode)
                with self.assertRaises(KeyboardInterrupt):
                    smoke_module.smoke(ALIAS,root=root,bridge_factory=world.bridge_factory,
                        executor_factory=world.executor_factory,clock=Clock(),run_token=TOKEN)
                report=json.loads((root/'runs'/('ssh-contract-'+TOKEN+'.json')).read_text(encoding='utf-8'))
                self.assertEqual(report['status'],'interrupted'); self.assertFalse(report['passed'])
                self.assertEqual(report['error']['type'],'KeyboardInterrupt')
                self.assertTrue(report['cleanup'])
                self.assertEqual(bool(report['unresolved_jobs']),mode=='interrupt_unresolved')

if __name__=='__main__': unittest.main(verbosity=2)
