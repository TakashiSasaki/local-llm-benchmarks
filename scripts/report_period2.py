"""Render the period-002 saved-evidence comparison, without refreshing period 001."""
import html,json,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save

DEST=ROOT/'experiments/period-002/reports'
LABELS={'q35-4b-base':'通常 Qwen3.5-4B','q35-4b-abliterix':'Abliterix4B','q35-9b-base':'通常 Qwen3.5-9B','q35-9b-huihui':'Huihui9B','q35-9b-heretic':'Heretic9B','q35-9b-defiant':'Defiant9B','q36-35b-base':'通常 Qwen3.6-35B-A3B','q36-35b-huihui':'Huihui35B-A3B'}

def inline(text):
    text=html.escape(text)
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',text)
    return re.sub(r'`([^`]+)`',r'<code>\1</code>',text)

def render():
    d=load(DEST/'comparison.json');rows=d['conditions'];index={(r['model'],r['suite'],r['thinking']):r for r in rows}
    lines=['# 第2期 主比較 — 保存済み部分結果','',
        '2026-11-06監査。測定停止中、期はopen。**588/1,600回答を保存、未収集1,012回答**。11条件完了・1条件部分収集・20条件未実施。速度probe、smoke、採点replayを新規能力回答に含めません。','',
        '| 配布物（すべてQ4_K_M、MTP OFF） | BFCL OFF | BFCL ON | HumanEval OFF | HumanEval ON |',
        '| --- | ---: | ---: | ---: | ---: |']
    for key,label in LABELS.items():
        cells=[]
        for suite,mode in [('bfcl','off'),('bfcl','on'),('humaneval','off'),('humaneval','on')]:
            r=index.get((key,suite,mode));cells.append('未実施' if r is None else f"{r['passed_saved']}/{r['saved']}"+(f"（部分・残り{r['uncollected']}）" if r['uncollected'] else ''))
        lines.append('| '+label+' | '+' | '.join(cells)+' |')
    lines+=['','通常9B HE ONの7/8は保存済み8問の得点です。20問の完了得点にも、残り12問を不正解にした7/20にも換算しません。親/条件manifestのfailedは実行制限によるdeferred（model_failure=false）です。','',
        '## 出力・時間・形式','',
        'capはfinish_reason=lengthかつ要求出力数まで到達した回答。空finalはcontentもtool_callsも空の回答。BFCLの無呼び出し正解は実ツール実行成功とは異なります。秒数は保存済み回答のAPI待機時間合計、decode速度は保存されたAPI decode時間で重み付けした値で、短文probeとは別です。','',
        '| 配布物 | 条件 | 保存/予定 | cap | 空final | decode形式エラー | API合計秒 | decode tok/s | legacy HE replay |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        replay='—' if r['legacy_replay_passed'] is None else str(r['legacy_replay_passed'])+'/'+str(r['saved'])
        lines.append(f"| {LABELS[r['model']]} | {r['suite']} {r['thinking'].upper()} | {r['saved']}/{r['expected']} | {len(r['output_caps'])} | {r['empty_final_cases']} | {r['decode_error_cases']} | {r['total_api_seconds']:.1f} | {r['aggregate_decode_tps']:.2f} | {replay} |")
    lines+=['','通常4B HE ONで2問、Abliterix4B HE ONで1問がcapに到達。Abliterix HE ONの主得点17/20に対して、旧制限付きreplayは16/20です。通常9B HE ONのHumanEval/35はprompt130＋completion64,000、約6,763.7秒、no_final_code、不正解。出力上限でありAPI待機上限7,200秒やcontext65,536の不足ではありません。','',
        '## 速度probeとメモリ','',
        '速度は256 tokens×3 prompts×3回、思考OFFの中央値です。メモリは各モデルrun全体の約3秒間隔の標本で、GPUはシステム全体。条件ごとの瞬間最大値、共有GPUメモリ、連続した電力/温度/clockの統制は保証しません。','',
        '| 配布物 | 配置 | 短文decode tok/s | GPUピーク MiB | 最小空きRAM GiB | 標本数 |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for p in d['model_performance']:
        m=p['memory'];placement='全層 / CPU MoE0' if '4b' in p['model'] else '-ngl24 / CPU MoE0'
        lines.append(f"| {LABELS[p['model']]} | {placement} | {p['fixed256_median_decode_tps']:.2f} | {m['peak_gpu_used_mib_system_total']:.0f} | {m['minimum_available_ram_bytes']/1024**3:.2f} | {m['sample_count']} |")
    lines+=['','9B共通-ngl24は試した候補内で成立した配置です。b11960の-nglは出力層込みで、decoder層数とは異なります。Defiantは-ngl28で7,681 MiB、-ngl24で7,059 MiBを観測。未試験の25〜27を含む理論上の最大配置とは呼びません。','',
        '## 対応する問題の変化','',
        '| 比較 | 条件 | 改善（誤→正） | 悪化（正→誤） |',
        '| --- | --- | ---: | ---: |']
    pair_details=[]
    for suite in ['bfcl','humaneval']:
        for mode in ['off','on']:
            pair=[{c['id']:c for c in d['cases'] if c['model']==key and c['suite']==suite and c['thinking']==mode} for key in ['q35-4b-base','q35-4b-abliterix']]
            better=[cid for cid in pair[0] if not pair[0][cid]['passed'] and pair[1][cid]['passed']];worse=[cid for cid in pair[0] if pair[0][cid]['passed'] and not pair[1][cid]['passed']]
            lines.append(f'| 通常4B→Abliterix4B | {suite} {mode.upper()} | {len(better)} | {len(worse)} |')
            pair_details+=['',suite+' '+mode.upper()+' 改善: '+(', '.join(better) or 'なし')+'。悪化: '+(', '.join(worse) or 'なし')+'。','']
    lines+=pair_details
    lines+=['## 条件と解釈の限界','',
        'b11960 / commit8642541b255bfb5dc39cd351a178be09013a55d6、context65,536、F16 K/V、1 slot、MTP OFF、最大出力64,000、入力から32 tokens予約。BFCL固定80問・公式AST・greedy/seed42。HumanEval固定20問・temperature0.6/seed42と保存済みsampler。','',
        'HumanEval主採点はhumaneval-b9453e8-windows-full-module-v1。公式test/実行本体を固定し、Windows JobObject/親watchdog（6秒・256 MiB・1 process）に適応。測定用Python3.14.9でcanonical164/164と正解・誤答・無限ループcontrolを検証済み。今回の保存108回答のreplayも一致。EvalPlusや公式Linux環境と完全同一とは呼びません。JobObject/reliability_guardは一般的なOSセキュリティsandboxではありません。','',
        '4B対はchat template SHAが一致しますが、Q4_K/Q5_K/Q6_K構成が異なります。これは配布物同士の比較で、拒否方向除去だけの因果効果を示しません。固定少数問題・単一seedから一般的な順位、無検閲性、日本語/数学能力は推定しません。XSTest、数学、日本語、Hermes実接続、MTP ON、追加27Bは別枠の未実施計画です。','',
        '## 停止と継続','',
        '2026-11-02 18:00 JST頃にshutdown_requestedと元所有プロセス全終了の記録あり。実際の電源断時刻は未検証。2026-11-06監査時、古い監視・関連Windows予約・8089待受・測定writerはなし。古い監視設定はenabled=trueのまま残るため再起動禁止。停止フラグと過去期限を維持し、新しいshutdown予約は作成していません。','',
        '再開にはユーザー指示が必要です。既存588回答を維持し、通常9B HE ONの未実施12問を新run/subsetで取得して既存8問を参照集計し、Huihui/Heretic/Defiant9Bの600問、35B対の400問を続けます。旧run/sourceをresume・上書きしません。run_period2_remaining.pyの丸ごと再実行は通常9Bの完了条件を再測定するので禁止。','',
        '## 原証拠と再現','',
        '[機械可読比較・全問題判定・raw参照・SHA](comparison.json) · [監査と継続手順](../AUDIT.md) · [取得/環境監査](../environment/handoff-20261106.json) · [主採点の定義](../../../vendor/humaneval/b9453e8/README.md)','',
        '検証: `python -B -X utf8 tools/verify_period2.py --regrade --report experiments/period-002/reports/comparison.json`（測定用Python）。推論APIには接続せず、rawは読み取り専用です。第1期の原結果・inventory・frozen recipe・比較ページを変更していません。','']
    markdown='\n'.join(lines);(DEST/'comparison.md').write_text(markdown,encoding='utf-8')
    # Simple accessible HTML tables and paragraphs, with escaped text throughout.
    body=[];table=False
    for line in lines:
        if line.startswith('|'):
            if set(line.replace('|','').replace(' ','').replace(':','').replace('-',''))==set():continue
            if not table:body.append('<div class="scroll"><table>');table=True
            tag='th' if not body[-1].endswith('</tr>') else 'td'
            body.append('<tr>'+''.join('<'+tag+'>'+html.escape(x.strip())+'</'+tag+'>' for x in line.strip('|').split('|'))+'</tr>');continue
        if table:body.append('</table></div>');table=False
        if line.startswith('# '):body.append('<h1>'+html.escape(line[2:])+'</h1>')
        elif line.startswith('## '):body.append('<h2>'+html.escape(line[3:])+'</h2>')
        elif line:body.append('<p>'+inline(line)+'</p>')
    if table:body.append('</table></div>')
    links='<nav><a href="../README.md">第2期</a> · <a href="comparison.json">JSON・raw参照</a> · <a href="comparison.md">Markdown</a> · <a href="../AUDIT.md">監査・継続</a></nav>'
    (DEST/'index.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>第2期 保存済み比較</title><style>body{font:16px/1.7 system-ui;max-width:1200px;margin:24px auto;padding:20px;color:#18283b;background:#f7f9fc}table{border-collapse:collapse;background:white;width:100%;min-width:620px}th,td{padding:10px;border:1px solid #ccd5df;text-align:left}.scroll{overflow:auto}p{overflow-wrap:anywhere}a{color:#176c65}</style>'+links+''.join(body)+'</html>',encoding='utf-8')
    c=d['continuation'];plan={'schema_version':1,'period':'period-002','status':'prepared; blocked until explicit user resumption and a new execution window','grader_policy':'standard-windows-v1','thinking':'on','new_answer_count':12,'referenced_answer_count':8,'combined_expected':20,'model_sha256':load(ROOT/'experiments/period-002/models/q35-9b-base.json')['sha256'],**c}
    save(ROOT/'experiments/period-002/configs/q35-9b-he-on-continuation.json',plan)
    print(json.dumps({'comparison_rows':len(rows),'saved_answers':d['saved_answers'],'continuation_pending_ids':c['pending_ids']}))

if __name__=='__main__':render()
