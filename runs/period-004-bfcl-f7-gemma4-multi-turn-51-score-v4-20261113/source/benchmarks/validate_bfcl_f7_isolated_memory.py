"""Synthetic official BFCL memory backend controls in a private workspace."""
import os,pathlib
from unittest.mock import patch
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.memory_kv import MemoryAPI_kv
    from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.memory_rec_sum import MemoryAPI_rec_sum
    from sentence_transformers import SentenceTransformer
    local=str(ROOT/'.local/bfcl-f7-minilm-1110a24')
    with patch('sentence_transformers.SentenceTransformer',
               lambda *a,**k:SentenceTransformer(local,device='cpu',local_files_only=True)):
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.memory_vector import MemoryAPI_vector,ENCODER_DIM
    assert ENCODER_DIM==384
    root=ROOT/'.local/validation/bfcl-f7-isolated-memory-20261113'
    root.mkdir(parents=True,exist_ok=False)
    cases=[(MemoryAPI_kv,'kv','core_memory_add',{'key':'probe','value':'synthetic'}),
           (MemoryAPI_rec_sum,'rec_sum','memory_append',{'text':'synthetic'}),
           (MemoryAPI_vector,'vector','core_memory_add',{'text':'synthetic'})]
    for cls,name,method,arguments in cases:
        folder=(root/name).resolve();folder.mkdir();backend=cls()
        backend._load_scenario({'model_result_dir':folder,'test_id':f'memory_{name}_prereq_0','scenario':'probe'})
        result=getattr(backend,method)(**arguments)
        assert 'error' not in result
        backend._flush_memory_to_local_file()
        files=[p.resolve() for p in folder.rglob('*.json')]
        assert files and all(p.is_relative_to(folder) for p in files)
        print(name,'passed; snapshots:',len(files),flush=True)

if __name__=='__main__':main()
