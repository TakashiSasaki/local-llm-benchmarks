"""Independently reconcile cross-study rows with saved grades, responses and speed trials.

No model inference, tool execution or generated HumanEval code is run here.
"""
import hashlib
import json
import math
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def relative(base, value):
    return (ROOT / base).parent.joinpath(value).resolve().relative_to(ROOT).as_posix()


def verify():
    d = read('reports/comprehensive/results.json')
    for name, sha in d['sources'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    base_path = 'reports/20261031-empero-qwen38-iq3m-64k/matrix-data.json'
    baseline = {m['key']: m for m in read(base_path)['models']}
    parent_ids = set()
    period_index=ROOT/'experiments/period-001/runs.json'
    period_ids=set(read(period_index.relative_to(ROOT))['run_ids']) if period_index.exists() else None
    for path in (ROOT / 'runs').glob('*/manifest.json'):
        if period_ids is not None and path.parent.name not in period_ids:
            continue
        m = read(path.relative_to(ROOT))
        if m['benchmark'] in ['quantization-mtp', 'mtp-speed-only'] and not m.get('config', {}).get('pilot'):
            parent_ids.add(path.parent.name)
    assert {r['id'] for r in d['rows'] if not r['id'].startswith('baseline-')} == parent_ids
    assert {r['id'][9:] for r in d['rows'] if r['id'].startswith('baseline-')} == set(baseline)
    seen = set()
    complete_conditions = 0
    for r in d['rows']:
        assert (ROOT / r['evidence']).is_file()
        assert r['context'] == 65536 and r['max_output'] == 64000
        assert r['kv_k'] == r['kv_v'] == 'f16' and 'b11960' in r['runtime']
        if r['kind'] == 'speed-only':
            assert not r['conditions']
        for key, c in r['conditions'].items():
            suite, mode = key.split('_')
            if r['id'].startswith('baseline-'):
                es = baseline[r['id'][9:]]['cases'][suite]
                expected = {relative(base_path, e[mode + '_raw']): (e['id'], e[mode]['passed']) for e in es}
            else:
                child = r['id'] + '-' + ('humaneval' if suite == 'he' else suite) + '-' + mode
                grade_path = f'runs/{child}/summaries/' + ('cases.json' if suite == 'he' else 'bfcl-cases.json')
                es = read(grade_path) if (ROOT / grade_path).exists() else []
                expected = {f"runs/{child}/raw/{(e.get('id') or e['task_id']).replace('/', '_')}.json": (e.get('id') or e['task_id'], e['passed']) for e in es}
                mp = ROOT / 'runs' / child / 'manifest.json'
                state = read(mp.relative_to(ROOT))['status'] if mp.exists() else 'not-started'
                assert c['complete'] == (state == 'complete' and len(es) == c['expected'])
            assert {x['raw']: (x['id'], x['passed']) for x in c['cases']} == expected
            assert c['saved'] == len(expected) and c['expected'] == (80 if suite == 'bfcl' else 20)
            assert c['passed_saved'] == sum(passed for _, passed in expected.values())
            if c['complete']:
                assert c['saved'] == c['expected'] and c['score'] == c['passed_saved']
                complete_conditions += 1
            else:
                assert c['score'] is None, 'Partial condition acquired a full-suite score'
            tokens = milliseconds = timed_cases = caps = unknown = errors = empty_passes = 0
            for item in c['cases']:
                assert item['raw'] not in seen, 'A referenced response was counted twice'
                seen.add(item['raw'])
                raw = read(item['raw'])
                response = raw.get('response', {})
                assert raw['request']['max_tokens'] == item['request_max_tokens'] == 64000
                choice = (response.get('choices') or [{}])[0]
                assert item['completion_tokens'] == response.get('usage', {}).get('completion_tokens')
                assert item['finish_reason'] == choice.get('finish_reason')
                t = response.get('timings', {})
                assert item['decode_tokens'] == t.get('predicted_n') and item['decode_ms'] == t.get('predicted_ms')
                if t.get('predicted_n') is not None and t.get('predicted_ms'):
                    tokens += t['predicted_n']
                    milliseconds += t['predicted_ms']
                    timed_cases += 1
                caps += item['finish_reason'] == 'length'
                unknown += item['completion_tokens'] is None
                errors += raw.get('http_status', 200) == 500
                msg = choice.get('message', {})
                empty_passes += item['passed'] and 'choices' in response and not (msg.get('content') or msg.get('tool_calls'))
            assert (caps, unknown, errors, empty_passes, timed_cases) == (c['caps_known'], c['unknown_statistics'], c['parser_errors'], c['passed_without_final'], c['decode_statistics_cases'])
            if timed_cases:
                assert math.isclose(c['benchmark_decode_tok_s'], tokens / (milliseconds / 1000))
        if r['fixed_speed']:
            speed_path = pathlib.PurePosixPath(r['fixed_speed']['evidence']).parent
            cases = read(str(speed_path / 'summaries/speed-cases.json'))
            assert len(cases) == 9
            rates = []
            drafted = 0
            for path in sorted((ROOT / speed_path / 'raw').glob('*.json')):
                raw = read(path.relative_to(ROOT))
                if raw.get('warmup') or 'warmup' in path.name:
                    continue
                request = raw['request']
                assert request['n_predict'] == 256 and request['ignore_eos'] is True
                t = raw['response']['timings']
                assert t['predicted_n'] == 256
                rates.append(t['predicted_per_second'])
                drafted += t.get('draft_n', 0)
            assert len(rates) == 9 and math.isclose(statistics.median(rates), r['fixed_speed']['tok_s'])
            assert (drafted > 0) == (r['mtp'] == 'on'), 'MTP label does not match actual draft tokens'
    assert len(seen) == d['counts']['unique_saved_responses']
    assert complete_conditions == d['counts']['complete_conditions']
    assert len(d['rows']) == d['counts']['configuration_rows']
    assert len({(r['model'], r['quantization']) for r in d['rows']}) == d['counts']['unique_model_quant_pairs_measured']
    assert len({(r['model'], r['quantization'], r['mtp']) for r in d['rows']}) == d['counts']['unique_model_quant_mtp_measured']
    for item in d['coverage']:
        for key, state in item['states'].items():
            cs = [r['conditions'][key] for r in d['rows'] if r['id'] in item['matching_rows'] and key in r['conditions']]
            expected = 'complete' if any(c['complete'] for c in cs) else 'partial' if any(c['saved'] for c in cs) else 'failed' if any(c['status'] == 'failed' for c in cs) else 'not-measured'
            assert state == expected
    result = {'passed': True, 'counts': d['counts'], 'checks': ['source hashes', 'exact parent-run and baseline inventory', 'saved grade and raw-response mapping', 'no reference double counting', 'partial score null', 'known/unknown response statistics', 'nine fixed 256-token speed trials per measured row', 'coverage states'], 'inference_or_model_code_executed': False}
    (ROOT / 'publication/comprehensive-evidence-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    verify()
