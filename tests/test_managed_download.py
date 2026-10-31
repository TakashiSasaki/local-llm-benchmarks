import hashlib,importlib.util,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('managed_download',ROOT/'scripts/download_model_managed.py');module=importlib.util.module_from_spec(spec)
import sys
sys.path.insert(0,str(ROOT/'scripts'));spec.loader.exec_module(module)

class ManagedDownload(unittest.TestCase):
    def test_prune_preserves_completed_model_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=pathlib.Path(tmp);data=b'example model bytes';model=directory/'demo.gguf';model.write_bytes(data)
            metadata={'filename':model.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            (directory/'demo.gguf.range-0-3').write_bytes(data[:4]);(directory/'demo.gguf.range-0-3.headers').write_text('header')
            unrelated=directory/'other.gguf.range-0-3';unrelated.write_bytes(b'keep')
            result=module.verified_prune(metadata,directory)
            self.assertEqual(result['removed_files'],2);self.assertEqual(model.read_bytes(),data);self.assertTrue(unrelated.exists())
    def test_bad_hash_keeps_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=pathlib.Path(tmp);(directory/'demo.gguf').write_bytes(b'data');cache=directory/'demo.gguf.range-0-3';cache.write_bytes(b'data')
            with self.assertRaises(AssertionError):module.verified_prune({'filename':'demo.gguf','bytes':4,'sha256':'0'*64},directory)
            self.assertTrue(cache.exists())
    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssertionError):module.verified_prune({'filename':'../escape.gguf','bytes':0,'sha256':'0'*64},pathlib.Path(tmp))

if __name__=='__main__':unittest.main()
