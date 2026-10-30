"""Summarize fresh matched-placement quantization/MTP cells without inference."""
import argparse, collections, csv, html, json, pathlib, statistics, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now

def build(prefix):
    cells=[];truncations=[]
    study_path=ROOT/'runs'/prefix/'manifest.json'
    study_config=load(study_path)['config'] if study_path.exists() else {}
    cell_runs=study_config.get('cell_runs',{})
    for quant in ['q4','iq3']:
        for mtp in ['off','on']:
            name=cell_runs.get(quant+'-'+mtp,prefix+'-'+quant+'-'+mtp);parent=ROOT/'runs'/name
            c={'run':name,'quantization':'Q4_K_M' if quant=='q4' else 'IQ3_M','mtp':mtp,'status':'not-started','metrics':{}}
            if (parent/'manifest.json').exists():
                m=load(parent/'manifest.json'); c.update(status=m['status'],config=m['config'],error=m.get('error'))
                if (parent/'summaries/memory.json').exists():c['memory']=load(parent/'summaries/memory.json')
                if (parent/'configs/cleanup.json').exists():c['resource_guard']=load(parent/'configs/cleanup.json').get('resource_guard',[])
                for suite in ['bfcl','humaneval']:
                    for thinking in ['off','on']:
                        p=ROOT/'runs'/(name+'-'+suite+'-'+thinking)
                        if (p/'summary.json').exists():
                            result=load(p/'summary.json');rawfiles=sorted((p/'raw').glob('*.json'));raw=[load(f) for f in rawfiles]
                            for f,r in zip(rawfiles,raw):
                                if r['response']['choices'][0]['finish_reason']=='length':
                                    truncations.append({'quantization':c['quantization'],'mtp':mtp,'benchmark':suite,'thinking':thinking,'case_id':f.stem.replace('HumanEval_','HumanEval/'),'completion_tokens':r['response']['usage']['completion_tokens'],'max_tokens':r['request']['max_tokens'],'seconds':r['seconds'],'kind':'output_limit','raw':f.relative_to(ROOT).as_posix()})
                            ts=[r['response'].get('timings',{}) for r in raw]
                            result.update(completion_tokens=sum(r['response']['usage']['completion_tokens'] for r in raw),draft_tokens=sum(t.get('draft_n',0) for t in ts),accepted_draft_tokens=sum(t.get('draft_n_accepted',0) for t in ts))
                            rates=[t['predicted_per_second'] for t in ts if isinstance(t.get('predicted_per_second'),(int,float))]
                            result['median_decode_tokens_per_second']=statistics.median(rates) if rates else None
                            result['empty_assistance_ids']=[f.stem.replace('HumanEval_','HumanEval/') for f,r in zip(rawfiles,raw) if not (r['response']['choices'][0]['message'].get('content') or r['response']['choices'][0]['message'].get('tool_calls'))]
                            result['empty_assistance_cases']=len(result['empty_assistance_ids'])
                            c['metrics'][suite+'_'+thinking]=result
                s=ROOT/'runs'/(name+'-speed')
                if (s/'summary.json').exists():c['speed']=load(s/'summary.json')
            cells.append(c)
    comparisons=[]
    for quant in ['q4','iq3']:
        quantization='Q4_K_M' if quant=='q4' else 'IQ3_M'
        off=next(c for c in cells if c['quantization']==quantization and c['mtp']=='off')
        on=next(c for c in cells if c['quantization']==quantization and c['mtp']=='on')
        pair={'quantization':off['quantization'],'capability_changes':{}}
        if 'speed' in off and 'speed' in on and on['speed']['draft_tokens']>0:
            pair['fixed_length_speedup']=on['speed']['median_decode_tokens_per_second']/off['speed']['median_decode_tokens_per_second']
            a=load(ROOT/'runs'/(off['run']+'-speed')/'summaries/speed-cases.json'); b=load(ROOT/'runs'/(on['run']+'-speed')/'summaries/speed-cases.json')
            pair['fixed_length_identical_content']=sum(x['content_sha256']==y['content_sha256'] for x,y in zip(a,b));pair['fixed_length_pairs']=len(a)
            pair['fixed_length_by_prompt']=[]
            for prompt in sorted({x['prompt_id'] for x in a}):
                aa=[x['timings']['predicted_per_second'] for x in a if x['prompt_id']==prompt];bb=[x['timings']['predicted_per_second'] for x in b if x['prompt_id']==prompt]
                ar=statistics.median(aa);br=statistics.median(bb)
                pair['fixed_length_by_prompt'].append({'prompt_id':prompt,'mtp_off_tok_s':ar,'mtp_on_tok_s':br,'speedup':br/ar,'mtp_off_range':[min(aa),max(aa)],'mtp_on_range':[min(bb),max(bb)]})
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
                    def comparable_message(response):
                        message=json.loads(json.dumps(response['choices'][0]['message']))
                        for call in message.get('tool_calls') or []:call.pop('id',None)
                        return message
                    if comparable_message(ar['response'])==comparable_message(br['response']):identical+=1
                    if x['passed']!=y['passed']:changes.append({'id':cid,'mtp_off':x['passed'],'mtp_on':y['passed']})
                pair['capability_changes'][key]={'score_changes':changes,'identical_messages':identical,'pairs':len(a),'request_time_speedup':off['metrics'][key]['total_seconds']/on['metrics'][key]['total_seconds']}
        comparisons.append(pair)
    deployment_speed=[]
    for mtp in ['off','on']:
        path=ROOT/'runs'/(prefix+'-iq3-cpu30-'+mtp)
        if not (path/'manifest.json').exists():continue
        manifest=load(path/'manifest.json');entry={'run':path.name,'cpu_moe_layers':30,'quantization':'IQ3_M','mtp':mtp,'status':manifest['status'],'config':manifest['config']}
        speed=ROOT/'runs'/(path.name+'-speed')/'summary.json'
        if speed.exists():entry['speed']=load(speed)
        if (path/'summaries/memory.json').exists():entry['memory']=load(path/'summaries/memory.json')
        deployment_speed.append(entry)
    data={'updated_at':now(),'prefix':prefix,'model':'Empero Qwen3.8-35B-A3B-Distill','context_tokens':65536,'max_output_tokens':64000,'cpu_moe_layers':34,'runtime':'b11960 / 8642541b2 / CUDA12.4','cells':cells,'comparisons':comparisons,'deployment_speed':deployment_speed,'limits':['能力試験は各条件1回、固定長速度は各プロンプト3回。同じ条件をまとめて測定し、実行順の無作為化はしていません。','過去の速度測定はCPU MoE 30層、主比較の新規対照は全構成34層です。30層での補足速度試験は別に表示します。','固定長速度は思考OFF・temperature 0・ignore_eosで256トークンを生成した測定です。品質の得点ではありません。','MTP動作は実際の予測・採用トークン数でも確認しています。propsのデフォルト表示は実行中でもnoneの場合があります。','HumanEvalは既存の制限付きWindows採点器、BFCLは固定80問のAST採点です。公式の全問スコアではありません。']}
    data['truncations']=truncations
    data['reference_iq3_prefix']=study_config.get('reference_iq3_prefix')
    data['q4_load_mode']=study_config.get('q4_load_mode')
    out=ROOT/'reports'/prefix;save(out/'matrix-data.json',data)
    with (out/'truncations.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['quantization','mtp','benchmark','thinking','case_id','completion_tokens','max_tokens','seconds','kind','raw']);writer.writeheader();writer.writerows(truncations)
    with (out/'conditions.csv').open('w',encoding='utf-8',newline='') as f:
        columns=['quantization','mtp','benchmark','thinking','passed','attempted','expected','median_seconds','total_seconds','completion_tokens','output_cap_hits','median_decode_tokens_per_second','draft_tokens','accepted_draft_tokens','run']
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for c in cells:
            for key,v in c['metrics'].items():
                suite,thinking=key.rsplit('_',1);row={k:v.get(k) for k in columns}
                row.update(quantization=c['quantization'],mtp=c['mtp'],benchmark=suite,thinking=thinking,run=c['run']+'-'+suite+'-'+thinking);writer.writerow(row)
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
        state='RAM保護停止' if c.get('resource_guard') else c['status']
        body+='<tr><th>'+esc(c['quantization'])+'<small>MTP '+esc(c['mtp'])+' · '+esc(state)+'</small></th>'+''.join('<td>'+v+'</td>' for v in fields)+'<td>'+speed+'</td><td>'+resource+'</td></tr>'
    page='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Empero 3bit / 4bit × MTP</title><style>body{font:16px system-ui,sans-serif;background:#101825;color:#edf4ff;max-width:1240px;margin:36px auto;padding:0 24px}a{color:#8ad3ff}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{padding:16px 12px;border-bottom:1px solid #34445c;text-align:left}small{display:block;color:#abc0da;font-size:12px;margin-top:6px}.scroll{overflow:auto}pre{white-space:pre-wrap;background:#172438;padding:20px}li{margin:10px 0}</style><a href="../../index.html">測定一覧</a><h1>Empero Qwen3.8 Distill<br>3bit / 4bit × MTP OFF / ON</h1><p>65,536 context · 最大64,000出力 · b11960 CUDA12.4 · 同じCPU MoE 34層 · 新規測定</p><p>BFCLは固定80問、HumanEvalは固定20問。思考OFF/ONとMTP OFF/ONは独立した設定です。</p><div class="scroll"><table><thead><tr><th>構成</th><th>BFCL 思考OFF</th><th>BFCL 思考ON</th><th>HE 思考OFF</th><th>HE 思考ON</th><th>固定長生成の中央値</th><th>最小空きRAM / 最大GPU</th></tr></thead><tbody>'''+body+'''</tbody></table></div><p>時間は各問題の生成API往復の合計・中央値です。固定長生成は思考OFFで256トークン×3種類×3回、予熱を除外。RAM/GPUはサーバー稼働中のサンプル値で、GPUはシステム全体の使用量です。</p><h2>MTPによる変化</h2><pre>'''+esc(json.dumps(comparisons,ensure_ascii=False,indent=2))+'''</pre><h2>比較範囲</h2><ul>'''+''.join('<li>'+esc(l)+'</li>' for l in data['limits'])+'''</ul><p><a href="matrix-data.json">全集計JSON</a> · <a href="../../docs/EMPERO_MTP.md">条件・解釈</a></p></html>'''
    comparison_html=''
    for pair in comparisons:
        comparison_html+='<h3>'+esc(pair['quantization'])+'</h3>'
        ratio=pair.get('fixed_length_speedup')
        if ratio is None:
            comparison_html+='<p>MTP OFF／ONの両方の測定を待っています。</p>'
            continue
        comparison_html+=f'<p><strong>固定長の生成速度: {ratio:.2f}倍（{(ratio-1)*100:+.1f}%）</strong><small>同じ生成内容だった試験: {pair["fixed_length_identical_content"]}/{pair["fixed_length_pairs"]}。内容が変わった試験も含む実測です。</small></p>'
        comparison_html+='<div class="scroll"><table><tr><th>生成する内容</th><th>MTP OFF</th><th>MTP ON</th><th>速度比</th></tr>'
        for row in pair['fixed_length_by_prompt']:
            label={'code':'Pythonコード','json':'JSON配列','prose':'技術説明文'}[row['prompt_id']]
            comparison_html+=f'<tr><td>{label}</td><td>{row["mtp_off_tok_s"]:.2f} tok/s</td><td>{row["mtp_on_tok_s"]:.2f} tok/s</td><td>{row["speedup"]:.2f}倍</td></tr>'
        comparison_html+='</table></div>'
        for key,value in pair['capability_changes'].items():
            suite,thinking=key.rsplit('_',1);changes=value['score_changes'];label=('BFCL' if suite=='bfcl' else 'HumanEval')+' / 思考'+thinking.upper()
            comparison_html+='<details><summary>'+label+f' — MTPによる成否の変化 {len(changes)}件</summary><p>API総時間の速度比: {value["request_time_speedup"]:.2f}倍。同じ回答（ランダムなtool IDを除外）: {value["identical_messages"]}/{value["pairs"]}。回答の長さが異なるため、純粋な生成速度とは別の指標です。</p><ul>'
            for change in changes:comparison_html+='<li>'+esc(change['id'])+': '+('改善' if change['mtp_on'] else '悪化')+'</li>'
            comparison_html+='</ul></details>'
    if deployment_speed:
        comparison_html+='<h2>従来の配置でも速度を確認</h2><p>IQ3_M・CPU MoE 30層・64K。こちらは速度だけの補足試験で、能力試験の主比較とは分けています。</p><table><tr><th>MTP</th><th>状態</th><th>固定長生成の中央値</th></tr>'
        for entry in deployment_speed:
            speed=entry.get('speed');rate=f"{speed['median_decode_tokens_per_second']:.2f} tok/s" if speed else '—'
            comparison_html+='<tr><td>'+esc(entry['mtp'])+'</td><td>'+esc(entry['status'])+'</td><td>'+rate+'</td></tr>'
        comparison_html+='</table>'
        if len(deployment_speed)==2 and all(e.get('speed') and e['status']=='complete' for e in deployment_speed):
            ratio=deployment_speed[1]['speed']['median_decode_tokens_per_second']/deployment_speed[0]['speed']['median_decode_tokens_per_second']
            data['deployment_speedup']=ratio;comparison_html+=f'<p>従来配置での速度比: <strong>{ratio:.2f}倍（{(ratio-1)*100:+.1f}%）</strong></p>'
    save(out/'matrix-data.json',data)
    raw_comparison='<pre>'+esc(json.dumps(comparisons,ensure_ascii=False,indent=2))+'</pre>'
    page=page.replace(raw_comparison,comparison_html).replace('<table><thead>','<table id="matrix"><thead>')
    page=page.replace('<h2>比較範囲</h2>',f'<p>完了した能力試験: {sum(len(c["metrics"]) for c in cells)}/16条件。得点は各条件1回答の測定です。</p><h2>比較範囲</h2>')
    page=page.replace('<a href="matrix-data.json">全集計JSON</a>','<a href="matrix-data.json">全集計JSON</a> · <a href="conditions.csv">条件別CSV</a>')
    page=page.replace('<h2>比較範囲</h2>',f'<p>能力試験での出力上限による打ち切り: {len(truncations)}件（固定長速度試験の意図的な終了は除外）。<a href="truncations.csv">打ち切り一覧CSV</a></p><h2>比較範囲</h2>')
    if study_config.get('reference_iq3_prefix'):
        prior=study_config['reference_iq3_prefix']
        page=page.replace('<h2>MTPによる変化</h2>','<p>4bitはメモリ保護停止後、読み込み方式を <code>--load-mode '+esc(study_config.get('q4_load_mode'))+'</code> に揃えてOFF／ONを再測定。3bitの400回答は、今回の先行runを元のIDのまま参照しています。<a href="../'+esc(prior)+'/index.html">初回試行（停止記録を含む）</a></p><h2>MTPによる変化</h2>')
    (out/'index.html').write_text(page,encoding='utf-8')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='20261031-empero-quant-mtp-64k');a=p.parse_args();d=build(a.prefix);print(json.dumps({'cells':[{'run':c['run'],'status':c['status'],'conditions':len(c['metrics'])} for c in d['cells']]}))
