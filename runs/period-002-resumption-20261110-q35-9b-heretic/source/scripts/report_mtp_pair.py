"""Report a new MTP pair and explicitly labelled, previously collected model references."""
import argparse,csv,html,json,pathlib,statistics,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,resolve_run
from local_llm_benchmarks.output_errors import is_output_parser_error

def cell(name):
    parent=resolve_run(name);c={'run':name,'status':'not-started','metrics':{},'truncations':[],'empty_responses':[],'timed_cases':[],'output_parser_errors':[],'incomplete_conditions':[]}
    if not (parent/'manifest.json').exists():return c
    m=load(parent/'manifest.json');cfg=m['config'];c.update(status=m['status'],config=cfg,model=cfg['model']['model'],quantization=cfg['model']['quantization'],mtp=cfg['profile']['mtp'])
    if m.get('error'):c['collection_error']=m['error']
    for filename,key in [('summaries/memory.json','memory'),('configs/cleanup.json','cleanup')]:
        if (parent/filename).exists():c[key]=load(parent/filename)
    if (parent/'summary.json').exists():c['collection_summary']=load(parent/'summary.json')
    speed=ROOT/'runs'/(name+'-speed')/'summary.json'
    if speed.exists():c['speed']=load(speed)
    for suite in ['bfcl','humaneval']:
        for mode in ['off','on']:
            p=ROOT/'runs'/(name+'-'+suite+'-'+mode)
            if not (p/'summary.json').exists():
                cm=load(p/'manifest.json') if (p/'manifest.json').exists() else {'status':'not-started'}
                filename='bfcl-cases.json' if suite=='bfcl' else 'cases.json';entries=load(p/'summaries'/filename) if (p/'summaries'/filename).exists() else []
                c['incomplete_conditions'].append({'run':name,'benchmark':suite,'thinking':mode,'status':cm['status'],'saved_records':len(entries),'correct_saved_records':sum(e['passed'] for e in entries),'server_output_parser_errors_saved':sum(bool(e.get('server_output_parser_error')) for e in entries),'expected':80 if suite=='bfcl' else 20,'error':cm.get('error'),'evidence':(p/'manifest.json').relative_to(ROOT).as_posix() if (p/'manifest.json').exists() else None})
                continue
            s=load(p/'summary.json');raw=[(f,load(f)) for f in sorted((p/'raw').glob('*.json'))]
            known=[r for _,r in raw if not is_output_parser_error(r)]
            s.update(completion_tokens=sum(r['response']['usage']['completion_tokens'] for r in known),draft_tokens=sum(r['response'].get('timings',{}).get('draft_n',0) for r in known),accepted_draft_tokens=sum(r['response'].get('timings',{}).get('draft_n_accepted',0) for r in known))
            if len(known)!=len(raw):s['statistics_note']='Token totals and output-cap counts cover only responses with returned generation statistics; parser-error cases have unknown statistics.'
            c['metrics'][suite+'_'+mode]=s
            for f,r in raw:
                if is_output_parser_error(r):
                    entry={'run':name,'quantization':c['quantization'],'mtp':c['mtp'],'benchmark':suite,'thinking':mode,'case_id':f.stem.replace('HumanEval_','HumanEval/'),'seconds':r['seconds'],'completion_tokens':None,'max_tokens':r['request']['max_tokens'],'finish_reason':None,'raw':f.relative_to(ROOT).as_posix(),'http_status':500,'api_error':r['response']['error']}
                    c['output_parser_errors'].append(entry);c['timed_cases'].append(entry);continue
                resp=r['response'];choice=resp['choices'][0];message=choice['message']
                entry={'run':name,'quantization':c['quantization'],'mtp':c['mtp'],'benchmark':suite,'thinking':mode,'case_id':f.stem.replace('HumanEval_','HumanEval/'),'seconds':r['seconds'],'completion_tokens':resp['usage']['completion_tokens'],'max_tokens':r['request']['max_tokens'],'finish_reason':choice['finish_reason'],'raw':f.relative_to(ROOT).as_posix()}
                c['timed_cases'].append(entry)
                if choice['finish_reason']=='length':c['truncations'].append({**entry,'kind':'output_limit'})
                if not (message.get('content') or message.get('tool_calls')):c['empty_responses'].append(entry)
    audit=ROOT/'runs'/(name+'-he-policy-audit')/'summary.json'
    if audit.exists():c['secondary_humaneval']=load(audit)['iq3_m'];c['secondary_audit_run']=name+'-he-policy-audit'
    return c

