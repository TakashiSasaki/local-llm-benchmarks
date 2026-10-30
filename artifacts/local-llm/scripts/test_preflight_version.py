"""Model-free simulation of the remote Python version gate.

No SSH host is contacted. These checks do not establish that Linux, SCP,
process groups or the remote worker work on an actual host.
"""
import contextlib
import io
import json
import os
import pathlib
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = pathlib.Path(r'C:\LocalLLM')
DRAFT = pathlib.Path(tempfile.gettempdir())
sys.path.insert(0, str(ROOT / 'scripts'))
import bootstrap


class SimulatedPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='preflight-sim-', dir=DRAFT)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'runs').mkdir()
        shutil.copyfile(ROOT / 'scripts' / 'executor_worker.py', self.root / 'scripts' / 'executor_worker.py')
        self.remote_root = self.root / 'remote'
        self.bridge = object.__new__(bootstrap.Bridge)
        self.bridge.alias = 'simulated'
        self.bridge.host = {
            'worker_path': '/home/testuser/codex-llm-test/executor_worker.py',
            'workspace_root': '/home/testuser/codex-llm-test/workspace',
            'state_root': '/home/testuser/codex-llm-test/jobs',
        }
        self.version = (3, 10, 0)
        self.remote_platform = 'Linux'
        self.bash_available = True
        self.bash_version_error = False
        self.payload_overrides = {}
        self.simulated_symlinks = set()
        self.resolve_overrides = {}
        self.worker_write_modes = []
        self.race_worker_appearance = False
        self.ssh_calls = 0
        self.bridge.ssh = self.fake_ssh

    def fake_ssh(self, command, stdin=None, timeout=30):
        self.ssh_calls += 1
        parts = shlex.split(command)
        self.assertEqual(parts[:2], ['python3', '-c'])
        payload = json.loads(stdin.decode('utf-8'))
        payload.update(root=str(self.remote_root), worker=str(self.remote_root / 'executor_worker.py'),
                       workspace=str(self.remote_root / 'workspace'), state=str(self.remote_root / 'jobs'))
        payload.update({key:str(value) for key,value in self.payload_overrides.items()})
        output = io.StringIO()
        original_is_symlink=pathlib.Path.is_symlink
        original_resolve=pathlib.Path.resolve
        original_open=pathlib.Path.open
        def simulated_is_symlink(path):
            return path in self.simulated_symlinks or original_is_symlink(path)
        def simulated_resolve(path,*args,**kwargs):
            if path in self.resolve_overrides: return self.resolve_overrides[path]
            return original_resolve(path,*args,**kwargs)
        def simulated_open(path,*args,**kwargs):
            mode=args[0] if args else kwargs.get('mode','r')
            if path==pathlib.Path(payload['worker']) and any(c in mode for c in 'wax+'):
                self.worker_write_modes.append(mode)
                if self.race_worker_appearance and mode=='xb':
                    with original_open(path,'wb') as race: race.write(b'concurrent worker')
            return original_open(path,*args,**kwargs)
        def simulated_which(command):
            return None if command=='bash' and not self.bash_available else '/usr/bin/'+command
        def simulated_bash_version(*args,**kwargs):
            if self.bash_version_error: raise subprocess.CalledProcessError(1,args[0])
            return 'GNU bash simulated\n'
        with patch.object(sys, 'version_info', self.version), \
             patch.object(sys, 'stdin', io.StringIO(json.dumps(payload))), \
             patch.object(platform, 'system', return_value=self.remote_platform), \
             patch.object(platform, 'platform', return_value='simulated Linux'), \
             patch.object(platform, 'node', return_value='simulated-host'), \
             patch.object(shutil, 'which', side_effect=simulated_which), \
             patch.object(pathlib.Path, 'is_symlink', simulated_is_symlink), \
             patch.object(pathlib.Path, 'resolve', simulated_resolve), \
             patch.object(pathlib.Path, 'open', simulated_open), \
             patch.object(subprocess, 'check_output', side_effect=simulated_bash_version), \
             contextlib.redirect_stdout(output):
            exec(compile(parts[2], '<simulated-remote-preflight>', 'exec'), {})
        return output.getvalue().encode('utf-8')

    def preflight(self):
        with patch.object(bootstrap, 'ROOT', self.root):
            return self.bridge.preflight()

    def test_reject_python_38_and_39_before_remote_writes(self):
        for version in [(3, 8, 20), (3, 9, 21)]:
            with self.subTest(version=version):
                self.version = version
                with self.assertRaisesRegex(RuntimeError, 'Python 3\\.10'):
                    self.preflight()
                self.assertFalse(self.remote_root.exists())
                self.assertFalse((self.root / 'runs' / 'ssh-preflight-simulated.json').exists())

    def test_supported_version_installs_exact_worker_in_simulated_tree(self):
        self.version = (3, 10, 0)
        result = self.preflight()
        self.assertEqual(result['hostname'], 'simulated-host')
        self.assertEqual((self.remote_root / 'executor_worker.py').read_bytes(),
                         (self.root / 'scripts' / 'executor_worker.py').read_bytes())
        self.assertEqual(self.worker_write_modes,['xb'])
        self.assertTrue((self.remote_root / 'workspace').is_dir())
        self.assertTrue((self.remote_root / 'jobs').is_dir())
        self.assertTrue((self.root / 'runs' / 'ssh-preflight-simulated.json').is_file())

    def test_existing_different_worker_is_not_replaced(self):
        self.remote_root.mkdir()
        existing = self.remote_root / 'executor_worker.py'
        existing.write_bytes(b'pre-existing worker')
        with self.assertRaisesRegex(RuntimeError, 'Existing remote worker differs'):
            self.preflight()
        self.assertEqual(existing.read_bytes(), b'pre-existing worker')

    def test_existing_matching_worker_is_not_written_again(self):
        self.remote_root.mkdir()
        existing=self.remote_root/'executor_worker.py'
        existing.write_bytes((self.root/'scripts'/'executor_worker.py').read_bytes())
        os.utime(existing,(946684800,946684800))
        mtime=existing.stat().st_mtime_ns
        self.preflight()
        self.assertEqual(self.worker_write_modes,[])
        self.assertEqual(existing.stat().st_mtime_ns,mtime)
        self.assertEqual(existing.read_bytes(),(self.root/'scripts'/'executor_worker.py').read_bytes())

    def test_worker_created_concurrently_is_never_overwritten(self):
        self.race_worker_appearance=True
        with self.assertRaises(FileExistsError): self.preflight()
        self.assertEqual(self.worker_write_modes,['xb'])
        self.assertEqual((self.remote_root/'executor_worker.py').read_bytes(),b'concurrent worker')
        self.assertFalse((self.remote_root/'workspace').exists())
        self.assertFalse((self.remote_root/'jobs').exists())

    def test_missing_bash_is_rejected_before_remote_writes(self):
        self.bash_available=False
        with self.assertRaisesRegex(RuntimeError,'bash is missing'):
            self.preflight()
        self.assertFalse(self.remote_root.exists())

    def test_wrong_platform_or_failed_bash_probe_does_not_write(self):
        self.remote_platform='Windows'
        with self.assertRaisesRegex(RuntimeError,'actual Linux'): self.preflight()
        self.assertFalse(self.remote_root.exists())
        self.remote_platform='Linux'; self.bash_version_error=True
        with self.assertRaises(subprocess.CalledProcessError): self.preflight()
        self.assertFalse(self.remote_root.exists())

    def test_local_configuration_rejects_escape_and_overlap_without_connection(self):
        examples=[('worker_path','/tmp/outside/executor_worker.py'),
                  ('state_root','/home/testuser/codex-llm-test/workspace/jobs'),
                  ('state_root','/home/testuser/codex-llm-test/../escape'),
                  ('workspace_root','relative/workspace')]
        original=dict(self.bridge.host)
        for field,value in examples:
            with self.subTest(field=field,value=value):
                self.bridge.host=dict(original); self.bridge.host[field]=value
                with self.assertRaises(ValueError): self.preflight()
                self.assertEqual(self.ssh_calls,0)
                self.assertFalse(self.remote_root.exists())

    def test_remote_rechecks_escape_and_overlap_before_writes(self):
        examples=[{'worker':self.root/'outside.py'},
                  {'state':self.remote_root/'workspace'/'jobs'},
                  {'worker':self.remote_root/'workspace'/'worker.py'},
                  {'workspace':self.remote_root/'other'/'workspace'}]
        for overrides in examples:
            with self.subTest(overrides=overrides):
                self.payload_overrides=overrides
                with self.assertRaises(ValueError): self.preflight()
                self.assertFalse(self.remote_root.exists())

    def test_existing_symlink_within_root_is_rejected_before_writes(self):
        self.remote_root.mkdir()
        parent=self.remote_root/'worker-dir'; parent.mkdir()
        self.payload_overrides={'worker':parent/'worker.py'}
        self.simulated_symlinks={parent}
        with self.assertRaisesRegex(ValueError,'Symlink'): self.preflight()
        self.assertFalse((parent/'worker.py').exists())
        self.assertFalse((self.remote_root/'workspace').exists())
        self.assertFalse((self.remote_root/'jobs').exists())

    def test_symlink_at_root_or_managed_path_is_rejected(self):
        self.remote_root.mkdir()
        for linked in [self.remote_root,self.remote_root/'workspace',self.remote_root/'jobs',self.remote_root/'executor_worker.py']:
            with self.subTest(linked=linked):
                self.simulated_symlinks={linked}
                with self.assertRaisesRegex(ValueError,'Symlink'): self.preflight()
                self.assertFalse((self.remote_root/'executor_worker.py').exists())
                self.assertFalse((self.remote_root/'workspace').exists())
                self.assertFalse((self.remote_root/'jobs').exists())

    def test_real_symlink_escape_is_rejected_when_supported(self):
        self.remote_root.mkdir(); outside=self.root/'outside'; outside.mkdir()
        link=self.remote_root/'linked-worker'
        try: os.symlink(outside,link,target_is_directory=True)
        except (OSError,NotImplementedError) as error: self.skipTest('Host does not permit symlink creation: '+str(error))
        self.payload_overrides={'worker':link/'executor_worker.py'}
        with self.assertRaisesRegex(ValueError,'Symlink'): self.preflight()
        self.assertFalse((outside/'executor_worker.py').exists())
        self.assertFalse((self.remote_root/'workspace').exists())
        self.assertFalse((self.remote_root/'jobs').exists())

    def test_resolved_escape_is_rejected_before_writes(self):
        worker=self.remote_root/'executor_worker.py'
        self.resolve_overrides={worker:self.root/'outside'/'executor_worker.py'}
        with self.assertRaisesRegex(ValueError,'Resolved path outside'): self.preflight()
        self.assertFalse(self.remote_root.exists())

    def test_existing_non_directory_parent_is_rejected_before_writes(self):
        self.remote_root.mkdir(); parent=self.remote_root/'not-a-directory'; parent.write_text('leave intact')
        self.payload_overrides={'state':parent/'jobs'}
        with self.assertRaisesRegex(ValueError,'parent is not a directory'): self.preflight()
        self.assertEqual(parent.read_text(),'leave intact')
        self.assertFalse((self.remote_root/'executor_worker.py').exists())
        self.assertFalse((self.remote_root/'workspace').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
