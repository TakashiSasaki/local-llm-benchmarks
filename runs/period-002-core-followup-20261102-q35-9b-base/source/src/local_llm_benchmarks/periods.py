"""Period membership without moving or rewriting immutable historical run files."""
import json
import re


def registry(root):
    path = root / 'experiments/registry.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def new_run_period(root, requested=None):
    data = registry(root)
    if data is None:
        return None  # Standalone fixture / pre-period repository compatibility.
    period = requested or data.get('active_period')
    if not period or period not in data['periods'] or data['periods'][period]['status'] != 'open':
        raise ValueError('No open experiment period. Start a new period with scripts/start_period.py; closed periods cannot receive new runs.')
    return period


def membership(root, manifest):
    data = registry(root)
    if data is None:
        return None
    period = manifest.get('period')
    if period:
        assert period in data['periods'], 'Unknown experiment period'
        assert manifest['run_id'].startswith(period + '-'), 'Run ID must carry its period prefix'
        info=data['periods'][period]
        if info['status']=='closed':
            ids=json.loads((root/info['run_index']).read_text(encoding='utf-8'))['run_ids']
            assert manifest['run_id'] in ids, 'Run was added to a closed period'
        return period
    for key, info in data['periods'].items():
        if info.get('run_index'):
            ids = json.loads((root / info['run_index']).read_text(encoding='utf-8'))['run_ids']
            if manifest['run_id'] in ids:
                return key
    raise ValueError('Unassigned run: use a period rather than mixing new measurements with the closed study')


def validate_id(value):
    if not re.fullmatch(r'period-\d{3,}', value):
        raise ValueError('Use a period ID such as period-002')
    return value
