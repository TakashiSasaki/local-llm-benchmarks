"""Bounded research notes and verifiable pointers into saved page snapshots.

The ledger records provenance and the model's own assertions; it never
establishes that a claim follows from a source.
"""
import hashlib
import json
from pathlib import Path


class ResearchLedger:
    MAX_REQUIREMENTS = 16
    MAX_EVIDENCE = 512
    MAX_NOTE = 240

    def __init__(self, path, question):
        self.path = Path(path)
        if self.path.exists():
            raise FileExistsError('A new case must have a new ledger')
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError('invalid question')
        self.requirements = [{'id': 'R1', 'description': question, 'origin': 'user_question',
                              'status': 'open', 'claim': None, 'evidence_ids': []}]
        self.evidence = []
        self.archived_turns = []
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        obj = {'version': 1, 'scope': 'Provenance and model notes only; no semantic verification.',
               'requirements': self.requirements, 'evidence': self.evidence,
               'archived_turns': self.archived_turns}
        tmp = self.path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        tmp.replace(self.path)

    def add_requirement(self, description):
        if not isinstance(description, str) or not description.strip() or len(description) > self.MAX_NOTE:
            raise ValueError('requirement must be 1-240 characters')
        description = description.strip()
        for item in self.requirements:
            if item['description'] == description:
                return item.copy()
        if len(self.requirements) >= self.MAX_REQUIREMENTS:
            raise ValueError('requirement ledger is full')
        item = {'id': 'R' + str(len(self.requirements) + 1), 'description': description,
                'origin': 'model', 'status': 'open', 'claim': None, 'evidence_ids': []}
        self.requirements.append(item)
        self._save()
        return item.copy()

    def add_evidence(self, page, start, end, kind, section=None, query=None, mode=None):
        text = page['text']
        if (type(start) is not int or type(end) is not int or start < 0 or
                start >= end or end > len(text)):
            raise ValueError('invalid source range')
        for item in self.evidence:
            if item['page_id'] == page['id'] and item['offset'] == start and item['end'] == end:
                return item['id']
        if len(self.evidence) >= self.MAX_EVIDENCE:
            raise ValueError('evidence ledger is full')
        item = {'id': 'E' + str(len(self.evidence) + 1), 'page_id': page['id'],
                'url': page['url'], 'offset': start, 'end': end, 'section': section,
                'page_sha256': page['sha256'],
                'range_sha256': hashlib.sha256(text[start:end].encode('utf-8')).hexdigest(),
                'tool': kind, 'query': query, 'mode': mode, 'seen_by_model': False}
        self.evidence.append(item)
        self._save()
        return item['id']

    def mark_seen(self, ids):
        ids = set(ids)
        changed = False
        for item in self.evidence:
            if item['id'] in ids and not item['seen_by_model']:
                item['seen_by_model'] = True
                changed = True
        if changed:
            self._save()

    def update_requirement(self, requirement_id, status, claim=None, evidence_ids=None):
        item = next((x for x in self.requirements if x['id'] == requirement_id), None)
        if item is None:
            raise ValueError('unknown requirement')
        if status == 'open':
            if claim is not None or evidence_ids not in (None, []):
                raise ValueError('an open requirement cannot assert evidence')
            item.update(status='open', claim=None, evidence_ids=[])
        elif status == 'candidate':
            if not isinstance(claim, str) or not claim.strip() or len(claim) > self.MAX_NOTE:
                raise ValueError('candidate claim must be 1-240 characters')
            if (not isinstance(evidence_ids, list) or not evidence_ids or len(evidence_ids) > 5 or
                    not all(isinstance(x, str) for x in evidence_ids)):
                raise ValueError('candidate needs 1-5 evidence IDs')
            known = {x['id']: x for x in self.evidence}
            if any(eid not in known or not known[eid]['seen_by_model'] for eid in evidence_ids):
                raise ValueError('evidence must exist and have been shown to the model')
            item.update(status='candidate', claim=claim.strip(), evidence_ids=list(dict.fromkeys(evidence_ids)))
        else:
            raise ValueError('status must be open or candidate')
        self._save()
        return {**item, 'caveat': 'Model assertion only; evidence and meaning are not automatically verified.'}

    def note_archived(self, turns):
        if any(type(x) is not int or x < 0 for x in turns):
            raise ValueError('invalid archived turn')
        self.archived_turns = sorted(set(self.archived_turns).union(turns))
        self._save()

    def read_evidence(self, evidence_id, pages):
        item = next((x for x in self.evidence if x['id'] == evidence_id), None)
        if item is None or not item['seen_by_model']:
            raise ValueError('evidence is unknown or not yet shown')
        page = pages.get(item['page_id'])
        if page is None or page['url'] != item['url']:
            raise ValueError('saved source page is unavailable')
        text = page['text']
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != item['page_sha256']:
            raise ValueError('saved source page hash mismatch')
        content = text[item['offset']:item['end']]
        if hashlib.sha256(content.encode('utf-8')).hexdigest() != item['range_sha256']:
            raise ValueError('saved source range hash mismatch')
        return {'evidence_id': item['id'], 'page_id': item['page_id'], 'url': item['url'],
                'offset': item['offset'], 'end': item['end'], 'section': item['section'],
                'page_sha256': item['page_sha256'], 'range_sha256': item['range_sha256'],
                'content': content,
                'scope': 'Exact saved text; it may not support the model claim.'}

    def relevant_excerpts(self, pages, max_entries=2, max_characters=3200):
        """Re-expose bounded source text linked by the model to candidate requirements."""
        ids = list(dict.fromkeys(eid for req in self.requirements if req['status'] == 'candidate'
                                 for eid in req['evidence_ids']))
        included, errors, used = [], [], 0
        for eid in ids:
            try:
                entry = self.read_evidence(eid, pages)
            except ValueError as exc:
                errors.append({'evidence_id': eid, 'error': str(exc)})
                continue
            if len(included) >= max_entries or used + len(entry['content']) > max_characters:
                continue
            included.append(entry)
            used += len(entry['content'])
        return {'excerpts': included, 'total_linked_evidence': len(ids),
                'not_included': len(ids) - len(included), 'errors': errors,
                'scope': 'Exact untrusted source text; relevance and correctness are not verified.'}

    def inspect(self, start=0):
        if type(start) is not int or start < 0 or start > len(self.evidence):
            raise ValueError('invalid evidence index')
        end = min(start + 8, len(self.evidence))
        return {'requirements': self.requirements, 'evidence': self.evidence[start:end],
                'next_evidence_index': end if end < len(self.evidence) else None,
                'archived_turns': self.archived_turns,
                'scope': 'Evidence exposure and model assertions only, not proof of correctness.'}

    def context(self):
        """Compact, deterministic metadata; full ledger is always saved separately."""
        requirements = []
        for item in self.requirements:
            requirements.append({'id': item['id'], 'description': item['description'][:120],
                                 'description_truncated': len(item['description']) > 120,
                                 'status': item['status'], 'claim': item['claim'],
                                 'evidence_ids': item['evidence_ids']})
        cited = {eid for item in self.requirements for eid in item['evidence_ids']}
        selected = [x for x in self.evidence if x['id'] in cited]
        selected += [x for x in self.evidence[-8:] if x['id'] not in cited]
        evidence = [{k: x[k] for k in ('id', 'page_id', 'offset', 'end', 'seen_by_model')}
                    for x in selected]
        return {'requirements': requirements, 'evidence': evidence,
                'evidence_total': len(self.evidence),
                'evidence_not_shown': len(self.evidence) - len(evidence),
                'archived_turns': self.archived_turns,
                'scope': 'Untrusted notes and source pointers, not verified facts. Use inspect_ledger for more.'}
