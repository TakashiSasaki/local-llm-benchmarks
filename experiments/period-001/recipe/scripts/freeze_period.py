"""Two-stage study closure. Freeze membership/recipes, then seal evidence after QA.

Does not move historical run files or include external weights/runtimes.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.study import ROOT, load, save, now

PERIOD='period-001'
TAG='period-001-2026-11-01-r1'
FOLDER=ROOT/'experiments'/PERIOD


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    assert not (FOLDER/'manifest.json').exists(), 'Already prepared; do not overwrite a closed period'
    assert not (ROOT/'experiments/registry.json').exists(), 'Initial closure only'
    environment=json.loads((FOLDER/'environment.json').read_text(encoding='utf-8-sig'))
    assert not environment['active_model_processes'], 'Model process still active'
    assets=load(FOLDER/'assets.json')
    runs=[]
    for p in sorted((ROOT/'runs').glob('*/manifest.json')):
        m=load(p);assert m['status'] in ['complete','failed'], p.parent.name
        runs.append({'run_id':p.parent.name,'status':m['status'],'benchmark':m['benchmark'],'kind':m['kind'],'manifest_sha256':digest(p)})
    save(FOLDER/'runs.json',{'period':PERIOD,'run_ids':[r['run_id'] for r in runs],'runs':runs,'rule':'Membership index preserves original run bytes and paths; future measurements require a different period.'})
    files=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    recipe_folders={'benchmarks','src','scripts','tools','tests','configs','integrations','docs'}
    for rel in sorted(set(files)):
        p=ROOT/rel
        if not rel or not p.is_file() or pathlib.PurePosixPath(rel).parts[0] not in recipe_folders:continue
        target=FOLDER/'recipe'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    for m in assets['models']:
        save(FOLDER/'models'/(m['filename']+'.json'),{k:v for k,v in m.items() if k not in ['end_of_period_verification','sources']})
    save(ROOT/'experiments/registry.json',{'schema_version':1,'active_period':None,'periods':{PERIOD:{'title':'Initial Windows local-LLM series, closed 2026-11-01','status':'closed','directory':'experiments/'+PERIOD,'run_index':'experiments/'+PERIOD+'/runs.json','git_tag':TAG}}})
    save(FOLDER/'manifest.json',{'schema_version':1,'period':PERIOD,'status':'closing','closed_at_utc':now(),'git_tag':TAG,'results_baseline_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'runs':len(runs),'data_policy':'Original run/artifact paths preserved. Period directory contains frozen indexes, environment, acquisition manifests, code/config recipe and comparison. Future runs require another open period.','limitations':['Environment snapshot is retrospective; historical per-run evidence takes precedence','Weights and runtime binaries are obtained separately and checked by SHA256','Same inputs and seeds do not guarantee bit-for-bit generated answers or identical throughput']})
    print('Prepared closed membership and recipe; regenerate/verify reports before --seal')


def seal():
    m=load(FOLDER/'manifest.json');assert m['status']=='closing'
    assert not (FOLDER/'inventory.json').exists()
    comparison=ROOT/'reports/comprehensive'
    text=(comparison/'index.html').read_text(encoding='utf-8').replace('href="summary.md"','href="comparison.md"').replace('href="results.json"','href="comparison.json"').replace('src="dashboard.js"','src="comparison.js"')
    text=text.replace('</h1>','</h1><p>2026-11-01終了 · <a href="README.md">再現手順・環境・モデルhash</a></p>',1)
    (FOLDER/'report.html').write_text(text,encoding='utf-8')
    for src,dest in [('summary.md','comparison.md'),('results.json','comparison.json'),('dashboard.js','comparison.js'),('conditions.csv','conditions.csv')]:shutil.copyfile(comparison/src,FOLDER/dest)
    markdown=(FOLDER/'comparison.md').read_text(encoding='utf-8').replace('](index.html)','](report.html)').replace('](results.json)','](comparison.json)')
    (FOLDER/'comparison.md').write_text(markdown,encoding='utf-8')
    for p in sorted((ROOT/'publication').glob('comprehensive*')):shutil.copyfile(p,FOLDER/p.name)
    data=load(comparison/'results.json')
    save(FOLDER/'profiles.json',{'source':'comparison.json','rows':[{k:v for k,v in r.items() if k in ['id','label','model','quantization','mtp','profile','placement','mode_control','model_hash','runtime','fixed_speed','memory']} for r in data['rows']]})
    m.update(status='closed',counts=data['counts'],sealed_at_utc=now());save(FOLDER/'manifest.json',m)
    run_ids=set(load(FOLDER/'runs.json')['run_ids'])
    inventory={}
    names=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    for rel in sorted(set(names)):
        p=ROOT/rel;parts=pathlib.PurePosixPath(rel).parts
        if not rel or not p.is_file():continue
        frozen=parts[0] in ['artifacts','data','datasets','vendor','third_party'] or (parts[0]=='runs' and len(parts)>1 and parts[1] in run_ids) or (parts[0]=='reports' and len(parts)>2) or (parts[0]=='publication' and not rel.endswith(PERIOD+'-validation.json')) or rel.startswith('experiments/'+PERIOD+'/')
        if frozen:inventory[rel]={'bytes':p.stat().st_size,'sha256':digest(p)}
    save(FOLDER/'inventory.json',{'period':PERIOD,'scope':'Frozen evidence, inputs, period reports and recipe. Root maintained code is preserved in recipe/ and by the annotated Git tag; catalog/registry may grow in future periods.','files':inventory})
    print(json.dumps({'period':PERIOD,'tag':TAG,'frozen_files':len(inventory),'runs':len(run_ids)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--seal',action='store_true');a=p.parse_args()
    prepare() if a.prepare else seal()
