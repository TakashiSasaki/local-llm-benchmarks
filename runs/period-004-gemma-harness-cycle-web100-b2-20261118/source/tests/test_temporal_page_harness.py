import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'integrations/page_harness'))
from temporal import explicit_temporal_phrases,temporal_instruction

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

if __name__=='__main__':unittest.main()
