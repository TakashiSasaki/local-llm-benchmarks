"""Add thinking ON BFCL cases to one pinned b11960 model OFF control."""
import copy, datetime, hashlib, html, json, socket, statistics, sys, threading, time, urllib.request, zipfile
from pathlib import Path
import memory, server

KEY=sys.argv[2]
ROOT=Path(r'C:\LocalLLM'); LIFE=ROOT/'hermes' if KEY.startswith('qwen-') else ROOT; BF=ROOT/'hermes/benchmarks/bfcl'
BASE=ROOT/'runs'/('legacy-models-64k-20261030-180109' if KEY in ['lfm','glm'] else 'bench64k-output-20261030-141002')
OUT=Path(sys.argv[1]); OUT.mkdir(exist_ok=True)
def save(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
ns={'__file__':str(BF/'run_comparison.py')}
adapter=(BF/'run_comparison.py').read_text(encoding='utf-8')
exec(compile(adapter[:adapter.index('selfcheck=[]')],'pinned_bfcl_adapter.py','exec'),ns)
cases=ns['SELECTED'];check=ns['check']
baseline=json.loads((BASE/'results.json').read_text(encoding='utf-8'));control=baseline['models'][KEY]
assert [c['problem']['id'] for c in cases]==baseline['bfcl_ids']
assert ns['HASHES']==baseline['bfcl_data_hashes']
off=control['bfcl'];assert len(off)==80
controls=[{'id':c['problem']['id'],'golden':check(c,ns['golden'](c))['valid'],'negative_rejected':not check(c,[{'not_a_valid_function':{}}] if c['category']=='irrelevance' else [])['valid']} for c in cases]
assert all(c['golden'] and c['negative_rejected'] for c in controls)
save(OUT/'selfchecks.json',controls);save(OUT/'selected-bfcl.json',cases)
profile=copy.deepcopy(control.get('profiles',{}).get('on',control['profile']))
assert profile['server_args'][profile['server_args'].index('--reasoning-budget')+1]=='-1'
pname='bfcl-thinking-'+KEY;ppath=LIFE/'profiles'/(pname+'.json')
tracked=list((ROOT/'profiles').glob('*.json'))+list((LIFE/'profiles').glob('*.json'))+[ROOT/'runtime-current.json',ROOT/'model-manifest.json',LIFE/'model-manifest.json',BASE/'results.json']
tracked=[p for p in tracked if p!=ppath]
before={str(p):sha(p) for p in tracked}
requests={};source_hashes={}
def grade_response(c,response):
    decoded=[];error=None
    try:
        for call in response['choices'][0]['message'].get('tool_calls') or []:
            args=json.loads(call['function']['arguments'])
            if not isinstance(args,dict):raise ValueError('Non-object arguments')
            decoded.append({call['function']['name']:args})
        outcome=check(c,decoded)
    except (ValueError,KeyError,TypeError) as exc:error=str(exc);outcome={'valid':False,'error':[error]}
    return decoded,error,outcome
for c,old in zip(cases,off):
    cid=c['problem']['id'];assert cid==old['id']
    rawpath=BASE/(KEY+'-bfcl-'+cid+'.json');source_hashes[str(rawpath)]=sha(rawpath)
    raw=json.loads(rawpath.read_text(encoding='utf-8'));payload=raw['request']
    assert payload['chat_template_kwargs']=={'enable_thinking':False}
    assert payload['max_tokens']==64000 and payload['model']==control.get('profiles',{}).get('off',control['profile'])['profile_id']
    assert payload['messages']==c['problem']['question'][0]
    assert payload['tools']==ns['convert_to_tool'](c['problem']['function'],ns['GORILLA_TO_OPENAPI'],ns['ModelStyle'].OPENAI_COMPLETIONS)
    _,_,outcome=grade_response(c,raw['response']);assert outcome['valid']==old['passed']
    requests[cid]=copy.deepcopy(payload)
save(OUT/'off-source-hashes.json',source_hashes)
if '--preflight-only' in sys.argv:
    print(json.dumps({'preflight':True,'model':KEY,'cases':len(cases),'off_passed':sum(x['passed'] for x in off),'on_profile':profile['profile_id']}),flush=True)
    sys.exit(0)
if (OUT/'results.json').exists():
    report=json.loads((OUT/'results.json').read_text(encoding='utf-8'));assert report['profile']==profile and report['source_hashes']==source_hashes
    before=report['original_hashes'];report.pop('error',None)
else:
    report={'model_key':KEY,'started_at':datetime.datetime.now().astimezone().isoformat(),'directory':str(OUT),'python':sys.version,'baseline_directory':str(BASE),'profile':profile,'original_hashes':before,'source_hashes':source_hashes,'dataset_hashes':ns['HASHES'],'bfcl_commit':(BF/'revision.txt').read_text().strip(),'off':off,'on':[],'protocol':{'cases':80,'categories':ns['CATEGORIES'],'context_per_slot':65536,'output_cap':64000,'http_timeout_seconds':7200,'budget_rule':'min(64000, 65536-rendered_input_tokens-32)','temperature':0,'seed':42,'thinking_control':'Native chat_template_kwargs.enable_thinking; CLI budget -1','comparison':'Reuse all 80 saved OFF responses; 80 new ON responses. Native ON versus native OFF, except LFM2.5 OFF used CLI budget 0 and ON uses -1 (embedded template ignores enable_thinking). Model alias differs only for LFM2.5. Same model, runtime and placement. No functions executed.'},'limits':['Fixed 80-case subset; one greedy answer per condition; not a full BFCL score.','OFF reused from earlier same-day run; timing and memory affected by background and thermal variation.','Grades native parsed tool calls; no actual external function execution or multi-turn agent workflow.','Memory samples after readiness may miss startup/instantaneous peaks.']}
def persist():save(OUT/'results.json',report)
def api(path,payload=None,timeout=7200):
    req=urllib.request.Request('http://127.0.0.1:8089'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def stats(entries):
    timings=[x['timings'] for x in entries if x.get('timings')];tokens=sum(t.get('predicted_n',0) for t in timings);ms=sum(t.get('predicted_ms',0) for t in timings)
    return {'passed':sum(x['passed'] for x in entries),'attempted':len(entries),'median_seconds':statistics.median(x['seconds'] for x in entries) if entries else None,'total_seconds':sum(x['seconds'] for x in entries),'generation_tokens_per_second':1000*tokens/ms if ms else None,'output_cap_hits':sum(x['finish_reason']=='length' for x in entries),'reasoning_observed_cases':sum(x['reasoning_observed'] for x in entries),'completion_tokens':sum(x.get('usage',{}).get('completion_tokens',0) for x in entries)}
server.ROOT=LIFE;monitor=None;guard_thread=None;guard_stop=threading.Event();owned=False
persist();print(json.dumps({'event':'preflight_passed','directory':str(OUT),'controls':80,'off_passed':sum(x['passed'] for x in off),'profile':KEY}),flush=True)
try:
    try:
        conn=socket.create_connection(('127.0.0.1',8089),timeout=1)
    except OSError:pass
    else:conn.close();raise RuntimeError('Port occupied; refusing to replace existing server')
    save(ppath,profile);owned=True;server.start(pname)
    state=json.loads((LIFE/'server-state.json').read_text(encoding='utf-8'));save(OUT/'server-state-started.json',state)
    monitor=memory.Monitor(state['pid'],OUT/'memory.jsonl').start()
    def guard():
        low=0
        while not guard_stop.wait(3):
            if not monitor.samples:continue
            low=low+1 if monitor.samples[-1]['available_ram_bytes']<1024**3 else 0
            if low>=3:
                report['resource_interruption']='Available RAM below 1 GiB for three observations; not an observed OOM'
                current=json.loads((LIFE/'server-state.json').read_text(encoding='utf-8'))
                if current['pid']==state['pid'] and current['profile']==pname:server.stop()
                return
    guard_thread=threading.Thread(target=guard,daemon=True);guard_thread.start()
    props=api('/props');save(OUT/'props.json',props)
    assert props['model_alias']==profile['profile_id'] and props['model_path']==str(ROOT/profile['model'])
    assert props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
    assert props['build_info']==control['runtime'];report['runtime']=props['build_info']
    for mode in (['on'] if KEY=='lfm' else ['off','on']):
        warm={'model':profile['profile_id'],'messages':[{'role':'user','content':'What is 17 times 23? Think carefully and then answer with the number.'}],'temperature':0,'seed':42,'max_tokens':512,'chat_template_kwargs':{'enable_thinking':mode=='on'},'cache_prompt':False}
        response=api('/v1/chat/completions',warm);save(OUT/('warmup-'+mode+'.json'),{'request':warm,'response':response})
        msg=response['choices'][0]['message'];observed=bool(msg.get('reasoning_content') or msg.get('reasoning'))
        assert observed==(mode=='on'),('Reasoning control failed',mode)
    report['warmup_mode_verified']=True;persist()
    for c in cases:
        cid=c['problem']['id']
        if any(x['id']==cid for x in report['on']):continue
        payload=copy.deepcopy(requests[cid]);payload['chat_template_kwargs']['enable_thinking']=True;payload['model']=profile['profile_id']
        template={k:v for k,v in payload.items() if k in ('messages','tools','tool_choice','parallel_tool_calls','chat_template_kwargs')}
        rendered=api('/apply-template',template,30)
        n=len(api('/tokenize',{'content':rendered['prompt'],'add_special':False},30)['tokens'])
        payload['max_tokens']=min(64000,65536-n-32);assert payload['max_tokens']==64000
        changed=[k for k in payload if payload[k]!=requests[cid][k]];assert set(changed)==({'model','chat_template_kwargs'} if KEY=='lfm' else {'chat_template_kwargs'})
        rawpath=OUT/('on-'+cid+'.json')
        if rawpath.exists():
            raw=json.loads(rawpath.read_text(encoding='utf-8'));assert raw['request']==payload
            response=raw['response'];elapsed=raw['seconds']
        else:
            active={'id':cid,'category':c['category'],'done':len(report['on']),'started_at':datetime.datetime.now().astimezone().isoformat()};save(OUT/'active-request.json',active)
            print(json.dumps({'event':'request_start',**active}),flush=True)
            start=time.monotonic();response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-start
            response['_benchmark_estimated_prompt_tokens']=n;response['_benchmark_requested_output_tokens']=payload['max_tokens']
            save(rawpath,{'request':payload,'response':response,'seconds':elapsed,'rendered_prompt_sha256':hashlib.sha256(rendered['prompt'].encode()).hexdigest()})
        msg=response['choices'][0]['message'];reason=msg.get('reasoning_content') or msg.get('reasoning') or ''
        decoded,error,outcome=grade_response(c,response)
        item={'id':cid,'category':c['category'],'seconds':elapsed,'passed':outcome['valid'],'grade':outcome,'decoded':decoded,'decode_error':error,'reasoning_observed':bool(reason),'reasoning_characters':len(reason),'finish_reason':response['choices'][0].get('finish_reason'),'usage':response.get('usage'),'timings':response.get('timings'),'prompt_tokens':n,'requested_output_tokens':payload['max_tokens'],'content':msg.get('content') or ''}
        report['on'].append(item);persist()
        print(json.dumps({'event':'case','id':cid,'done':len(report['on']),'passed':item['passed'],'seconds':round(elapsed,2),'reasoning':bool(reason),'finish':item['finish_reason']}),flush=True)
    assert len(report['on'])==80
except Exception as exc:report['error']=repr(exc);raise
finally:
    guard_stop.set()
    if guard_thread:guard_thread.join(6)
    if monitor:report['memory']=monitor.stop()
    sp=LIFE/'server-state.json'
    if owned and sp.exists():
        state=json.loads(sp.read_text(encoding='utf-8'))
        if state['profile']==pname:server.stop();report['test_server_stopped']=True
    report['settings_unchanged']={p:sha(Path(p))==h for p,h in before.items()}
    report['sources_unchanged']={p:sha(Path(p))==h for p,h in source_hashes.items()}
    report['finished_at']=datetime.datetime.now().astimezone().isoformat();persist()
    paths=[Path(__file__),BF/'run_comparison.py',BF/'handler_utils.py',BF/'bfcl_eval/eval_checker/ast_eval/ast_checker.py',ROOT/'scripts/server.py',ROOT/'scripts/memory.py',LIFE/'profiles/bench64k-qwen-large.json',ppath,ROOT/'bin/b11960-cuda12.4/runtime-manifest.json']
    with zipfile.ZipFile(OUT/'sources.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            if p.exists():z.write(p,str(p.relative_to(ROOT)))
if 'error' in report:sys.exit(1)
pairs=[{'id':a['id'],'category':a['category'],'off':a['passed'],'on':b['passed'],'off_seconds':a['seconds'],'on_seconds':b['seconds']} for a,b in zip(off,report['on'])]
summary={'model':Path(profile['model']).stem,'off':stats(off),'on':stats(report['on']),'categories':{cat:{mode:stats([x for x in report[mode] if x['category']==cat]) for mode in ['off','on']} for cat in ns['CATEGORIES']},'improved':[x for x in pairs if not x['off'] and x['on']],'regressed':[x for x in pairs if x['off'] and not x['on']],'failed_both':[x for x in pairs if not x['off'] and not x['on']],'memory':report.get('memory'),'pairs':pairs}
report['summary']=summary;persist();save(OUT/'summary.json',summary)
assert all(report['settings_unchanged'].values()) and all(report['sources_unchanged'].values())
try:conn=socket.create_connection(('127.0.0.1',8089),timeout=1)
except OSError:closed=True
else:conn.close();closed=False
assert closed
save(OUT/'validation.json',{'complete':True,'on_cases':80,'reused_off_cases':80,'golden_negative_controls':80,'payload_differences':(['enable_thinking','model alias; LFM2.5 CLI reasoning budget 0 -> -1'] if KEY=='lfm' else ['enable_thinking']),'same_runtime':True,'same_profile_except_lfm25_mode_budget_alias':True,'same_data_hashes':True,'unchanged_originals':True,'port_closed':closed})
labels={'simple_python':'単一関数','multiple':'候補から関数選択','parallel':'複数呼び出し','irrelevance':'呼び出さない判断'}
rows=''.join('<tr><td>'+labels[cat]+'</td>'+''.join('<td>'+str(summary['categories'][cat][m]['passed'])+'/20</td>' for m in ['off','on'])+'</tr>' for cat in ns['CATEGORIES'])
changes=''.join('<h3>'+title+'</h3><ul>'+''.join('<li>'+html.escape(x['id'])+'</li>' for x in summary[key])+'</ul>' for key,title in [('improved','改善'),('regressed','悪化'),('failed_both','両方失敗')])
page='<!doctype html><meta charset="utf-8"><title>BFCL 思考ON/OFF</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;line-height:1.7}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px 18px}</style><h1>ツール呼び出し：思考ON/OFF</h1><p>b11960・65,536コンテキスト・出力上限64,000・固定80問。OFFは保存済み応答、ONは今回の追加測定。関数の実行は行わず、関数名・引数・呼び出し選択を採点。</p><table><tr><th>項目</th><th>思考OFF</th><th>思考ON</th></tr><tr><td>総合</td><td>'+str(summary['off']['passed'])+'/80</td><td>'+str(summary['on']['passed'])+'/80</td></tr>'+rows+'</table><p>応答時間中央値：OFF '+str(round(summary['off']['median_seconds'],2))+'秒、ON '+str(round(summary['on']['median_seconds'],2))+'秒。出力打ち切り：OFF '+str(summary['off']['output_cap_hits'])+'件、ON '+str(summary['on']['output_cap_hits'])+'件。</p>'+changes+'<p>1条件1回答の部分集合評価です。OFFは以前の同日測定を再利用するため、時間・メモリの差には背景負荷や温度の影響も含まれます。</p><p><a href="summary.json">集計JSON</a> / <a href="results.json">全結果</a> / <a href="validation.json">検証</a></p>'
(OUT/'report.html').write_text(page,encoding='utf-8')
print(json.dumps({'event':'complete','off':summary['off'],'on':summary['on'],'improved':[x['id'] for x in summary['improved']],'regressed':[x['id'] for x in summary['regressed']],'failed_both':[x['id'] for x in summary['failed_both']],'directory':str(OUT)}),flush=True)
