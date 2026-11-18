"""Verify a sealed period without executing model inference or generated code."""
import argparse
import hashlib
import json
import pathlib
import sys

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,validate_run
from local_llm_benchmarks.periods import membership,validate_id


def verify(period,root=ROOT):
    validate_id(period);folder=root/'experiments'/period;m=load(folder/'manifest.json')
    assert m['status']=='closed'
    files=load(folder/'inventory.json')['files']
    for rel,value in files.items():
        path=(root/rel).resolve();assert path.is_relative_to(root.resolve())
        assert path.stat().st_size==value['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==value['sha256'],rel
    index=load(folder/'runs.json')
    assert len(index['run_ids'])==len(set(index['run_ids']))==m['runs']
    for entry in index['runs']:
        path=root/'runs'/entry['run_id'];run=validate_run(path)
        assert membership(root,run)==period
        assert hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()==entry['manifest_sha256']
    for path in (root/'runs').glob('*/manifest.json'):membership(root,load(path))
    assets=load(folder/'assets.json');present=0
    for asset in assets['models']:
        assert (folder/'models'/(asset['filename']+'.json')).relative_to(root).as_posix() in files, 'Acquisition manifest missing from frozen file inventory'
        assert asset['revision'] in asset['url'] and len(asset['revision'])==40
        assert asset['sha256']==load(folder/'models'/(asset['filename']+'.json'))['sha256']
        value=asset['end_of_period_verification']
        if value['present']:
            assert value['sha256']==asset['sha256'] and value['bytes']==asset['bytes'] and value['matches_pinned_artifact'];present+=1
    d=load(folder/'comparison.json')
    assert set(d['sources']).issubset(files), 'Referenced source missing from frozen file inventory'
    assert d['counts']==m['counts'] and d['counts']['registered_runs']==len(index['run_ids'])
    assert all(not pathlib.PurePosixPath(name).suffix.lower() in ['.exe','.dll','.gguf','.safetensors'] for name in files)
    result={'passed':True,'period':period,'tag':m['git_tag'],'frozen_files_verified':len(files),'registered_runs':len(index['run_ids']),'external_model_files_verified_at_close':present,'external_runtime_files_verified_at_close':sum(len(v['installed_files_verified']) for v in assets['runtimes']),'inference_performed':False,'tag_commit_resolution':'Resolve the annotated tag in Git; the manifest deliberately does not embed its own commit hash.'}
    print(json.dumps(result));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--period',default='period-001');a=p.parse_args()
    result=verify(a.period)
    (ROOT/'publication'/(a.period+'-validation.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
