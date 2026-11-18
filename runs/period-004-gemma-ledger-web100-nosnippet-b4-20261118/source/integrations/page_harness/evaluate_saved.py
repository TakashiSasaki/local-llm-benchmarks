"""Read-only f7 answer-string check for a selected completed/incomplete pilot."""
import argparse, importlib.util, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks import study
BFCL=ROOT/'.local/official-bfcl-f7cf735/berkeley-function-call-leaderboard/bfcl_eval'
BASE=ROOT/'runs/period-004-bfcl-searxng-gemma-thinking-on-all-gpu-r2-20261117/raw/category-scores/local-gemma4-f7-prompt/agentic/BFCL_v4_web_search_no_snippet_score.json'

def evaluate(run_id):
    run=study.resolve_run(run_id);assert study.validate_run(run)['status']=='complete'
    plan=study.load(run/'configs/cases.json')['cases'];goldpath=BFCL/'data/possible_answer/BFCL_v4_web_search.json'
    expected=study.load(ROOT/'experiments/period-004/configs/page-harness-12-case-20261118.json')
    assert study.sha(goldpath)==expected['answer_file_sha256'],'gold file mismatch'
    gold={o['id']:o['ground_truth'] for o in map(json.loads,goldpath.read_text(encoding='utf-8').splitlines())}
    records=[json.loads(line) for line in BASE.read_text(encoding='utf-8').splitlines() if line.strip()];header=records[0]
    assert header['correct_count']==21 and header['total_count']==100 and len(records)-1==79
    old_failed={x['id']:x for x in records[1:]};assert len(old_failed)==79
    checker=BFCL/'eval_checker/agentic_eval/agentic_checker.py';spec=importlib.util.spec_from_file_location('pinned_agentic_checker',checker);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    output=[]
    for case,question in plan:
        assert case in gold
        resultfile=run/'raw'/case/'result.json';result=study.load(resultfile) if resultfile.exists() else {'status':'missing'}
        status=result.get('status');answer=result.get('answer','');checked=module.agentic_checker(answer,gold[case]) if status=='complete' and answer else None
        old_id=case.replace('web_search_','web_search_no_snippet_',1);old=old_failed.get(old_id)
        output.append({'id':case,'status':status,'gold':gold[case],'answer':answer,'gold_string_match':checked['valid'] if checked else None,'baseline_valid':not bool(old),'baseline_error_type':old.get('error',{}).get('error_type') if old else None,'citation_warning':result.get('citation_warning'),'read_page_urls_cited':result.get('read_page_urls_cited',[]),'page_count':result.get('page_count',0),'counts':result.get('counts',{}),'compactions':result.get('compactions',0)})
    total=len(output);scored=[x for x in output if x['gold_string_match'] is not None];matched=sum(x['gold_string_match'] for x in scored)
    summary={'scope':'Selected BFCL-derived questions; raw f7 answer-string checker only. NOT official BFCL score; harness, prompting, MTP, page source and sampling differ.', 'checker_sha256':study.sha(checker),'gold_sha256':study.sha(goldpath),'planned':total,'completed_and_scored':len(scored),'matched':matched,'unscored':total-len(scored),'baseline_matched_on_same_scored_cases':sum(x['baseline_valid'] for x in scored),'cases':output}
    target=run/'summaries/answer-string-comparison.json'
    if target.exists():raise FileExistsError('preserve existing comparison')
    study.save(target,summary);print(json.dumps({k:v for k,v in summary.items() if k!='cases'},ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);evaluate(p.parse_args().run)
