"""Collect public, pinned Hub metadata for planning; never download model tensors."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'local-llm-benchmarks-metadata/1'}), timeout=60) as f:
        return f.read()


def metadata_only(value):
    if isinstance(value,list):return [metadata_only(x) for x in value]
    if not isinstance(value,dict):return value
    result={}
    for key,item in value.items():
        if key=='quantize_imatrix_file':continue
        if key=='chat_template':
            result[key+'_sha256']=hashlib.sha256((item if isinstance(item,str) else json.dumps(item,sort_keys=True)).encode()).hexdigest()
        else:result[key]=metadata_only(item)
    return result


def collect(repo):
    url='https://huggingface.co/api/models/'+urllib.parse.quote(repo,safe='/')+'?blobs=true'
    try:
        raw=fetch(url);d=json.loads(raw);revision=d['sha'];selected=[]
        for f in d.get('siblings',[]):
            name=f['rfilename']
            if not name.endswith('.gguf') or not any(q in name.upper() for q in ['Q4_K_M','Q3_K_M','Q8_0']):continue
            lfs=f.get('lfs',{});selected.append({'filename':name,'bytes':f.get('size',lfs.get('size')),'sha256':lfs.get('sha256',lfs.get('oid')),'url':f'https://huggingface.co/{repo}/resolve/{revision}/{urllib.parse.quote(name)}'})
        card=d.get('cardData') or {};gguf=dict(d.get('gguf') or {})
        template=gguf.pop('chat_template',None);gguf.pop('quantize_imatrix_file',None)
        if template is not None:gguf['chat_template_sha256']=hashlib.sha256((template if isinstance(template,str) else json.dumps(template,sort_keys=True)).encode()).hexdigest()
        result={'repo':repo,'url':'https://huggingface.co/'+repo,'api_url':url,'revision':revision,'created_at':d.get('createdAt'),'last_modified':d.get('lastModified'),'downloads_30d':d.get('downloads'),'likes':d.get('likes'),'gated':d.get('gated'),'library':d.get('library_name'),'parameter_counts':d.get('safetensors'),'config':d.get('config'),'gguf':gguf,'card_fields':{k:card[k] for k in ['license','base_model','base_model_relation','language','datasets'] if k in card},'selected_files':selected,'api_sha256':hashlib.sha256(raw).hexdigest()}
        for name in ['config.json','README.md']:
            target=f'https://huggingface.co/{repo}/resolve/{revision}/{name}'
            try:
                value=fetch(target);result[name+'_sha256']=hashlib.sha256(value).hexdigest();result[name+'_url']=target
                if name=='config.json':result['model_config']=json.loads(value)
            except urllib.error.HTTPError as exc:result[name+'_http_status']=exc.code
        return metadata_only(result)
    except (urllib.error.URLError,ValueError,KeyError) as exc:
        return {'repo':repo,'api_url':url,'error':str(exc),'http_status':getattr(exc,'code',None)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repos',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    assert not a.output.exists(),'Use a new observation file rather than replacing research evidence'
    repos=json.loads(a.repos.read_text(encoding='utf-8'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(collect,repos))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Public Hub metadata and card/config digests only; no tensor download, inference or remote code execution. Likes/downloads are popularity signals, not quality scores.','models':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for r in results:print(json.dumps({k:r.get(k) for k in ['repo','revision','downloads_30d','likes','error']}),flush=True)
