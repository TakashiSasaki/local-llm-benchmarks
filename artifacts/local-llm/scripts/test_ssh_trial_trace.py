"""Model-free tests for SSH task trace evidence, without network access."""
import copy, json, pathlib, tempfile, unittest
from trial import _direct_long_script,execution_trace

HOST='test-linux'
REMOTE='/home/testuser/llm-eval/trial/S3'
JOB='a'*32

def event(name,args,result):
    return {'call':{'function':{'name':name,'arguments':json.dumps(args,ensure_ascii=False)}},'result':result}

def start(script='./long.sh',host=HOST,cwd=REMOTE,job=JOB,status='running',exit_code=None,result_host=None):
    return event('run_ssh_bash',{'host_alias':host,'cwd':cwd,'script':script},
                 {'host':host if result_host is None else result_host,'job_id':job,'status':status,'exit_code':exit_code})

def poll(job=JOB,status='completed',exit_code=0,host=HOST,result_job=None):
    return event('poll_process',{'job_id':job},{'host':host,'job_id':job if result_job is None else result_job,'status':status,'exit_code':exit_code})

class S2TraceTests(unittest.TestCase):
    remote='/home/testuser/llm-eval/trial/S2'
    first='1'*32
    second='2'*32
    def start_step(self,script,job,status='completed',exit_code=0,host=HOST,result_host=None,cwd=None,env=None):
        return event('run_ssh_bash',{'host_alias':host,'cwd':cwd or self.remote+'/work','script':script,
                     'env':env if env is not None else {'BUILD_LABEL':'日本語 label','REGION':'test-east'}},
                     {'host':host if result_host is None else result_host,'job_id':job,'status':status,'exit_code':exit_code})
    def trace(self,events): return execution_trace('S2',events,HOST,self.remote,pathlib.Path('C:/LocalLLM/workspace/test'))
    def good(self): return [self.start_step('./step1.sh',self.first),self.start_step('./step2.sh',self.second)]
    def test_synchronous_calls_with_explicit_arguments(self):
        self.assertTrue(all(self.trace(self.good()).values()))
    def test_async_completion_before_next_job(self):
        events=[self.start_step('bash step1.sh',self.first,status='running',exit_code=None),
                poll(job=self.first),self.start_step('bash ./step2.sh',self.second,status='running',exit_code=None),poll(job=self.second)]
        self.assertTrue(all(self.trace(events).values()))
    def test_unrelated_failed_commands_do_not_count(self):
        events=[self.start_step('false',self.first,exit_code=1),self.start_step('false',self.second,exit_code=1)]
        self.assertFalse(all(self.trace(events).values()))
    def test_step2_must_start_after_step1_success(self):
        first=self.start_step('./step1.sh',self.first,status='running',exit_code=None)
        second=self.start_step('./step2.sh',self.second,status='running',exit_code=None)
        self.assertFalse(all(self.trace([second,first,poll(job=self.first),poll(job=self.second)]).values()))
        self.assertFalse(all(self.trace([first,second,poll(job=self.first),poll(job=self.second)]).values()))
    def test_separate_jobs_and_separate_calls_required(self):
        self.assertFalse(all(self.trace([self.good()[0],self.start_step('./step2.sh',self.first)]).values()))
        self.assertFalse(all(self.trace([self.start_step('./step1.sh; ./step2.sh',self.first),self.start_step('true',self.second)]).values()))
    def test_failure_host_cwd_or_env_mismatch(self):
        invalid=[self.start_step('./step1.sh',self.first,exit_code=1),
                 self.start_step('./step1.sh',self.first,exit_code=False),
                 self.start_step('./step1.sh',self.first,host='other'),
                 self.start_step('./step1.sh',self.first,result_host='other'),
                 self.start_step('./step1.sh',self.first,cwd=self.remote),
                 self.start_step('./step1.sh',self.first,env={'BUILD_LABEL':'wrong','REGION':'test-east'}),
                 self.start_step('./step1.sh',self.first,env={'BUILD_LABEL':'日本語 label'})]
        for first in invalid:
            with self.subTest(first=first): self.assertFalse(all(self.trace([first,self.good()[1]]).values()))
    def test_poll_must_match_completed_successful_job_and_host(self):
        first=self.start_step('./step1.sh',self.first,status='running',exit_code=None)
        for wrong in [poll(job=self.first,status='running',exit_code=None),poll(job=self.first,exit_code=1),
                      poll(job=self.first,host='other'),poll(job=self.first,result_job=self.second),poll(job=self.second)]:
            with self.subTest(poll=wrong): self.assertFalse(all(self.trace([first,wrong,self.good()[1]]).values()))
    def test_unrecognized_or_conditional_script_does_not_get_auto_credit(self):
        for script in ['echo ./step1.sh','true || ./step1.sh','if true; then ./step1.sh; fi','./step1.sh &','eval "$CMD"']:
            with self.subTest(script=script): self.assertFalse(all(self.trace([self.start_step(script,self.first),self.good()[1]]).values()))
    def test_trailing_cwd_slash_and_absolute_script_are_accepted(self):
        first=self.start_step(self.remote+'/work/step1.sh',self.first,cwd=self.remote+'/work/')
        self.assertTrue(all(self.trace([first,self.good()[1]]).values()))

