"""Build read-only NoCloud media and run a task-owned Debian VM."""

import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile


HERE = Path(__file__).resolve().parent
DOWNLOADS = HERE / 'downloads'


def program(name):
    executable, = (HERE / 'qemu-portable').rglob(name + '.exe')
    return executable


def make_iso(path, stage, content, network, inputs):
    library = HERE / 'pycdlib'
    if not library.exists():
        with zipfile.ZipFile(DOWNLOADS / 'pycdlib.whl') as archive:
            archive.extractall(library)
    sys.path.insert(0, str(library))
    import pycdlib

    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, rock_ridge='1.09', vol_ident='CIDATA')
    files = {'user-data': content.encode('utf-8'),
             'meta-data': f'instance-id: hep-{stage}\nlocal-hostname: humaneval-plus\n'.encode()}
    if not network:
        files['network-config'] = b'version: 2\nethernets: {}\n'
    if stage.startswith('prep'):
        wheel, = DOWNLOADS.glob('evalplus-0.3.1-*.whl')
        files[wheel.name] = wheel.read_bytes()
        source = DOWNLOADS / 'evalplus-v0.3.1-source.tar.gz'
        files['evalplus-source.tar.gz'] = source.read_bytes()
    else:
        files['samples.jsonl'] = (inputs / 'samples.jsonl').read_bytes()
        files['dataset.jsonl.gz'] = (DOWNLOADS / 'HumanEvalPlus-v0.1.10.jsonl.gz').read_bytes()
        files['SHA256SUMS'] = (inputs / 'evaluation-sha256sums').read_bytes()
    for number, (name, data) in enumerate(files.items()):
        iso.add_fp(io.BytesIO(data), len(data), iso_path=f'/F{number:07d}.BIN;1',
                   rr_name=name, joliet_path='/' + name)
    iso.write(str(path))
    iso.close()


def run_stage(stage, timeout, acceleration, prep_disk, inputs, cloud_config):
    work = HERE / stage
    work.mkdir()
    network = stage.startswith('prep')
    fresh = network and stage != 'prepare-r4'
    base = DOWNLOADS / 'debian-12-genericcloud-amd64.qcow2' if fresh else HERE / prep_disk / 'guest.qcow2'
    disk = work / 'guest.qcow2'
    image = program('qemu-img')
    subprocess.run([str(image), 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(disk)], check=True)
    if fresh:
        subprocess.run([str(image), 'resize', str(disk), '8G'], check=True)
    seed = work / 'seed.iso'
    content = cloud_config.read_text(encoding='utf-8')
    make_iso(seed, stage, content, network, inputs)
    bios, = (HERE / 'qemu-portable').rglob('bios-256k.bin')
    executable = program('qemu-system-x86_64')
    command = [str(executable), '-L', str(bios.parent), '-machine', f'q35,accel={acceleration}',
               '-m', '4096', '-smp', '2', '-display', 'none', '-monitor', 'none', '-parallel', 'none',
               '-smbios', 'type=1,serial=ds=nocloud',
               '-serial', 'file:' + str(work / 'serial.log'),
               '-drive', f'file={disk},format=qcow2,if=virtio',
               '-drive', f'file={seed},format=raw,if=virtio,readonly=on',
               '-nic', 'user,model=virtio-net-pci' if network else 'none', '-no-reboot']
    with (work / 'qemu.log').open('xb') as log:
        child = subprocess.Popen(command, cwd=executable.parent, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        (work / 'launch.json').write_text(json.dumps({'pid': child.pid, 'args': command}, indent=2), encoding='utf-8')
        print(f'{stage} VM PID {child.pid}', flush=True)
        try:
            return child.wait(timeout=timeout)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
            (work / 'exit.json').write_text(json.dumps({'pid': child.pid, 'returncode': child.returncode}),
                                             encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('evaluate-lfm3', 'evaluate-lfm3-r2', 'evaluate-lfm3-q8',
                                          'evaluate-lfm3-q8-r2', 'evaluate-lfm3-q8-chat', 'evaluate-lfm3-q8-chat-r2'))
    parser.add_argument('--prep-disk', choices=('prepare-r4',), default='prepare-r4')
    parser.add_argument('--inputs', type=Path, default=HERE / 'lfm3-inputs')
    parser.add_argument('--cloud-config', type=Path, default=HERE / 'evaluate.yaml')
    parser.add_argument('--acceleration', choices=('tcg', 'whpx:tcg'), default='whpx:tcg')
    parser.add_argument('--timeout', type=int, default=1500)
    args = parser.parse_args()
    sys.exit(run_stage(args.stage, args.timeout, args.acceleration, args.prep_disk, args.inputs, args.cloud_config))
