"""Synthetic memory prerequisite -> retrieval -> official scorer controls."""
import copy,json,os,pathlib,sys,types
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from bfcl_f7_gemma4_guarded_adapter import GuardedGemma4
from bfcl_f7_guarded_executor import install_guarded_executor
from bfcl_f7_guarded_scoring import install_case_allowlists
import bfcl_eval

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    from sentence_transformers import SentenceTransformer
    model=str(ROOT/'.local/bfcl-f7-minilm-1110a24')
    with patch('sentence_transformers.SentenceTransformer',
        lambda *a,**k:SentenceTransformer(model,device='cpu',local_files_only=True)):
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code import memory_vector
    assert memory_vector.ENCODER_DIM==384
    from bfcl_eval.eval_checker import eval_runner
    install_guarded_executor();install_case_allowlists(eval_runner)
    root=ROOT/'.local/validation/bfcl-f7-memory-chain-20261113';root.mkdir(parents=True,exist_ok=False)
    spec=[('kv','core_memory_add(key="probe",value="synthetic")','core_memory_retrieve(key="probe")'),
          ('rec_sum','memory_append(text="synthetic")','memory_retrieve()'),
          ('vector','core_memory_add(text="synthetic")','core_memory_retrieve_all()')]
    for name,write,read in spec:
        docs=pathlib.Path(bfcl_eval.__file__).parent/f'data/multi_turn_func_doc/memory_{name}.json'
        functions=[json.loads(x) for x in docs.read_text(encoding='utf8').splitlines()]
        folder=(root/name).resolve();folder.mkdir();backend='MemoryAPI_'+name
        def entry(identifier):
            return {'id':identifier,'scenario':'customer','function':copy.deepcopy(functions),
                'question':[[{'role':'user','content':'synthetic memory control'}]],
                'involved_classes':[backend],
                'initial_config':{backend:{'model_result_dir':folder,'scenario':'customer','test_id':identifier}}}
        h=GuardedGemma4('synthetic',0.001,'synthetic-memory-'+name,False)
        responses=iter([write,'stored'])
        def fake(self,data):
            return SimpleNamespace(choices=[SimpleNamespace(text=next(responses))],
                usage=SimpleNamespace(prompt_tokens=1,completion_tokens=1)),0.01
        h._query_prompting=types.MethodType(fake,h)
        h.inference(entry('memory_'+name+'_prereq_999-customer-0'),True,False)
        files=[p.resolve() for p in folder.rglob('*.json')]
        assert files and all(p.is_relative_to(folder) for p in files)
        responses=iter([read,'synthetic'])
        result,metadata=h.inference(entry('memory_'+name+'_999-customer-0'),True,False)
        assert result==[[read,'synthetic']] and 'synthetic' in repr(metadata['inference_log'])
        scorer=GuardedGemma4('synthetic',0.001,'synthetic-memory-score-'+name,False)
        evaluation=eval_runner._evaluate_single_agentic_entry(scorer,'memory_'+name+'_999-customer-0',
            result,['synthetic'],entry('memory_'+name+'_999-customer-0'),'synthetic-memory-score-'+name,'memory_'+name)
        assert evaluation['valid'] and not hasattr(scorer,'allowed_names')
        print(name,'PASS: prerequisite snapshot, retrieval and official agentic scorer',flush=True)

if __name__=='__main__':main()