class S3TraceTests(unittest.TestCase):
    def trace(self,events): return execution_trace('S3',events,HOST,REMOTE,pathlib.Path('C:/LocalLLM/workspace/test'))
    def test_success_after_same_job_completed(self):
        result=self.trace([start(),poll(status='running',exit_code=None),poll()])
        self.assertTrue(result['polled_remote_job_completed_successfully'])
        self.assertTrue(result['no_wrong_ssh_host'])
    def test_only_running_poll_is_not_confirmation(self):
        self.assertFalse(self.trace([start(),poll(status='running',exit_code=None)])['polled_remote_job_completed_successfully'])
    def test_wrong_job_host_order_or_nonzero_cannot_pass(self):
        for events in [[start(),poll(job='b'*32)], [start(),poll(result_job='b'*32)],
                       [start(),poll(host='other')], [start(),poll(exit_code=1)],
                       [start(),poll(exit_code=False)], [poll(),start()],
                       [start(host='other'),poll()], [start(result_host='other'),poll()],
                       [start(status='completed',exit_code=1),poll()]]:
            with self.subTest(events=events): self.assertFalse(self.trace(events)['polled_remote_job_completed_successfully'])
        self.assertFalse(self.trace([start(host='other'),poll()])['no_wrong_ssh_host'])
    def test_unrelated_or_quoted_reference_is_not_a_launch(self):
        for script in ['echo ./long.sh','printf "%s" ./long.sh','# ./long.sh\necho ok','bash -c "echo ./long.sh"','chmod +x ./long.sh',
                       'true || ./long.sh','false && ./long.sh; echo done','if true; then ./long.sh; fi',
                       './long.sh &','cat <<EOF\n./long.sh\nEOF','echo "$(echo ./long.sh)"',
                       'exit 0; ./long.sh','cd /tmp; ./long.sh','exec true; ./long.sh',
                       "trap 'exit 0' DEBUG; ./long.sh",'set -n; ./long.sh','bash -n ./long.sh','long.sh']:
            with self.subTest(script=script): self.assertFalse(self.trace([start(script=script),poll()])['polled_remote_job_completed_successfully'])
    def test_direct_invocation_variants(self):
        for script in ['./long.sh','bash ./long.sh','bash long.sh','bash -c "./long.sh"','chmod +x ./long.sh; ./long.sh',REMOTE+'/long.sh','KEY=value env OTHER=x bash ./long.sh']:
            with self.subTest(script=script): self.assertTrue(_direct_long_script(script,REMOTE,REMOTE))
        self.assertFalse(_direct_long_script('./long.sh',REMOTE,REMOTE+'/other'))
    def test_exploratory_job_does_not_count(self):
        events=[start(script='echo ok',job='b'*32),poll(job='b'*32),start(),poll(status='running',exit_code=None)]
        self.assertFalse(self.trace(events)['polled_remote_job_completed_successfully'])

class S4TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='trace-s4-'); self.addCleanup(self.temp.cleanup)
        self.local=pathlib.Path(self.temp.name).resolve()
        self.remote='/home/testuser/llm-eval/trial/S4'
        self.remote_copy=self.remote+'/remote copy 日本語.txt'
        self.source=str(self.local/'source 日本語.txt'); self.roundtrip=str(self.local/'roundtrip 日本語.txt')
    def transfer(self,direction,local,remote=None,host=HOST,status='completed',exit_code=0,result_host=None,result_local=None,result_remote=None):
        remote=remote or self.remote_copy
        return event('transfer_file',{'host_alias':host,'direction':direction,'local_path':local,'remote_path':remote},
                     {'host':host if result_host is None else result_host,'status':status,'exit_code':exit_code,
                      'local_path':local if result_local is None else result_local,'remote_path':remote if result_remote is None else result_remote})
    def trace(self,events): return execution_trace('S4',events,HOST,self.remote,self.local)
    def good(self): return [self.transfer('upload',self.source),self.transfer('download',self.roundtrip)]
    def test_correct_paths_order_and_success(self):
        self.assertTrue(all(self.trace(self.good()).values()))
    def test_unrelated_paths_do_not_count(self):
        for bad in [[self.transfer('upload',str(self.local/'unrelated')),self.transfer('download',self.roundtrip)],
                    [self.transfer('upload',self.source,remote=self.remote+'/unrelated'),self.transfer('download',self.roundtrip)],
                    [self.transfer('upload',self.source),self.transfer('download',str(self.local/'unrelated'))],
                    [self.transfer('upload',self.source,result_remote=self.remote+'/other'),self.transfer('download',self.roundtrip)],
                    [self.transfer('upload',self.source,result_local=str(self.local/'other')),self.transfer('download',self.roundtrip)]]:
            with self.subTest(events=bad): self.assertFalse(all(self.trace(bad).values()))
    def test_wrong_host_failed_or_noncompleted_transfer_does_not_count(self):
        for upload in [self.transfer('upload',self.source,host='other'),self.transfer('upload',self.source,result_host='other'),
                       self.transfer('upload',self.source,exit_code=1),self.transfer('upload',self.source,exit_code=False),
                       self.transfer('upload',self.source,status='running')]:
            with self.subTest(upload=upload): self.assertFalse(all(self.trace([upload,self.good()[1]]).values()))
    def test_upload_must_precede_download(self):
        self.assertFalse(self.trace(list(reversed(self.good())))['upload_before_download'])
    def test_relative_local_path_not_accepted(self):
        self.assertFalse(all(self.trace([self.transfer('upload','source 日本語.txt'),self.good()[1]]).values()))
    def test_extra_wrong_host_call_is_reported(self):
        events=self.good()+[self.transfer('upload',self.source,host='other')]
        self.assertFalse(self.trace(events)['no_wrong_ssh_host'])

if __name__=='__main__': unittest.main(verbosity=2)