def compare(a,b):
    d={'off_run':a['run'],'on_run':b['run'],'capability_changes':{}}
    if a.get('speed') and b.get('speed'):
        d['fixed_length_speedup']=b['speed']['median_decode_tokens_per_second']/a['speed']['median_decode_tokens_per_second']
        aa=load(ROOT/'runs'/(a['run']+'-speed')/'summaries/speed-cases.json');bb=load(ROOT/'runs'/(b['run']+'-speed')/'summaries/speed-cases.json')
        assert [(r['prompt_id'],r['repeat']) for r in aa]==[(r['prompt_id'],r['repeat']) for r in bb]
        d['identical_speed_contents']=sum(x['content_sha256']==y['content_sha256'] for x,y in zip(aa,bb));d['speed_pairs']=len(aa)
        d['by_prompt']=[]
        for key in sorted({r['prompt_id'] for r in aa}):
            av=[r['timings']['predicted_per_second'] for r in aa if r['prompt_id']==key];bv=[r['timings']['predicted_per_second'] for r in bb if r['prompt_id']==key]
            d['by_prompt'].append({'prompt_id':key,'off_median':statistics.median(av),'on_median':statistics.median(bv),'off_range':[min(av),max(av)],'on_range':[min(bv),max(bv)]})
    for key in a['metrics'].keys()&b['metrics'].keys():
        suite,mode=key.rsplit('_',1);filename='bfcl-cases.json' if suite=='bfcl' else 'cases.json'
        aa=load(ROOT/'runs'/(a['run']+'-'+key.replace('_','-'))/'summaries'/filename);bb=load(ROOT/'runs'/(b['run']+'-'+key.replace('_','-'))/'summaries'/filename)
        assert len(aa)==len(bb)
        changes=[];identical=0
        def message(parent,cid):
            raw=load(ROOT/'runs'/(parent['run']+'-'+suite+'-'+mode)/'raw'/(cid.replace('/','_')+'.json'))
            if is_output_parser_error(raw):return {'http_status':500,'error':raw['response']['error']}
            r=raw['response']['choices'][0]['message']
            for t in r.get('tool_calls') or []:t.pop('id',None)
            return r
        for x,y in zip(aa,bb):
            cid=x.get('id') or x['task_id'];assert cid==(y.get('id') or y['task_id'])
            identical+=message(a,cid)==message(b,cid)
            if x['passed']!=y['passed']:changes.append({'id':cid,'mtp_off':x['passed'],'mtp_on':y['passed']})
        d['capability_changes'][key]={'score_changes':changes,'identical_messages':identical,'pairs':len(aa),'request_time_speedup':a['metrics'][key]['total_seconds']/b['metrics'][key]['total_seconds']}
    return d

