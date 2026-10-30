"""Probe the official Hermes stdio bridge, then register the verified command in Codex."""
import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import tomllib

ROOT = Path(__file__).resolve().parent
install = json.loads((ROOT / 'installation.json').read_text(encoding='utf-8'))
env = dict(os.environ, HERMES_HOME=install['hermes_home'], PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
stderr_path = ROOT / 'logs' / 'mcp-probe.stderr.log'
responses = queue.Queue()
with stderr_path.open('w', encoding='utf-8') as stderr:
    child = subprocess.Popen([install['hermes_launcher'], 'mcp-serve'], cwd=install['workspace'], env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                             text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
    def reader():
        for line in child.stdout:
            responses.put(line)
        responses.put(None)
    threading.Thread(target=reader, daemon=True).start()
    def send(message):
        child.stdin.write(json.dumps(message) + '\n')
        child.stdin.flush()
    def request(identifier, method, params):
        send({'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params})
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            line = responses.get(timeout=max(.1, deadline-time.monotonic()))
            if line is None:
                raise RuntimeError('MCP process exited; inspect ' + str(stderr_path))
            message = json.loads(line)
            if message.get('id') == identifier:
                if 'error' in message:
                    raise RuntimeError(str(message['error']))
                return message['result']
        raise TimeoutError(method)
    try:
        init = request(1, 'initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                      'clientInfo': {'name': 'hermes-local-setup-probe', 'version': '1.0'}})
        send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        tools = request(2, 'tools/list', {})['tools']
        names = [tool['name'] for tool in tools]
        expected = {'conversations_list', 'conversation_get', 'messages_read', 'attachments_fetch',
                    'events_poll', 'events_wait', 'messages_send', 'channels_list',
                    'permissions_list_open', 'permissions_respond'}
        if set(names) != expected:
            raise RuntimeError('Unexpected MCP tool surface: ' + str(names))
        reads = {}
        for identifier, name in [(3, 'conversations_list'), (4, 'channels_list')]:
            result = request(identifier, 'tools/call', {'name': name, 'arguments': {}})
            if result.get('isError'):
                raise RuntimeError('Read-only probe failed: ' + name)
            reads[name] = result
        report = {'verified_at': datetime.datetime.now().astimezone().isoformat(),
                  'server': init, 'tools': names, 'read_only_calls': reads,
                  'model_required': False, 'gateway_required_for_reads': False}
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.terminate()
            child.wait(timeout=10)

(ROOT / 'runs' / 'mcp-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
config_path = Path.home() / '.codex' / 'config.toml'
before = config_path.read_bytes()
before_text = before.decode('utf-8-sig')
before_config = tomllib.loads(before_text)
if 'hermes' in before_config.get('mcp_servers', {}):
    raise RuntimeError('hermes MCP entry already exists; probe passed but registration not overwritten')
settings = {'command': install['hermes_launcher'], 'args': ['mcp-serve'], 'cwd': install['workspace'],
            'enabled': True, 'startup_timeout_sec': 60, 'tool_timeout_sec': 120,
            'env': {'HERMES_HOME': install['hermes_home'], 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}}
lines = ['', '[mcp_servers.hermes]']
for key, value in settings.items():
    if key != 'env':
        lines.append(key + ' = ' + json.dumps(value, ensure_ascii=False))
lines += ['', '[mcp_servers.hermes.env]']
lines += [key + ' = ' + json.dumps(value, ensure_ascii=False) for key, value in settings['env'].items()]
after_text = before_text.rstrip('\r\n') + '\n' + '\n'.join(lines) + '\n'
after_config = tomllib.loads(after_text)
assert after_config['mcp_servers']['hermes'] == settings
del after_config['mcp_servers']['hermes']
assert after_config == before_config, 'Existing configuration would change'
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup = ROOT / 'runs' / ('codex-config-before-hermes-' + stamp + '.toml')
backup.write_bytes(before)
temporary = config_path.with_name('config.toml.hermes-setup.tmp')
if temporary.exists():
    raise RuntimeError('Temporary configuration already exists')
temporary.write_bytes(after_text.encode('utf-8'))
os.replace(temporary, config_path)
report['codex_config'] = str(config_path)
report['codex_config_backup'] = str(backup)
report['registered'] = True
(ROOT / 'runs' / 'mcp-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'mcp_probe': 'passed', 'tool_count': len(names), 'read_only_calls': list(reads),
                  'registered': True, 'backup': str(backup)}, ensure_ascii=False))
