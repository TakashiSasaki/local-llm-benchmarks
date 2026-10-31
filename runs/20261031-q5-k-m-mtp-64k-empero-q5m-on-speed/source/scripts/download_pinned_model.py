"""Download an explicitly pinned GGUF outside the repository and verify its SHA256."""
import argparse,concurrent.futures,hashlib,json,pathlib,re,subprocess

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=pathlib.Path,required=True);ap.add_argument('--model-dir',type=pathlib.Path,required=True);ap.add_argument('--connections',type=int,default=1);a=ap.parse_args()
    repo=pathlib.Path(__file__).resolve().parents[1];dest=a.model_dir.resolve()
    assert not dest.is_relative_to(repo),'Weights must stay outside the repository'
    m=json.loads(a.manifest.read_text(encoding='utf-8'));dest.mkdir(parents=True,exist_ok=True);target=dest/m['filename']
    assert target.parent==dest and m['revision'] in m['url'],'Expected pinned single-file model URL'
    if not target.exists():
        part=target.with_suffix(target.suffix+'.part')
        if a.connections==1:
            subprocess.run(['curl.exe','--fail','--location','--silent','--show-error','--retry','5','--continue-at','-','--output',str(part),m['url']],check=True)
        else:
            start=part.stat().st_size if part.exists() else 0;block=64*1024*1024
            ranges=[(s,min(s+block,m['bytes'])-1) for s in range(start,m['bytes'],block)]
            def fetch(pair):
                lo,hi=pair;p=dest/(target.name+f'.range-{lo}-{hi}');header=p.with_suffix(p.suffix+'.headers')
                if p.exists() and p.stat().st_size==hi-lo+1 and header.exists():
                    if re.search(fr'(?im)^content-range: bytes {lo}-{hi}/{m["bytes"]}\s*$',header.read_text()):return p
                url=m['url']+f'?range_start={lo}'
                subprocess.run(['curl.exe','--fail','--location','--silent','--show-error','--retry','5','--range',f'{lo}-{hi}','--dump-header',str(header),'--output',str(p),url],check=True)
                assert p.stat().st_size==hi-lo+1 and re.search(fr'(?im)^content-range: bytes {lo}-{hi}/{m["bytes"]}\s*$',header.read_text()),'Incorrect range response'
                return p
            with concurrent.futures.ThreadPoolExecutor(max_workers=a.connections) as pool:
                for done,_ in enumerate(pool.map(fetch,ranges),1):
                    if done%8==0 or done==len(ranges):print(json.dumps({'range_downloads_done':done,'ranges_total':len(ranges)}),flush=True)
            with part.open('ab') as out:
                for pair in ranges:
                    with (dest/(target.name+f'.range-{pair[0]}-{pair[1]}')).open('rb') as f:
                        for data in iter(lambda:f.read(8*1024*1024),b''):out.write(data)
        assert part.stat().st_size==m['bytes'] and digest(part)==m['sha256'],'Download size/hash mismatch'
        part.rename(target)
    assert target.stat().st_size==m['bytes'] and digest(target)==m['sha256'],'Existing model size/hash mismatch'
    print(json.dumps({'verified':True,'filename':target.name,'bytes':target.stat().st_size,'sha256':m['sha256']}),flush=True)
