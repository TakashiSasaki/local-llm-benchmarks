import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'integrations/page_harness'))
from temporal import explicit_temporal_phrases,temporal_instruction,temporal_evidence_advisory,temporal_url_advisory

class TemporalQuestionTests(unittest.TestCase):
    def test_explicit_as_of_is_preserved(self):
        q='Who is the party leader of the mayor (as of April 2025) in the capital of the host of the 2024 Olympics?'
        self.assertEqual(explicit_temporal_phrases(q),['as of April 2025'])
        text=temporal_instruction(q)
        self.assertIn('as of April 2025',text)
        self.assertIn('later publication may describe the past',text)
        self.assertNotIn('2024 Olympics',text)
    def test_japanese_and_ordinary_event_year(self):
        self.assertEqual(explicit_temporal_phrases('2025年4月時点の市長は誰ですか？'),['2025年4月時点'])
        self.assertEqual(explicit_temporal_phrases('Who won the 2024 Olympics?'),[])
    def test_does_not_invent_historical_answer(self):
        self.assertNotIn('Anne Hidalgo',temporal_instruction('Who was mayor as of April 2025?'))
    def test_later_date_is_a_cue_not_a_verdict(self):
        question='Who was mayor as of April 2025?'
        text='Updated in 2026: In 2025 Anne Hidalgo was mayor.'
        result=temporal_evidence_advisory(question,text,1200)
        self.assertEqual(result['latest_question_year'],2025)
        self.assertEqual(result['later_years'][0]['year'],2026)
        self.assertEqual(result['later_years'][0]['page_offset'],1200+text.index('2026'))
        self.assertIn('source reporting past facts',result['scope'])
        self.assertNotIn('contradiction',result.keys())
        self.assertIsNone(temporal_evidence_advisory(question,'It happened in 2024 and 2025.'))
    def test_multiple_dates_and_japanese_offsets(self):
        q='Results as of April 2024, and as of May 2025?'
        result=temporal_evidence_advisory(q,'Prior 2025; later 2026.')
        self.assertEqual(result['latest_question_year'],2025)
        self.assertEqual([x['year'] for x in result['later_years']],[2026])
        j='市長（2026年3月就任）';result=temporal_evidence_advisory('2025年4月時点の市長は？',j,200)
        self.assertEqual(result['later_years'][0]['page_offset'],200+j.index('2026'))
    def test_ordinary_year_or_no_later_year_does_not_create_warning(self):
        self.assertIsNone(temporal_evidence_advisory('Who won the 2024 game?','Updated in 2026.'))
        self.assertIsNone(temporal_evidence_advisory('Who was mayor as of 2025?','The record is from 2025.'))
        with self.assertRaises(ValueError):temporal_evidence_advisory('as of 2025','2026',-1)
    def test_later_valid_path_date_is_a_cue_not_publication_or_contradiction(self):
        q='Who was mayor as of April 2025?'
        url='https://www.france24.com/en/france/20260322-socialist-frontrunner-elected-paris-mayor'
        result=temporal_url_advisory(q,url)
        self.assertEqual(result['later_path_dates'][0]['path_date'],'2026-03-22')
        self.assertIn('not necessarily a publication date',result['scope'])
        self.assertIn('later source can report historical facts',result['scope'])
        self.assertNotIn('verdict',result)
    def test_url_path_rejects_invalid_earlier_query_fragment_and_long_ids(self):
        q='Who was mayor as of April 2025?'
        for url in ['https://example.org/news/20260230-story',
                    'https://example.org/news/20250322-story',
                    'https://example.org/news/story?date=20260322',
                    'https://example.org/news/story#20260322',
                    'https://example.org/news/120260322123-story',
                    'https://example.org/news/x20260322y']:
            with self.subTest(url=url):self.assertIsNone(temporal_url_advisory(q,url))
        self.assertIsNone(temporal_url_advisory('Who won the 2024 race?', 'https://example.org/20260322-story'))
    def test_url_path_percent_encoded_date_and_multiple_targets(self):
        q='Who was mayor as of April 2024 and as of April 2025?'
        x=temporal_url_advisory(q,'https://example.org/20250322/2026%30%33%32%32-story')
        self.assertEqual(x['latest_question_year'],2025)
        self.assertEqual([v['path_date'] for v in x['later_path_dates']],['2026-03-22'])
        self.assertIsNone(temporal_url_advisory(q,'not a url /20260322'))

if __name__=='__main__':unittest.main()
