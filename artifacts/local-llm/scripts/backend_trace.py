"""Capture actual backend placement and FA selection with startup debug logging."""
import argparse, copy, json
from server import ROOT,load_profile,start,stop

def trace(model):
    stop(); p=copy.deepcopy(load_profile(model)); p['profile_id']=model+'-backend-trace'; p['status']='startup diagnostics only'; p['server_args']+=['-lv','5']
    name=model+'-backend-trace'
    (ROOT/'profiles'/f'{name}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        start(name); state=json.loads((ROOT/'server-state.json').read_text())
        lines=__import__('pathlib').Path(state['log']).read_text(encoding='utf-8',errors='replace').splitlines()
        selected=[line for line in lines if any(s in line.lower() for s in ['flash_attn','flash attention','load_backend','offloaded','buffer size','cuda0','cpu backend'])]
        report={'profile':p,'startup':state,'evidence':selected,'generation_performed':False}
        (ROOT/'runs'/f'backend-trace-{model}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'model':model,'evidence':selected[-35:]},ensure_ascii=False),flush=True)
    finally: stop()

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('models',nargs='+',choices=['qwen','lfm','glm']); a=ap.parse_args()
    for model in a.models: trace(model)
