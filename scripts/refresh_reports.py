"""Build the static run catalog; each completed experiment keeps its own report."""
import html,json,pathlib,os,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,validate_run
def relative(target,base):return os.path.relpath(target,base).replace('\\','/')
def refresh():
    rows=[]
    for folder in sorted((ROOT/'runs').iterdir(),reverse=True):
        if not folder.is_dir() or not(folder/'manifest.json').exists():continue
        manifest=validate_run(folder);summary=load(folder/'summary.json') if (folder/'summary.json').exists() else {}
        if manifest['kind']=='replay':continue
        if manifest.get('report'):report=ROOT/manifest['report']
        else:
            report=ROOT/'reports'/folder.name/'index.html';report.parent.mkdir(parents=True,exist_ok=True)
            files=[p for p in folder.rglob('*') if p.is_file() and 'source' not in p.relative_to(folder).parts]
            body='<h1>'+html.escape(manifest['title'])+'</h1><p>'+html.escape(manifest['status'])+'</p><h2>Summary</h2><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre><h2>Evidence</h2><ul>'+''.join('<li><a href="'+relative(p,report.parent)+'">'+html.escape(p.relative_to(folder).as_posix())+'</a></li>' for p in files)+'</ul>'
            report.write_text('<!doctype html><meta charset="utf-8"><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:16px}pre{white-space:pre-wrap}</style>'+body,encoding='utf-8')
        rows.append((manifest,summary,report))
    for output in [ROOT/'index.html',ROOT/'reports/index.html']:
        output.parent.mkdir(parents=True,exist_ok=True)
        content='<h1>local-llm-benchmarks</h1><p>ローカルLLM測定の実行記録・スクリプト・結果。</p><div class="table-scroll"><table><thead><tr><th>Run</th><th>Benchmark</th><th>Status</th><th>Summary</th></tr></thead><tbody>'
        for m,s,p in rows:
            score=(str(s['passed'])+'/'+str(s['attempted'])) if 'passed' in s else (str(s['conditions'])+' conditions / '+str(s['answers'])+' answers') if 'conditions' in s else '—'
            content+='<tr><td><a href="'+relative(p,output.parent)+'">'+html.escape(m['title'])+'</a><br><small>'+html.escape(m['run_id'])+'</small></td><td>'+html.escape(m['benchmark'])+'</td><td>'+html.escape(m['status'])+'</td><td>'+html.escape(score)+'</td></tr>'
        content+='</tbody></table></div><p><a href="'+relative(ROOT/'README.md',output.parent)+'">README</a> · <a href="'+relative(ROOT/'docs/WORKFLOW.md',output.parent)+'">追加測定の手順</a></p>'
        output.write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Local LLM benchmark runs</title><style>body{font:16px/1.6 system-ui;max-width:1200px;margin:40px auto;padding:20px}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:580px}td,th{text-align:left;border-bottom:1px solid #ccc;padding:14px}small{color:#555}a{color:#176c65}</style>'+content+'</html>',encoding='utf-8')
    print(json.dumps({'catalog_runs':len(rows)}))
if __name__=='__main__':refresh()
