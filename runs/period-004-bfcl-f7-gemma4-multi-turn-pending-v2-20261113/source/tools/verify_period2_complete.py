"""Offline audit of all period-002 primary answers, preserving the earlier audit.

Default: inspect saved records and re-score BFCL (no model/tool function execution).
--regrade explicitly executes saved HumanEval code in the pinned Windows worker;
use the recorded Python and understand that JobObject is not a security sandbox.
"""
import argparse
import ast
import collections
import gzip
import json
import pathlib
import random
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.study import ROOT, load, sha, validate_run
from local_llm_benchmarks.bfcl import components

PERIOD = ROOT / 'experiments/period-002'
RECOVERY = 'period-002-timeout-recovery-20261110'
MODELS = ['q35-4b-base', 'q35-4b-abliterix', 'q35-9b-base',
          'q35-9b-huihui', 'q35-9b-heretic', 'q35-9b-defiant',
          'q36-35b-base', 'q36-35b-huihui']


def require(value, message):
    if not value:
        raise ValueError(message)


def case_id(row):
    return row.get('id', row.get('task_id'))


def empty_final(response):
    message = response['choices'][0]['message']
    return not bool((message.get('content') or '').strip() or message.get('tool_calls'))


def capped_no_final(response):
    return response['choices'][0]['finish_reason'] == 'length' and empty_final(response)


def capped_no_final_aware_pass(passed, response):
    """Sensitivity annotation, NOT a replacement for the pinned primary grader."""
    return bool(passed and not capped_no_final(response))


def insert_unique(mapping, identity, value):
    require(identity not in mapping, 'Duplicate canonical answer: ' + str(identity))
    mapping[identity] = value


def source_selection(plan):
    refs = [dict(r, cohort='original-7200s') for r in plan['references']]
    summary = load(ROOT / 'runs' / RECOVERY / 'summary.json')
    require(summary['outcome'] == 'passed' and summary['new_answers'] == 647,
            'Recovery is not complete')
    for model in summary['completed_models']:
        for condition in model['conditions']:
            run = condition['run']
            suite, mode = re.search(r'-(bfcl|humaneval)-(on|off)$', run).groups()
            relative = 'summaries/' + ('bfcl-cases.json' if suite == 'bfcl' else 'cases.json')
            rows = load(ROOT / 'runs' / run / relative)
            refs.append(dict(run=run, model=model['model'], suite=suite, thinking=mode,
                             cases=relative, ids=[case_id(c) for c in rows], cohort='recovery-14400s'))
    return refs


