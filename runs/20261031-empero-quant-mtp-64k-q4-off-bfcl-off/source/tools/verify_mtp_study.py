"""Check saved MTP trials, fixed-length outputs and official BFCL grades; no inference."""
import argparse, collections, hashlib, json, pathlib, statistics, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,validate_run,save
from local_llm_benchmarks.bfcl import components

def verify(prefix):
    dataset=ROOT/'datasets/mtp-speed/v1';dm=load(dataset/'manifest.json');assert hashlib.sha256((dataset/'prompts.json').read_bytes()).hexdigest()==dm['files']['prompts.json']
    prompts={p['id']:p['prompt'] for p in load(dataset/'prompts.json')}
    cases,convert,grade=components(); count=0; cells=[]
    for quant in ['q4','iq3']:
        for mtp in ['off','on']:
            parent=ROOT/'runs'/(prefix+'-'+quant+'-'+mtp);m=validate_run(parent);assert m['status']=='complete'
            cfg=m['config'];profile=cfg['profile'];args=profile['server_args']
            assert args[args.index('--n-cpu-moe')+1]=='34'
            assert args[args.index('--spec-type')+1]==('draft-mtp' if mtp=='on' else 'none')
            props=load(parent/'configs/server-props.json');assert props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
            assert cfg['model']['sha256']==profile['model_hash']==load(parent/'configs/model-file-verification.json')['sha256']
            clean=load(parent/'configs/cleanup.json');assert clean['server_stopped'] and not clean['resource_guard']
            speed=ROOT/'runs'/(parent.name+'-speed');sm=validate_run(speed);assert sm['status']=='complete'
            raw=[load(f) for f in sorted((speed/'raw').glob('*.json')) if f.name!='warmup.json'];assert len(raw)==9
            assert collections.Counter(r['prompt_id'] for r in raw)=={name:3 for name in prompts}
            assert all(r['response']['timings']['predicted_n']==256 and r['request']['ignore_eos'] and r['request']['temperature']==0 and r['request']['cache_prompt'] is False for r in raw)
            assert all(r['response']['timings']['cache_n']==0 and prompts[r['prompt_id']] in r['request']['prompt'] for r in raw)
            assert all(all(r['request'][key]==value for key,value in {'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'seed':42,'n_predict':256,'stream':False}.items()) for r in raw)
            drafted=sum(r['response']['timings'].get('draft_n',0) for r in raw);accepted=sum(r['response']['timings'].get('draft_n_accepted',0) for r in raw)
            assert (drafted>0)==(mtp=='on') and 0<=accepted<=drafted
            summary=load(speed/'summary.json');assert summary['draft_tokens']==drafted and summary['accepted_draft_tokens']==accepted
            assert summary['median_decode_tokens_per_second']==statistics.median(r['response']['timings']['predicted_per_second'] for r in raw)
            scores={}
            for suite in ['bfcl','humaneval']:
                for thinking in ['off','on']:
                    child=ROOT/'runs'/(parent.name+'-'+suite+'-'+thinking);cm=validate_run(child);assert cm['status']=='complete'
                    entries=load(child/('summaries/bfcl-cases.json' if suite=='bfcl' else 'summaries/cases.json'));assert len(entries)==(80 if suite=='bfcl' else 20)
                    if suite=='humaneval':assert all(c['passed'] for c in load(child/'configs/canonical-controls.json'))
                    for i,e in enumerate(entries):
                        cid=e.get('id') or e['task_id'];r=load(child/'raw'/(cid.replace('/','_')+'.json'));req=r['request'];resp=r['response']
                        assert req['chat_template_kwargs']['enable_thinking']==(thinking=='on') and req['model']==profile['profile_id']
                        assert req['max_tokens']==min(64000,65536-r['estimated_prompt_tokens']-32)
                        assert resp['usage']['total_tokens']<=65536 and resp['usage']==e['usage']
                        assert e['seconds']==r['seconds']
                        if suite=='bfcl':
                            assert cid==cases[i]['problem']['id'];out=grade(cases[i],resp);assert (out['passed'],out['decoded'])==(e['passed'],e['decoded']);count+=1
                    s=load(child/'summary.json');assert s['passed']==sum(e['passed'] for e in entries) and s['attempted']==len(entries)
                    scores[suite+'_'+thinking]={'passed':s['passed'],'attempted':s['attempted'],'caps':s['output_cap_hits']}
            cells.append({'run':parent.name,'scores':scores,'draft_tokens':drafted,'accepted_draft_tokens':accepted})
    report=load(ROOT/'reports'/prefix/'matrix-data.json');assert all(c['status']=='complete' for c in report['cells'])
    return {'passed':True,'cells':cells,'bfcl_raw_outputs_regraded':count,'humaneval_saved_records_checked':160,'fixed_length_cases':36,'model_inference_performed':False,'generated_code_executed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='20261031-empero-quant-mtp-64k');p.add_argument('--report',type=pathlib.Path);a=p.parse_args();result=verify(a.prefix)
    if a.report:save(a.report,result)
    print(json.dumps(result))
