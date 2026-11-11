"""Explicitly open a new experiment period; never starts inference or copies old scores."""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.periods import validate_id
from local_llm_benchmarks.study import ROOT, load, save, now


def start(period, title, root=ROOT):
    validate_id(period)
    data = load(root / 'experiments/registry.json')
    if data.get('active_period') or period in data['periods']:
        raise ValueError('Close the active period first; never reuse an existing period ID')
    folder = root / 'experiments' / period
    folder.mkdir(exist_ok=False)
    for sub in ['configs', 'environment', 'reports']:
        (folder / sub).mkdir()
    (folder / 'README.md').write_text(f'# {title}\n\nPeriod: `{period}`. New run IDs must start with `{period}-`. Record environment and comparability decisions before inference. Results remain in `runs/` with explicit period membership.\n', encoding='utf-8')
    data['periods'][period] = {'title': title, 'status': 'open', 'opened_at_utc': now(), 'directory': 'experiments/' + period}
    data['active_period'] = period
    save(root / 'experiments/registry.json', data)
    return folder


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--id', required=True)
    p.add_argument('--title', required=True)
    a = p.parse_args()
    print(start(a.id, a.title))
