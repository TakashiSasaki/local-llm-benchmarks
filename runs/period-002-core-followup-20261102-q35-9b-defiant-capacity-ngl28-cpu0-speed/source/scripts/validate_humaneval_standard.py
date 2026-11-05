"""Pin standard-test Windows policy with canonical and discrimination controls."""
import argparse,gzip,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,snapshot_sources,load,save,now
from local_llm_benchmarks.humaneval_standard_windows import grade,provenance

def validate(run_id):
    path=create_run('Period 002 HumanEval standard-test Windows adapter validation','grader-validation',run_id=run_id,kind='replay',config={'policy':provenance(),'inference_answers':0})
    snapshot_sources(path);manifest=load(path/'manifest.json');manifest.update(status='running',started_at=now());save(path/'manifest.json',manifest)
    try:
        rows=[json.loads(s) for s in gzip.decompress((ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
        controls=[{'id':p['task_id'],**grade(p['prompt']+p['canonical_solution'],p)} for p in rows]
        save(path/'summaries/canonical.json',controls)
        assert len(controls)==164 and all(c['passed'] for c in controls),'Canonical implementation failure'
        problem={'task_id':'policy/control','prompt':'','test':'def check(candidate):\n    assert candidate([2,3,4]) == 24','entry_point':'f'}
        samples=[('type-and-operator','import operator\nimport functools\ndef f(a):\n    assert type(a) is list\n    return functools.reduce(operator.mul,a,1)',True),('wrong-answer','def f(a): return 0',False),('nonterminating','def f(a):\n    while True: pass',False)]
        checks=[{'name':name,'expected_pass':expected,**grade(code,problem)} for name,code,expected in samples]
        save(path/'summaries/discrimination.json',checks)
        assert all(c['passed']==c['expected_pass'] for c in checks)
        assert checks[-1]['status']=='timeout'
        save(path/'summary.json',{'outcome':'passed','canonical_passed':164,'canonical_expected':164,'discrimination_controls':checks,'policy':provenance(),'inference_answers':0})
        manifest.update(status='complete',completed_at=now())
    except BaseException as error:manifest.update(status='failed',completed_at=now(),error=repr(error));raise
    finally:save(path/'manifest.json',manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);args=parser.parse_args();validate(args.id)
