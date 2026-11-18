"""Prepare or collect bounded follow-ups to the saved BFCL f7 Gemma 4 runs."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
from types import MethodType, SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'benchmarks')]

from local_llm_benchmarks.study import create_run, load, now, save, sha

CHECKOUT = ROOT / '.local/official-bfcl-f7cf735/berkeley-function-call-leaderboard'
VENV = ROOT / '.local/bfcl-f7-isolated-20261113'
INVENTORY = ROOT / 'experiments/period-004/configs/bfcl-f7cf735-source-inventory.json'
PROVENANCE = ROOT / 'runs/period-004-bfcl-f7-gemma4-single-turn-20261112/configs/model-runtime-provenance.json'
SERVER = ROOT / 'runs/period-004-bfcl-f7-gemma4-memory-v5-20261113/configs/server-command.json'
SOURCE_AUDIT = ROOT / 'runs/period-004-gemma4-saved-evidence-audit-r2-20261115/summaries/multi-turn-exclusions.json'
PRIOR_SCORES = ROOT / 'runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v7-score-20261113/configs/evidence-verification.json'
COMMIT = 'f7cf7359b7ac615a0b294831c5ba2bc95ee4a000'
MODEL = 'local-gemma4-f7-prompt'
ALIAS = 'period4-bfcl-gemma4'
BASE = 'multi_turn_base'
WEB = ('web_search_base', 'web_search_no_snippet')
WEB_SCOPES = ('web-pilot', 'web-full')
PILOT_NUMBERS = tuple(range(0, 100, 11))
BASE_NUMBERS = (0, 7, 23, 26, 55, 90)
EXISTING_ADAPTERS = ('gemma4_adapter', 'gemma4_guarded_adapter_v5', 'call_guard_v5', 'safe_arithmetic',
                     'guarded_decoder_v5', 'guarded_executor_v5', 'guarded_scoring_v5', 'context_limit')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def offline(event, args):
    if event.startswith('socket.') and event not in ('socket.__new__', 'socket.gethostname'):
        raise RuntimeError(f'Network access forbidden in plan validation: {event}')


def verify_sources():
    require(Path(sys.executable).resolve() == (VENV / 'Scripts/python.exe').resolve(),
            'Use the existing isolated BFCL Python')
    inventory = load(INVENTORY)
    require(inventory['commit'] == COMMIT, 'unexpected upstream revision')
    package_root = VENV / 'Lib/site-packages'
    files = {name: digest for name, digest in inventory['files'].items()
             if name.endswith('.py') or name.startswith('bfcl_eval/data/')}
    installed = {p.relative_to(package_root).as_posix() for p in (package_root / 'bfcl_eval').rglob('*.py')}
    require(installed == {name for name in files if name.endswith('.py')}, 'installed Python file set changed')
    for name, digest in files.items():
        upstream = CHECKOUT / name
        require(sha(upstream) == digest, f'Pinned BFCL source hash mismatch: {name}')
        require(upstream.read_bytes().replace(b'\r\n', b'\n') ==
                (package_root / name).read_bytes().replace(b'\r\n', b'\n'),
                f'Installed BFCL source differs: {name}')
    previous = load(SERVER.parents[1] / 'source-manifest.json')['files']
    for name in EXISTING_ADAPTERS:
        relative = f'benchmarks/bfcl_f7_{name}.py'
        require(sha(ROOT / relative) == previous[relative], f'Existing local guard changed: {relative}')
    return {'package_files': len(files), 'package_python_files': len(installed), 'inventory_sha256': sha(INVENTORY)}


def snapshot_followup_sources(run):
    paths = [f'benchmarks/bfcl_f7_{name}.py' for name in (*EXISTING_ADAPTERS, 'followup', 'searxng_mcp')]
    paths.append('benchmarks/validate_bfcl_f7_searxng_mcp.py')
    paths.extend(f'src/local_llm_benchmarks/{name}.py' for name in ('study', 'periods', 'memory_windows'))
    files = {}
    for name in paths:
        destination = run / 'source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
        files[name] = sha(destination)
    save(run / 'source-manifest.json', {'files': files})


def previous_interruptions(ids):
    audit = load(SOURCE_AUDIT)['guard_interrupted']
    prior = load(PRIOR_SCORES)
    require(set(ids) == set(audit) == set(prior['excluded_guard_interrupted']), 'interrupted IDs changed')
    require(not set(ids).intersection(prior['sources']), 'one of the target IDs is already in the prior score')
    for case, info in audit.items():
        source = ROOT / 'runs' / info['source_run']
        require(source.resolve().parent == (ROOT / 'runs').resolve(), 'invalid source run path')
        require(sha(source / 'manifest.json') == info['manifest_sha256'], f'changed manifest: {case}')
        for filename, expected in info['raw_http_sha256'].items():
            path = source / 'raw/http' / filename
            require(sha(path) == expected and load(path)['case_id'] == case, f'changed original trace: {case}')
    return audit


def select_cases(scope, utils):
    categories = WEB if scope in WEB_SCOPES else (BASE,)
    entries = {category: utils.load_dataset_entry(category) for category in categories}
    available = {item['id']: item for collection in entries.values() for item in collection}
    if scope in WEB_SCOPES:
        from bfcl_f7_searxng_mcp import language_for_region
        require(len(available) == 200, 'unexpected web dataset coverage')
        numbers = PILOT_NUMBERS if scope == 'web-pilot' else range(100)
        ids = [f'{category}_{number}' for i, number in enumerate(numbers)
               for category in (WEB[::-1] if i % 2 else WEB)]
        for number in numbers:
            require(available[f'{WEB[0]}_{number}']['question'] ==
                    available[f'{WEB[1]}_{number}']['question'], 'different paired prompts')
        cases = utils.populate_initial_settings_for_web_search_test_cases([available[case] for case in ids])
        for item in cases:
            documents = {spec['name']: spec for spec in item['function']}
            require(set(documents) == {'search_engine_query', 'fetch_url_content'}, 'unexpected tool list')
            for region in documents['search_engine_query']['parameters']['properties']['region']['enum']:
                language_for_region(region)
            require(item['initial_config']['WebSearchAPI']['show_snippet'] ==
                    item['id'].startswith(WEB[0] + '_'), 'incorrect snippet setting')
        previous = {}
    else:
        require(len(available) == 200, 'unexpected base dataset coverage')
        ids = [f'{BASE}_{number}' for number in BASE_NUMBERS]
        previous = previous_interruptions(ids)
        cases = [available[case] for case in ids]
    require(len(ids) == len(set(ids)) == len(cases) and [case['id'] for case in cases] == ids,
            'duplicate or unordered planned cases')
    return entries, cases, previous


def web_tool_contract(tool):
    contract = copy.deepcopy(tool)
    search_info = contract['outputSchema']['$defs']['SearchInfo']
    if 'request_id' not in search_info.get('required', []):
        search_info['properties'].pop('request_id', None)
    return contract


def load_completed_web_cases(run_ids, allowed_ids, endpoint):
    from bfcl_f7_searxng_mcp import ENGINE
    from local_llm_benchmarks.study import resolve_run, validate_run

    completed = {}
    evidence = {}
    setups = {}
    for run_id in run_ids:
        source = resolve_run(run_id)
        manifest = validate_run(source)
        require(manifest['period'] == 'period-004' and manifest['kind'] == 'measurement'
                and manifest['status'] in ('complete', 'failed')
                and manifest['config'].get('scope') in WEB_SCOPES
                and manifest['config'].get('inference') is True
                and manifest['config'].get('commit') == COMMIT, f'Incompatible run: {run_id}')
        backend = load(source / 'configs/backend.json')
        require(backend['host'] == urlsplit(endpoint).hostname and backend['engine'] == ENGINE
                and backend['organic_only'] is True and backend['automatic_retries'] == 0,
                f'Backend conditions differ: {run_id}')
        require(load(source / 'configs/live-server.json')['files'] == load(PROVENANCE),
                f'Model provenance differs: {run_id}')
        hashes = load(source / 'source-manifest.json')['files']
        for name in (*EXISTING_ADAPTERS, 'searxng_mcp'):
            relative = f'benchmarks/bfcl_f7_{name}.py'
            require(hashes[relative] == sha(ROOT / relative), f'Adapter differs: {run_id}: {name}')
        event_path = source / 'raw/backend-events.jsonl'
        with event_path.open(encoding='utf-8') as stream:
            run_setups = [event for line in stream if (event := json.loads(line))
                          and event['operation'] == 'mcp_setup']
        require(len(run_setups) == 1, f'Missing unique MCP setup: {run_id}')
        planned_ids = set(load(source / 'configs/case-plan.json')['ordered_ids'])
        for path in sorted((source / 'raw/cases').glob('*.json')):
            case = load(path)
            case_id = case['id']
            require(case_id == path.stem and case_id in allowed_ids and case_id in planned_ids
                    and case_id not in completed, f'Duplicate or unplanned saved case: {case_id}')
            completed[case_id] = case
            evidence[case_id] = {'run_id': run_id, 'path': path.relative_to(source).as_posix(),
                                 'sha256': sha(path)}
        setups[run_id] = run_setups[0]
    return completed, evidence, setups


def install_backend(search, page_fetcher):
    from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
    from bfcl_f7_searxng_mcp import WebSearchAPI

    CLASS_FILE_PATH_MAPPING['WebSearchAPI'] = 'bfcl_f7_searxng_mcp'
    WebSearchAPI.search_backend = search
    WebSearchAPI.page_backend = page_fetcher


def offline_controls(handler, entries, cases, scoring):
    """Run the actual BFCL tool loop and scorer with in-memory web replies."""
    if WEB[0] in entries:
        from bfcl_f7_searxng_mcp import BackendStop, ENGINE

        def make_response(self, data):
            return SimpleNamespace(choices=[SimpleNamespace(text=next(responses))],
                                   usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1)), 0.01

        def fake_search(query, max_results, language):
            require((query, max_results, language) == ('fixture', 10, 'all'), 'search arguments differ')
            return [{'title': 'fixture result', 'url': 'https://example.org/', 'engine': ENGINE,
                     'content': 'FIXTURE_SNIPPET'}]

        install_backend(SimpleNamespace(search=fake_search), None)
        handler._query_prompting = MethodType(make_response, handler)
        score_handler = scoring.get_handler(MODEL)
        for category in WEB:
            item = copy.deepcopy(next(item for item in cases if item['id'].startswith(category + '_')))
            responses = iter(['[search_engine_query(keywords="fixture")]', 'fixture-answer'])
            result, metadata = handler.inference(item, include_input_log=True, exclude_state_log=False)
            require(result == [['[search_engine_query(keywords="fixture")]', 'fixture-answer']],
                    'unexpected simulated BFCL transcript')
            require(('FIXTURE_SNIPPET' in json.dumps(metadata['inference_log'])) == (category == WEB[0]),
                    'snippet exclusion did not propagate through BFCL')
            check = scoring._evaluate_single_agentic_entry(
                score_handler, item['id'], result, ['fixture-answer'], copy.deepcopy(item), MODEL, category)
            require(check['valid'], 'official agentic scorer rejected scripted answer')

        def fail_search(*args):
            raise BackendStop('fixture_backend_stop')

        install_backend(SimpleNamespace(search=fail_search), None)
        responses = iter(['[search_engine_query(keywords="fixture")]'])
        try:
            handler.inference(copy.deepcopy(cases[0]), include_input_log=True, exclude_state_log=False)
        except BackendStop:
            pass
        else:
            raise RuntimeError('upstream attempted to swallow an infrastructure stop')
        return {'fixture_tool_loop': 'passed', 'fixture_snippet_control': 'passed',
                'fixture_agentic_score': 'passed', 'fixture_backend_stop': 'passed'}
    return {'saved_multi_turn_trace_audit': 'passed', 'saved_http_traces': 29}


def verify_server(run):
    import requests
    from local_llm_benchmarks import memory_windows

    provenance = load(PROVENANCE)
    arguments = load(SERVER)['args']
    model_path = Path(arguments[arguments.index('-m') + 1])
    require(sha(Path(arguments[0])) == provenance['runtime_sha256'], 'llama-server file differs')
    require(sha(model_path) == provenance['model_sha256'], 'model file differs')
    with requests.Session() as session:
        session.trust_env = False
        with session.get('http://127.0.0.1:8089/props', timeout=5, allow_redirects=False) as response:
            response.raise_for_status()
            props = response.json()
    require(props.get('model_alias') == ALIAS and Path(props['model_path']).resolve() == model_path.resolve(),
            'provided server is not the expected Gemma 4 instance')
    require(props.get('build_info') == 'b11960-8642541b2' and props.get('total_slots') == 1
            and props['default_generation_settings']['n_ctx'] == 65536, 'server context or build differed')
    snapshot = memory_windows.snapshot(os.getpid())
    require(snapshot['available_ram_bytes'] >= 3 * 1024**3
            and snapshot['gpu_used_mib'] is not None and snapshot['gpu_used_mib'] <= 7676,
            'available RAM or GPU admission limit not met')
    save(run / 'configs/live-server.json', {'props': props, 'admission': snapshot, 'expected_args': arguments,
                                          'files': provenance})


def collect(run, handler, cases, entries, utils, scorer, reused=None):
    from bfcl_f7_context_limit import run_case
    import bfcl_f7_gemma4_adapter as adapter

    completed = dict(reused or {})
    for case in cases:
        case_id = case['id']
        adapter.CURRENT_CASE = case_id
        print(f'Collecting {case_id}', flush=True)
        result = run_case(handler, copy.deepcopy(case), True, False)
        save(run / 'raw/cases' / f'{case_id}.json', result)
        completed[case_id] = result
    totals = {}
    score_handler = scorer.get_handler(MODEL)
    for category, prompts in entries.items():
        rows = [completed[item['id']] for item in prompts if item['id'] in completed]
        destination = run / 'raw/bfcl-results' / MODEL / utils.get_directory_structure_by_category(category)
        utils.write_list_of_dicts_to_file(utils.get_file_name_by_category(category, is_result_file=True),
                                         copy.deepcopy(rows), destination)
        scorer.evaluate_task(category, run / 'raw/bfcl-results', run / 'raw/category-scores',
                             rows, MODEL, score_handler, {}, allow_missing=True)
        header_path, = (run / 'raw/category-scores').rglob(f'*_{category}_score.json')
        with header_path.open(encoding='utf-8') as stream:
            header = json.loads(next(stream))
        require(header['total_count'] == len(rows), f'category denominator differs: {category}')
        totals[category] = {'correct': header['correct_count'], 'scored': header['total_count'],
                            'dataset_total': len(prompts)}
    return totals


def record_backend(run, item, case_id=None):
    with (run / 'raw/backend-events.jsonl').open('a', encoding='utf-8') as log:
        log.write(json.dumps({'at': now(), 'case_id': case_id, **item}, ensure_ascii=False) + '\n')


def record_tool_error(run, reply, token):
    folder = ROOT / '.local/bfcl-probe-errors' / run.name
    folder.mkdir(parents=True, exist_ok=False)
    content = json.dumps(reply, ensure_ascii=False, indent=2)
    if token:
        content = content.replace(token, '[REDACTED]')
    with (folder / 'tool-result.json').open('x', encoding='utf-8') as stream:
        stream.write(content + '\n')


def probe_search(run, endpoint):
    from bfcl_f7_searxng_mcp import ENGINE, CallBudget, SearxngMCP

    budget = CallBudget(1, 'search')
    token = os.getenv('BFCL_SEARXNG_MCP_BEARER')

    client = SearxngMCP(endpoint, budget, lambda item: record_backend(run, item),
                        token, record_tool_error=lambda reply: record_tool_error(run, reply, token))
    try:
        rows = client.search('Python official documentation', 3, 'all')
        require(any(row['engine'] == ENGINE and row['url'].startswith(('https://', 'http://')) for row in rows),
                'probe returned no public web row from the selected engine')
        return {'outcome': 'search_probe_passed', 'model_requests': 0, 'page_requests': 0,
                'search_requests': budget.used, 'returned_results': len(rows), 'language_requested': 'all'}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'probe', 'collect'))
    parser.add_argument('scope', choices=(*WEB_SCOPES, 'multi-base-six'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--search-budget', type=int)
    parser.add_argument('--page-budget', type=int)
    parser.add_argument('--reuse-results-from', action='append', default=[])
    parser.add_argument('--mcp-version', help='Require this MCP build and verify its tool contract against reused runs')
    options = parser.parse_args()
    has_web = options.scope in WEB_SCOPES
    live = options.action == 'collect'
    probe = options.action == 'probe'
    endpoint = os.getenv('BFCL_SEARXNG_MCP_URL') if has_web and (live or probe) else None
    if probe and (options.scope != 'web-pilot' or not endpoint):
        parser.error('probe requires web-pilot and BFCL_SEARXNG_MCP_URL')
    if options.reuse_results_from and (probe or options.scope != 'web-full'):
        parser.error('reuse applies only to web-full planning and collection')
    if options.mcp_version and not (live and has_web):
        parser.error('pinning the MCP build requires live web collection')
    if options.reuse_results_from and not endpoint:
        endpoint = os.getenv('BFCL_SEARXNG_MCP_URL')
        if not endpoint:
            parser.error('the expected BFCL_SEARXNG_MCP_URL is needed to verify reused evidence')
    if live and has_web:
        if not endpoint or options.search_budget is None or options.search_budget < 1 or (
                options.page_budget is None or options.page_budget < 1):
            parser.error('web collection requires BFCL_SEARXNG_MCP_URL and positive explicit budgets')
    elif options.search_budget is not None or options.page_budget is not None:
        parser.error('network budgets apply only to live web collection')
    if not live and not probe:
        sys.addaudithook(offline)
    run = create_run('Gemma 4 BFCL f7 follow-up', 'bfcl',
                     {'scope': options.scope, 'commit': COMMIT, 'inference': live, 'retries': 0},
                     run_id=options.run_id, period='period-004',
                     kind='measurement' if live or probe else 'replay',
                     experiment_type='transport-integration' if probe else 'benchmark',
                     harness='mcp' if probe else None)
    manifest_path = run / 'manifest.json'
    manifest = load(manifest_path)
    manifest.update(status='running', started_at=now())
    save(manifest_path, manifest)
    mcp = None
    search_budget = page_budget = None
    try:
        verified = verify_sources()
        snapshot_followup_sources(run)
        if probe:
            summary = probe_search(run, endpoint)
            save(run / 'summary.json', summary)
            manifest.update(status='complete', completed_at=now())
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            return
        os.chdir(run / 'workspace')
        os.environ.update(BFCL_PROJECT_ROOT=str(run / 'workspace'), HF_HUB_OFFLINE='1',
                          TRANSFORMERS_OFFLINE='1', LOCAL_SERVER_ENDPOINT='127.0.0.1',
                          LOCAL_SERVER_PORT='8089', BFCL_RAW_HTTP_DIR=str(run / 'raw/http'))
        from bfcl_eval import utils
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING, ModelConfig
        from bfcl_eval.eval_checker import eval_runner
        from bfcl_f7_context_limit import install_capture
        import bfcl_f7_gemma4_adapter as adapter
        from bfcl_f7_gemma4_guarded_adapter_v5 import GuardedGemma4
        from bfcl_f7_guarded_decoder_v5 import install_guarded_decoder
        from bfcl_f7_guarded_executor_v5 import install_guarded_executor
        from bfcl_f7_guarded_scoring_v5 import install_case_allowlists

        install_guarded_decoder()
        install_guarded_executor()
        install_case_allowlists(eval_runner)
        install_capture(adapter, run / 'raw/context-failures')
        entries, cases, prior = select_cases(options.scope, utils)
        reused, reused_evidence, previous_setups = load_completed_web_cases(
            options.reuse_results_from, {case['id'] for case in cases}, endpoint)
        previous_versions = {run_id: setup['server']['version']
                             for run_id, setup in previous_setups.items()}
        versions = set(previous_versions.values())
        require(options.mcp_version or len(versions) <= 1, 'Reused cases span more than one MCP build')
        expected_mcp_version = options.mcp_version or next(iter(versions), None)
        cases = [case for case in cases if case['id'] not in reused]
        plan = {'ordered_ids': [c['id'] for c in cases], 'counts': {
            category: sum(case['id'].startswith(category + '_') for case in cases)
            for category in entries}, 'prior_interrupted': prior, 'verified_sources': verified,
            'reused_cases': reused_evidence, 'reused_mcp_versions': previous_versions,
            'expected_mcp_version': expected_mcp_version}
        save(run / 'configs/case-plan.json', plan)
        model_config = ModelConfig(model_name=ALIAS, display_name='Gemma 4 E4B Q4_K_M follow-up',
            url='https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF', org='local',
            license='see model repository', model_handler=GuardedGemma4, is_fc_model=False)
        MODEL_CONFIG_MAPPING[MODEL] = model_config
        handler = GuardedGemma4(ALIAS, 0.001, MODEL, False)
        if live:
            verify_server(run)
            if has_web:
                from bfcl_f7_searxng_mcp import ENGINE, CallBudget, PublicPageFetcher, SearxngMCP

                def record(item):
                    record_backend(run, item, adapter.CURRENT_CASE)
                    if item['operation'] == 'mcp_setup':
                        require(expected_mcp_version is None or item['server']['version'] == expected_mcp_version,
                                'MCP build differs from the expected version')
                        for run_id, setup in previous_setups.items():
                            require(web_tool_contract(item['tool']) == web_tool_contract(setup['tool']),
                                    f'MCP search tool contract differs from {run_id}')

                search_budget = CallBudget(options.search_budget, 'search')
                page_budget = CallBudget(options.page_budget, 'page')
                token = os.getenv('BFCL_SEARXNG_MCP_BEARER')
                mcp = SearxngMCP(endpoint, search_budget, record, token,
                                 record_tool_error=lambda reply: record_tool_error(run, reply, token))
                install_backend(mcp, PublicPageFetcher(page_budget, record))
                save(run / 'configs/backend.json', {'host': urlsplit(endpoint).hostname,
                     'provider': 'SearXNG MCP', 'engine': ENGINE, 'organic_only': True,
                     'search_budget': options.search_budget,
                     'page_budget_including_redirects': options.page_budget, 'automatic_retries': 0})
                mcp.connect()
            totals = collect(run, handler, cases, entries, utils, eval_runner, reused)
            summary = {'outcome': 'scored', 'categories': totals,
                       'new_cases': len(cases), 'reused_cases': len(reused)}
        else:
            fixture_cases = select_cases('web-pilot', utils)[1] if options.scope == 'web-full' else cases
            controls = offline_controls(handler, entries, fixture_cases, eval_runner)
            summary = {'outcome': 'plan_validated', 'planned_cases': len(cases), 'controls': controls,
                       'reused_cases': len(reused), 'network_calls': 0, 'model_requests': 0}
        save(run / 'summary.json', summary)
        require(load(run / 'summary.json') == summary, 'summary readback differs')
        manifest.update(status='complete', completed_at=now())
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save(run / 'summary.json', {'outcome': 'incomplete',
             'completed_case_files': len(list((run / 'raw/cases').glob('*.json')))})
        manifest.update(status='failed', failed_at=now(), error_type=type(exc).__name__)
        raise
    finally:
        if mcp is not None:
            mcp.close()
            save(run / 'summaries/backend-attempts.json', {'search': search_budget.used, 'page_http_get': page_budget.used})
        save(manifest_path, manifest)


if __name__ == '__main__':
    main()
