"""Offline audit of cited-URL exposure using preserved search/read events."""
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(pathlib.Path(__file__).parent)]
from local_llm_benchmarks import study
from page_harness import audit_citations

def audit(run_id):
    run=study.resolve_run(run_id);assert study.validate_run(run)['status']=='complete'
    cases=[]
    for d in sorted((run/'raw').iterdir()):
        if not d.is_dir() or not (d/'result.json').exists():continue
        result=study.load(d/'result.json');events=study.load(d/'events.json');pages={p.stem:study.load(p) for p in (d/'pages').glob('*.json')}
        allowed={r['url'] for x in events if x.get('type')=='tool' and x.get('name')=='search' for r in x.get('result',{}).get('results',[]) if isinstance(r.get('url'),str)}
        reads={x['arguments']['page_id'] for x in events if x.get('type')=='tool' and (x.get('name')=='read_page' or (x.get('name')=='find_in_page' and x.get('result',{}).get('matches'))) and x.get('arguments',{}).get('page_id') in pages}
        report=audit_citations(result.get('answer',''),pages,reads,allowed)
        cases.append({'id':d.name,'status':result.get('status'),'answer':result.get('answer',''),'opened_pages':len(pages),'pages_with_exposed_passages':len(reads),'audit':report})
    out={'scope':'Offline URL-exposure audit; no claim, quote or section verification. Original model results are unchanged.','audit_code_sha256':study.sha(pathlib.Path(__file__).with_name('page_harness.py')),'cases':cases}
    target=run/'summaries/citation-exposure-audit-v2.json'
    if target.exists():raise FileExistsError('preserve previous audit')
    study.save(target,out);print(run_id,'cases',len(cases),'URL warnings',sum(bool(x['audit']['warnings']) for x in cases))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);audit(p.parse_args().run)
