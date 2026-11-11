"""Refresh SHA256SUMS after intentional publication changes, or validate it with --check."""
import argparse,hashlib,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def candidates():
    try:
        names=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z','--cached','--others','--exclude-standard']).decode('utf-8').split('\0')
        return sorted({ROOT/name for name in names if name and (ROOT/name).is_file() and ROOT/name!=target})
    except (OSError,subprocess.CalledProcessError):
        ignored={'.git','__pycache__','.local','.cache','.venv','venv','node_modules'}
        return sorted(p for p in ROOT.rglob('*') if p.is_file() and not ignored.intersection(p.relative_to(ROOT).parts) and p!=target)
target=ROOT/'SHA256SUMS'
if args.check:
    entries=[line.split('  ',1) for line in target.read_text(encoding='utf-8').splitlines()]
    assert {name for _,name in entries}=={p.relative_to(ROOT).as_posix() for p in candidates()},'Checksum inventory differs from publication candidates'
    for expected,name in entries:assert sha(ROOT/name)==expected,name
    print(f'{len(entries)} file checksums passed')
else:
    paths=candidates()
    target.write_text(''.join(sha(p)+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in paths),encoding='utf-8');print(f'Wrote {len(paths)} checksums')
