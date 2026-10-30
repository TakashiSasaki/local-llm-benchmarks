"""Render matched-budget thinking comparison without exposing reasoning traces in the page."""
import html
import json
from pathlib import Path
import statistics
import sys

run=Path(sys.argv[1]);report=json.loads((run/'results.json').read_text(encoding='utf-8'))
esc=lambda v:html.escape(str(v))
names={'daily':'Qwen3.5-4B Q4_K_M','large':'Qwen3.6-35B-A3B UD-Q3_K_M'}
rows=[]
for profile,model in report['models'].items():
    for mode,entries in model['modes'].items():
        summary=model['summary'][mode]
        timings=[r['timings'] for r in entries if r.get('timings')]
        n=sum(t.get('predicted_n',0) for t in timings);ms=sum(t.get('predicted_ms',0) for t in timings)
        summary['generation_tokens_per_second']=round(n/ms*1000,2) if ms else None
        summary['total_completion_tokens_reported']=sum(r.get('usage',{}).get('completion_tokens',0) for r in entries if r.get('usage'))
        summary['median_reasoning_characters']=round(statistics.median(r.get('reasoning_characters',0) for r in entries),1) if entries else None
        rows.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [names[profile],mode.upper(),f"{summary['passed']}/{summary['attempted']}",summary['median_seconds'],summary['total_seconds'],summary['total_completion_tokens_reported'],summary['output_cap_hits'],summary['no_final_code'],f"{summary['reasoning_observed_cases']}/{summary['attempted']}"] )+'</tr>')
    off={r['task_id']:r for r in model['modes']['off']};on={r['task_id']:r for r in model['modes']['on']}
    shared=off.keys()&on.keys()
    model['paired']={'both_pass':sum(off[k]['passed'] and on[k]['passed'] for k in shared),'on_only_pass':sum(on[k]['passed'] and not off[k]['passed'] for k in shared),'off_only_pass':sum(off[k]['passed'] and not on[k]['passed'] for k in shared),'both_fail':sum(not off[k]['passed'] and not on[k]['passed'] for k in shared)}
