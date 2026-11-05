"""Fresh Hermes read/terminal/write trial using an existing local server and installation."""
import argparse,hashlib,json,os,pathlib,sqlite3,subprocess,sys,time,uuid,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[3]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,resolve_run,snapshot_sources

def run(a):
    path=resolve_run(a.run);m=load(path/'manifest.json');assert m['status']=='planned','Use a new integration run for each attempt'
    install=load(a.installation);env=dict(os.environ,HERMES_HOME=install['hermes_home'],PYTHONUTF8='1',PYTHONIOENCODING='utf-8',LLAMA_ARG_THINK='deepseek')
    with urllib.request.urlopen('http://127.0.0.1:8089/props',timeout=30) as f:props=json.load(f)
    assert props['model_alias']==a.model and props['default_generation_settings']['n_ctx']==65536
    fixture={'ticket':uuid.uuid4().hex,'amounts':[137,259,83,41]};expected={'ticket':fixture['ticket'],'count':4,'total':520,'terminal_marker':'HERMES35B_TERMINAL_OK'}
    work=path/'workspace';save(work/'input.json',fixture);digest=hashlib.sha256((work/'input.json').read_bytes()).hexdigest();save(path/'configs/expected.json',expected);save(path/'configs/input-sha256.json',{'input_sha256':digest})
    query='Perform this local integration test using the actual tools, not a simulated answer. First read input.json with read_file. Then use the terminal tool to execute exactly `echo HERMES35B_TERMINAL_OK`. Then write output.json with exactly four keys: ticket copied from input.json, count equal to the number of amounts, total equal to their sum, and terminal_marker copied from the actual terminal output (trim whitespace). Do not change input.json. Finish with a concise result.'
    (path/'configs/query.txt').write_text(query,encoding='utf-8');snapshot_sources(path)
    m.update(status='running',started_at=now(),runtime_build=props['build_info'],hermes_version=install['hermes_version'],hermes_commit=install['hermes_commit']);save(path/'manifest.json',m)
    command=[install['hermes_launcher'],'chat','--cli','--oneshot','--query-file',str(path/'configs/query.txt'),'--provider','local-qwen','--model',a.model,'--in',str(work),'--max-turns','12','--format','stream-json']
    start=time.monotonic()
    with (path/'raw/hermes.stdout.jsonl').open('w',encoding='utf-8') as out,(path/'logs/hermes.stderr.log').open('w',encoding='utf-8') as err:
        child=subprocess.Popen(command,env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        try:code=child.wait(timeout=900)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);code=-1
    events=[]
    for line in (path/'raw/hermes.stdout.jsonl').read_text(encoding='utf-8').splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    final=next((e for e in reversed(events) if e.get('type')=='result'),{});sid=final.get('session_id');session=None;tools=[]
    if sid:
        db=sqlite3.connect((pathlib.Path(install['hermes_home'])/'state.db').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        row=db.execute('SELECT model,billing_base_url FROM sessions WHERE id=?',(sid,)).fetchone();session=dict(row) if row else None
        for row in db.execute("SELECT tool_name,content FROM messages WHERE session_id=? AND role='tool' ORDER BY id",(sid,)):
            item=dict(row);item['result']=json.loads(item.pop('content'));tools.append(item)
        db.close()
    save(path/'raw/session-tools.json',{'session_id':sid,'session':session,'tools':tools})
    actual=load(work/'output.json') if (work/'output.json').exists() else None
    checks={'exit_zero':code==0,'artifact_correct':actual==expected,'input_unchanged':hashlib.sha256((work/'input.json').read_bytes()).hexdigest()==digest,'session_model':bool(session and session['model']==a.model),'local_endpoint':bool(session and session['billing_base_url']=='http://127.0.0.1:8089/v1'),'read_saw_ticket':any(t['tool_name']=='read_file' and fixture['ticket'] in t['result'].get('content','') for t in tools),'terminal_real_output':any(t['tool_name']=='terminal' and t['result'].get('exit_code')==0 and t['result'].get('output','').strip()==expected['terminal_marker'] for t in tools),'write_verified':any(t['tool_name']=='write_file' and t['result'].get('verified') is True for t in tools)}
    summary={'outcome':'passed' if all(checks.values()) else 'failed','headline':'Fresh Hermes read / terminal / write roundtrip','checks':checks,'seconds':time.monotonic()-start,'artifact':actual,'session_id':sid,'thinking':'Hermes normal ON configuration; short conversation','limitations':['One short trial; not long-context reliability']}
    save(path/'summary.json',summary);m.update(status='complete',completed_at=now());save(path/'manifest.json',m);print(json.dumps(summary),flush=True);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--model',required=True);p.add_argument('--installation',type=pathlib.Path,required=True);run(p.parse_args())
