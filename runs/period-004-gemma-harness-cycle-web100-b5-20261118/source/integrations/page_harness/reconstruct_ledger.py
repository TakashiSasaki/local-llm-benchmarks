"""Reconstruct source ranges from saved tool events, without changing the run."""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from local_llm_benchmarks import study


def reconstruct(run_id):
    run = study.resolve_run(run_id)
    study.validate_run(run)
    cases = []
    for directory in sorted((run / 'raw').iterdir()):
        if not directory.is_dir() or not (directory / 'events.json').exists():
            continue
        entries = []
        for event in study.load(directory / 'events.json'):
            name, result = event.get('name'), event.get('result', {})
            if event.get('type') != 'tool' or not isinstance(result, dict):
                continue
            common = {'turn': event.get('turn'), 'tool': name,
                      'page_id': result.get('page_id'), 'url': result.get('url')}
            if name == 'read_page' and 'content' in result:
                entries.append({**common, 'offset': result.get('offset'),
                                'end': result.get('end'), 'section': result.get('section')})
            elif name == 'find_in_page':
                for hit in result.get('matches', []):
                    entries.append({**common, 'query': result.get('query'),
                                    'mode': result.get('mode'), 'offset': hit.get('offset'),
                                    'read_offset': hit.get('read_offset'),
                                    'section': hit.get('section')})
        cases.append({'id': directory.name, 'entries': entries})
    out = {'scope': ('Ranges produced by read/find tool events. They do not establish '
                     'claim correctness, and an unfinished case may end before its '
                     'last tool result is shown to the model.'),
           'cases': cases}
    target = run / 'summaries' / 'source-ledger-reconstructed-v1.json'
    if target.exists():
        raise FileExistsError('Preserve the existing ledger: ' + str(target))
    study.save(target, out)
    print(run_id, 'cases', len(cases), 'ranges', sum(len(x['entries']) for x in cases))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    reconstruct(parser.parse_args().run)
