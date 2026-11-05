"""Validate maintained runs and scan publication candidates, without inference."""
import hashlib,json,os,pathlib,re,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,validate_run,load
def candidates():
    try:
        raw=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z','--cached','--others','--exclude-standard'])
        return sorted({ROOT/p for p in raw.decode('utf-8').split('\0') if p and (ROOT/p).is_file()})
    except (OSError,subprocess.CalledProcessError):
        return [p for p in ROOT.rglob('*') if p.is_file() and not any(n in p.parts for n in ['.git','.local','.cache','.venv','node_modules','__pycache__'])]
def check():
    manifests=[p/'manifest.json' for p in (ROOT/'runs').iterdir() if p.is_dir() and (p/'manifest.json').exists()]
    for path in manifests:validate_run(path.parent)
    for item in load(ROOT/'publication/hermes-export-manifest.json')['entries']:
        assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['exported_sha256'],item['path']
    for location in [ROOT/'datasets/bfcl/6ea5797',ROOT/'datasets/humaneval/b9453e8',ROOT/'vendor/bfcl',ROOT/'vendor/humaneval/b9453e8']:
        for rel,expected in load(location/'manifest.json')['files'].items():assert hashlib.sha256((location/rel).read_bytes()).hexdigest()==expected,str(location/rel)
    private_user=os.environ.get('USERNAME','');findings=[]
    patterns=[r'github_pat_[A-Za-z0-9_]{20,}',r'gh[pousr]_[A-Za-z0-9_]{20,}',r'hf_[A-Za-z0-9]{24,}',r'sk-(?:proj-)?[A-Za-z0-9_-]{25,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    for p in candidates():
        assert p.name not in {'state.db','config.yaml'} and not p.name.startswith(('state.db-','codex-config-before-')),str(p)
        assert p.suffix.lower() not in {'.gguf','.safetensors','.exe','.dll','.pyd','.bin','.pt','.pth','.onnx','.pyc'},str(p)
        try:text=p.read_text(encoding='utf-8-sig')
        except (UnicodeDecodeError,OSError):continue
        if private_user and re.search(r'(?i)[A-Z]:[\\/]+Users[\\/]+'+re.escape(private_user)+r'(?=[\\/"\s]|$)',text):findings.append({'file':p.relative_to(ROOT).as_posix(),'kind':'private_user_path'})
        if any(re.search(pattern,text) for pattern in patterns):findings.append({'file':p.relative_to(ROOT).as_posix(),'kind':'credential_pattern'})
    if findings:raise ValueError(json.dumps(findings,ensure_ascii=False))
    for path in (ROOT/'experiments').glob('period-*/inventory.json'):
        subprocess.run([sys.executable,'-B',str(ROOT/'tools/verify_period.py'),'--period',path.parent.name],check=True,stdout=subprocess.DEVNULL)
    print(json.dumps({'passed':True,'registered_runs':len(manifests),'publication_candidate_files':len(candidates()),'credential_or_private_path_findings':0}))
if __name__=='__main__':check()
