"""Secondary sensitivity check; keeps all original scores and generation intact."""
import ast,ctypes,json,pathlib,subprocess,sys
from ctypes import wintypes as w
from pathlib import Path
from install_lfm3_runtime import save,sha256
root=Path(r'C:\LocalLLM');run=Path(sys.argv[1]);bench=root/'hermes/benchmarks'
r=json.loads((run/'results.json').read_text(encoding='utf-8'))
assert 'error' not in r and len(r['models'])==6
audit=run/'grader-sensitivity';audit.mkdir(exist_ok=True)
original=(bench/'grade_worker.py').read_text(encoding='utf-8')
# Only these conventional pure-Python operations are added. The original AST,
# file/process/network restrictions and Windows job limits remain in force.
worker=original.replace("MODULES={'math'","MODULES={'operator','math'",1)
worker=worker.replace("ATTRS=set(","ATTRS={'mul'} | set(",1)
worker=worker.replace("SAFE=set(","SAFE={'type'} | set(",1)
worker=worker.replace("    return builtins.__import__", "    if name=='operator' and any(n not in {'mul','add'} for n in fromlist): raise ValueError('Unsupported operator import')\n    return builtins.__import__",1)
worker=worker.replace("        if isinstance(node,ast.ImportFrom):", "        if isinstance(node,ast.ImportFrom):\n            if node.module=='operator' and any(a.name not in {'mul','add'} for a in node.names): raise ValueError('Unsupported operator import')",1)
(audit/'grade_worker.py').write_text(worker,encoding='utf-8')
ns={'ctypes':ctypes,'w':w,'subprocess':subprocess,'sys':sys,'BENCH':audit,'json':json}
source=(bench/'compare_models.py').read_text(encoding='utf-8')
exec(compile(source[source.index('class BasicLimits'):source.index('\ndef canonical_selfcheck')],'same_windows_job_grader.py','exec'),ns)
import gzip,random
data=[json.loads(x) for x in gzip.decompress((bench/'HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
problems={p['task_id']:p for p in data}
canonical=[{'id':pid,**ns['grade'](problems[pid]['prompt']+problems[pid]['canonical_solution'],problems[pid])} for pid in r['human_eval_ids']]
assert all(c['passed'] for c in canonical)
he=json.loads(Path(r['human_eval_reference']).read_text(encoding='utf-8'))
models={k:m['human_eval'] for k,m in r['models'].items()}
# All six models are freshly measured in this run; no historical answers added.
out={'purpose':'Sensitivity only, not a replacement for original scores. Adds type() and operator.mul/add support to every saved model condition. No new generations.','original_worker_sha256':sha256(bench/'grade_worker.py'),'secondary_worker_sha256':sha256(audit/'grade_worker.py'),'canonical':canonical,'models':{}}
for name,modes in models.items():
    out['models'][name]={}
    for mode,entries in modes.items():
        assert len(entries)==20
        results=[]
        for e in entries:
            if e['passed']:result={'passed':True,'status':'original_pass_retained'}
            elif e.get('code','').strip():result=ns['grade'](e['code'],problems[e['task_id']])
            else:result={'passed':False,'status':'no_final_code'}
            results.append({'task_id':e['task_id'],'original_passed':e['passed'],'secondary':result,'original_grade':e.get('grade')})
        out['models'][name][mode]={'original_passed':sum(e['passed'] for e in entries),'secondary_passed':sum(e['secondary']['passed'] for e in results),'rescued_ids':[e['task_id'] for e in results if not e['original_passed'] and e['secondary']['passed']],'cases':results}
save(audit/'results.json',out)
print(json.dumps({'sensitivity':{k:{mode:{field:v[field] for field in ['original_passed','secondary_passed','rescued_ids']} for mode,v in modes.items()} for k,modes in out['models'].items()}}))
