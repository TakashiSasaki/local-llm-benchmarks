"""Download an explicitly pinned GGUF outside the repository and verify its SHA256."""
import argparse,hashlib,json,pathlib,subprocess

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=pathlib.Path,required=True);ap.add_argument('--model-dir',type=pathlib.Path,required=True);a=ap.parse_args()
    repo=pathlib.Path(__file__).resolve().parents[1];dest=a.model_dir.resolve()
    assert not dest.is_relative_to(repo),'Weights must stay outside the repository'
    m=json.loads(a.manifest.read_text(encoding='utf-8'));dest.mkdir(parents=True,exist_ok=True);target=dest/m['filename']
    assert target.parent==dest and m['revision'] in m['url'],'Expected pinned single-file model URL'
    if not target.exists():
        part=target.with_suffix(target.suffix+'.part')
        subprocess.run(['curl.exe','--fail','--location','--silent','--show-error','--retry','5','--continue-at','-','--output',str(part),m['url']],check=True)
        assert part.stat().st_size==m['bytes'] and digest(part)==m['sha256'],'Download size/hash mismatch'
        part.rename(target)
    assert target.stat().st_size==m['bytes'] and digest(target)==m['sha256'],'Existing model size/hash mismatch'
    print(json.dumps({'verified':True,'filename':target.name,'bytes':target.stat().st_size,'sha256':m['sha256']}),flush=True)
