"""Model-independent SSH fixture transport. Run source over stdin by bootstrap.py."""
import base64, hashlib, json, os, pathlib, subprocess, sys, tempfile

def operate(r):
    directory=pathlib.Path(r['directory']).resolve()
    if r['action']=='seed':
        if directory.exists(): raise RuntimeError('Existing trial must not be overwritten')
        directory.mkdir(parents=True)
        for name,data in r['files'].items():
            path=directory/name
            if not path.resolve().is_relative_to(directory): raise ValueError('Fixture escapes workspace')
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(base64.b64decode(data))
        for name in r.get('executable',[]): (directory/name).chmod(0o700)
        return {'seeded':True,'host':os.uname().nodename,'directory':str(directory)}
    if r['action']=='snapshot':
        files={}
        for path in directory.rglob('*'):
            if path.is_file():
                if path.is_symlink(): raise ValueError('Symlink in fixture')
                data=path.read_bytes()
                if len(data)>1024*1024: raise ValueError('Unexpectedly large fixture output')
                files[path.relative_to(directory).as_posix()]={'base64':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest(),'executable':os.access(path,os.X_OK)}
        return {'host':os.uname().nodename,'directory':str(directory),'files':files}
    if r['action']=='invoke':
        script=(directory/r['script']).resolve()
        if not script.is_relative_to(directory): raise ValueError('Script outside trial')
        p=subprocess.run([str(script),*r.get('args',[])],cwd=directory,env={**os.environ,**r.get('env',{})},capture_output=True,timeout=20)
        return {'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
    raise ValueError('Unknown action')

if __name__=='__main__':
    try: print(json.dumps(operate(json.load(sys.stdin)),ensure_ascii=False))
    except Exception as e: print(json.dumps({'error':str(e),'type':type(e).__name__})); sys.exit(1)
