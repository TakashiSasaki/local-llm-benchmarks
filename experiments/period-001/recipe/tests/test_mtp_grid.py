"""Check reference provenance and capacity exclusions using saved measurements only."""
import importlib.util,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('grid_report',ROOT/'scripts/report_mtp_grid.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)

class MtpGrid(unittest.TestCase):
    def test_dense_ngl_counts_output_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);parent=root/'parent';parent.mkdir()
            meta='configs/model.json';(root/'configs').mkdir();(root/meta).write_text(json.dumps({'model':'Dense fixture','quantization':'Q4_K_M','decoder_layers':36}),encoding='utf-8')
            cfg={'title':'Placement fixture','groups':[{'key':'dense','model_manifest':meta,'cpu_moe_layers':0,'states':['off']}],'cell_runs':{'dense-off':'fixture'}}
            (parent/'manifest.json').write_text(json.dumps({'status':'running','config':cfg}),encoding='utf-8')
            cell={'run':'fixture','status':'running','metrics':{},'truncations':[],'empty_responses':[],'timed_cases':[],'output_parser_errors':[],'config':{'profile':{'server_args':['-ngl','20']}}}
            with patch.object(report,'ROOT',root),patch.object(report,'resolve_run',return_value=parent),patch.object(report,'cell',return_value=cell):data=report.build('fixture')
            self.assertEqual(data['cells'][0]['placement_label'],'CPU 17層 / GPU 19層＋出力層（-ngl 20）')

    def test_references_keep_original_scores_and_unavailable_has_no_score(self):
        names={mtp:'20261031-qwen36-q4-mtp-64k-q4-'+mtp for mtp in ['off','on']}
        manifest_path='configs/models/qwen36-35b-q4-k-m.json'
        group={'key':'q4-control','model_manifest':manifest_path,'cpu_moe_layers':34,'load_mode':'none','role':'matched Q4 control','reference_runs':names}
        unavailable=[{'model_manifest':'not-measured.json','mtp':'on','reason':'capacity'}]
        cfg={'title':'Saved fixture','groups':[group],'cell_runs':{'q4-control-'+k:v for k,v in names.items()},'unavailable':unavailable}
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);parent=root/'parent';parent.mkdir()
            (parent/'manifest.json').write_text(json.dumps({'status':'complete','config':cfg}),encoding='utf-8')
            target=root/manifest_path;target.parent.mkdir(parents=True);target.write_bytes((ROOT/manifest_path).read_bytes())
            with patch.object(report,'ROOT',root),patch.object(report,'resolve_run',return_value=parent):data=report.build('fixture')
            self.assertEqual(len(data['cells']),2)
            self.assertTrue(all(not c['fresh_inference'] for c in data['cells']))
            self.assertEqual(data['cells'][0]['metrics']['bfcl_off']['passed'],75)
            self.assertEqual(data['unavailable'],unavailable)
            self.assertEqual(data['truncations'],[])
            self.assertAlmostEqual(data['comparisons'][0]['fixed_length_speedup'],1.29311137,places=5)
            self.assertTrue((root/'reports/fixture/index.html').exists())

if __name__=='__main__':unittest.main()
