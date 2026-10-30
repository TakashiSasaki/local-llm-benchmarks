"""Summarize fresh matched-placement quantization/MTP cells without inference."""
import argparse, collections, html, json, pathlib, statistics, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now

def build(prefix):
    cells=[]
    for quant in ['q4','iq3']:
        for mtp in ['off','on']:
            name=prefix+'-'+quant+'-'+mtp; parent=ROOT/'runs'/name
            c={'run':name,'quantization':'Q4_K_M' if quant=='q4' else 'IQ3_M','mtp':mtp,'status':'not-started','metrics':{}}
            if (parent/'manifest.json').exists():
                m=load(parent/'manifest.json'); c.update(status=m['status'],config=m['config'],error=m.get('error'))
                if (parent/'summaries/memory.json').exists():c['memory']=load(parent/'summaries/memory.json')
                for suite in ['bfcl','humaneval']:
                    for thinking in ['off','on']:
                        p=ROOT/'runs'/(name+'-'+suite+'-'+thinking)
                        if (p/'summary.json').exists():
                            result=load(p/'summary.json'); raw=[load(f) for f in sorted((p/'raw').glob('*.json'))]
                            ts=[r['response'].get('timings',{}) for r in raw]
                            result.update(completion_tokens=sum(r['response']['usage']['completion_tokens'] for r in raw),draft_tokens=sum(t.get('draft_n',0) for t in ts),accepted_draft_tokens=sum(t.get('draft_n_accepted',0) for t in ts))
                            rates=[t['predicted_per_second'] for t in ts if 'predicted_per_second' in t]
                            result['median_decode_tokens_per_second']=statistics.median(rates) if rates else None
                            c['metrics'][suite+'_'+thinking]=result
                s=ROOT/'runs'/(name+'-speed')
                if (s/'summary.json').exists():c['speed']=load(s/'summary.json')
            cells.append(c)
    comparisons=[]
    for quant in ['q4','iq3']:
        off=next(c for c in cells if c['run']==prefix+'-'+quant+'-off')
        on=next(c for c in cells if c['run']==prefix+'-'+quant+'-on')
        pair={'quantization':off['quantization'],'capability_changes':{}}
        if 'speed' in off and 'speed' in on:
            pair['fixed_length_speedup']=on['speed']['median_decode_tokens_per_second']/off['speed']['median_decode_tokens_per_second']
            a=load(ROOT/'runs'/(off['run']+'-speed')/'summaries/speed-cases.json'); b=load(ROOT/'runs'/(on['run']+'-speed')/'summaries/speed-cases.json')
            pair['fixed_length_identical_content']=sum(x['content_sha256']==y['content_sha256'] for x,y in zip(a,b));pair['fixed_length_pairs']=len(a)
        for suite in ['bfcl','humaneval']:
            for thinking in ['off','on']:
                key=suite+'_'+thinking
                if key not in off['metrics'] or key not in on['metrics']:continue
                ap=ROOT/'runs'/(off['run']+'-'+suite+'-'+thinking);bp=ROOT/'runs'/(on['run']+'-'+suite+'-'+thinking)
                filename='bfcl-cases.json' if suite=='bfcl' else 'cases.json'
                a=load(ap/'summaries'/filename);b=load(bp/'summaries'/filename);changes=[];identical=0
                for x,y in zip(a,b):
                    cid=x.get('id') or x['task_id'];assert cid==(y.get('id') or y['task_id'])
                    ar=load(ap/'raw'/(cid.replace('/','_')+'.json'));br=load(bp/'raw'/(cid.replace('/','_')+'.json'))
                    if ar['response']['choices'][0]['message']==br['response']['choices'][0]['message']:identical+=1
                    if x['passed']!=y['passed']:changes.append({'id':cid,'mtp_off':x['passed'],'mtp_on':y['passed']})
                pair['capability_changes'][key]={'score_changes':changes,'identical_messages':identical,'pairs':len(a),'request_time_speedup':off['metrics'][key]['total_seconds']/on['metrics'][key]['total_seconds']}
        comparisons.append(pair)
    data={'updated_at':now(),'prefix':prefix,'model':'Empero Qwen3.8-35B-A3B-Distill','context_tokens':65536,'max_output_tokens':64000,'cpu_moe_layers':34,'runtime':'b11960 / 8642541b2 / CUDA12.4','cells':cells,'comparisons':comparisons,'limits':['One run per capability condition; fixed-length speed has three repeats per prompt, measured in blocks rather than randomized interleaving.','Historical timing used 30 CPU MoE layers; these fresh paired controls all use 34.','Fixed-length speed forces 256 output tokens with ignore_eos, thinking OFF and temperature 0; it is not a quality score.','MTP must be verified by actual draft/accepted counts; /props default speculative.types can remain none even while MTP executes.','HumanEval uses the existing restricted Windows grader; BFCL is a fixed 80-case AST subset, not the full leaderboard.']}
    out=ROOT/'reports'/prefix;save(out/'matrix-data.json',data)
    def esc(x):return html.escape(str(x))
    body=''
    for c in cells:
        fields=[]
        for key in ['bfcl_off','bfcl_on','humaneval_off','humaneval_on']:
            v=c['metrics'].get(key);fields.append(f"{v['passed']}/{v['expected']}<small>{v['total_seconds']:.1f} s · median {v['median_seconds']:.2f} s</small>" if v else '—')
        s=c.get('speed');memory=c.get('memory',{})
        speed=f"{s['median_decode_tokens_per_second']:.2f} tok/s<small>draft {s['accepted_draft_tokens']}/{s['draft_tokens']}</small>" if s else '—'
        ram=memory.get('minimum_available_ram_bytes');gpu=memory.get('peak_gpu_used_mib_system_total')
        resource=(f'{ram/1024**3:.2f} GiB / {gpu:.0f} MiB' if ram is not None and gpu is not None else '—')
        body+='<tr><th>'+esc(c['quantization'])+'<small>MTP '+esc(c['mtp'])+' · '+esc(c['status'])+'</small></th>'+''.join('<td>'+v+'</td>' for v in fields)+'<td>'+speed+'</td><td>'+resource+'</td></tr>'
    page='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Empero 3bit / 4bit × MTP</title><style>body{font:16px system-ui,sans-serif;background:#101825;color:#edf4ff;max-width:1240px;margin:36px auto;padding:0 24px}a{color:#8ad3ff}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{padding:16px 12px;border-bottom:1px solid #34445c;text-align:left}small{display:block;color:#abc0da;font-size:12px;margin-top:6px}.scroll{overflow:auto}pre{white-space:pre-wrap;background:#172438;padding:20px}li{margin:10px 0}</style><a href="../../index.html">測定一覧</a><h1>Empero Qwen3.8 Distill<br>3bit / 4bit × MTP OFF / ON</h1><p>65,536 context · 最大64,000出力 · b11960 CUDA12.4 · 同じCPU MoE 34層 · 新規測定</p><p>BFCLは固定80問、HumanEvalは固定20問。思考OFF/ONとMTP OFF/ONは独立した設定です。</p><div class="scroll"><table><thead><tr><th>構成</th><th>BFCL 思考OFF</th><th>BFCL 思考ON</th><th>HE 思考OFF</th><th>HE 思考ON</th><th>固定長生成の中央値</th><th>最小空きRAM / 最大GPU</th></tr></thead><tbody>'''+body+'''</tbody></table></div><p>時間は各問題のAPI往復の合計・中央値です。固定長生成は思考OFFで256トークン×3種類×3回、予熱を除外。RAM/GPUはサーバー稼働全体のサンプル値です。</p><h2>MTPによる変化</h2><pre>'''+esc(json.dumps(comparisons,ensure_ascii=False,indent=2))+'''</pre><h2>比較範囲</h2><ul>'''+''.join('<li>'+esc(l)+'</li>' for l in data['limits'])+'''</ul><p><a href="matrix-data.json">全集計JSON</a> · <a href="../../docs/EMPERO_MTP.md">条件・解釈</a></p></html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='20261031-empero-quant-mtp-64k');a=p.parse_args();d=build(a.prefix);print(json.dumps({'cells':[{'run':c['run'],'status':c['status'],'conditions':len(c['metrics'])} for c in d['cells']]}))