def build(prefix):
    parent=resolve_run(prefix);m=load(parent/'manifest.json');cfg=m['config'];meta=load(ROOT/cfg['model_manifest'])
    assert meta['quantization']=='Q4_K_M','This report is for Q4_K_M pairs'
    cells=[cell(name) for name in cfg['cell_runs'].values()];refs=[]
    if cfg.get('reference_matrix'):
        previous=load(resolve_run(cfg['reference_matrix'])/'manifest.json');assert previous['status']=='complete'
        refs=[cell(name) for name in previous['config']['cell_runs'].values()]
    data={'updated_at':now(),'prefix':prefix,'model':meta['model'],'context_tokens':cfg['context_tokens'],'max_output_tokens':cfg['max_output_tokens'],'cpu_moe_layers':cfg['cpu_moe_layers'],'load_mode':cfg['load_mode'],'cells':cells,'references':refs,'reference_matrix':cfg.get('reference_matrix'),'comparison':compare(*cells),'truncations':[r for c in cells for r in c['truncations']],'empty_responses':[r for c in cells for r in c['empty_responses']]}
    data['longest_cases']=sorted([r for c in cells for r in c['timed_cases']],key=lambda r:r['seconds'],reverse=True)[:10]
    out=ROOT/'reports'/prefix;save(out/'matrix-data.json',data)
    with (out/'conditions.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['role','model','quantization','mtp','benchmark','thinking','passed','attempted','secondary_policy_passed','median_seconds','total_seconds','completion_tokens','output_cap_hits','run']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for role,rows in [('new',cells),('reference',refs)]:
            for c in rows:
                for key,s in c['metrics'].items():
                    suite,mode=key.rsplit('_',1);r={k:s.get(k) for k in fields};r.update(role=role,model=c['model'],quantization=c['quantization'],mtp=c['mtp'],benchmark=suite,thinking=mode,run=c['run']+'-'+suite+'-'+mode)
                    if suite=='humaneval':r['secondary_policy_passed']=c.get('secondary_humaneval',{}).get(mode,{}).get('secondary_passed')
                    w.writerow(r)
    with (out/'truncations.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['run','quantization','mtp','benchmark','thinking','case_id','seconds','completion_tokens','max_tokens','finish_reason','raw','kind'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data['truncations'])
    def score(c,key):
        s=c['metrics'].get(key);return f"{s['passed']}/{s['expected']}" if s else '未完了'
    def score_html(c,key):
        value='<span class="score">'+score(c,key)+'</span>';s=c['metrics'].get(key)
        return value+(f"<small>合計 {s['total_seconds']:.1f} s · 中央値 {s['median_seconds']:.2f} s</small>" if s else '')
    def rate(c):return f"{c['speed']['median_decode_tokens_per_second']:.2f}" if c.get('speed') else '—'
    def label(c):return c.get('model',meta['model'])+' '+c.get('quantization',meta['quantization'])+' / MTP '+c.get('mtp',c['run'].rsplit('-',1)[-1])
    esc=lambda x:html.escape(str(x))
    def table(rows,identity,show_status=True):
        result='<div class="scroll"><table id="'+identity+'"><thead><tr><th>構成</th><th>BFCL 思考OFF</th><th>思考ON</th><th>HE 思考OFF</th><th>思考ON</th><th>固定長 tok/s</th>'+('<th>状態</th>' if show_status else '')+'</tr></thead><tbody>'
        for c in rows:result+='<tr><th><a href="../../runs/'+esc(c['run'])+'/manifest.json">'+esc(label(c))+'</a></th>'+''.join('<td>'+score_html(c,key)+'</td>' for key in ['bfcl_off','bfcl_on','humaneval_off','humaneval_on'])+'<td>'+rate(c)+'</td>'+('<td>'+esc(c['status'])+'</td>' if show_status else '')+'</tr>'
        return result+'</tbody></table></div>'
    explanation=f"65,536 context · 最大64,000出力 · CPU MoE {cfg['cpu_moe_layers']}層 · F16 KV · load-mode {cfg['load_mode']} · b11960 / 8642541b2 / CUDA12.4"
    md=['# '+meta['model']+' Q4_K_M × MTP','','主比較: '+explanation+'。BFCL各80問、HumanEval各20問。','', '| 構成 | 状態 | BFCL OFF | ON | HE OFF | ON | 生成速度 tok/s |','| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for c in cells:md.append('| '+label(c)+' | '+c['status']+' | '+' | '.join(score(c,k) for k in ['bfcl_off','bfcl_on','humaneval_off','humaneval_on'])+' | '+rate(c)+' |')
    md+=['','速度は思考OFF・greedy・固定256出力トークン、3プロンプト各3回の中央値。生成内容の一致は保証しません。予熱は除外。得点は主採点で、各問題1回答です。','']
    state='完了' if m['status']=='complete' else '収集中（予定400回答）'
    body='<a href="../../index.html">測定一覧</a><h1>'+esc(meta['model'])+'<br>Q4_K_M × MTP OFF / ON</h1><p>'+esc(explanation)+'</p><p>新規測定: 2構成 × BFCL80問・HumanEval20問 × 思考OFF/ON = 400回答。状態: '+state+'。収集完了と正答率は区別しています。</p>'+table(cells,'main-matrix')
    body+='<h2>稼働中のメモリ</h2><p>空きRAMとシステム全体のGPU使用量のサンプル値です。収集済みの値を表示し、将来のピークを保証するものではありません。</p><table><tr><th>MTP</th><th>最小空きRAM</th><th>最大GPU使用量</th></tr>'
    md+=['## 稼働中のメモリ（サンプル値）','','| MTP | 最小空きRAM GiB | 最大GPU MiB |','| --- | ---: | ---: |']
    for c in cells:
        memory=c.get('memory',{});ram=memory.get('minimum_available_ram_bytes');gpu=memory.get('peak_gpu_used_mib_system_total')
        ram_text=f'{ram/1024**3:.2f}' if ram is not None else '未確定';gpu_text=f'{gpu:.0f}' if gpu is not None else '未確定';mode=c.get('mtp',c['run'].rsplit('-',1)[-1])
        body+='<tr><td>'+mode+'</td><td>'+ram_text+' GiB</td><td>'+gpu_text+' MiB</td></tr>';md.append('| '+mode+' | '+ram_text+' | '+gpu_text+' |')
    body+='</table>';md+=['','GPUはシステム全体のサンプル値です。','']
    comp=data['comparison']
    if 'fixed_length_speedup' in comp:
        ratio=comp['fixed_length_speedup'];body+=f'<h2>固定長生成の速度差</h2><p><strong>{ratio:.3f}倍（{(ratio-1)*100:+.1f}%）</strong>。思考OFF・greedy・256出力トークン、3プロンプト各3回。予熱を除外。</p><p>同じ生成内容だった試験: '+str(comp['identical_speed_contents'])+'/'+str(comp['speed_pairs'])+'。生成量は固定していますが本文は同一とは限りません。</p>'
        md+=['固定長生成の速度比: '+f'{ratio:.3f}倍（{(ratio-1)*100:+.1f}%）','']
        body+='<table><tr><th>プロンプト</th><th>MTP OFF tok/s</th><th>MTP ON tok/s</th></tr>'
        for r in comp['by_prompt']:body+='<tr><td>'+esc(r['prompt_id'])+'</td><td>'+f"{r['off_median']:.2f}"+'</td><td>'+f"{r['on_median']:.2f}"+'</td></tr>'
        body+='</table>'
    for key,v in sorted(comp['capability_changes'].items()):body+='<details><summary>'+esc(key)+' — 成否変化 '+str(len(v['score_changes']))+'件</summary><p>API総時間の速度比 '+f"{v['request_time_speedup']:.3f}"+'倍。同じ回答（ランダムなtool IDを除外） '+str(v['identical_messages'])+'/'+str(v['pairs'])+'。</p><pre>'+esc(json.dumps(v['score_changes'],ensure_ascii=False,indent=2))+'</pre></details>'
    body+='<h2>出力打ち切りと長時間生成</h2><p>出力上限による打ち切り '+str(len(data['truncations']))+'件、最終回答とツール呼び出しが両方とも空の応答 '+str(len(data['empty_responses']))+'件。BFCLの呼び出し不要問題は空の回答でも正解になる場合があります。</p><div class="scroll"><table><tr><th>構成</th><th>試験</th><th>問題</th><th>秒</th><th>出力トークン</th><th>終了</th></tr>'
    md+=['出力上限の打ち切り '+str(len(data['truncations']))+'件、最終回答とツール呼び出しが両方とも空の応答 '+str(len(data['empty_responses']))+'件。BFCLの正解と回答の完了は別に確認してください。','','## 長時間の問題','','| 構成 | 試験 | 問題 | 秒 | 出力トークン | 終了 |','| --- | --- | --- | ---: | ---: | --- |']
    for r in data['longest_cases']:
        mode=r['mtp'];test=r['benchmark']+' / 思考'+r['thinking'];link='../../'+r['raw'];body+='<tr><td>MTP '+mode+'</td><td>'+esc(test)+'</td><td><a href="'+esc(link)+'">'+esc(r['case_id'])+'</a></td><td>'+f"{r['seconds']:.1f}"+'</td><td>'+str(r['completion_tokens'])+'</td><td>'+esc(r['finish_reason'])+'</td></tr>'
        md.append('| MTP '+mode+' | '+test+' | ['+r['case_id']+']('+link+') | '+f"{r['seconds']:.1f}"+' | '+str(r['completion_tokens'])+' | '+r['finish_reason']+' |')
    body+='</table></div>'
    if any(c.get('secondary_humaneval') for c in cells):
        body+='<h2>HumanEval補助採点</h2><p>既知のtype()制限を確認する既存ポリシーのreplay。主得点は変更しません。</p><table><tr><th>MTP</th><th>思考OFF 主→補助</th><th>思考ON 主→補助</th></tr>'
        md+=['','## HumanEval補助採点（主得点を置き換えない）','','| MTP | 思考OFF 主→補助 | 思考ON 主→補助 |','| --- | ---: | ---: |']
        for c in cells:
            audit=c.get('secondary_humaneval')
            if not audit:continue
            values=[str(audit[k]['original_passed'])+' → '+str(audit[k]['secondary_passed'])+' /20' for k in ['off','on']]
            body+='<tr><td>'+c['mtp']+'</td>'+''.join('<td>'+v+'</td>' for v in values)+'</tr>';md.append('| '+c['mtp']+' | '+' | '.join(values)+' |')
        body+='</table>'
    if refs:
        body+='<h2>先に測ったEmperoとの比較</h2><p>以下は元runの参照で、新規推論には数えません。CPU MoE34層・64K、4bitはload-mode none、3bitはmmapです。ファイルごとの較正・テンプレート等も異なり、差をビット数や学習だけに帰属させません。</p>'+table(refs,'reference-matrix',False)
        body+='<p><a href="../'+esc(cfg['reference_matrix'])+'/index.html">Emperoの詳細・停止記録・補助採点</a> · <a href="../20261031-empero-qwen38-iq3m-64k/index.html">以前の10構成比較</a></p>'
        md+=['','## 先行Empero測定の参照（新規推論ではない）','','| 構成 | BFCL OFF | ON | HE OFF | ON | 速度 tok/s |','| --- | ---: | ---: | ---: | ---: | ---: |']
        for c in refs:md.append('| '+label(c)+' | '+' | '.join(score(c,k) for k in ['bfcl_off','bfcl_on','humaneval_off','humaneval_on'])+' | '+rate(c)+' |')
    body+='<h2>測定の範囲</h2><ul><li>固定80問・20問の部分集合。公式の全問スコアではありません。</li><li>能力試験は各問題1回答、速度試験は各プロンプト3回。条件ごとのブロック順で、実行順の無作為化はしていません。</li><li>MTPは実際のdraft/acceptedトークン数でも確認。思考設定とは独立しています。</li><li>生成量が変われば、固定長生成が速くても課題完了までの時間は長くなることがあります。</li><li>BFCLはAST採点で、外部関数やHermesの実ツールは実行していません。</li></ul><p><a href="matrix-data.json">全データJSON</a> · <a href="conditions.csv">条件CSV</a> · <a href="truncations.csv">打ち切りCSV</a> · <a href="summary.md">GitHub用集計</a> · <a href="../../docs/QWEN36_Q4_MTP.md">条件・解釈</a></p>'
    page='<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(meta['model'])+' Q4 × MTP</title><style>body{font:16px system-ui,sans-serif;background:#101825;color:#edf4ff;max-width:1240px;margin:36px auto;padding:0 24px}a{color:#8ad3ff}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{padding:15px 12px;border-bottom:1px solid #34445c;text-align:left}.scroll{overflow:auto}pre{white-space:pre-wrap;background:#172438;padding:16px}li,details{margin:10px 0}</style>'+body+'</html>'
    page=page.replace('.scroll{overflow:auto}', '.scroll{overflow:auto}small{display:block;color:#abc0da;font-size:12px;margin-top:6px}')
    (out/'index.html').write_text(page,encoding='utf-8')
    md+=['','[全データJSON](matrix-data.json) · [条件CSV](conditions.csv) · [打ち切りCSV](truncations.csv) · [表示ページ](index.html) · [条件・解釈](../../docs/QWEN36_Q4_MTP.md)','']
    (out/'summary.md').write_text('\n'.join(md),encoding='utf-8')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);a=p.parse_args();d=build(a.prefix);print(json.dumps({'cells':[{'run':c['run'],'status':c['status'],'conditions':len(c['metrics'])} for c in d['cells']],'reference_cells':len(d['references'])}))
