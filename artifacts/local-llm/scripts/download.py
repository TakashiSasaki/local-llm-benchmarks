"""Pinned downloads, resumable via Windows curl, with SHA-256 verification."""
import hashlib, json, pathlib, subprocess, sys, time, zipfile

ROOT = pathlib.Path(r'C:\LocalLLM')

def atomic_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()

def download(url, dest, size, expected):
    if dest.exists() and dest.stat().st_size == size:
        actual = digest(dest)
        if actual == expected:
            return actual
        raise RuntimeError(f'Existing file hash mismatch: {dest}')
    part = dest.with_suffix(dest.suffix + '.part')
    print(json.dumps({'event':'download_start','file':dest.name,'bytes':size}), flush=True)
    subprocess.run(['curl.exe','--fail','--location','--retry','5','--retry-delay','3',
                    '--continue-at','-','--output',str(part),url], check=True)
    if part.stat().st_size != size:
        raise RuntimeError(f'Size mismatch: {part}')
    actual = digest(part)
    if actual != expected:
        raise RuntimeError(f'SHA-256 mismatch: {part}: {actual}')
    part.rename(dest)
    print(json.dumps({'event':'verified','file':dest.name,'sha256':actual}), flush=True)
    return actual

def runtime():
    release = json.loads((ROOT/'docs/release-b11946.json').read_text(encoding='utf-8-sig'))
    assets = [a for a in release['assets'] if 'win-cuda-12.4-x64.zip' in a['name']]
    out = ROOT/'bin/b11946-cuda12.4'
    out.mkdir(exist_ok=True)
    source=json.loads((ROOT/'docs/runtime-source-commit.json').read_text(encoding='utf-8-sig'))
    manifest = {'build':'b11946','commit':source['commit'],'url':release['html_url'],'assets':[]}
    for a in assets:
        expected = a['digest'].removeprefix('sha256:')
        dest = ROOT/'downloads'/a['name']
        actual = download(a['browser_download_url'],dest,a['size'],expected)
        with zipfile.ZipFile(dest) as z:
            z.extractall(out)
        manifest['assets'].append({'name':a['name'],'url':a['browser_download_url'],'bytes':a['size'],'sha256':actual})
    manifest['files'] = [{'path':str(p.relative_to(ROOT)),'sha256':digest(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()]
    atomic_json(ROOT/'runtime-manifest.json',manifest)

def models(selected):
    manifest_path = ROOT/'model-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else []
    order={'Qwen3.6':0,'LFM2.5':1,'GLM-4.7':2}
    for p in sorted((ROOT/'docs').glob('*.gguf.metadata.json'),key=lambda p:next((n for prefix,n in order.items() if p.name.startswith(prefix)),99)):
        m = json.loads(p.read_text(encoding='utf-8-sig'))
        if selected != 'all' and selected.lower() not in m['repo'].lower():
            continue
        f=m['file']; name=f['rfilename']
        url=f"https://huggingface.co/{m['repo']}/resolve/{m['revision']}/{name}"
        actual=download(url,ROOT/'models'/name,f['size'],f['lfs']['sha256'])
        source_name='qwen' if name.startswith('Qwen') else 'lfm' if name.startswith('LFM') else 'glm'
        source=json.loads((ROOT/'docs'/f'model-source-{source_name}.json').read_text(encoding='utf-8-sig'))
        card=source['cardData']
        record={'repo':m['repo'],'revision':m['revision'],'filename':name,'bytes':f['size'],'sha256':actual,'license':card.get('license_name',card.get('license')),'license_source_repo':source['repo'],'license_source_revision':source['revision'],'url':url,'verified_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        manifest=[x for x in manifest if x['filename']!=name]+[record]
        atomic_json(manifest_path,manifest)

if __name__=='__main__':
    runtime() if sys.argv[1]=='runtime' else models(sys.argv[1])
