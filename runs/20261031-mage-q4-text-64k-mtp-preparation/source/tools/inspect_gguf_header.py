"""Inspect GGUF v2/v3 metadata and tensor names without loading tensor weights."""
import argparse,hashlib,json,pathlib,struct

FORMATS={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}

def inspect(path):
    with path.open('rb') as stream:
        def number(fmt):
            size=struct.calcsize('<'+fmt);data=stream.read(size)
            if len(data)!=size:raise ValueError('Truncated GGUF header')
            return struct.unpack('<'+fmt,data)[0]
        def string(keep=True):
            size=number('Q')
            if size>path.stat().st_size-stream.tell():raise ValueError('Invalid GGUF string length')
            if not keep:stream.seek(size,1);return None
            return stream.read(size).decode('utf-8')
        def value(kind,keep=True):
            if kind in FORMATS:
                result=number(FORMATS[kind]);return result if keep else None
            if kind==8:return string(keep)
            if kind==9:
                subtype=number('I');count=number('Q')
                if subtype in FORMATS:
                    size=count*struct.calcsize('<'+FORMATS[subtype])
                    if size>path.stat().st_size-stream.tell():raise ValueError('Invalid GGUF array length')
                    stream.seek(size,1)
                else:
                    if count>path.stat().st_size:raise ValueError('Invalid GGUF array count')
                    for _ in range(count):value(subtype,False)
                return {'array_type':subtype,'count':count} if keep else None
            raise ValueError('Unknown GGUF metadata type: '+str(kind))
        if stream.read(4)!=b'GGUF':raise ValueError('Not a GGUF file')
        version=number('I')
        if version not in (2,3):raise ValueError('Only little-endian GGUF v2/v3 are supported')
        tensors=number('Q');keys=number('Q');metadata={}
        for _ in range(keys):
            key=string();kind=number('I')
            # Omit tokenizer strings and arrays; retain structure, not model chat-template text.
            metadata[key]=value(kind,not key.startswith('tokenizer.'))
        names=[]
        for _ in range(tensors):
            names.append(string());dimensions=number('I')
            if dimensions>4:raise ValueError('Unexpected tensor rank')
            for _ in range(dimensions):number('Q')
            number('I');number('Q')
        end=stream.tell();stream.seek(0);digest=hashlib.sha256(stream.read(end)).hexdigest()
    return {'filename':path.name,'bytes':path.stat().st_size,'gguf_version':version,'tensor_count':tensors,'metadata':{k:v for k,v in metadata.items() if v is not None},'tensor_names':names,'header_bytes':end,'header_sha256':digest,'tensor_weights_loaded':False,'scope':'Header inspection only; absence of MTP metadata/tensors is not a throughput measurement.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('model',type=pathlib.Path);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args();result=inspect(a.model);a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('metadata','tensor_names')}))
