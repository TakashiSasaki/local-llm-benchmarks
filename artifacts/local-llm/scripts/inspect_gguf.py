"""Read a bounded GGUF prefix from each pinned URL; never loads model weights.

This is metadata inspection, not model inference or full-file integrity checking.
Large vocabulary arrays are skipped rather than expanded in the JSON report.
"""
import argparse, io, json, pathlib, struct, urllib.request
from server import ROOT

FORMATS={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
class Reader:
    def __init__(self,data): self.stream=io.BytesIO(data)
    def number(self,fmt):
        size=struct.calcsize('<'+fmt); raw=self.stream.read(size)
        if len(raw)!=size: raise EOFError('GGUF metadata exceeds fetched prefix')
        return struct.unpack('<'+fmt,raw)[0]
    def string(self,keep=True):
        n=self.number('Q')
        if n>self.stream.getbuffer().nbytes-self.stream.tell(): raise EOFError('GGUF string exceeds prefix')
        if keep: return self.stream.read(n).decode('utf-8')
        self.stream.seek(n,1); return None
    def value(self,typ,keep=True):
        if typ==8: return self.string(keep)
        if typ==9:
            inner=self.number('I'); n=self.number('Q')
            if keep and n<128: return [self.value(inner) for _ in range(n)]
            if inner in FORMATS:
                skip=struct.calcsize('<'+FORMATS[inner])*n
                if skip>self.stream.getbuffer().nbytes-self.stream.tell(): raise EOFError('GGUF array exceeds prefix')
                self.stream.seek(skip,1)
            else:
                for _ in range(n): self.value(inner,False)
            return {'element_type':inner,'length':n,'values':'not expanded'}
        if typ not in FORMATS: raise ValueError('Unknown GGUF type '+str(typ))
        return self.number(FORMATS[typ])

def inspect(path):
    meta=json.loads(path.read_text(encoding='utf-8-sig')); f=meta['file']; name=f['rfilename']
    url=f"https://huggingface.co/{meta['repo']}/resolve/{meta['revision']}/{name}"
    maximum=32*1024*1024
    req=urllib.request.Request(url,headers={'Range':f'bytes=0-{maximum-1}','User-Agent':'LocalLLM-metadata-inspection'})
    with urllib.request.urlopen(req,timeout=60) as response:
        data=response.read(maximum); headers={'status':response.status,'content_range':response.headers.get('Content-Range')}
    r=Reader(data)
    if r.stream.read(4)!=b'GGUF': raise ValueError('Not a GGUF file')
    version=r.number('I'); tensors=r.number('Q'); count=r.number('Q')
    selected={}; templates={}; error=None; parsed=0; tensor_names=[]
    try:
        for _ in range(count):
            key=r.string(); typ=r.number('I')
            keep=not key.startswith(('tokenizer.ggml.tokens','tokenizer.ggml.scores','tokenizer.ggml.token_type','tokenizer.ggml.merges'))
            value=r.value(typ,keep); parsed+=1
            if 'chat_template' in key and isinstance(value,str): templates[key]=value
            elif keep: selected[key]=value
        for _ in range(tensors):
            tensor_name=r.string(); dimensions=r.number('I'); shape=[r.number('Q') for _ in range(dimensions)]; typ=r.number('I'); offset=r.number('Q')
            tensor_names.append(tensor_name)
    except EOFError as e: error=str(e)
    result={'repo':meta['repo'],'revision':meta['revision'],'filename':name,'inspection':'bounded metadata prefix; full file SHA-256 not checked by this script','prefix_bytes':len(data),'http':headers,'gguf_version':version,'tensor_count':tensors,'kv_count':count,'kv_parsed':parsed,'metadata_complete':parsed==count,'tensor_headers_complete':len(tensor_names)==tensors,'metadata':selected,'template_keys':list(templates),'mtp_named_tensors':[n for n in tensor_names if any(s in n.lower() for s in ['mtp','nextn','draft'])],'mtp_name_match_is_not_runtime_validation':True,'error':error}
    model='qwen' if name.startswith('Qwen') else 'lfm' if name.startswith('LFM') else 'glm'
    for key,template in templates.items(): (ROOT/'docs'/f'{model}-{key.replace(".","-")}.jinja').write_text(template,encoding='utf-8')
    (ROOT/'docs'/f'gguf-inspection-{model}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'model':model,'architecture':selected.get('general.architecture'),'metadata_complete':result['metadata_complete'],'tensor_headers_complete':result['tensor_headers_complete'],'templates':list(templates),'mtp_named_tensor_count':len(result['mtp_named_tensors']),'error':error},ensure_ascii=False),flush=True)

if __name__=='__main__':
    for path in sorted((ROOT/'docs').glob('*.gguf.metadata.json')): inspect(path)
