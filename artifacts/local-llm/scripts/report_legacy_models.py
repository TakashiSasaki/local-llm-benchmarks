"""Compare two added checkpoints with the six saved b11960 measurements."""
import html,json,pathlib,statistics,sys
from install_lfm3_runtime import save
run=pathlib.Path(sys.argv[1]);read=lambda p:json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
r=read(run/'results.json');reference=pathlib.Path(r['reference_64k']);ref=read(reference)
assert 'error' not in r and len(r['models'])==2 and r['reference_unchanged']
labels={'lfm':'LFM2.5-24B-A2B QAD-Q4_0','glm':'GLM-4.7-Flash Q4_K_M','lfm3':'LFM3 Text QAD-Q4_0','lfm3-vl-q4':'LFM3 VL QAD-Q4_0','lfm3-q8':'LFM3 Text Q8_0','lfm3-vl-q8':'LFM3 VL Q8_0','qwen-daily':'Qwen3.5-4B Q4_K_M','qwen-large':'Qwen3.6-35B-A3B UD-Q3_K_M'}
def stat(es):
    ts=[e['timings'] for e in es if e.get('timings')];ms=sum(t.get('predicted_ms',0) for t in ts)
    return {'passed':sum(e['passed'] for e in es),'attempted':len(es),'median_seconds':statistics.median(e['seconds'] for e in es),'total_seconds':sum(e['seconds'] for e in es),'tokens_per_second':1000*sum(t.get('predicted_n',0) for t in ts)/ms if ms else None,'output_cap_hits':sum(e.get('finish_reason')=='length' for e in es),'no_final_content':sum(not e.get('content','').strip() for e in es),'reasoning_observed_cases':sum(e.get('reasoning_observed',False) for e in es),'maximum_actual_output_tokens':max(e['usage']['completion_tokens'] for e in es),'maximum_actual_total_tokens':max(e['usage']['total_tokens'] for e in es)}
models=[]
for origin,record,path in [('new',r,run/'results.json'),('reused',ref,reference)]:
    for key in record['protocol']['order']:
        m=record['models'][key]
        assert m['test_server_stopped'] and len(m['human_eval']['off'])==20 and len(m['human_eval']['on'])==20 and len(m['bfcl'])==80
        models.append({'key':key,'model':labels[key],'origin':origin,'source':str(path),'runtime':m['runtime'],'human_eval':{mode:stat(es) for mode,es in m['human_eval'].items()},'bfcl':stat(m['bfcl']),'bfcl_categories':{cat:stat([e for e in m['bfcl'] if e['category']==cat]) for cat in ['simple_python','multiple','parallel','irrelevance']},'memory':m['memory'],'mode_control':m.get('mode_control','Native template enable_thinking switch'),'profile':m['profile']})
audits={}
for parent in [run,reference.parent]:
    p=parent/'grader-sensitivity/results.json'
    if p.exists():
        for k,modes in read(p)['models'].items():audits[k]={mode:{field:v[field] for field in ['original_passed','secondary_passed','rescued_ids']} for mode,v in modes.items()}