def audit(regrade=False):
    evidence = {}
    def pin(path):
        evidence[path.relative_to(ROOT).as_posix()] = sha(path)
    planpath = PERIOD / 'configs/timeout-recovery-20261110.json'
    plan = load(planpath)
    pin(planpath)
    # The 953 original answers and their source snapshots were pinned before recovery.
    for relative, digest in plan['files'].items():
        path = (ROOT / relative).resolve()
        require(path.is_relative_to(ROOT.resolve()), 'Pin escapes repository')
        require(sha(path) == digest, 'Changed checkpoint file: ' + relative)
        pin(path)
    bf, convert, bgrade = components()
    bfmap = {c['problem']['id']: c for c in bf}
    dataset = ROOT / 'datasets/humaneval/b9453e8'
    for relative, digest in load(dataset / 'manifest.json')['files'].items():
        require(sha(dataset / relative) == digest, 'Changed HumanEval dataset')
        pin(dataset / relative)
    all_he = [json.loads(s) for s in gzip.decompress((dataset / 'HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
    he = [all_he[i] for i in sorted(random.Random(42).sample(range(164), 20))]
    hemap = {p['task_id']: p for p in he}
    canonical = {'bfcl': list(bfmap), 'humaneval': list(hemap)}
    require(canonical == plan['canonical_ids'], 'Canonical selection changed')
    # Load only the pinned extractor function, never execute model-generated code here.
    extractor_path = ROOT / 'artifacts/local-llm/hermes/benchmarks/compare_models.py'
    tree = ast.parse(extractor_path.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'unwrap_code')
    namespace = {'re': re}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(extractor_path), 'exec'), namespace)
    unwrap = namespace['unwrap_code']
    pin(extractor_path)
    policy = load(ROOT / 'runs/period-002-he-policy-validation-20261102/summary.json')['policy']
    if regrade:
        from local_llm_benchmarks.humaneval_standard_windows import grade, provenance
        require(sys.version == policy['python'], 'Use recorded benchmark Python for HumanEval replay')
        require(provenance() == policy, 'HumanEval replay policy changed')
    records = {}
    sources = []
    parents = {}
    cohort_counts = collections.Counter()
    replays = 0
    for ref in source_selection(plan):
        run = ROOT / 'runs' / ref['run']
        manifest = validate_run(run)
        model, suite, mode = ref['model'], ref['suite'], ref['thinking']
        require(manifest['benchmark'] == suite and manifest['config']['model']['id'] == model
                and manifest['execution']['thinking'] == mode, 'Mislabeled source ' + run.name)
        require(manifest['status'] in ['complete', 'failed'], 'Nonterminal source')
        execution = manifest['execution']
        timeout = execution.get('api_timeout_seconds', 7200)
        require(timeout == (14400 if ref['cohort'] == 'recovery-14400s' else 7200), 'Timeout cohort mismatch')
        model_info = load(PERIOD / 'models' / (model + '.json'))
        require(manifest['config']['model']['sha256'] == model_info['sha256'], 'Model hash mismatch')
        profile = manifest['config']['profile']
        args = profile['server_args']
        placement = {'gpu_layers': args[args.index('-ngl') + 1],
                     'cpu_moe_layers': int(args[args.index('--n-cpu-moe') + 1])}
        require(profile['mtp'] == 'off' and profile['context_tokens'] == 65536
                and profile['max_tokens'] == 64000, 'Changed core inference settings')
        for flag in ['-ctk', '-ctv']:
            require(args[args.index(flag) + 1] == 'f16', 'Changed KV cache')
        rows = load(run / ref['cases'])
        require([case_id(c) for c in rows] == ref['ids'], 'Changed source case IDs')
        require({p.name for p in (run / 'raw').glob('*.json')} ==
                {cid.replace('/', '_') + '.json' for cid in ref['ids']}, 'Unaccounted raw files')
        for relative in ['manifest.json', 'source-manifest.json', ref['cases']]:
            pin(run / relative)
        if (run / 'summary.json').exists():
            pin(run / 'summary.json')
        parent_id = manifest['config']['parent_run']
        parents[parent_id] = model
        if suite == 'humaneval':
            saved_policy = load(run / 'configs/grader-policy.json')
            require(saved_policy == policy, 'Saved HumanEval policy differs')
            pin(run / 'configs/grader-policy.json')
        for c in rows:
            cid = case_id(c)
            rawpath = run / 'raw' / (cid.replace('/', '_') + '.json')
            pin(rawpath)
            raw = load(rawpath)
            request, response = raw['request'], raw['response']
            choice = response['choices'][0]
            message, usage = choice['message'], response['usage']
            require(request['max_tokens'] == min(64000, 65536 - raw['estimated_prompt_tokens'] - 32), 'Output budget differs')
            require(request['temperature'] == (0 if suite == 'bfcl' else 0.6)
                    and request['seed'] == 42 and request['cache_prompt'] is False
                    and request['chat_template_kwargs'] == {'enable_thinking': mode == 'on'}, 'Sampler differs')
            require(c['usage'] == usage and c['seconds'] == raw['seconds']
                    and c['finish_reason'] == choice['finish_reason'], 'Case/raw metadata differ')
            require(usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens'] <= 65536, 'Context accounting differs')
            require(c['reasoning_observed'] == bool(message.get('reasoning_content') or message.get('reasoning')), 'Reasoning metadata differs')
            if choice['finish_reason'] == 'length':
                require(usage['completion_tokens'] == request['max_tokens'], 'Cap accounting differs')
            if suite == 'bfcl':
                problem = bfmap[cid]
                result = bgrade(problem, response)
                for field in ['passed', 'decoded', 'decode_error']:
                    require(result[field] == c[field], 'BFCL re-score mismatch: ' + str((run.name, cid, field)))
                require(request['messages'] == problem['problem']['question'][0]
                        and request['tools'] == convert(problem), 'BFCL prompt/tool mismatch')
                sampler = dict(top_p=1, top_k=0, min_p=0, repeat_penalty=1)
            else:
                problem = hemap[cid]
                content = message.get('content') or ''
                code = unwrap(content, problem['prompt'], problem['entry_point']) if content.strip() else ''
                require(code == c['code'], 'HumanEval extractor mismatch')
                require(request['messages'][1] == {'role': 'user', 'content': problem['prompt']}, 'HumanEval prompt mismatch')
                require(bool(c['passed']) == (c['status'] == 'passed'), 'HumanEval pass/status mismatch')
                if not code:
                    require(not c['passed'] and c['status'] == 'no_final_code', 'Empty HumanEval code is not failure')
                if regrade:
                    result = grade(code, problem) if code else dict(passed=False, status='no_final_code')
                    require(result['passed'] == c['passed'] and result['status'] == c['status'], 'HumanEval replay mismatch')
                    replays += 1
                sampler = dict(top_p=0.95, top_k=20, min_p=0, presence_penalty=0, repeat_penalty=1)
            require(all(request[k] == v for k, v in sampler.items()), 'Sampler fields differ')
            row = dict(model=model, suite=suite, thinking=mode, id=cid, passed=c['passed'],
                       capped_no_final_aware_passed=capped_no_final_aware_pass(c['passed'], response),
                       status=c.get('status'), category=c.get('category'), finish_reason=choice['finish_reason'],
                       empty_final=empty_final(response), reasoning_observed=c['reasoning_observed'],
                       decode_error=c.get('decode_error'), seconds=raw['seconds'],
                       completion_tokens=usage['completion_tokens'], prompt_tokens=usage['prompt_tokens'],
                       decode_tokens=response['timings']['predicted_n'], decode_ms=response['timings']['predicted_ms'],
                       legacy_replay_passed=c.get('legacy_replay', {}).get('passed'),
                       raw=rawpath.relative_to(ROOT).as_posix(), raw_sha256=sha(rawpath), run=run.name,
                       api_timeout_seconds=timeout, cohort=ref['cohort'], placement=placement)
            insert_unique(records, (model, suite, mode, cid), row)
            cohort_counts[ref['cohort']] += 1
        if (run / 'summary.json').exists():
            summary = load(run / 'summary.json')
            require(summary['attempted'] == len(rows), 'Summary attempt count differs')
            score_field = 'passed' if 'passed' in summary else 'passed_saved'
            require(summary[score_field] == sum(c['passed'] for c in rows), 'Summary score differs')
            if manifest['status'] == 'complete':
                require(summary['expected'] == len(rows), 'Completed source expected count differs')
                require(summary['total_seconds'] == sum(c['seconds'] for c in rows)
                        and summary['median_seconds'] == statistics.median(c['seconds'] for c in rows), 'Summary latency differs')
                require(summary['output_cap_hits'] == sum(c['finish_reason'] == 'length' for c in rows), 'Summary caps differ')
                require(summary['reasoning_observed_cases'] == sum(c['reasoning_observed'] for c in rows), 'Summary reasoning differs')
                if suite == 'humaneval':
                    require(summary['legacy_replay_passed'] == sum(c['legacy_replay']['passed'] for c in rows), 'Summary legacy score differs')
                else:
                    for category, counts in summary['categories'].items():
                        selected = [c for c in rows if c['category'] == category]
                        require(counts == {'passed': sum(c['passed'] for c in selected), 'attempted': len(selected)}, 'Summary category counts differ')
        sources.append(dict(ref, count=len(rows), parent_run=parent_id, placement=placement, api_timeout_seconds=timeout))
    universe = {(m, s, t, cid) for m in MODELS for s, ids in canonical.items() for t in ['off', 'on'] for cid in ids}
    require(set(records) == universe and len(records) == 1600, 'Incomplete/extra canonical records')
    require(dict(cohort_counts) == {'original-7200s': 953, 'recovery-14400s': 647}, 'Wrong cohort counts')
    conditions = []
    for model in MODELS:
        for suite in ['bfcl', 'humaneval']:
            for mode in ['off', 'on']:
                cases = [records[model, suite, mode, cid] for cid in canonical[suite]]
                categories = {cat: dict(saved=sum(c['category'] == cat for c in cases),
                                       passed=sum(c['passed'] and c['category'] == cat for c in cases))
                              for cat in sorted({c['category'] for c in cases if c['category']})}
                conditions.append(dict(model=model, suite=suite, thinking=mode, saved=len(cases), expected=len(cases),
                    collection='complete', passed_saved=sum(c['passed'] for c in cases),
                    capped_no_final_aware_passed=sum(c['capped_no_final_aware_passed'] for c in cases),
                    output_caps=[c['id'] for c in cases if c['finish_reason'] == 'length'],
                    empty_final_cases=sum(c['empty_final'] for c in cases), decode_error_cases=sum(bool(c['decode_error']) for c in cases),
                    reasoning_observed_cases=sum(c['reasoning_observed'] for c in cases),
                    total_api_seconds=sum(c['seconds'] for c in cases), median_api_seconds=statistics.median(c['seconds'] for c in cases),
                    completion_tokens=sum(c['completion_tokens'] for c in cases),
                    aggregate_decode_tps=sum(c['decode_tokens'] for c in cases)/(sum(c['decode_ms'] for c in cases)/1000),
                    legacy_replay_passed=sum(c['legacy_replay_passed'] for c in cases) if suite == 'humaneval' else None,
                    categories=categories, source_runs=list(dict.fromkeys(c['run'] for c in cases)),
                    timeout_cohorts=dict(collections.Counter(c['api_timeout_seconds'] for c in cases))))
    performance = []
    for parent_id, model in parents.items():
        parent = ROOT / 'runs' / parent_id
        validate_run(parent)
        model_verification = load(parent / 'configs/model-file-verification.json')
        model_info = load(PERIOD / 'models' / (model + '.json'))
        require(model_verification['verified'] is True and model_verification['sha256'] == model_info['sha256']
                and model_verification['bytes'] == model_info['bytes'], 'Served model verification differs')
        runtime = load(parent / 'configs/runtime-file-verification.json')
        require(runtime['sha256'] == '81f65c6681d66099e5d48757aa2c050ba958dc43816e584f0bb4181eb7c910d8', 'Served runtime hash differs')
        for relative in ['manifest.json', 'source-manifest.json', 'configs/model-file-verification.json', 'configs/runtime-file-verification.json']:
            pin(parent / relative)
        memory = load(parent / 'summaries/memory.json')
        samples = [json.loads(line) for line in (parent / 'logs/memory.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        require(len(samples) == memory['sample_count'], 'Memory sample count differs')
        for field, out, func in [('process_working_set_bytes', 'peak_process_working_set_bytes', max),
                                 ('process_private_bytes', 'peak_process_private_bytes', max),
                                 ('available_ram_bytes', 'minimum_available_ram_bytes', min),
                                 ('gpu_used_mib', 'peak_gpu_used_mib_system_total', max),
                                 ('gpu_temperature_c', 'peak_gpu_temperature_c', max)]:
            require(func(s[field] for s in samples if s[field] is not None) == memory[out], 'Memory aggregation differs')
        for relative in ['summaries/memory.json', 'logs/memory.jsonl', 'configs/server-command.json', 'configs/cleanup.json']:
            pin(parent / relative)
        require(load(parent / 'configs/cleanup.json')['server_stopped'], 'Owned server cleanup not recorded')
        speed = ROOT / 'runs' / (parent_id + '-speed')
        entry = dict(model=model, run=parent_id, memory=memory,
                     placement=next(s['placement'] for s in sources if s['parent_run'] == parent_id),
                     memory_scope='Parent model-run lifetime, sampled approximately every 3 seconds; system-total GPU, not per-condition maxima')
        if speed.exists():
            probes = [load(p) for p in sorted((speed / 'raw').glob('*.json')) if p.name != 'warmup.json']
            sp = load(speed / 'summary.json')
            require(len(probes) == sp['attempted'] == 9, 'Speed probe count differs')
            require(all(p['request']['n_predict'] == 256 and p['request']['ignore_eos'] is True and p['request']['seed'] == 42 for p in probes), 'Speed probe protocol differs')
            median = statistics.median(p['response']['timings']['predicted_per_second'] for p in probes)
            require(median == sp['median_decode_tokens_per_second'], 'Speed probe median differs')
            require(sp['aggregate_decode_tokens_per_second'] == sum(p['response']['timings']['predicted_n'] for p in probes) /
                    (sum(p['response']['timings']['predicted_ms'] for p in probes) / 1000), 'Speed probe aggregate differs')
            require(sp['draft_tokens'] == sp['accepted_draft_tokens'] == 0, 'MTP probe evidence differs')
            entry.update(fixed256_median_decode_tps=median, speed_run=speed.name)
            for p in [speed / 'summary.json', *sorted((speed / 'raw').glob('*.json'))]:
                pin(p)
        else:
            entry.update(fixed256_median_decode_tps=None, speed_run=None)
        performance.append(entry)
    cases = list(records.values())
    caps = [c for c in cases if c['finish_reason'] == 'length']
    return dict(schema_version=1, period='period-002', scope='All unique primary capability answers; probes, controls and replay excluded',
                saved_answers=1600, planned_answers=1600, uncollected_answers=0, conditions_complete=32,
                bfcl_regraded=1280, humaneval_records_verified=320, humaneval_replayed=replays, new_inference_answers=0,
                grader_policy=policy['policy'], audit_python=sys.version, cohort_counts=dict(cohort_counts),
                output_cap_count=len(caps), output_caps=caps,
                capped_no_final_primary_passes=[c for c in caps if c['empty_final'] and c['passed']],
                sensitivity_policy='Preserve pinned primary scores; secondary capped-no-final-aware scores treat finish_reason=length with neither final content nor tool_calls as failure. Not an official BFCL metric.',
                latency_scope='Successful saved API responses only; excludes unsuccessful timed-out attempts, startup, warmup, grading, and idle time. Decode throughput uses summed API predicted_n / summed predicted_ms.',
                sources=sources, conditions=conditions, model_performance=performance, cases=cases, evidence_sha256=evidence)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regrade', action='store_true', help='Execute saved HumanEval code using the recorded Windows worker; not an OS sandbox')
    parser.add_argument('--report', type=pathlib.Path)
    parser.add_argument('--verify-report', type=pathlib.Path, help='Verify a previously generated report and every evidence hash before auditing')
    args = parser.parse_args()
    if args.verify_report:
        previous = load(args.verify_report)
        for relative, digest in previous['evidence_sha256'].items():
            path = (ROOT / relative).resolve()
            require(path.is_relative_to(ROOT.resolve()) and sha(path) == digest, 'Changed completed evidence: ' + relative)
    result = audit(args.regrade)
    if args.verify_report:
        for field in ['sources', 'conditions', 'model_performance', 'cases', 'evidence_sha256']:
            # JSON roundtrip normalizes integer dictionary keys (timeout cohorts).
            require(json.loads(json.dumps(result[field])) == previous[field], 'Changed report field: ' + field)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['saved_answers', 'conditions_complete', 'bfcl_regraded', 'humaneval_records_verified', 'humaneval_replayed', 'output_cap_count', 'cohort_counts']}))
