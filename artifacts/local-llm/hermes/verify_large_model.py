"""Cross-check the large-model trial against Hermes' persisted tool results."""
import json
from pathlib import Path
import re
import sqlite3

root=Path(__file__).resolve().parent
run=root/'runs'/'large-hermes-20261029-133137'
report=json.loads((run/'report.json').read_text(encoding='utf-8'))
events=[]
for line in (run/'hermes.stdout.jsonl').read_text(encoding='utf-8').splitlines():
    try: events.append(json.loads(line))
    except ValueError: pass
final=next(e for e in reversed(events) if e.get('type')=='result')
session_id=final['session_id']
install=json.loads((root/'installation.json').read_text(encoding='utf-8'))
db=sqlite3.connect((Path(install['hermes_home'])/'state.db').as_uri()+'?mode=ro',uri=True)
db.row_factory=sqlite3.Row
session=dict(db.execute('SELECT id,model,billing_provider,billing_base_url,tool_call_count,input_tokens,output_tokens FROM sessions WHERE id=?',(session_id,)).fetchone())
tools=[]
for row in db.execute("SELECT tool_name,content,tool_call_id FROM messages WHERE session_id=? AND role='tool' ORDER BY id",(session_id,)):
    item=dict(row)
    try: item['result']=json.loads(item.pop('content'))
    except ValueError: item['result']={'text':item.pop('content')}
    tools.append(item)
db.close()
terminal=next(t['result'] for t in tools if t['tool_name']=='terminal')
read=next(t['result'] for t in tools if t['tool_name']=='read_file')
write=next(t['result'] for t in tools if t['tool_name']=='write_file')
checks={'session_model_matches':session['model']==report['test_model'],
        'read_saw_ticket':report['expected']['ticket'] in str(read),
        'terminal_exited_zero':terminal.get('exit_code')==0,
        'terminal_real_output':terminal.get('output','').strip()=='HERMES35B_TERMINAL_OK',
        'write_verified':write.get('verified') is True and not write.get('error'),
        'artifact_matches':report['artifact_matches'],'input_unchanged':report['input_unchanged']}
report.update(session=session,tool_results=tools,independent_checks=checks,
              success=report['success'] and all(checks.values()),
              usage_note='Session input token counts are cumulative across API calls, not the maximum simultaneous context.')
loads=sorted((root/'runs').glob('load-large-*.json'),key=lambda p:p.stat().st_mtime)
load=json.loads(loads[-1].read_text(encoding='utf-8'))
report['load_seconds']=load['load_seconds']
log=Path(load['log']).read_text(encoding='utf-8',errors='replace')
report['prompt_eval_token_counts']=[int(n) for n in re.findall(r'prompt eval time\s*=.*?/\s*(\d+) tokens',log)]
report.pop('maximum_observed_prompt_tokens',None)
report['maximum_prompt_eval_tokens']=max(report['prompt_eval_token_counts'],default=None)
report['maximum_observed_slot_tokens']=max((int(n) for n in re.findall(r'stop processing: n_tokens = (\d+)',log)),default=None)
report['context_measurement_note']='Prompt eval counts are newly evaluated tokens after cache reuse; slot tokens include input and generation.'
(run/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if not report['success']: raise RuntimeError(str(checks))
profile_path=root/'profiles/large.json'
profile=json.loads(profile_path.read_text(encoding='utf-8'))
before=dict(profile)
profile['status']='Hermes read_file/terminal/write_file basic flow verified 2026-10-29; one short conversation'
profile['parser']='Embedded GGUF Jinja; Hermes tool roundtrip verified; see runs/large-hermes-20261029-133137/report.json'
assert {k:v for k,v in before.items() if k not in ('status','parser')}=={k:v for k,v in profile.items() if k not in ('status','parser')}
profile_path.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report['profile_metadata_updated_after_test']={'path':str(profile_path),'fields':['status','parser'],'inference_parameters_changed':False}
(run/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'success':report['success'],'session':session,'checks':checks,'tool_results':tools,
                 'load_seconds':report['load_seconds'],'maximum_observed_slot_tokens':report['maximum_observed_slot_tokens']},ensure_ascii=False))
