"""Check historical Hermes artifacts and recorded tool results without running an agent."""
import argparse,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[3]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,sha,validate_run

def verify():
    export=load(ROOT/'publication/hermes-export-manifest.json')
    for item in export['entries']:assert sha(ROOT/item['path'])==item['exported_sha256'],item['path']
    folders=[p for p in (ROOT/'runs').iterdir() if p.is_dir() and (p/'manifest.json').exists() and load(p/'manifest.json').get('harness')=='hermes']
    for folder in folders:validate_run(folder)
    art=ROOT/'artifacts/local-llm';h=art/'hermes';w=art/'workspace/hermes'
    native=load(h/'runs/verification.json');inp=load(w/'validation-input.json');out=load(w/'validation-output.json')
    assert out==native['artifact_actual']==native['artifact_expected']=={'ticket':inp['ticket'],'total':sum(inp['amounts'])}
    # Preserve the failed oneshot terminal attempt as well as the successful resumed command.
    terminal=[x['result'] for x in native['tool_results'] if x['name']=='terminal']
    assert any(x.get('status')=='blocked' for x in terminal)
    assert any(x.get('exit_code')==0 and x.get('output','').strip()=='89' for x in terminal)
    large=load(h/'runs/large-hermes-20261029-133137/report.json')
    inp=load(w/'large-trial-20261029-133137/input.json');out=load(w/'large-trial-20261029-133137/output.json')
    assert out==large['artifact']==large['expected']
    assert (out['ticket'],out['count'],out['total'])==(inp['ticket'],len(inp['amounts']),sum(inp['amounts']))
    tools={x['tool_name']:x['result'] for x in large['tool_results']}
    assert inp['ticket'] in tools['read_file']['content']
    assert tools['terminal']['exit_code']==0 and tools['terminal']['output'].strip()==out['terminal_marker']
    assert tools['write_file']['verified'] and all(large['independent_checks'].values())
    context=load(h/'runs/context64k-20261029-195220/results.json')
    for model,m in context['models'].items():
        inp=load(w/'context64k-20261029-195220'/model/'input.json');out=load(w/'context64k-20261029-195220'/model/'output.json')
        assert out==m['hermes']['artifact']=={'ticket':inp['ticket'],'count':len(inp['amounts']),'total':sum(inp['amounts'])}
        results={t['tool_name']:json.loads(t['content']) for t in m['hermes']['tool_results']}
        assert inp['ticket'] in results['read_file']['content'] and results['write_file']['verified']
        assert all(m['hermes']['checks'].values()) and all(m['hermes']['independent_tool_checks'].values())
        assert m['hermes']['session']['model']==m['alias'] and m['hermes']['session']['billing_base_url']=='http://127.0.0.1:8089/v1'
    for suffix in ['140654','141429']:
        source=load(h/('benchmarks/comparison-20261029-'+suffix)/'results.json')
        summary=load(ROOT/('runs/20261029-hermes-tasks-'+suffix)/'summary.json')
        cases=[c for m in source['models'].values() for c in m['hermes']]
        assert summary['attempted']==len(cases) and summary['passed']==sum(c['passed'] for c in cases)
    mcp=load(h/'runs/mcp-verification.json');app=load(h/'runs/mcp-app-connection.json')
    assert len(mcp['tools'])==10 and all(not v.get('isError') for v in mcp['read_only_calls'].values())
    assert app['AppTransport']=='Failed: tunnel_client_not_seen'
    return {'passed':True,'supplemental_export_files_verified':len(export['entries']),'historical_hermes_runs_checked':len(folders),'artifact_roundtrips_checked':4,'local_mcp_stdio_record':'passed','app_mcp_transport_record':app['AppTransport'],'model_inference_performed':False,'hermes_started':False,'generated_code_executed':False,'note':'Evidence consistency checks; not fresh integration measurements or a claim that every recorded task passed.'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--report',type=pathlib.Path);args=ap.parse_args();result=verify()
    if args.report:save(args.report,result)
    print(json.dumps(result,ensure_ascii=False))
