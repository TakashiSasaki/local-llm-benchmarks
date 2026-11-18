"""Replay saved failures with the study's already established secondary grader policy."""
import argparse,ctypes,gzip,json,pathlib,random,shutil,subprocess,sys
from ctypes import wintypes as w
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,sha,create_run,snapshot_sources,now

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);a=p.parse_args()
    source=ROOT/'artifacts/local-llm/runs/bench64k-output-20261030-141002/grader-sensitivity'
    baseline=load(source/'results.json');worker=source/'grade_worker.py';assert sha(worker)==baseline['secondary_worker_sha256']
    modelmeta=load(ROOT/'runs'/a.study/'manifest.json')['config']['model']
    audit=create_run(modelmeta['model']+' '+modelmeta['quantization']+' HumanEval grader policy sensitivity','humaneval-policy-audit',config={'source_study':a.study,'model':modelmeta,'policy':'Existing secondary policy adds type and operator.mul/add; primary scores are unchanged'},run_id=a.study+'-he-policy-audit',kind='replay')
    snapshot_sources(audit);shutil.copyfile(worker,audit/'grade_worker.py')
    bench=ROOT/'artifacts/local-llm/hermes/benchmarks';source_code=(bench/'compare_models.py').read_text(encoding='utf-8')
    scope={'ctypes':ctypes,'w':w,'subprocess':subprocess,'sys':sys,'json':json,'BENCH':audit}
    exec(compile(source_code[source_code.index('class BasicLimits'):source_code.index('\ndef canonical_selfcheck')],'same_windows_job_limits.py','exec'),scope)
    rows=[json.loads(x) for x in gzip.decompress((ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()];problems={p['task_id']:p for p in rows}
    ids=[rows[i]['task_id'] for i in sorted(random.Random(42).sample(range(164),20))]
    controls=[{'id':pid,**scope['grade'](problems[pid]['prompt']+problems[pid]['canonical_solution'],problems[pid])} for pid in ids];assert all(c['passed'] for c in controls)
    result={'purpose':'Secondary policy sensitivity only; not a replacement of primary scores. No new model inference. Previously passing results retained, saved failures re-executed under identical Windows limits.','worker_sha256':sha(audit/'grade_worker.py'),'python':sys.version,'canonical':controls,'iq3_m':{},'ud_q3_k_m':baseline['models']['qwen-large'],'baseline_reference':source.relative_to(ROOT).as_posix()+'/results.json'}
    for mode in ['off','on']:
        entries=load(ROOT/'runs'/(a.study+'-humaneval-'+mode)/'summaries/cases.json');checked=[]
        for e in entries:
            secondary={'passed':True,'status':'original_pass_retained'} if e['passed'] else scope['grade'](e['code'],problems[e['task_id']]) if e['code'] else {'passed':False,'status':'no_final_code'}
            checked.append({'task_id':e['task_id'],'original_passed':e['passed'],'secondary':secondary})
        result['iq3_m'][mode]={'original_passed':sum(e['passed'] for e in entries),'secondary_passed':sum(e['secondary']['passed'] for e in checked),'rescued_ids':[e['task_id'] for e in checked if not e['original_passed'] and e['secondary']['passed']],'cases':checked}
    result['model']=modelmeta
    save(audit/'summaries/results.json',result);save(audit/'summary.json',{'outcome':'complete','model':modelmeta['model'],'headline':'Secondary HumanEval grader audit; saved outputs, no new inference','iq3_m':{k:{f:v[f] for f in ['original_passed','secondary_passed','rescued_ids']} for k,v in result['iq3_m'].items()},'ud_q3_k_m':{k:{f:v[f] for f in ['original_passed','secondary_passed','rescued_ids']} for k,v in result['ud_q3_k_m'].items()}})
    manifest=load(audit/'manifest.json');manifest.update(status='complete',completed_at=now());save(audit/'manifest.json',manifest)
    print(json.dumps(load(audit/'summary.json')))
