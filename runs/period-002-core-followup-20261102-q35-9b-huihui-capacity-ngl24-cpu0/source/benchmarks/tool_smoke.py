"""Short official BFCL examples and mode checks, explicitly not a capability score."""
from local_llm_benchmarks.bfcl import components
from local_llm_benchmarks.study import save


def collect(path,api,alias):
    cases,convert,grade=components();selected=[next(c for c in cases if c['category']==k) for k in ['simple_python','multiple','parallel','irrelevance']];entries=[];checks=[]
    for mode in ['off','on']:
        payload={'model':alias,'messages':[{'role':'user','content':'What is 17 times 23? Think carefully then answer.'}],'max_tokens':1024,'temperature':0,'seed':42,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':mode=='on'}}
        response=api('/v1/chat/completions',payload,timeout=600);save(path/'raw'/('mode-'+mode+'.json'),{'request':payload,'response':response})
        msg=response['choices'][0]['message'];observed=bool(msg.get('reasoning_content') or msg.get('reasoning'))
        checks.append({'mode':mode,'reasoning_observed':observed,'matches_request':observed==(mode=='on'),'finish_reason':response['choices'][0]['finish_reason']})
        for c in selected:
            payload={'model':alias,'messages':c['problem']['question'][0],'tools':convert(c),'tool_choice':'auto','parallel_tool_calls':True,'temperature':0,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'seed':42,'max_tokens':2048,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':mode=='on'}}
            response=api('/v1/chat/completions',payload,timeout=600);save(path/'raw'/('smoke-'+mode+'-'+c['problem']['id']+'.json'),{'request':payload,'response':response})
            out=grade(c,response);entries.append({'mode':mode,'id':c['problem']['id'],'category':c['category'],'passed':out['passed'],'parsed_calls':len(response['choices'][0]['message'].get('tool_calls') or []),'finish_reason':response['choices'][0]['finish_reason']})
    return {'scope':'Short smoke only; not BFCL80 or HE20 capability collection','mode_checks':checks,'cases':entries,'transport_and_mode_checks_passed':all(c['matches_request'] for c in checks) and all(any(e['mode']==mode and e['parsed_calls'] for e in entries) for mode in ['off','on'])}
