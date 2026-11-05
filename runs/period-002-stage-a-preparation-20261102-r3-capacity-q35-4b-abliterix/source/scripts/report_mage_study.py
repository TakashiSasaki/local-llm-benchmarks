"""Separate completed scores, incomplete trials and deployment throughput in Mage reports."""
import csv,html,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save

def build():
    v=load(ROOT/'publication/mage-text-evidence-validation.json');assert v['passed']
    out=ROOT/'reports/20261031-mage-text-64k';out.mkdir(parents=True,exist_ok=True)
    gpu=load(ROOT/'runs/20261031-mage-q3-text-64k-gpu-placement/summary.json')
    bf=[next(r['summary'] for r in v['bfcl'] if r['run'].endswith('q3-off-bfcl-'+mode)) for mode in ['off','on']]
    speeds=[{'quantization':'Q4_K_M','ngl':20,'cpu_layers':17,'gpu_decoder_layers':19,'tok_s':next(r['median_tok_s'] for r in v['speed_checks'] if r['run']=='20261031-mage-q4-text-64k-parser-errors-mage-text-off-speed')},
            {'quantization':'Q3_K_M','ngl':20,'cpu_layers':17,'gpu_decoder_layers':19,'tok_s':gpu['baseline']['summary']['median_decode_tokens_per_second']},
            {'quantization':'Q3_K_M','ngl':23,'cpu_layers':14,'gpu_decoder_layers':22,'tok_s':gpu['selected_throughput']['speed']['median_decode_tokens_per_second']}]
    data={'collection_status':'incomplete','evidence_validation':'publication/mage-text-evidence-validation.json','q3_bfcl':bf,'q4_partial_bfcl':next(r for r in v['bfcl'] if 'parser-errors' in r['run']),'fixed_length_speed':speeds,'gpu_placement':gpu,'failures':v['failures'],'native_mtp':{'q4':'not attempted','q3':'unsupported: no MTP layers'},'humaneval_model_answers_saved':0}
    save(out/'results.json',data)
    with (out/'speed.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(speeds[0]));writer.writeheader();writer.writerows(speeds)
    esc=lambda x:html.escape(str(x))
    def table(identifier,headers,rows):return '<div class="scroll"><table id="'+identifier+'"><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    body='<a href="../../index.html">測定一覧</a><h1>Mage-VL-Cowork：テキスト評価とGPU配置</h1><p class="notice">全試行は終了しましたが、Q4・Q3ともに予定した200回答の能力試験は完了していません。Q3のBFCL160件と固定長速度・容量試験を評価できます。</p>'
    body+='<p>llama.cpp b11960-8642541b2 / CUDA12.4 · 65,536 context · 最大64,000出力 · F16 KV · 画像なし。公式active window 32,768を超える拡張条件で、64K長文理解やOSWorldの再現試験ではありません。</p><h2>能力試験</h2>'
    body+=table('capability',['配布物','BFCL 思考OFF','BFCL 思考ON','HumanEval 思考OFF','HumanEval 思考ON'],[['Q4_K_M','未完了：8件保存、うち7正解','未実施','未実施','未実施'],['Q3_K_M',str(bf[0]['passed'])+'/80',str(bf[1]['passed'])+'/80','1問目で通信タイムアウト。モデル回答は未保存','未実施']])
    body+='<p>呼び出しが必要な60問ではQ3 OFF 1問・ON 4問正解。不要な20問では18問・17問正解でした。BFCLは関数を実行せず公式ASTで採点します。汎用ツール形式に従えない出力が多く、量子化だけの影響とは断定できません。Q4の一部回答だけとQ3全80問を同等の正答率として比較しません。</p>'
    body+='<p>HTTP 500の出力形式拒否はQ3 OFF 3件・ON 6件で、失敗として数えています。出力の修正・再試行はせず、返らなかった生成トークン数・終了理由・思考状態は不明です。取得できた統計での出力上限到達は0件でした。</p><h2>固定長生成速度と配置</h2><p>同じ3プロンプト×3回、思考OFF・greedy・256トークン。予熱を除く中央値。出力層を-nglに含め、入力embeddingはCPUです。</p>'
    body+=table('speed',['配布物','-ngl','CPU decoder層','GPU decoder層＋出力','トークン/秒'],[[r['quantization'],r['ngl'],r['cpu_layers'],str(r['gpu_decoder_layers'])+'＋出力層',f"{r['tok_s']:.2f}"] for r in speeds])
    body+='<p>Q3はGPU decoder層を19→22、CPUを17→14へ変更し、固定長中央値が'+f"{(gpu['fixed_length_speedup']-1)*100:.1f}%"+'向上しました。短文での速度差で、数万トークン生成や正答率の改善は検証していません。</p><h2>GPU容量の確認</h2>'
    body+=table('capacity',['-ngl（出力込み）','GPU観測ピーク MiB','短い容量試験','512 MiB余裕の方針'],[[t['ngl_including_output'],t['memory']['peak_gpu_used_mib_system_total'],t['status'],'採用可能' if t['admissible'] else '余裕不足で不採用'] for t in gpu['trials']])
    body+='<p>-ngl23を選択。24も短い試験に成功しましたが、観測ピーク7,759 MiBで基準7,676 MiBを超えたため不採用。OOMとは扱いません。25・26は未実施です。観測GPU値はシステム全体で、将来の長時間・長入力時の余裕を保証しません。</p><h2>MTPと途中終了</h2><p>Q3はnative MTP指定で起動を試し、MTP層がないため拒否されました。Q4のMTP確認は先行試験の失敗で未実施です。非対応に能力得点や速度向上率は付けません。</p><ul>'
    for r in v['failures']:body+='<li>'+esc(r['child'])+'：2時間のAPIタイムアウト。最終観測'+str(r['last_observed_generated_tokens'])+'生成トークン。最終応答は未保存で、64,000出力上限やRAM保護による停止とは別です。</li>'
    body+='</ul><h2>証拠と比較範囲</h2><p>HumanEvalのcanonical control 20件は通りましたが、モデル回答のHumanEval得点・補助採点は取得できていません。全所有サーバーは停止済み。主得点・出力形式・短い速度・容量・失敗ログを分けて保存しています。</p><ul>'
    links=[('results.json','集計JSON'),('speed.csv','速度CSV'),('../../publication/mage-text-evidence-validation.json','独立照合結果'),('../../docs/MAGE_VL_COWORK.md','条件・経緯・制約'),('../20261031-mage-q3-text-64k/index.html','Q3条件別ページ'),('../20261031-mage-q4-text-64k-parser-errors/index.html','Q4途中終了ページ'),('../20261031-mage-q4-text-64k/index.html','Q4最初の形式エラー停止'),('../20261031-mage-q3-text-64k-gpu-placement/index.html','GPU配置の全記録'),('../20261031-q5-k-m-mtp-64k/index.html','先行Q5・Q4比較')]
    for url,label in links:body+='<li><a href="'+esc(url)+'">'+label+'</a></li>'
    body+='</ul>';style='body{font:16px/1.6 system-ui,sans-serif;background:#101825;color:#edf4ff;max-width:1200px;margin:32px auto;padding:0 20px}a{color:#8ad3ff}h1{font-size:1.8rem}h2{margin-top:2rem}table{border-collapse:collapse;width:100%;margin:20px 0}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #34445c;padding:12px}.scroll{overflow:auto}p,li{overflow-wrap:anywhere}.notice{border-left:4px solid #ffc475;background:#222d40;padding:16px}'
    (out/'index.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mageテキスト評価・配置・MTP</title><style>'+style+'</style>'+body+'</html>',encoding='utf-8')

if __name__=='__main__':build();print(json.dumps({'report':'reports/20261031-mage-text-64k/index.html','capability_collection':'incomplete'}))
