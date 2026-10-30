"""Model-free checks of process/error/state contracts."""
import json, pathlib, time, uuid
from executor import Executor
from executor_worker import launch
from server import ROOT

def run():
    workspace=ROOT/'executor-tests'; workspace.mkdir(exist_ok=True)
    e=Executor(workspace); results=[]
    def check(name,ok,detail):
        results.append({'name':name,'passed':bool(ok),'detail':detail})
        if not ok: raise AssertionError(name+': '+json.dumps(detail,ensure_ascii=False))
    def ps(script,**kw): return e.execute('run_powershell',{'script':script,'cwd':str(workspace),'timeout':5,**kw})
    r=ps("'日本語 空白 [角括弧]'; Write-Output $env:LLM_TEST_MARKER",env={'LLM_TEST_MARKER':'一時 env'})
    check('unicode_and_explicit_env',r['exit_code']==0 and '日本語 空白 [角括弧]' in r['stdout'] and '一時 env' in r['stdout'],r)
    r=ps('if ($env:LLM_TEST_MARKER) { throw "environment leaked" }; (Get-Location).Path')
    check('fresh_process',r['exit_code']==0 and str(workspace).lower() in r['stdout'].lower(),r)
    r=ps("Get-Item -LiteralPath 'missing-file-for-test' | Out-Null")
    check('cmdlet_error',r['exit_code']!=0 and r['shell_status']['kind']=='powershell_exception',r)
    r=ps('& $env:ComSpec /d /c exit 23')
    check('native_error',r['exit_code']==23 and r['shell_status']['kind']=='native_exit',r)
    r=ps('try { & $env:ComSpec /d /c exit 23 } catch [System.Management.Automation.NativeCommandExitException] { "handled" }; "continued"')
    check('handled_native_error_is_not_final_failure',r['exit_code']==0 and r['shell_status']['last_native_exit_code']==23 and 'continued' in r['stdout'],r)
    r=ps('exit 7')
    check('explicit_script_exit',r['exit_code']==7,r)
    r=ps("[pscustomobject]@{Name='日本語-object';Value=37} | Select-Object Name,Value")
    check('object_formatting_flushed',r['exit_code']==0 and '日本語-object' in r['stdout'] and '37' in r['stdout'],r)
    r=ps("[pscustomobject]@{Name='before-exit';Value=17}; exit 7")
    check('object_output_with_explicit_exit',r['exit_code']==7 and 'before-exit' in r['stdout'] and '17' in r['stdout'],r)
    (workspace/'日本語 listing.txt').write_text('fixture',encoding='utf-8')
    r=ps("Get-ChildItem -LiteralPath . -File | Select-Object Name,Length")
    check('fileinfo_listing_output',r['exit_code']==0 and '日本語 listing.txt' in r['stdout'],r)
    r=ps('& (Get-Process -Id $PID).Path -NoProfile -Command "Write-Output \'日本語 native\'"')
    check('native_powershell_unicode',r['exit_code']==0 and '日本語 native' in r['stdout'],r)
    r=ps('$text="line1\nline2"; [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))')
    check('script_embedded_lf_preserved',r['exit_code']==0 and 'bGluZTEKbGluZTI=' in r['stdout'],r)
    r=ps('throw "deliberate exception"')
    check('exception',r['exit_code']!=0 and 'deliberate exception' in r['stderr'],r)
    r=ps("'first'; Start-Sleep -Seconds 2; 'last'",timeout=0)
    check('async_running',r['status']=='running' and r['exit_code'] is None,r)
    job=r['job_id']; text=r['stdout']; offset=r['stdout_next_offset']
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        r=e.execute('poll_process',{'job_id':job,'stdout_offset':offset}); text+=r['stdout']; offset=r['stdout_next_offset']
        if r['status']=='completed': break
        time.sleep(.2)
    check('poll_complete',r['status']=='completed' and r['exit_code']==0 and text.count('first')==1 and text.count('last')==1,r)
    r=ps("'started'; Start-Sleep -Seconds 90; 'must not reach'",timeout=.5)
    r=e.execute('stop_process',{'job_id':r['job_id']})
    check('stop_verified',r.get('stop_verified') and r['exit_code']!=0 and 'must not reach' not in r['stdout'],r)
    r=ps("'x' * 50000")
    check('truncation',r['stdout_truncated'] and r['stdout_bytes']>32768 and pathlib.Path(r['stdout_log']).stat().st_size==r['stdout_bytes'],r)
    r=ps("('a' * 32767) + '日本語'")
    part=r['stdout']; tail=e.execute('poll_process',{'job_id':r['job_id'],'stdout_offset':r['stdout_next_offset']})
    check('unicode_poll_boundary',part+tail['stdout']==pathlib.Path(r['stdout_log']).read_bytes().decode('utf-8') and '\ufffd' not in part+tail['stdout'],{'first_next_offset':r['stdout_next_offset'],'tail':tail['stdout']})
    try: e.execute('run_ssh_bash',{'host_alias':'not-configured','script':'true','cwd':'/tmp'})
    except ValueError: check('unknown_host_rejected',True,{})
    else: check('unknown_host_rejected',False,{})
    job_id=uuid.uuid4().hex; filename='once-'+job_id+'.txt'
    request={'job_id':job_id,'script':"Add-Content -LiteralPath './"+filename+"' -Value 'once' -Encoding utf8; Start-Sleep -Seconds 1",'cwd':str(workspace),'timeout':.2,'state_root':str(ROOT/'jobs'),'workspace_root':str(workspace),'host':'windows-local','powershell':e.config['powershell']}
    first=launch(request); e.register(first,None); second=launch(dict(request))
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        r=e.execute('poll_process',{'job_id':job_id})
        if r['status']=='completed': break
        time.sleep(.1)
    check('start_nonce_is_idempotent',first['job_id']==second['job_id']==job_id and (workspace/filename).read_text(encoding='utf-8-sig').splitlines()==['once'],r)
    try: launch({**request,'script':'different'})
    except ValueError: check('nonce_cannot_change_script',True,{})
    else: check('nonce_cannot_change_script',False,{})
    return results

if __name__=='__main__':
    try: results=run()
    except Exception:
        import traceback; traceback.print_exc(); raise
    (ROOT/'runs/executor-selftest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(results),'results':[{'name':r['name'],'passed':r['passed']} for r in results]},ensure_ascii=False))
