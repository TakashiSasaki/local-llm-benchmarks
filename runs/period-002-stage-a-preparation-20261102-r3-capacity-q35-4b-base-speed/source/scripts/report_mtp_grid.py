"""Render arbitrary declared quantization/MTP groups from immutable run evidence."""
import argparse,csv,html,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,resolve_run
from report_mtp_pair import cell,compare

def build(prefix):
    manifest=load(resolve_run(prefix)/'manifest.json');cfg=manifest['config'];cells=[];comparisons=[]
    for group in cfg['groups']:
        pair=[]
        for mtp in group.get('states',['off','on']):
            name=cfg['cell_runs'][group['key']+'-'+mtp];c=cell(name)
            meta=load(ROOT/group['model_manifest'])
            c.update(group=group['key'],model=meta['model'],quantization=meta['quantization'],mtp=mtp,cpu_moe_layers=group['cpu_moe_layers'],load_mode=group.get('load_mode','none'),role=group.get('role','target'),fresh_inference=name not in group.get('reference_runs',{}).values())
            c['placement_label']=group.get('placement_label','CPU MoE '+str(group['cpu_moe_layers'])+'層')
            if meta.get('decoder_layers') and group['cpu_moe_layers']==0 and c.get('config'):
                args=c['config']['profile']['server_args'];ngl=int(args[args.index('-ngl')+1]);layers=meta['decoder_layers']
                cpu=min(layers,max(0,layers+1-ngl));gpu=layers-cpu;output='＋出力層' if ngl>0 else ''
                c['placement_label']=f'CPU {cpu}層 / GPU {gpu}層{output}（-ngl {ngl}）'
                c['placement_interpretation']='b11960 counts the output layer within -ngl. Input embeddings remain on CPU. Derived from saved arguments and pinned runtime allocation code; not an additional inference run.'
            cells.append(c);pair.append(c)
        if len(pair)==2 and [c['mtp'] for c in pair]==['off','on']:comparisons.append({'group':group['key'],**compare(*pair)})
    data={'updated_at':now(),'prefix':prefix,'status':manifest['status'],'title':cfg['title'],'cells':cells,'comparisons':comparisons,'unavailable':cfg.get('unavailable',[]),'truncations':[r for c in cells for r in c['truncations']],'empty_responses':[r for c in cells for r in c['empty_responses']]}
    data['output_parser_errors']=[r for c in cells for r in c['output_parser_errors']]
    data['incomplete_conditions']=[r for c in cells for r in c.get('incomplete_conditions',[])]
    out=ROOT/'reports'/prefix;save(out/'matrix-data.json',data)
    fields=['role','fresh_inference','model','quantization','cpu_moe_layers','placement_label','load_mode','mtp','benchmark','thinking','passed','attempted','secondary_policy_passed','total_seconds','completion_tokens','output_cap_hits','server_output_parser_errors','unavailable_response_stats_cases','run']
    with (out/'conditions.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in cells:
            for key,s in c['metrics'].items():
                suite,mode=key.rsplit('_',1);r={k:c.get(k,s.get(k)) for k in fields};r.update(benchmark=suite,thinking=mode,run=c['run']+'-'+suite+'-'+mode)
                if suite=='humaneval':r['secondary_policy_passed']=c.get('secondary_humaneval',{}).get(mode,{}).get('secondary_passed')
                w.writerow(r)
    with (out/'truncations.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['run','quantization','mtp','benchmark','thinking','case_id','seconds','completion_tokens','max_tokens','finish_reason','raw','kind'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data['truncations'])
    esc=lambda v:html.escape(str(v))
    keys=['bfcl_off','bfcl_on','humaneval_off','humaneval_on']
    def score(c,k):
        s=c['metrics'].get(k);return str(s['passed'])+'/'+str(s['expected']) if s else '未完了'
    def rate(c):return f"{c['speed']['median_decode_tokens_per_second']:.2f}" if c.get('speed') else '—'
    def label(c):return c['model']+' '+c['quantization']+' / MTP '+c['mtp']+' / '+c['placement_label']
    md=['# '+cfg['title'],'','65,536 context・最大64,000出力・F16 KV・b11960-8642541b2 CUDA12.4。BFCL80問／HumanEval20問の固定部分集合。','', '| 構成 | 取得 | 状態 | BFCL OFF | ON | HE OFF | ON | 固定長 tok/s |','| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    if cfg.get('context_note'):md[2]+=' '+cfg['context_note']
    body='<a href="../../index.html">測定一覧</a><h1>'+esc(cfg['title'])+'</h1><p>65,536 context · 最大64,000出力 · F16 KV · b11960-8642541b2 / CUDA12.4</p><p>状態: '+esc(manifest['status'])+'。収集の完了と正答率は別です。CPU/GPU配置は各行と保存した起動引数を参照してください。'+esc(cfg.get('context_note',''))+'</p><label>構成を絞り込む <input id="filter" type="search" placeholder="モデル・量子化・MTP"></label><div class="scroll"><table id="main-matrix"><thead><tr><th>構成 / 取得</th><th>BFCL 思考OFF</th><th>思考ON</th><th>HE 思考OFF</th><th>思考ON</th><th>固定長 tok/s</th><th>状態</th></tr></thead><tbody>'
    for c in cells:
        origin='新規推論' if c['fresh_inference'] else '既存run参照';description=label(c)
        body+='<tr><th><a href="../../runs/'+esc(c['run'])+'/manifest.json">'+esc(description)+'</a><small>'+esc(origin+' / '+c['role']+' / load '+c['load_mode'])+'</small></th>'
        for k in keys:
            s=c['metrics'].get(k);body+='<td>'+score(c,k)+(f"<small>{s['total_seconds']:.1f} s · 打ち切り {s['output_cap_hits']}</small>" if s else '')+'</td>'
        body+='<td>'+rate(c)+'</td><td>'+esc(c['status'])+'</td></tr>'
        md.append('| '+description+' | '+origin+' | '+c['status']+' | '+' | '.join(score(c,k) for k in keys)+' | '+rate(c)+' |')
    body+='</tbody></table></div><p>BFCLは外部関数を実行しないAST採点。各問題1回答です。固定長速度は思考OFF・greedy・256トークン、3種類×3回の中央値で、予熱は除外しています。生成内容の一致は保証しません。</p>'
    if data['incomplete_conditions']:
        body+='<h2>途中終了・未実施の条件</h2><p>以下の正解数は保存できた分だけです。未完了条件を全問の正答率比較には含めません。</p><div class="scroll"><table><tr><th>条件</th><th>状態</th><th>保存件数</th><th>保存分の正解数</th><th>原因</th></tr>'
        md+=['','## 途中終了・未実施','', '保存できた分の正解数であり、全問の正答率ではありません。']
        for r in data['incomplete_conditions']:
            label_text=r['run']+' / '+r['benchmark']+' / 思考'+r['thinking'];label_html=esc(label_text)
            if r['evidence']:label_html='<a href="../../'+esc(r['evidence'])+'">'+label_html+'</a>'
            body+='<tr><th>'+label_html+'</th><td>'+esc(r['status'])+'</td><td>'+str(r['saved_records'])+'/'+str(r['expected'])+'</td><td>'+str(r['correct_saved_records'])+'</td><td>'+esc(r['error'] or '—')+'</td></tr>'
            md+=['','- '+label_text+': '+r['status']+'、保存 '+str(r['saved_records'])+'/'+str(r['expected'])+'、保存分の正解 '+str(r['correct_saved_records'])+'。'+str(r['error'] or '')]
        body+='</table></div>'
    if data['output_parser_errors']:
        note='不正なツール出力をllama.cppが拒否したHTTP 500は失敗として集計し、出力の修正や再試行はしていません。この応答では生成トークン数・思考の有無・終了理由が返らず不明です。トークン合計と打ち切り件数は統計が取得できた回答だけの値です。'
        body+='<h2>出力形式エラー '+str(len(data['output_parser_errors']))+'件</h2><p>'+note+'</p><ul>'
        for r in data['output_parser_errors']:body+='<li><a href="../../'+esc(r['raw'])+'">'+esc(r['benchmark']+' / 思考'+r['thinking']+' / '+r['case_id'])+'</a></li>'
        body+='</ul>';md+=['',note,'']+[r['benchmark']+' / 思考'+r['thinking']+' / '+r['case_id'] for r in data['output_parser_errors']]
    body+='<h2>MTPの比較</h2>'
    for comp in comparisons:
        body+='<details open><summary>'+esc(comp['group'])+'</summary>'
        if 'fixed_length_speedup' in comp:
            ratio=comp['fixed_length_speedup'];value=f'{ratio:.3f}倍（{(ratio-1)*100:+.1f}%）'
            body+='<p>固定長生成 '+value+'。内容一致 '+str(comp['identical_speed_contents'])+'/'+str(comp['speed_pairs'])+'。</p>';md+=['','MTP '+comp['group']+': '+value+'。']
        body+='<pre>'+esc(json.dumps(comp['capability_changes'],ensure_ascii=False,indent=2))+'</pre></details>'
    body+='<h2>メモリと回答の完了</h2><p>メモリは採取間隔のある観測値。GPU使用量はシステム全体です。出力上限打ち切り '+str(len(data['truncations']))+'件、本文とツール呼び出しが両方空の応答 '+str(len(data['empty_responses']))+'件。BFCLの呼び出し不要問題は空の回答でも合格する場合があります。</p><div class="scroll"><table><tr><th>構成</th><th>最小空きRAM GiB</th><th>最大GPU MiB</th><th>HE補助採点 OFF / ON</th></tr>'
    for c in cells:
        memory=c.get('memory',{});ram=memory.get('minimum_available_ram_bytes');gpu=memory.get('peak_gpu_used_mib_system_total');audit=c.get('secondary_humaneval',{})
        secondary=' / '.join(str(audit[k]['original_passed'])+'→'+str(audit[k]['secondary_passed'])+'/20' if k in audit else '未完了' for k in ['off','on'])
        body+='<tr><th>'+esc(label(c))+'</th><td>'+(f'{ram/1024**3:.2f}' if ram is not None else '—')+'</td><td>'+(str(gpu) if gpu is not None else '—')+'</td><td>'+secondary+'</td></tr>'
    body+='</table></div><p>補助採点は既存の実行制限を緩めた別runのreplayで、主得点を変更しません。</p>'
    if data['unavailable']:
        body+='<h2>測定できなかった条件</h2><pre>'+esc(json.dumps(data['unavailable'],ensure_ascii=False,indent=2))+'</pre>';md+=['','## 容量などで測定できなかった条件','',json.dumps(data['unavailable'],ensure_ascii=False,indent=2)]
    body+='<h2>比較上の注意</h2><p>量子化の比較ではCPU配置とload-modeも確認してください。配置が異なる構成の速度差を量子化だけの効果には帰属できません。モデル配布物にはテンプレートや較正等の差もあります。全問版の公式ベンチマーク値ではなく、このPCでの部分集合・単回の結果です。</p><p><a href="matrix-data.json">JSON</a> · <a href="conditions.csv">条件CSV</a> · <a href="truncations.csv">打ち切りCSV</a> · <a href="summary.md">集計Markdown</a></p>'
    if cfg.get('reference_report'):
        if (ROOT/cfg['reference_report']).exists():body+='<p><a href="../../'+esc(cfg['reference_report'])+'">過去のモデル比較</a>。元モデル、配置、配布物などの差は各runを確認してください。</p>'
        else:body+='<p>予定した比較元ページは未作成です。先行試験の失敗・未完了は保存したrunと利用不可条件を参照してください。</p>'
    style='body{font:16px system-ui,sans-serif;background:#101825;color:#edf4ff;max-width:1500px;margin:36px auto;padding:0 24px}a{color:#8ad3ff}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{padding:14px 12px;border-bottom:1px solid #34445c;text-align:left}.scroll{overflow:auto}small{display:block;color:#abc0da;font-size:12px;margin-top:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#172438;padding:16px}input{font:inherit;padding:8px;margin:8px}details{margin:16px 0}'
    script="document.querySelector('#filter').addEventListener('input',e=>{for(const r of document.querySelectorAll('#main-matrix tbody tr'))r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase())})"
    (out/'index.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(cfg['title'])+'</title><style>'+style+'</style>'+body+'<script>'+script+'</script></html>',encoding='utf-8')
    (out/'summary.md').write_text('\n'.join(md)+'\n',encoding='utf-8');return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);a=p.parse_args();d=build(a.prefix);print(json.dumps({'cells':len(d['cells']),'status':d['status']}))
