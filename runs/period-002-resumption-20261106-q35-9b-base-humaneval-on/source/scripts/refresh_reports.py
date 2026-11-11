"""Build separate benchmark, harness, transport and capacity sections in one run catalog."""
import html,json,pathlib,os,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,validate_run,EXPERIMENT_TYPES
from local_llm_benchmarks.periods import membership,registry

LABELS={'benchmark':'モデル単体のベンチマーク','harness-integration':'Hermes等のエージェント動作検証','transport-integration':'MCP等の接続・通信検証','capacity':'コンテキスト容量と関連動作の検証'}
STYLE='body{font:16px/1.6 system-ui;max-width:1200px;margin:32px auto;padding:20px;color:#18283b;background:#f7f9fc}h1{font-size:1.8rem}h2{margin-top:2rem}section{background:white;border:1px solid #dce4ed;border-radius:12px;padding:16px;margin:16px 0}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:580px}td,th{text-align:left;border-bottom:1px solid #dce4ed;padding:12px;vertical-align:top}small{color:#556576}a{color:#176c65}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}li{overflow-wrap:anywhere}.note{color:#556576}code{overflow-wrap:anywhere}'
def esc(value):return html.escape(str(value))
def relative(target,base):return os.path.relpath(target,base).replace('\\','/')
def link(target,base,label):return '<a href="'+esc(relative(target,base))+'">'+esc(label)+'</a>'
def write_page(output,title,body):
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+STYLE+'</style>'+body+'</html>',encoding='utf-8')

def run_report(folder,m,summary):
    output=ROOT/'reports'/folder.name/'index.html'
    body='<p>'+link(ROOT/'index.html',output.parent,'測定・検証一覧へ')+'</p><h1>'+esc(m['title'])+'</h1>'
    body+='<p>'+esc(LABELS[m.get('experiment_type','benchmark')])+' / '+esc(m.get('harness') or 'direct API')+'</p>'
    body+='<p>収集状態: '+esc(m['status'])+' / 検証結果: '+esc(summary.get('outcome','see summary'))+'</p>'
    if summary.get('outcome')=='deferred':body+='<p><strong>停止指示・実行窓による保留。部分結果を保存し、モデル障害や完了0点として扱いません。</strong></p>'
    if m.get('notes'):body+='<p class="note">'+esc(m['notes'])+'</p>'
    body+='<section><h2>Summary</h2><pre>'+esc(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre></section>'
    body+='<details><summary>実験定義・使用モデル・時刻・出典</summary><pre>'+esc(json.dumps(m,ensure_ascii=False,indent=2))+'</pre></details>'
    files={p for p in folder.rglob('*') if p.is_file() and 'source' not in p.relative_to(folder).parts}
    files.update(ROOT/x['path'] for x in m.get('evidence',[]))
    body+='<section><h2>保存された証拠ファイル</h2><p>リクエスト、ログ、実ツール結果、入力・生成物、当時のスクリプト。過去の記録は再測定として扱いません。</p><ul>'
    body+=''.join('<li>'+link(p,output.parent,p.relative_to(ROOT).as_posix())+'</li>' for p in sorted(files))+'</ul></section>'
    write_page(output,m['title'],body)
    return output

def refresh():
    rows=[]
    for folder in sorted((ROOT/'runs').iterdir(),reverse=True):
        if not folder.is_dir() or not(folder/'manifest.json').exists():continue
        m=validate_run(folder);s=load(folder/'summary.json') if (folder/'summary.json').exists() else {}
        if m['kind']=='replay':continue
        period=membership(ROOT,m);periods=registry(ROOT)
        existing=ROOT/'reports'/folder.name/'index.html'
        report=ROOT/m['report'] if m.get('report') else existing if period and periods['periods'][period]['status']=='closed' and existing.exists() else run_report(folder,m,s)
        rows.append((m,s,report))
    for output in [ROOT/'index.html',ROOT/'reports/index.html']:
        period_page=ROOT/'experiments/period-001/report.html'
        body='<h1>local-llm-benchmarks</h1><p>モデルの性能比較から、Hermesを通した実ツール実行、MCP接続までの実験記録。</p><p>'+link(period_page if period_page.exists() else ROOT/'reports/comprehensive/index.html',output.parent,'第1期の横断比較（モデル・量子化・MTP・思考・配置）')+' · '+link(ROOT/'experiments/README.md',output.parent,'実験期の区分と再現記録')+'</p><p class="note">completeは記録の収集完了です。結果のpassed / partial / failedとは別です。BFCLの呼び出し採点と、Hermesによる実際のツール実行も別々に表示します。</p>'
        for typ in EXPERIMENT_TYPES:
            if typ==EXPERIMENT_TYPES[0] and (ROOT/'experiments/period-002/reports/index.html').exists():
                body+='<p>'+link(ROOT/'experiments/period-002/reports/index.html',output.parent,'第2期の主比較（保存回答・保留と未実施を区別）')+'</p>'
            group=[row for row in rows if row[0].get('experiment_type','benchmark')==typ]
            if not group:continue
            body+='<section><h2>'+esc(LABELS[typ])+'</h2><div class="table-scroll"><table><thead><tr><th>Run</th><th>Suite / Harness</th><th>収集状態 / 結果</th><th>Summary</th></tr></thead><tbody>'
            for m,s,p in group:
                score=s.get('headline') or (str(s['passed'])+'/'+str(s['attempted']) if 'passed' in s else str(s['conditions'])+' conditions / '+str(s['answers'])+' answers' if 'conditions' in s and 'answers' in s else str(s['capability_answers'])+' capability answers' if 'capability_answers' in s else '—')
                if s.get('outcome')=='deferred' and 'passed_saved' in s:score=str(s['passed_saved'])+'/'+str(s['attempted'])+' saved; '+str(s.get('expected','?'))+' planned; 部分収集'
                body+='<tr><td>'+link(p,output.parent,m['title'])+'<br><small>'+esc(m['run_id'])+' / '+esc(membership(ROOT,m) or 'legacy')+'</small></td><td>'+esc(m['benchmark'])+'<br><small>'+esc(m.get('harness') or 'direct API')+'</small></td><td>'+esc(m['status'])+'<br><strong>'+esc(s.get('outcome','see report'))+'</strong></td><td>'+esc(score)+'</td></tr>'
            body+='</tbody></table></div></section>'
        body+='<p>'+link(ROOT/'README.md',output.parent,'README')+' · '+link(ROOT/'docs/WORKFLOW.md',output.parent,'追加実験の手順')+' · '+link(ROOT/'integrations/hermes/README.md',output.parent,'Hermes検証の構成')+'</p>'
        write_page(output,'Local LLM benchmark and integration runs',body)
    print(json.dumps({'catalog_runs':len(rows),'experiment_types':{t:sum(m.get('experiment_type','benchmark')==t for m,_,_ in rows) for t in EXPERIMENT_TYPES}}))
if __name__=='__main__':refresh()
