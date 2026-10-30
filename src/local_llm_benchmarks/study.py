"""Run directories and source provenance, independent of model/runtime locations."""
import datetime,hashlib,json,pathlib,re,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def resolve_run(value,root=ROOT):
    base=(root/'runs').resolve();path=(base/value).resolve()
    if path.parent!=base or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',value):raise ValueError('Use a single run ID under runs/')
    return path
def create_run(title,benchmark,config=None,run_id=None,root=ROOT,kind='measurement'):
    slug=re.sub(r'[^a-z0-9]+','-',title.lower()).strip('-')[:60] or 'experiment'
    name=run_id or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+slug
    path=resolve_run(name,root);path.mkdir(parents=True,exist_ok=False)
    for sub in ['raw','logs','summaries','source']: (path/sub).mkdir()
    save(path/'manifest.json',{'schema_version':1,'run_id':name,'title':title,'benchmark':benchmark,'kind':kind,'status':'planned','created_at':now(),'config':config or {}})
    return path
def snapshot_sources(path,root=ROOT):
    files={}
    for folder in ['benchmarks','src','scripts','tools']:
        for p in (root/folder).rglob('*'):
            if not p.is_file() or p.suffix not in ['.py','.ps1','.cjs','.json'] or '__pycache__' in p.parts:continue
            rel=p.relative_to(root);dest=path/'source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);files[rel.as_posix()]=sha(dest)
    result={'files':files,'git_commit':None,'git_dirty':None}
    try:
        def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.DEVNULL).strip()
        result.update(git_commit=git('rev-parse','HEAD'),git_dirty=bool(git('status','--porcelain')))
    except (OSError,subprocess.CalledProcessError):pass
    save(path/'source-manifest.json',result)
def validate_run(path):
    m=load(path/'manifest.json');assert m['schema_version']==1 and m['run_id']==path.name
    assert m['status'] in ['planned','running','complete','failed'] and m['kind'] in ['measurement','imported','replay']
    if (path/'source-manifest.json').exists():
        for rel,value in load(path/'source-manifest.json')['files'].items():assert sha(path/'source'/rel)==value,rel
    if m['status']=='complete':assert (path/'summary.json').exists()
    return m
