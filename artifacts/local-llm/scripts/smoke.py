"""P1/P2 protocol smoke tests. No operating-system tool execution."""
import argparse, datetime, json, pathlib, sys, uuid
from client import Client
from server import ROOT, load_profile

def smoke(name,thinking=False,diagnostic_profile=None):
    p=load_profile(diagnostic_profile or name)
    if name in ['qwen','glm']:
        p['chat_template_kwargs']['enable_thinking']=thinking
        if not thinking and name=='qwen': p['sampling'].update(temperature=.7,top_p=.8,presence_penalty=1.5)
    run_id='smoke-'+p['profile_id']+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    log=ROOT/'runs'/f'{run_id}.jsonl'; c=Client(p,log)
    c.record('run_start',run_id=run_id,test='pseudo_tool',real_execution=False,thinking=p['chat_template_kwargs'])
    short=c.chat([{'role':'user','content':'接続確認です。「接続成功」とだけ答えてください。'}],max_tokens=512)
    short_ok=short['finish_reason']=='stop' and '接続成功' in short['message']['content']
    expected={'path':'資料 フォルダ/[日本語] メモ.txt','label':'確認 "テスト" と空白'}
    tools=[{'type':'function','function':{'name':'inspect_fixture','description':'固定の疑似executorに文字列を渡し、検査結果を取得する。OSコマンドは実行しない。','parameters':{'type':'object','properties':{'path':{'type':'string'},'label':{'type':'string'}},'required':['path','label'],'additionalProperties':False}}}]
    messages=[{'role':'system','content':'利用できるtoolを使い、返された結果だけに基づいて日本語で短く回答してください。'},
              {'role':'user','content':'inspect_fixtureを一度呼び出してください。引数は次のJSONの文字列を一文字も変えずに使ってください: '+json.dumps(expected,ensure_ascii=False)+'。結果を受け取ってから、stdoutの確認コード、stderr、exit_codeを報告してください。'}]
    first=c.chat(messages,tools)
    calls=first['message'].get('tool_calls',[])
    protocol_ok=len(calls)==1
    if calls:
        call=calls[0]
        try: protocol_ok=protocol_ok and call['function']['name']=='inspect_fixture' and json.loads(call['function']['arguments'])==expected
        except ValueError: protocol_ok=False
    final=None; final_ok=False
    if protocol_ok:
        nonce='TEST-'+uuid.uuid4().hex[:10]
        result={'stdout':f'確認コード: {nonce}\n対象を検出しました。','stderr':'固定警告: 読み取り専用テスト','exit_code':7,'status':'completed','host':'pseudo-only','real_execution':False}
        c.record('pseudo_tool_result',call=calls[0],result=result)
        messages.extend([first['message'],{'role':'tool','tool_call_id':calls[0]['id'],'content':json.dumps(result,ensure_ascii=False)}])
        final=c.chat(messages,tools)
        text=final['message'].get('content','')
        final_ok=final['finish_reason']=='stop' and not final['message'].get('tool_calls') and nonce in text and '7' in text and '読み取り専用テスト' in text
    summary={'run_id':run_id,'profile_id':p['profile_id'],'diagnostic_cpu_only':p.get('diagnostic_cpu_only',False),'thinking':p['chat_template_kwargs'],'short_ok':short_ok,'tool_arguments_ok':protocol_ok,'tool_result_ok':final_ok,'passed':short_ok and protocol_ok and final_ok,'real_execution':False,'log':str(log)}
    c.record('run_end',**summary)
    (ROOT/'runs'/f'{run_id}.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary['passed']

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('profile',choices=['qwen','lfm','glm']); ap.add_argument('--thinking',action='store_true'); ap.add_argument('--diagnostic-profile'); a=ap.parse_args()
    sys.exit(0 if smoke(a.profile,a.thinking,a.diagnostic_profile) else 1)