(run/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
parts=['<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HumanEval 思考ON/OFF比較</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1300px;margin:40px auto;padding:0 24px;background:#f5f7fa;color:#18212b}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}th,td{border-bottom:1px solid #dce2e8;padding:10px;text-align:left}th{background:#e6edf5}.scroll{overflow:auto}details{padding:12px;background:white;border-radius:6px;margin:8px 0}pre{white-space:pre-wrap;background:#17212b;color:#eaf0f8;padding:16px;overflow:auto}.pass{color:#147347}.fail{color:#a52d33}</style><h1>HumanEval：思考ON/OFFの比較</h1><p>前回と同じ20問。今回は思考ONとOFFの両方を4096出力トークン上限で測定しました。各条件1回の抜粋試験で、公式フル版スコアではありません。</p><div class="scroll"><table><tr><th>構成</th><th>思考</th><th>正解</th><th>応答中央値 秒</th><th>20問合計 秒</th><th>総出力token（API値）</th><th>出力上限</th><th>最終コード前に枠切れ</th><th>思考内容の返却を確認</th></tr>'+''.join(rows)+'</table></div>']
if report.get('error'):parts.append('<p>実行は未完了です：'+esc(report['error'])+'</p>')
parts.append('<p>この4096トークン上限では、35Bは思考ONで17問から19問へ改善しました。4Bは14問から6問へ低下し、ONの12問は最終コード前に出力枠を使い切りました。4Bの思考能力そのものが低いと断定できる試験ではなく、より大きい出力枠や思考枠の制御は未検証です。</p>')
parts.append('<p>採点器の制限による不合格も別に数えています。4B OFFのHumanEval/129はsys、35B OFFのHumanEval/8はoperatorのimportで拒否されました。後者は通常のsum/product実装なので、17→19問という差には採点器の許可リストによる影響も含まれます。採点器は条件間で変更していません。問題別のguard_rejected・syntax_error・failed・budget_exhausted_before_final_codeを区別して参照してください。</p>')
parts.append('<h2>条件・読み方</h2><ul><li>データ・問題・プロンプト・採点器は前回と同じ。temperature 0.6、top_p 0.95、top_k 20、presence_penalty 0、seed 42。両モデルの公式カードにある精密コーディング向け推奨値に統一し、同一モデル内では思考切り替え以外の生成条件を統一。OFF→ONとON→OFFを問題ごとに交互に実行。</li><li>モデル順は4B→35B。各モデルの64K設定は維持していますが、64K長文を埋める試験ではありません。</li><li>思考ON/OFFは各モデルの事前確認で、reasoning_contentが実際に返る／返らないことを照合。サーバー起動時だけLLAMA_ARG_THINK=deepseekを指定し、思考内容と最終コードを分離しました。保存済みの通常プロファイル・既定モデルは変更していません。</li><li>思考に使う分も総出力上限を消費します。最終回答がない場合に思考途中のコードを答えとして採点することはしていません。</li><li>APIが思考トークン数を提供しない場合は不明とし、文字数から推測していません。「思考内容の返却」はその文字列が非空だった件数です。</li><li>前回のOFFはtemperature 0・1024上限でした。今回とはサンプリングと上限が違うため、ONの効果比較は今回のOFF・4096・temperature 0.6を基準にします。前回の結果は変更していません。</li><li>公式テストを使う既存の制限付きPython採点器で、20問の公式解答が通ることを事前に確認。Windows Jobの256MiB上限、1プロセス、6秒制限、構文・import等の制限があります。</li><li>モデル世代・量子化・CPU/GPU配置が異なるため、モデルサイズだけの効果ではありません。小規模・各1回なので一般的な優劣や再現性は未確定です。</li></ul>')
parts.append('<h2>途中の試験と条件変更</h2><p>最初にtemperature 0で実施した予備試験は、4Bの思考ONで8問中6問が最終コード前に出力上限へ到達したため中断しました。両モデルの公式モデルカードを確認し、精密コーディング向け推奨サンプリングに統一して全20問・両モードを最初から再測定しました。予備試験の部分結果は最終スコアに混ぜていません。予備試験の記録はthinking-comparison-20261029-173548に保存しています。</p><h2>過去のOFF・1024上限（参考のみ）</h2><table><tr><th>構成</th><th>正解</th><th>中央値 秒</th></tr>')
old=json.loads(Path(report['previous_1024_reference']).read_text(encoding='utf-8'))
for profile,m in old['models'].items():
    s=m['summary'];parts.append('<tr><td>'+esc(names[profile])+'</td><td>'+esc(f"{s['humaneval_passed']}/{s['humaneval_attempted']}")+'</td><td>'+esc(s['humaneval_median_seconds'])+'</td></tr>')
parts.append('</table><h2>メモリの観測</h2><table><tr><th>構成</th><th>最小空きRAM GiB</th><th>最大システムGPU MiB</th></tr>')
for profile,m in report['models'].items():parts.append('<tr><td>'+esc(names[profile])+'</td><td>'+esc(m['minimum_available_ram_gib'])+'</td><td>'+esc(m['maximum_system_gpu_mib'])+'</td></tr>')
parts.append('</table><p>定期採取値で、モデル単体の割り当て量や厳密なピークではありません。</p><h2>問題別の結果</h2><div class="scroll"><table><tr><th>問題</th><th>4B OFF</th><th>4B ON</th><th>35B OFF</th><th>35B ON</th></tr>')
for task_id in report['task_ids']:
    cells=[]
    for profile in ['daily','large']:
        for mode in ['off','on']:
            entry=next((r for r in report['models'].get(profile,{}).get('modes',{}).get(mode,[]) if r['task_id']==task_id),None)
            if entry is None:cells.append('<td>未実施</td>');continue
            text=('合格' if entry['passed'] else '不合格')+f" / {entry['seconds']}秒"
            if entry.get('finish_reason')=='length':text+=' / 上限到達'
            if entry.get('failure_kind'):text+=' / '+entry['failure_kind']
            cells.append('<td class="'+('pass' if entry['passed'] else 'fail')+'">'+esc(text)+'</td>')
    parts.append('<tr><td>'+esc(task_id)+'</td>'+''.join(cells)+'</tr>')
parts.append('</table></div><h2>失敗した最終コード</h2>')
for profile,m in report['models'].items():
    for mode,entries in m['modes'].items():
        for r in entries:
            if not r['passed']:parts.append('<details><summary>'+esc(names[profile]+' '+mode.upper()+' '+r['task_id'])+'</summary><p>'+esc(r.get('failure_kind'))+'</p><p>'+esc(r.get('grade',{}))+'</p><pre>'+esc(r.get('code',''))+'</pre></details>')
parts.append('<h2>推奨サンプリングの一次資料</h2><p><a href="https://huggingface.co/Qwen/Qwen3.5-4B">Qwen3.5-4B</a> / <a href="https://huggingface.co/Qwen/Qwen3.6-35B-A3B">Qwen3.6-35B-A3B</a>。両カードの精密コーディング用の共通値を使用。ON/OFFそれぞれを別々に最適化した比較ではありません。</p><h2>再現情報</h2><p>HumanEval commit: '+esc(report['dataset_commit'])+'<br>dataset SHA256: '+esc(report['dataset_sha256'])+'</p><p>選択seed 42。詳細設定・応答・生成統計・メモリ記録は <a href="results.json">results.json</a> と同じフォルダーに保存。思考本文はこのページには表示していません。</p></html>')
(run/'report.html').write_text(''.join(parts),encoding='utf-8')
print(json.dumps({'report':str(run/'report.html'),'models':{k:{'summary':m['summary'],'paired':m['paired'],'min_ram':m['minimum_available_ram_gib'],'max_gpu':m['maximum_system_gpu_mib']} for k,m in report['models'].items()}},ensure_ascii=False))
