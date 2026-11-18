"""Wait for the continuation, verify both sources, then launch authorized scoring."""
import gzip, hashlib, json, os, pathlib, subprocess, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.study import ROOT, load, save, sha, now

OLD = ROOT / 'runs/period-004-gemma-humaneval-prefix-20261112'
NEW = ROOT / 'runs/period-004-gemma-humaneval-continuation-20261112'
AGG = ROOT / 'runs/period-004-gemma-humaneval-aggregate-20261112'
SCORE = ROOT / 'runs/period-004-gemma-humaneval-score-combined-20261112'
DATA = ROOT / '.local/official-humaneval-b9453e8/data/HumanEval.jsonl.gz'

def main():
    manifest = load(AGG / 'manifest.json')
    try:
        manifest.update(status='running', started_at=now()); save(AGG / 'manifest.json', manifest)
        while True:
            state = load(NEW / 'manifest.json')['status']
            if state == 'complete': break
            if state == 'failed': raise RuntimeError('Continuation failed; no aggregation or scoring')
            time.sleep(10)
        proof = load(NEW / 'configs/prior-evidence.json')
        assert sha(DATA) == proof['dataset_sha256']
        assert sha(OLD / 'summaries/samples.jsonl') == proof['sample_jsonl_sha256']
        problems = [json.loads(x) for x in gzip.decompress(DATA.read_bytes()).decode().splitlines()]
        combined = []
        references = []
        for run, expected in ((OLD, problems[:89]), (NEW, problems[89:])):
            sample_path = run / 'summaries/samples.jsonl'
            samples = [json.loads(x) for x in sample_path.read_text(encoding='utf-8').splitlines()]
            assert [s['task_id'] for s in samples] == [p['task_id'] for p in expected]
            for sample, problem in zip(samples, expected):
                raw = run / 'raw' / (sample['task_id'].replace('/', '_') + '.json')
                record = load(raw)
                assert record['task_id'] == sample['task_id'] and record['response']['content'] == sample['completion']
                assert record['request']['prompt'] == problem['prompt']
                raw_sha = sha(raw)
                if run == OLD: assert raw_sha == proof['raw_sha256'][sample['task_id']]
                references.append({'task_id':sample['task_id'], 'run':run.name, 'raw_sha256':raw_sha})
            assert len(list((run / 'raw').glob('*.json'))) == len(expected)
            combined.extend(samples)
        assert len(combined) == len({s['task_id'] for s in combined}) == 164
        path = AGG / 'summaries/samples.jsonl'
        assert not path.exists()
        path.write_text(''.join(json.dumps(s, ensure_ascii=False) + '\n' for s in combined), encoding='utf-8')
        save(AGG / 'configs/source-references.json', {'references': references, 'combined_sha256':sha(path), 'dataset_sha256':sha(DATA)})
        save(AGG / 'summary.json', {'outcome':'aggregated', 'samples':164, 'source_counts':{OLD.name:89, NEW.name:75}, 'duplicate_ids':0, 'missing_ids':0})
        manifest.update(status='complete', completed_at=now())
        save(AGG / 'manifest.json', manifest)
        local_app_data = os.environ.get('LOCALAPPDATA')
        if not local_app_data: raise RuntimeError('LOCALAPPDATA is required for the historical Hermes Python path')
        python = str(pathlib.Path(local_app_data) / 'Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/hermes/tools/python-3.14.9+20261021-win32-x64/python.exe')
        result = subprocess.run([python, '-B', '-X', 'utf8', str(ROOT / 'benchmarks/official_humaneval_score_combined.py')], cwd=ROOT)
        if result.returncode: raise RuntimeError('Scoring process failed: ' + str(result.returncode))
    except BaseException as exc:
        if manifest['status'] != 'complete':
            manifest.update(status='failed', failed_at=now(), error=repr(exc)); save(AGG / 'manifest.json', manifest)
        raise

if __name__ == '__main__': main()
