"""Install case-scoped allowlists around pinned BFCL's serial scoring entrypoints.

This does not change the upstream checker or make it a general OS sandbox.
UnsupportedCall inherits BaseException so upstream's Exception handler cannot
convert a guard stop into a model error.
"""
from functools import wraps


def names_from_entry(entry):
    docs = entry.get('function')
    if not isinstance(docs, list) or not docs:
        raise RuntimeError('Cannot score: case function documents are missing')
    docs = list(docs)
    missed = entry.get('missed_function', {})
    if not isinstance(missed, dict):
        raise RuntimeError('Cannot score: invalid missed-function mapping')
    for group in missed.values():
        if not isinstance(group, list):
            raise RuntimeError('Cannot score: invalid missed-function list')
        docs.extend(group)
    names = set()
    for doc in docs:
        if not isinstance(doc, dict) or not isinstance(doc.get('name'), str) or not doc['name']:
            raise RuntimeError('Cannot score: invalid function document')
        names.add(doc['name'])
    return names


def install_case_allowlists(eval_runner):
    """Wrap two upstream serial entrypoints; fail closed if called twice."""
    for attr in ('_evaluate_single_multi_turn_entry', '_evaluate_single_agentic_entry'):
        original = getattr(eval_runner, attr)
        if getattr(original, '_case_allowlist_wrapper', False):
            raise RuntimeError('Scoring allowlist wrapper already installed')

        @wraps(original)
        def wrapped(handler, *args, _original=original, **kwargs):
            # In both pinned f7 entrypoints prompt_entry is argument 4 after handler.
            entry = kwargs.get('prompt_entry') if 'prompt_entry' in kwargs else args[3]
            names = names_from_entry(entry)
            if hasattr(handler, 'allowed_names'):
                raise RuntimeError('Scoring handler retained a prior case allowlist')
            handler.allowed_names = names
            try:
                return _original(handler, *args, **kwargs)
            finally:
                del handler.allowed_names

        wrapped._case_allowlist_wrapper = True
        setattr(eval_runner, attr, wrapped)
