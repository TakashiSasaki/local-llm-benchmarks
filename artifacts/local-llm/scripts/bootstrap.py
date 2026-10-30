"""SSH preflight, helper installation and fixture bridge. Only configured hosts."""
import argparse, base64, hashlib, json, pathlib, shlex, subprocess
from bounded_windows import run_owned
from server import ROOT

class Bridge:
    def __init__(self,alias):
        self.config=json.loads((ROOT/'executor-config.json').read_text(encoding='utf-8-sig'))
        self.alias=alias; self.host=self.config['ssh_hosts'][alias]
    def ssh(self,command,stdin=None,timeout=30):
        p=run_owned([self.config['ssh'],'-T','-o','BatchMode=yes','-o','ConnectTimeout=10',self.alias,command],input_bytes=stdin,timeout=timeout)
        if p.returncode: raise RuntimeError(p.stderr.decode('utf-8',errors='replace')+p.stdout.decode('utf-8',errors='replace'))
        return p.stdout
    def __call__(self,payload):
        source=(ROOT/'scripts/remote_helper.py').read_bytes()
        encoded=base64.b64encode(source).decode()
        command='python3 -c '+shlex.quote("import base64; exec(compile(base64.b64decode('"+encoded+"'),'<validator-bridge>','exec'))")
        return json.loads(self.ssh(command,json.dumps(payload,ensure_ascii=False).encode(),timeout=60))
    def preflight(self):
        paths={k:pathlib.PurePosixPath(self.host[k]) for k in ['workspace_root','state_root','worker_path']}
        if any(not p.is_absolute() or '..' in p.parts for p in paths.values()):
            raise ValueError('Remote paths must be absolute without parent traversal')
        remote_root=paths['workspace_root'].parent
        # Require a dedicated absolute directory; never install into the home root.
        if len(remote_root.parts)<4: raise ValueError('Dedicated remote root required')
        if any(p==remote_root or not p.is_relative_to(remote_root) for p in paths.values()):
            raise ValueError('Worker, workspace and state must stay inside the dedicated remote root')
        def overlaps(a,b): return a==b or a.is_relative_to(b) or b.is_relative_to(a)
        if any(overlaps(a,b) for i,a in enumerate(paths.values()) for b in list(paths.values())[i+1:]):
            raise ValueError('Worker, workspace and state paths must not overlap')
        code='''import hashlib,json,os,pathlib,platform,shutil,subprocess,sys
r=json.load(sys.stdin)
if platform.system()!='Linux': raise RuntimeError('SSH evaluation requires an actual Linux peer')
if sys.version_info < (3,10): raise RuntimeError('SSH evaluation requires Python 3.10 or newer')
bash=shutil.which('bash')
if not bash: raise RuntimeError('Remote bash is missing')
bash_version=subprocess.check_output([bash,'--version'],text=True).splitlines()[0]
paths={name:pathlib.Path(r[name]) for name in ['root','worker','workspace','state']}
if any(not path.is_absolute() or '..' in path.parts for path in paths.values()): raise ValueError('Remote paths must be absolute without parent traversal')
root=paths['root']
if len(root.parts)<4 or paths['workspace'].parent!=root: raise ValueError('Dedicated remote root required')
if any(path==root or not path.is_relative_to(root) for name,path in paths.items() if name!='root'): raise ValueError('Remote path outside dedicated root')
def overlaps(a,b): return a==b or a.is_relative_to(b) or b.is_relative_to(a)
managed=[paths[name] for name in ['worker','workspace','state']]
if any(overlaps(a,b) for i,a in enumerate(managed) for b in managed[i+1:]): raise ValueError('Remote paths overlap')
# A pre-existing symlink at or beneath the dedicated root could redirect writes.
for path in managed:
    current=root
    if current.is_symlink(): raise ValueError('Symlink in dedicated remote root')
    for part in path.relative_to(root).parts:
        current=current/part
        if current.is_symlink(): raise ValueError('Symlink in managed remote path')
resolved_root=root.resolve()
if len(resolved_root.parts)<4: raise ValueError('Resolved root is not a dedicated remote directory')
resolved={name:path.resolve() for name,path in paths.items() if name!='root'}
if any(path==resolved_root or not path.is_relative_to(resolved_root) for path in resolved.values()): raise ValueError('Resolved path outside dedicated root')
resolved_managed=list(resolved.values())
if any(overlaps(a,b) for i,a in enumerate(resolved_managed) for b in resolved_managed[i+1:]): raise ValueError('Resolved remote paths overlap')
if root.exists() and not root.is_dir(): raise ValueError('Remote root is not a directory')
for path in managed:
    parent=path.parent
    while parent!=root:
        if parent.exists() and not parent.is_dir(): raise ValueError('Remote parent is not a directory')
        parent=parent.parent
for name in ['workspace','state']:
    if paths[name].exists() and not paths[name].is_dir(): raise ValueError('Remote '+name+' is not a directory')
worker=paths['worker']
if worker.exists() and not worker.is_file(): raise ValueError('Remote worker is not a file')
content=bytes.fromhex(r['source_hex'])
worker_exists=worker.exists()
if worker_exists and worker.read_bytes()!=content: raise RuntimeError('Existing remote worker differs; review before replacing')
root.mkdir(parents=True,exist_ok=True)
worker.parent.mkdir(parents=True,exist_ok=True)
if not worker_exists:
    # Do not overwrite a worker created concurrently after the existence check.
    with worker.open('xb') as out: out.write(content)
paths['workspace'].mkdir(parents=True,exist_ok=True)
paths['state'].mkdir(parents=True,exist_ok=True)
print(json.dumps({'hostname':platform.node(),'platform':platform.platform(),'python':sys.version,'bash':bash,'bash_version':bash_version,'sha256sum':shutil.which('sha256sum'),'worker_sha256':hashlib.sha256(content).hexdigest(),'root':str(root),'resolved_root':str(resolved_root),'resolved_paths':{name:str(path) for name,path in resolved.items()}}))
'''
        payload={'root':str(remote_root),'worker':self.host['worker_path'],'workspace':self.host['workspace_root'],'state':self.host['state_root'],'source_hex':(ROOT/'scripts/executor_worker.py').read_bytes().hex()}
        command='python3 -c '+shlex.quote(code)
        result=json.loads(self.ssh(command,json.dumps(payload).encode(),timeout=30))
        if not result['bash']: raise RuntimeError('Remote bash is missing')
        (ROOT/'runs'/f'ssh-preflight-{self.alias}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('host_alias'); a=ap.parse_args()
    print(json.dumps(Bridge(a.host_alias).preflight(),ensure_ascii=False))
