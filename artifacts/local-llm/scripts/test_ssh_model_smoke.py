"""Pure validation tests: these never open SSH or start a model."""
import base64, hashlib, json, unittest
from smoke_real_ssh import evidence,final_evidence,make_script

class ModelSshSmokeTests(unittest.TestCase):
    def setUp(self):
        self.alias='test-linux'; self.remote='/home/test/llm/workspace/smoke'; self.filename='[日本語] 空白 メモ.txt'
        self.script,self.content,self.out,self.err=make_script(self.filename,'abc123')
        self.sha=hashlib.sha256(self.content).hexdigest(); self.job='a'*32
        self.snapshot={'host':'linux-host','directory':self.remote,'files':{self.filename:{'base64':base64.b64encode(self.content).decode(),'sha256':self.sha}}}
        def event(name,args,result): return {'call':{'function':{'name':name,'arguments':json.dumps(args)}},'result':result}
        self.start=event('run_ssh_bash',{'host_alias':self.alias,'cwd':self.remote,'script':self.script},
                         {'host':self.alias,'cwd':self.remote,'status':'running','job_id':self.job,'stdout':'','stderr':''})
        self.poll=event('poll_process',{'job_id':self.job},
                        {'host':self.alias,'cwd':self.remote,'job_id':self.job,'status':'completed','exit_code':7,'stdout':self.out+'\nHOSTNAME=linux-host\n'+self.sha,'stderr':self.err})
    def check(self,events,snapshot=None,lock=True):
        return evidence(events,self.alias,self.remote,self.script,self.filename,self.content,self.out,self.err,
                        snapshot or self.snapshot,'linux-host',lock)
    def test_real_evidence_contract(self):
        self.assertTrue(self.check([self.start,self.poll])['passed'])
        self.assertNotIn('abc123',self.script)
        self.assertNotIn(self.sha,self.script)
    def test_unknown_job_or_exit_rejected(self):
        wrong=json.loads(json.dumps(self.poll)); wrong['call']['function']['arguments']=json.dumps({'job_id':'b'*32})
        self.assertFalse(self.check([self.start,wrong])['passed'])
        wrong=json.loads(json.dumps(self.poll)); wrong['result']['exit_code']=0
        self.assertFalse(self.check([self.start,wrong])['passed'])
    def test_wrong_host_or_modified_bytes_rejected(self):
        wrong=json.loads(json.dumps(self.poll)); wrong['result']['host']='another'
        self.assertFalse(self.check([self.start,wrong])['passed'])
        wrong=json.loads(json.dumps(self.poll)); wrong['result']['stdout']=wrong['result']['stdout'].replace('HOSTNAME=linux-host','HOSTNAME=other')
        self.assertFalse(self.check([self.start,wrong])['passed'])
        wrong=json.loads(json.dumps(self.snapshot)); wrong['directory']='/somewhere/else'
        self.assertFalse(self.check([self.start,self.poll],wrong)['passed'])
        wrong=json.loads(json.dumps(self.snapshot)); wrong['files'][self.filename]['base64']=base64.b64encode(b'bad').decode()
        self.assertFalse(self.check([self.start,self.poll],wrong)['passed'])
    def test_missing_stderr_and_changed_lock_rejected(self):
        wrong=json.loads(json.dumps(self.poll)); wrong['result']['stderr']=''
        self.assertFalse(self.check([self.start,wrong])['passed'])
        self.assertFalse(self.check([self.start,self.poll],lock=False)['passed'])
    def test_unrelated_second_start_rejected(self):
        other=json.loads(json.dumps(self.start)); a=json.loads(other['call']['function']['arguments']); a['script']='true'; other['call']['function']['arguments']=json.dumps(a)
        self.assertFalse(self.check([self.start,other,self.poll])['passed'])
    def test_nonce_cannot_be_obtained_through_other_tools(self):
        for name in ['transfer_file','run_powershell','stop_process']:
            with self.subTest(name=name):
                other={'call':{'function':{'name':name,'arguments':'{}'}},'result':{}}
                self.assertFalse(self.check([other,self.start,self.poll])['passed'])
        other=json.loads(json.dumps(self.poll)); other['call']['function']['arguments']=json.dumps({'job_id':'b'*32})
        self.assertFalse(self.check([other,self.start,self.poll])['passed'])
    def test_final_must_report_all_real_values(self):
        final=f'stdout: {self.out}; stderr: {self.err}; SHA-256: {self.sha}\nexit_code: 7'
        self.assertTrue(final_evidence(final,self.out,self.err,self.sha)['passed'])
        self.assertFalse(final_evidence(final.replace('exit_code: 7','exit_code: 0'),self.out,self.err,self.sha)['passed'])
        self.assertFalse(final_evidence(final.replace('exit_code: 7','exit_code: 0; expected 7'),self.out,self.err,self.sha)['passed'])
        self.assertFalse(final_evidence(final.replace(self.err,''),self.out,self.err,self.sha)['passed'])

if __name__=='__main__': unittest.main(verbosity=2)
