"""Download one pinned model with a disk reserve; prune only verified range caches."""
import argparse,datetime,json,pathlib,re,shutil,subprocess,sys,time
from download_pinned_model import digest

ROOT=pathlib.Path(__file__).resolve().parents[1]

def verified_prune(metadata,directory):
    directory=directory.resolve();target=(directory/metadata['filename']).resolve()
    assert not directory.is_relative_to(ROOT),'Model directory must be outside the repository'
    assert target.parent==directory and target.name==metadata['filename'],'Expected a single model filename'
    assert target.is_file() and target.stat().st_size==metadata['bytes'],'Completed model absent or wrong size'
    assert digest(target)==metadata['sha256'],'Completed model hash mismatch; cache retained'
    pattern=re.compile(re.escape(target.name)+r'\.range-(\d+)-(\d+)(?:\.headers)?$')
    candidates=[]
    for p in directory.iterdir():
        match=pattern.fullmatch(p.name)
        if not match or not p.is_file():continue
        resolved=p.resolve();assert resolved.parent==directory,'Cache path escapes model directory'
        lo,hi=map(int,match.groups());assert 0<=lo<=hi<metadata['bytes'],'Unexpected cached byte range'
        candidates.append((resolved,resolved.stat().st_size))
    removed=0
    for p,size in candidates:p.unlink();removed+=size
    return {'verified_model':target.name,'model_sha256':metadata['sha256'],'removed_files':len(candidates),'removed_cache_bytes':removed}

def run(a):
    metadata=json.loads(a.manifest.read_text(encoding='utf-8'));directory=a.model_dir.resolve()
    assert not directory.is_relative_to(ROOT),'Weights must stay outside Git'
    target=directory/metadata['filename'];assert target.parent==directory and target.name==metadata['filename']
    assert a.connections>=1 and a.min_free_gib>=0
    if a.status_only:
        received=0
        for p in directory.glob(target.name+'.range-*'):
            if p.suffix=='.headers':continue
            with p.open('rb') as f:f.seek(0,2);received+=f.tell()
        print(json.dumps({'filename':target.name,'completed_file_exists':target.exists(),'received_GB':round(received/1e9,2),'model_GB':round(metadata['bytes']/1e9,2),'free_GB':round(shutil.disk_usage(directory).free/1e9,2)}));return
    directory.mkdir(parents=True,exist_ok=True)
    reserve=int(a.min_free_gib*1024**3);before=shutil.disk_usage(directory).free
    if not target.exists():
        assert not a.prune_only,'Prune-only requires a completed model'
        required=2*metadata['bytes']+reserve
        if before<required:raise RuntimeError(f'Insufficient disk reserve: free={before}, required={required}; no download started')
        command=[sys.executable,'-B',str(ROOT/'scripts/download_pinned_model.py'),'--manifest',str(a.manifest),'--model-dir',str(directory),'--connections',str(a.connections)]
        process=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while process.poll() is None:
                if shutil.disk_usage(directory).free<reserve:
                    # The PID belongs to this Popen and is still running; stop its curl children as well.
                    subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
                    process.wait();raise RuntimeError('Owned download stopped at the disk reserve; partial files retained')
                time.sleep(2)
            if process.returncode:raise RuntimeError('Pinned downloader failed: '+str(process.returncode))
        finally:
            if process.poll() is None:
                subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],check=True,creationflags=subprocess.CREATE_NO_WINDOW);process.wait()
    result=verified_prune(metadata,directory)
    result.update(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),free_bytes_before=before,free_bytes_after=shutil.disk_usage(directory).free,reserve_bytes=reserve)
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=pathlib.Path,required=True);p.add_argument('--model-dir',type=pathlib.Path,required=True);p.add_argument('--connections',type=int,default=32);p.add_argument('--min-free-gib',type=float,default=32);p.add_argument('--prune-only',action='store_true');p.add_argument('--status-only',action='store_true');p.add_argument('--report',type=pathlib.Path);run(p.parse_args())