s={'models':models,'new_scored_generations':240,'reused_scored_generations':720,'total_compared_configurations':8,'context_per_slot':65536,'output_target':64000,'budget_rule':r['protocol']['budget_rule'],'reference_source':str(reference),'reference_sha256':r['reference_64k_sha256'],'grader_sensitivity':audits,'limits':r['limits']}
save(run/'summary.json',s)
def table(head,rows):return '<table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
scores=table(['モデル','測定','HumanEval OFF /20','HumanEval ON /20','BFCL OFF /80'],[[m['model']+(' *' if m['key']=='lfm' else ''),'今回追加' if m['origin']=='new' else '保存済みb11960結果',m['human_eval']['off']['passed'],m['human_eval']['on']['passed'],m['bfcl']['passed']] for m in models])
categories=table(['モデル','単一関数 /20','候補選択 /20','複数呼び出し /20','呼び出し不要 /20'],[[m['model']]+[m['bfcl_categories'][k]['passed'] for k in ['simple_python','multiple','parallel','irrelevance']] for m in models])
budgets=table(['モデル','HE OFF 上限到達 /20','HE ON 上限到達 /20','HE ON 最終回答欄が空 /20','BFCL 上限到達 /80','HE ON 最大出力token'],[[m['model'],m['human_eval']['off']['output_cap_hits'],m['human_eval']['on']['output_cap_hits'],m['human_eval']['on']['no_final_content'],m['bfcl']['output_cap_hits'],m['human_eval']['on']['maximum_actual_output_tokens']] for m in models])
reason=table(['モデル','HE OFF 思考欄あり /20','HE ON 思考欄あり /20','BFCL 思考欄あり /80'],[[m['model'],m['human_eval']['off']['reasoning_observed_cases'],m['human_eval']['on']['reasoning_observed_cases'],m['bfcl']['reasoning_observed_cases']] for m in models])
perf=table(['モデル','HE OFF 中央値 秒','HE ON 中央値 秒','BFCL 中央値 秒','HE ON 生成token/秒','システム全体GPU最大 MiB','空きRAM最小 GiB'],[[m['model'],round(m['human_eval']['off']['median_seconds'],2),round(m['human_eval']['on']['median_seconds'],2),round(m['bfcl']['median_seconds'],2),round(m['human_eval']['on']['tokens_per_second'],1),m['memory']['peak_gpu_used_mib_system_total'],round(m['memory']['minimum_available_ram_bytes']/1024**3,2)] for m in models])
doc='''<!doctype html><html lang="ja"><meta charset="utf-8"><title>旧モデルのb11960追加ベンチマークと8構成比較</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:1300px;margin:32px auto;padding:0 24px;color:#182a3b}table{border-collapse:collapse;width:100%;margin:24px 0 36px;font-size:14px}td,th{padding:9px;border:1px solid #d3dce6;text-align:left}th{background:#edf2f7}.note{padding:16px;background:#fff5dc}</style><h1>旧モデルのb11960追加ベンチマーク</h1><p>LFM2.5-24B-A2BとGLM-4.7-Flashを追加測定。今回240件を生成し、新版b11960で測定済みの6構成・720件と比較した。既存の測定結果と通常利用設定は保持した。</p><p>全構成で総コンテキスト65,536、1 slot、出力は最大64,000。入力をテンプレート展開・トークン化して予約出力が総枠を超えないよう調整した。同じ短い選択問題のテストであり、入力を64Kまで埋める長文読解試験ではない。</p><p class="note">* LFM2.5の埋め込みテンプレートにはenable_thinking切り替えがなく、常に&lt;think&gt;から始まる。OFFは新版ランタイムの--reasoning-budget 0（思考を即時終了）、ONは-1（出力上限内で無制限）で制御し、別サーバーで測定した。GLMは通常のテンプレート切り替えを使用。他の6構成のOFFも通常のテンプレート切り替えを用いた。各モードの実際の思考欄の有無を記録した。OFFでも最終回答欄で説明・推論する可能性がある。</p>'''
syntax_count=sum(e.get('failure_kind')=='syntax_error' for e in r['models']['lfm']['human_eval']['off'])
example='例えばHumanEval/6ではPythonの代わりに、提供していないwrite_todosツールへの呼び出し文字列を返した。' if any(e['task_id']=='HumanEval/6' and 'write_todos' in e['content'] for e in r['models']['lfm']['human_eval']['off']) else ''
doc+='<p>LFM2.5のOFFでは共通の正規化後の構文エラーが'+str(syntax_count)+'件あった。'+example+'強制OFF時の指示遵守・応答形式も含む結果として扱い、純粋な問題解法の能力だけには帰属しない。</p>'
doc+='<h2>正解数</h2>'+scores+'<h2>BFCLの内訳</h2>'+categories+'<h2>出力量と打ち切り</h2>'+budgets+reason+'<h2>所要時間・生成速度・メモリ</h2>'+perf
if audits:
    doc+='<h2>採点器の許可範囲に関する補助再採点</h2><p>元の点数を保持し、type()とoperator.mul/addだけを追加許可して保存済み回答を再採点した。再生成はしていない。</p>'+table(['モデル','OFF 元→補助','ON 元→補助'],[[labels[k],str(audits[k]['off']['original_passed'])+' → '+str(audits[k]['off']['secondary_passed']),str(audits[k]['on']['original_passed'])+' → '+str(audits[k]['on']['secondary_passed'])] for k in [m['key'] for m in models]])
doc+='''<h2>測定条件と比較の範囲</h2><ul><li>HumanEvalは前回と同じ20問、temperature 0.6、top_p 0.95、top_k 20、seed 42、同じコード正規化とWindows制限付き採点器。BFCLは同じ80問、temperature 0、思考OFF、元のメッセージとツール定義、固定した公式AST採点器。関数は実行していない。</li><li>LFM2.5はOFFをまとめて測定した後ONを測定。GLMと保存済み6構成は問題ごとにOFF/ONの順序を交替。各条件1回答で、最適化したモデル別サンプリングや統計的反復ではない。</li><li>LFM2.5はCPUに最初の24層のMoE重み、GLMは35層、Qwen 35Bは30層を置く。LFM2.5の生成スレッド数は既存の調整済み6、他は8。トークナイザーや量子化も異なる。速度差をモデル規模・ランタイムだけに帰属しない。</li><li>メモリは準備完了後の定期サンプルで、起動時や瞬間的なピークを保証しない。LFM2.5のメモリ集計はOFF/ONと再開前の測定窓を含む。</li><li>旧版でのこの2モデルの記録は独自エージェント課題・ログ速度測定。同じHumanEval/BFCLの旧版スコアはないため、ランタイム更新による正解率の改善量は算出していない。</li><li>LFM3 Text/VLは学習方法も異なる。QAD量子化には追加蒸留も含まれる。この少数のコード・ツール課題を一般的な言語能力、画像能力やHermes統合の順位にはしない。</li></ul><p>採点補助環境の不足を修正する前に生成した最初の回答は、そのまま回収・採点した。生成条件・採点関数は変更していない。履歴とソース版はresults.jsonとsources.zipに記録した。</p><p><a href="results.json">今回の全結果</a> / <a href="summary.json">8構成集計</a> / <a href="sources.zip">ソース</a></p></html>'''
(run/'report.html').write_text(doc,encoding='utf-8')
print(json.dumps({'report':str(run/'report.html'),'new_models':[{'model':m['model'],'off':m['human_eval']['off']['passed'],'on':m['human_eval']['on']['passed'],'bfcl':m['bfcl']['passed']} for m in models if m['origin']=='new']},ensure_ascii=False))
