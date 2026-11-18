"""Citation exposure tests, including previously saved regression cases."""
import importlib.util
import json
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/'integrations/page_harness/page_harness.py'
spec=importlib.util.spec_from_file_location('citation_audit_harness',P)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class CitationAuditTests(unittest.TestCase):
    def setUp(self):
        self.pages={'page_1':{'url':'https://example.org/a'},'page_2':{'url':'https://example.org/b'}}
        self.evidence=[{'id':'E1','page_id':'page_1','url':'https://example.org/a','offset':10,'end':20,'seen_by_model':True},
                       {'id':'E2','page_id':'page_2','url':'https://example.org/b','offset':0,'end':10,'seen_by_model':False}]

    def audit(self,text):
        return module.audit_citations(text,self.pages,{'page_1'},{'https://notread.example/a'},self.evidence)

    def test_shown_evidence_reference_is_not_missing_url(self):
        report=self.audit('Answer (E1).')
        self.assertFalse(report['warnings'])
        self.assertEqual(report['evidence_id_references'][0]['state'],'seen')
        self.assertEqual(report['evidence_id_references'][0]['offset'],10)
        self.assertIn('does not verify',report['scope'])

    def test_fake_and_unseen_identifiers_are_flagged(self):
        report=self.audit('Answer E1, E2, E88, E_search_1, page_2, page_9.')
        self.assertEqual({x['evidence_id']:x['state'] for x in report['evidence_id_references']},
                         {'E1':'seen','E2':'unseen','E88':'unknown','E_search_1':'unknown'})
        self.assertEqual({x['page_id']:x['state'] for x in report['page_id_references']},
                         {'page_2':'opened_unread','page_9':'unknown'})
        self.assertTrue(any('evidence ID' in w for w in report['warnings']))
        self.assertTrue(any('page ID' in w for w in report['warnings']))

    def test_numeric_answer_does_not_require_inline_url(self):
        report=self.audit('7')
        self.assertTrue(report['numeric_only']);self.assertFalse(report['warnings'])
        without_sources=module.audit_citations('7',{},set(),set(),[])
        self.assertEqual(without_sources['warnings'],['No saved-page passage was read'])

    def test_older_call_without_ledger_does_not_claim_id_is_fake(self):
        report=module.audit_citations('Answer E1',self.pages,{'page_1'},set())
        self.assertEqual(report['evidence_id_references'][0]['state'],'uncheckable')
        self.assertFalse(any('evidence ID' in w for w in report['warnings']))

    def test_evidence_must_correspond_to_a_saved_page(self):
        self.evidence[0]['url']='https://other.example.org/wrong'
        report=self.audit('Answer E1')
        self.assertEqual(report['evidence_id_references'][0]['state'],'unknown_source')
        self.assertTrue(any('evidence ID' in w for w in report['warnings']))

    def test_read_page_reference_and_unknown_url_are_distinguished(self):
        self.assertFalse(self.audit('Answer page_1')['warnings'])
        report=self.audit('page_1 and https://notread.example/a')
        self.assertEqual(report['urls'][0]['state'],'search_only')
        self.assertTrue(any('URL' in w for w in report['warnings']))

    def test_old_case_with_invented_evidence_ids(self):
        case=ROOT/'runs/period-004-gemma-ledger-web100-nosnippet-b2-20261118/raw/web_search_34'
        if not case.exists():self.skipTest('saved private case is absent')
        result=json.loads((case/'result.json').read_text(encoding='utf8'))
        ledger=json.loads((case/'ledger.json').read_text(encoding='utf8'))
        pages={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (case/'pages').glob('*.json')}
        report=module.audit_citations(result['answer'],pages,set(),set(),ledger['evidence'])
        self.assertTrue(report['evidence_id_references'])
        self.assertTrue(all(x['state']=='unknown' for x in report['evidence_id_references']))


if __name__=='__main__':unittest.main()
