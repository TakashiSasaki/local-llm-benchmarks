"""One local-only, synthetic long-context compaction probe using a saved page.

The historical turns are fixtures, not claims that the model generated them.
No SearXNG/Crawl4AI or other external endpoint is contacted.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import socket
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(pathlib.Path(__file__).parent)]
from local_llm_benchmarks import memory_windows as memory, study
from context_manager import add_context, archive_candidates, archived_turn_page, public_messages
from ledger import ResearchLedger
from page_harness import PageStore
import run_probe as probe

SOURCE = ROOT / 'runs/period-004-gemma-mtp-page-harness-targeted-20261118/raw/web_search_4/pages/page_4.json'
SOURCE_TEXT_SHA = 'd7005bbc2579b9ebffe9cea7f113b3c1c0abdc9fedde32136d13acf0b4b37e78'
MODEL_SHA = '85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87'
ASSISTANT_SHA = '5fe3a6c5ebd2f241d9f27d2529fbf023564a6ac4c3db501fa7837887f37ece77'
QUESTION = ('According to the saved Connecticut tourism page, which lake is called the largest '
            'natural body of water and which is called the largest man-made reservoir? '
            'Give both names and the source URL. Do not infer which lake is largest overall.')


def file_sha(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def tool_call(name, args, call_id):
    return {'id': call_id, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}


def main(run_id):
    run = study.resolve_run(run_id)
    manifest = study.load(run / 'manifest.json')
    if manifest['status'] != 'planned' or (run / 'source-manifest.json').exists():
        raise ValueError('Use a new planned run')
    study.assert_run_writable(run)
    probe.snapshot_harness_sources(run)
    manifest.update(status='running', started_at=study.now())
    study.save(run / 'manifest.json', manifest)
    server = None
    monitor = None
    stop = threading.Event()
    guard_hits = []
    try:
        if shutil.disk_usage(ROOT).free < 32 * 1024**3:
            raise RuntimeError('C: free-space reserve not met')
        source = study.load(SOURCE)
        source_hash = hashlib.sha256(source['text'].encode('utf-8')).hexdigest()
        if source_hash != SOURCE_TEXT_SHA or source['sha256'] != SOURCE_TEXT_SHA:
            raise ValueError('saved source text changed')
        args = list(study.load(ROOT / '.local/humaneval-plus-20261117/gemma-mtp-fullctx-command-20261118.json')['args'])
        model = pathlib.Path(args[args.index('-m') + 1])
        assistant = pathlib.Path(args[args.index('--spec-draft-model') + 1])
        if file_sha(model) != MODEL_SHA or file_sha(assistant) != ASSISTANT_SHA:
            raise ValueError('model or assistant hash mismatch')
        args[args.index('--port') + 1] = '18096'
        args[args.index('--alias') + 1] = 'gemma-page-harness'
        args[args.index('--host') + 1] = '127.0.0.1'
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', 18096)) == 0:
                raise RuntimeError('model port is already in use')
        initial = memory.snapshot(0)
        if (initial['gpu_used_mib'] is None or initial['gpu_used_mib'] > 1000 or
                initial['available_ram_bytes'] < 3 * 1024**3):
            raise RuntimeError('GPU or RAM preflight failed')
        study.save(run / 'configs/preflight.json', initial)
        study.save(run / 'configs/server-command.json', {'args': args})
        study.save(run / 'configs/probe.json', {
            'scope': 'Synthetic saved-page transcript, not BFCL or autonomous search; no external calls.',
            'source_run_path': SOURCE.relative_to(ROOT).as_posix(), 'source_text_sha256': SOURCE_TEXT_SHA,
            'model_sha256': MODEL_SHA, 'assistant_sha256': ASSISTANT_SHA, 'context': 65536,
            'threshold_fraction': 0.5, 'recent_turns': 2, 'main_thinking': True,
            'summary_thinking': False, 'summary_max_output': 2048,
            'main_max_output_per_response': 2048, 'max_main_responses': 3,
            'inference_retry': 0, 'network': 'loopback llama-server only', 'question': QUESTION})
        with (run / 'logs/server.log').open('wb') as stream:
            server = subprocess.Popen(args, cwd=pathlib.Path(args[0]).parent, stdout=stream,
                                      stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        monitor = memory.Monitor(server.pid, run / 'logs/memory.jsonl').start()

        def guard():
            low = 0
            while not stop.wait(3):
                sample = memory.snapshot(server.pid)
                low = low + 1 if sample['available_ram_bytes'] < 3 * 1024**3 else 0
                if low >= 3:
                    guard_hits.append('RAM reserve')
                    server.terminate()
                    return

        threading.Thread(target=guard, daemon=True).start()
        for _ in range(600):
            if server.poll() is not None:
                raise RuntimeError('server exited during startup')
            try:
                if probe.local_api('/health', timeout=5)['status'] == 'ok':
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise TimeoutError('server startup')
        props = probe.local_api('/props', timeout=30)
        if props['total_slots'] != 1 or props['default_generation_settings']['n_ctx'] != 65536:
            raise ValueError('unexpected served context or slot count')
        admission = memory.snapshot(server.pid)
        if (admission['gpu_used_mib'] is None or admission['gpu_used_mib'] > 7676 or
                admission['available_ram_bytes'] < 3 * 1024**3):
            raise RuntimeError('resource admission failed')
        study.save(run / 'configs/admission.json', admission)
        study.save(run / 'configs/server-props.json', props)

        case = run / 'raw/long_context'
        case.mkdir()
        store = PageStore(case / 'pages')
        page_info = store.add(source['url'], source['text'], {'source_run': SOURCE.relative_to(ROOT).as_posix()})
        page = store.pages[page_info['page_id']]
        ledger = ResearchLedger(case / 'ledger.json', QUESTION)
        requirement = ledger.add_requirement('Distinguish natural water body from man-made reservoir.')
        messages = [{'role': 'system', 'content': probe.SYSTEM_PROMPT}, {'role': 'user', 'content': QUESTION}]
        first = tool_call('search', {'query': 'Connecticut lakes'}, 'fixture-search')
        messages += [{'role': 'assistant', 'content': None, 'tool_calls': [first], '_turn': 0},
                     {'role': 'tool', 'tool_call_id': first['id'], '_turn': 0,
                      'content': json.dumps({'results': [{'title': 'Saved tourism page', 'url': source['url']}]})}]
        observed = []
        relevant = None
        before = 0
        for turn in range(1, 21):
            calls, replies = [], []
            for j in range(4):
                offset = (((turn - 1) * 4 + j) * 2400) % (len(source['text']) - 2400)
                out = store.read(page_info['page_id'], offset)
                eid = ledger.add_evidence(page, out['offset'], out['end'], 'read_page', out['section'])
                out['evidence_id'] = eid
                observed.append(eid)
                if offset <= 49207 and out['end'] > 50280:
                    relevant = eid
                call = tool_call('read_page', {'page_id': page_info['page_id'], 'offset': offset}, f'fixture-{turn}-{j}')
                calls.append(call)
                replies.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(out, ensure_ascii=False), '_turn': turn})
            messages.append({'role': 'assistant', 'content': None, 'tool_calls': calls, '_turn': turn})
            messages.extend(replies)
            if turn >= 8:
                # These are simulated past exposures, explicitly labelled in the run manifest.
                ledger.mark_seen(observed)
                if relevant and ledger.requirements[1]['status'] == 'open':
                    ledger.update_requirement(requirement['id'], 'candidate', 'This range may distinguish both types; inspect it.', [relevant])
                clean = add_context(public_messages(messages), ledger.context(), '')
                before = probe.prompt_tokens(clean, probe.tools(), thinking=True)
                if before >= 32768 and relevant:
                    break
        else:
            raise ValueError('fixture did not reach half the context with its relevant range')
        candidates = archive_candidates(messages, recent_turns=2)
        if not candidates:
            raise ValueError('no eligible complete turns to summarize')
        study.save(case / 'synthetic-transcript.json', {
            'scope': 'Simulated turns built solely from an existing saved page; no model produced these turns.',
            'messages': public_messages(messages), 'relevant_evidence_id': relevant,
            'trigger_prompt_tokens': before, 'candidate_turns': candidates})
        print(f'COMPACTION input={before} candidate_turns={len(candidates)}', flush=True)
        summary, detail = probe.summarize_turns(case, turn + 1, messages, candidates, QUESTION, ledger, '')
        proposed = set(candidates)
        ledger_view = ledger.context()
        ledger_view['archived_turns'] = sorted(proposed)
        clean = add_context(public_messages(messages, proposed), ledger_view, summary,
                            ledger.relevant_excerpts(store.pages))
        after = probe.prompt_tokens(clean, probe.tools(), thinking=True)
        if after >= before:
            raise ValueError('generated summary did not reduce prompt')
        ledger.note_archived(candidates)
        study.save(case / 'compaction-decision.json', {'trigger_prompt_tokens': before,
                   'post_compaction_prompt_tokens': after, 'threshold_tokens': 32768,
                   'detail': detail, 'summary': summary, 'relevant_evidence_id': relevant,
                   'summary_mentions_bantam': 'bantam' in summary.lower(),
                   'summary_mentions_candlewood': 'candlewood' in summary.lower(),
                   'caveat': 'Substring checks do not prove correct interpretation.'})
        print(f'COMPACTED input={after}; generating a bounded response', flush=True)
        answer = ''
        events = []
        pending = []
        for index in range(3):
            req = {'model': 'gemma-page-harness', 'messages': clean, 'tools': probe.tools(),
                   'temperature': 0.6, 'top_p': 0.95, 'top_k': 64, 'min_p': 0,
                   'repeat_penalty': 1.0, 'seed': 42, 'max_tokens': min(2048, 65536 - after - 32),
                   'chat_template_kwargs': {'enable_thinking': True}}
            if req['max_tokens'] <= 0:
                raise ValueError('no output space')
            started = time.monotonic()
            response = probe.local_api('/v1/chat/completions', req)
            study.save(case / f'fixture-model-{index:02}.json', {'request': req, 'response': response,
                       'seconds': time.monotonic() - started})
            ledger.mark_seen(pending)
            pending = []
            choice = response['choices'][0]
            msg = choice['message']
            calls = msg.get('tool_calls') or []
            events.append({'index': index, 'finish_reason': choice.get('finish_reason'),
                           'tool_names': [x.get('function', {}).get('name') for x in calls]})
            study.save(case / 'fixture-events.json', events)
            if not calls:
                answer = (msg.get('content') or '').strip()
                break
            clean.append(msg)
            for call in calls:
                name = call['function']['name']
                try:
                    raw_args = call['function']['arguments']
                    params = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    if name == 'inspect_ledger':
                        out = ledger.inspect(params['start'])
                    elif name == 'read_archived_turn':
                        out = archived_turn_page(messages, proposed, params['turn'], params['offset'])
                    elif name == 'read_page':
                        out = store.read(params['page_id'], params['offset'])
                        eid = ledger.add_evidence(store.pages[out['page_id']], out['offset'], out['end'], name, out['section'])
                        out['evidence_id'] = eid
                        pending.append(eid)
                    elif name == 'read_evidence':
                        out = ledger.read_evidence(params['evidence_id'], store.pages)
                        pending.append(params['evidence_id'])
                    elif name == 'find_in_page':
                        out = store.find(params['page_id'], params['query'])
                        for hit in out['matches']:
                            eid = ledger.add_evidence(store.pages[out['page_id']], hit['excerpt_offset'], hit['excerpt_end'],
                                                      name, hit['section'], out['query'], out['mode'])
                            hit['evidence_id'] = eid
                            pending.append(eid)
                    elif name == 'page_outline':
                        out = store.outline(params['page_id'], params['start'])
                    elif name == 'add_requirement':
                        out = ledger.add_requirement(params['description'])
                    elif name == 'update_requirement':
                        out = ledger.update_requirement(params['requirement_id'], params['status'], params.get('claim'), params.get('evidence_ids'))
                    else:
                        out = {'error': 'External search/open is unavailable in this saved-page fixture.'}
                except (KeyError, ValueError, TypeError) as exc:
                    out = {'error': type(exc).__name__ + ': ' + str(exc)[:300]}
                clean.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(out, ensure_ascii=False)})
                events.append({'index': index, 'tool': name, 'result': out})
            study.save(case / 'fixture-events.json', events)
            clean[0] = add_context([{'role': 'system', 'content': probe.SYSTEM_PROMPT}], ledger.context(), summary,
                                   ledger.relevant_excerpts(store.pages))[0]
            after = probe.prompt_tokens(clean, probe.tools(), thinking=True)
        result = {'outcome': 'passed' if answer else 'partial', 'answer': answer,
                  'answer_mentions_bantam': 'bantam' in answer.lower(),
                  'answer_mentions_candlewood': 'candlewood' in answer.lower(),
                  'trigger_prompt_tokens': before, 'post_compaction_prompt_tokens': detail.get('post_compaction_prompt_tokens', None),
                  'model_responses': len([x for x in events if 'finish_reason' in x]),
                  'scope': 'One synthetic saved-page probe; substring checks are not proof of accuracy.'}
        result['post_compaction_prompt_tokens'] = study.load(case / 'compaction-decision.json')['post_compaction_prompt_tokens']
        study.save(case / 'result.json', result)
        study.save(run / 'summary.json', result)
        manifest.update(status='complete', completed_at=study.now())
        print('RESULT ' + json.dumps(result, ensure_ascii=False), flush=True)
    except BaseException as exc:
        manifest.update(status='failed', error=type(exc).__name__ + ': ' + str(exc)[:500], failed_at=study.now())
        raise
    finally:
        stop.set()
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        if monitor:
            study.save(run / 'summaries/memory.json', monitor.stop())
        study.save(run / 'configs/cleanup.json', {'server_stopped': server is None or server.poll() is not None,
                                                  'resource_guard': guard_hits})
        study.save(run / 'manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    main(parser.parse_args().run)
