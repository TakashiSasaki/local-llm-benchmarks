"""Keep private originals under .local and anonymize machine paths in fresh public run evidence."""
import argparse,hashlib,importlib.util,json,pathlib,shutil,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,resolve_run
from import_hermes_history import scrub

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--study',required=True);a=ap.parse_args();resolve_run(a.study)
    entries=[]
    for folder in (ROOT/'runs').iterdir():
        if folder.name!=a.study and not folder.name.startswith(a.study+'-'):continue
        for p in folder.rglob('*'):
            if not p.is_file() or 'source' in p.relative_to(folder).parts or p.suffix not in {'.json','.jsonl','.log','.txt'}:continue
            original=p.read_bytes();text=original.decode('utf-8-sig');public=scrub(text).encode('utf-8')
            if original==public:continue
            rel=p.relative_to(ROOT);backup=ROOT/'.local/original-evidence'/rel
            if backup.exists():assert backup.read_bytes()==original,'Private backup differs'
            else:backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(original)
            p.write_bytes(public);entries.append({'path':rel.as_posix(),'original_sha256':hashlib.sha256(original).hexdigest(),'public_sha256':hashlib.sha256(public).hexdigest(),'action':'Anonymize Windows user/organization/host paths; private original retained outside Git'})
    target=ROOT/'publication'/(a.study+'-redactions.json')
    if target.exists():
        existing=load(target)['entries'];assert not entries,'Use a new redaction manifest for further transformations';entries=existing
    else:save(target,{'study':a.study,'entries':entries})
    print(json.dumps({'files_with_public_path_redactions':len(entries),'private_originals_tracked':False}))
