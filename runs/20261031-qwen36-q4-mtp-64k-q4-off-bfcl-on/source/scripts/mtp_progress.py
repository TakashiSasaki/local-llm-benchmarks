"""Small read-only progress snapshot for an MTP study, including an unfinished download."""
import argparse,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,resolve_run

def tail(path):
    if not path.exists():return None
    with path.open('rb') as f:
        f.seek(0,2);length=f.tell();f.seek(max(0,length-8192));lines=f.read().decode('utf-8',errors='replace').splitlines()
    return lines[-1] if lines else None

def snapshot(prefix):
    parent=resolve_run(prefix);m=load(parent/'manifest.json');cfg=m['config']
    event=tail(parent/'logs/progress.jsonl')
    out={'run':prefix,'status':m['status'],'progress':json.loads(event) if event else None,'cells':[]}
    if cfg.get('model_manifest'):
        model=load(ROOT/cfg['model_manifest']);target=pathlib.Path(r'C:\LocalLLM\models')/model['filename']
        if not target.exists():
            received=0
            for p in target.parent.glob(target.name+'.range-*'):
                if p.suffix=='.headers':continue
                # Open-file lengths can be newer than NTFS directory metadata.
                with p.open('rb') as f:f.seek(0,2);received+=f.tell()
            out['download']={'received_GB':round(received/1e9,2),'total_GB':round(model['bytes']/1e9,2)}
    for name in cfg['cell_runs'].values():
        cell=resolve_run(name)
        if not (cell/'manifest.json').exists():out['cells'].append({'run':name,'status':'not-started'});continue
        cm=load(cell/'manifest.json');entry={'run':name,'status':cm['status']}
        if cm['status']=='running':
            entry['conditions']={suite+'_'+mode:line for suite in ['bfcl','humaneval'] for mode in ['off','on'] if (line:=tail(cell/'logs'/(suite+'-'+mode+'.log')))}
            entry['generation']=tail(cell/'logs/llama-server.log')
            raw=tail(cell/'logs/memory.jsonl')
            if raw:
                mem=json.loads(raw);entry['memory']={'available_ram_GiB':round(mem['available_ram_bytes']/1024**3,2),'gpu_MiB':mem['gpu_used_mib'],'gpu_C':mem['gpu_temperature_c']}
        out['cells'].append(entry)
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);a=p.parse_args();print(json.dumps(snapshot(a.prefix),ensure_ascii=True))
