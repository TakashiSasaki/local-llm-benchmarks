"""Real model/process round trips for local poll/stop tool contracts, outside P5."""
import argparse, json, pathlib, uuid
from agent import run
from grading import capture_lock
from server import ROOT

def test(model,mode):
    directory=ROOT/'workspace'/('job-protocol-'+uuid.uuid4().hex[:10]); directory.mkdir(parents=True)
    token='JOB-'+uuid.uuid4().hex[:12]
    script="Start-Sleep -Seconds "+('3' if mode=='poll' else '90')+"\nSet-Content -LiteralPath './完了 marker.txt' -Value '"+token+"' -Encoding utf8NoBOM -NoNewline\n'"+token+"'"
    operation='返されたjob_idをpoll_processで確認し、status=completedとexit_code=0を確認してから結果を報告してください。' if mode=='poll' else '返されたjob_idをstop_processで停止し、停止確認結果を報告してください。完了を待って90秒放置しないでください。'
    prompt='管理jobの'+mode+'疎通試験です。次のスクリプトの起動は一度だけです。run_powershellでcwd='+str(directory)+'、timeout=0.2、scriptには次のPowerShellコードブロックの中身をそのまま渡してください。フェンスは含めず、行間は実際のLF、末尾の改行は加えません。\n```powershell\n'+script+'\n```\n同じ処理を重複起動しないでください。追加の読み取り確認は可能です。'+operation
    lock=capture_lock()
    def validate(events):
        calls=[]
        for e in events:
            try: calls.append((e['call']['function']['name'],json.loads(e['call']['function']['arguments']),e['result']))
            except Exception: pass
        starts=[(a,r) for name,a,r in calls if name=='run_powershell' and a.get('script')==script]
        first=starts[0] if starts else ({},{})
        args,result=first; job=result.get('job_id')
        exact=args.get('script')==script and args.get('cwd')==str(directory) and args.get('timeout')==.2
        checks={'one_start':len(starts)==1,'exact_arguments':exact,'returned_running':result.get('status')=='running','lock_unchanged':lock()}
        marker=directory/'完了 marker.txt'
        if mode=='poll':
            checks['polled_completion']=any(name=='poll_process' and a.get('job_id')==job and r.get('status')=='completed' and r.get('exit_code')==0 for name,a,r in calls)
            checks['exact_artifact']=marker.exists() and marker.read_bytes()==token.encode()
        else:
            checks['stopped_and_verified']=any(name=='stop_process' and a.get('job_id')==job and r.get('stop_verified') and r.get('status')=='completed' and r.get('exit_code')!=0 for name,a,r in calls)
            checks['artifact_absent']=not marker.exists()
            state=ROOT/'jobs'/str(job)/'status.json'
            checks['worker_records_stopped']=state.exists() and json.loads(state.read_text(encoding='utf-8')).get('stopped') is True
        return {'passed':all(checks.values()),'test_version':'local-job-protocol-v3-fenced','mode':mode,'checks':checks}
    result=run(model,prompt,directory,limit=120,validator=validate,lock_check=lock)
    (ROOT/'runs'/('job-protocol-'+mode+'-'+result['run_id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('model',choices=['qwen','lfm','glm']); ap.add_argument('mode',choices=['poll','stop']); a=ap.parse_args()
    raise SystemExit(0 if test(a.model,a.mode)['success'] else 1)
