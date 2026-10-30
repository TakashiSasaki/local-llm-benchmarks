"""Regression checks for task-visible JSON types and PS4 dynamic grading."""
import json, pathlib, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
import grading
from strict_json import equal,loads
from test_grading import golden,item

class JsonTypeTests(unittest.TestCase):
    def test_numbers_are_not_booleans(self):
        self.assertFalse(equal(loads('{"a":[false,true]}'),{'a':[0,1]}))
        self.assertTrue(equal(loads('{"a":true}'),{'a':True}))
        self.assertTrue(equal(loads('{"n":1.0}'),{'n':1}))
        self.assertTrue(equal(loads('3.35'),3.35))
        self.assertFalse(equal(loads('"0"'),0))
        self.assertTrue(loads('1e9999').is_finite())
    def test_bash_counts_reject_boolean_one(self):
        local,remote=golden('B1'); remote['counts.json']=item('{"api":2,"db":true}')
        self.assertFalse(grading.static_grade('B1',local,remote)['passed'])
        remote['counts.json']=item('{"api":2.0,"db":1.0}')
        self.assertTrue(grading.static_grade('B1',local,remote)['passed'])
    def test_nonstandard_json_constants_rejected(self):
        for const in ['NaN','Infinity','-Infinity']:
            with self.subTest(const=const):
                local,remote=golden('PS2'); local['extra.json']=item('{"x":'+const+'}')
                self.assertFalse(grading.static_grade('PS2',local,remote)['passed'])
    def test_ps4_rejects_boolean_zero(self):
        for field in ['count','total']:
            with self.subTest(field=field),tempfile.TemporaryDirectory(prefix='strict-json-') as temp:
                root=pathlib.Path(temp); (root/'validation').mkdir()
                (root/'Get-WeightedTotal.ps1').write_text('# synthetic',encoding='utf-8')
                def fake_process(args,**kwargs):
                    src=pathlib.Path(args[args.index('-InputPath')+1]); dst=pathlib.Path(args[args.index('-OutputPath')+1])
                    if src.stem in ['invalid','missing_column']: return SimpleNamespace(returncode=1)
                    value={'normal':{'count':2,'total':10},'decimal':{'count':2,'total':3.35},'empty':{'count':0,'total':0}}[src.stem]
                    if src.stem=='empty': value[field]=False
                    dst.write_text(json.dumps(value),encoding='utf-8')
                    return SimpleNamespace(returncode=0)
                with patch.object(grading,'ROOT',root),patch('subprocess.run',side_effect=fake_process):
                    result=grading.grade_ps4(root,'stub')
                self.assertFalse(result['passed'])
                self.assertFalse(next(x for x in result['cases'] if x['case']=='empty')['passed'])

if __name__=='__main__': unittest.main(verbosity=2)
