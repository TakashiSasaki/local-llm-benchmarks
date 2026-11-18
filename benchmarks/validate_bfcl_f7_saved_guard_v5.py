"""Offline regression of v3 guard on already saved responses; no tool calls."""
import json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from bfcl_eval._llm_response_generation import get_involved_test_entries
from bfcl_f7_gemma4_guarded_adapter_v5 import GuardedGemma4
from bfcl_f7_guarded_executor_v5 import install_guarded_executor
from bfcl_f7_guarded_decoder_v5 import install_guarded_decoder
from bfcl_f7_guarded_scoring_v5 import names_from_entry
from bfcl_f7_call_guard_v5 import UnsupportedCall
ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    _,entries=get_involved_test_entries(['multi_turn'],False)
    cases={e['id']:e for e in entries};assert len(cases)==800
    install_guarded_decoder();install_guarded_executor()
    h=GuardedGemma4('synthetic',0.001,'synthetic-saved-control',False)
    names=('period-004-bfcl-f7-gemma4-multi-turn-20261113',
           'period-004-bfcl-f7-gemma4-multi-turn-remaining-20261113',
           'period-004-bfcl-f7-gemma4-multi-turn-pending-20261113',
           'period-004-bfcl-f7-gemma4-multi-turn-pending-v2-20261113',
           'period-004-bfcl-f7-gemma4-multi-turn-pending-v3-20261113',
           'period-004-bfcl-f7-gemma4-multi-turn-pending-v4-20261113')
    total=0;blocked=[];ordinary=0;decoded=0
    for name in names:
        for p in sorted((ROOT/'runs'/name/'raw/http').glob('*.json')):
            item=json.loads(p.read_text(encoding='utf8'));case=item['case_id']
            h.allowed_names=names_from_entry(cases[case]);text=item['response']['choices'][0]['message']['content'] or ''
            try:h.decode_execute(text,False);decoded+=1
            except UnsupportedCall as e:blocked.append({'run':name,'file':p.name,'case':case,'reason':str(e)})
            except Exception:ordinary+=1
            total+=1
    assert total==1012
    assert not blocked,blocked
    print(json.dumps({'responses':total,'decoded':decoded,'ordinary_noncall_or_format':ordinary,'guard_stops':blocked}))

if __name__=='__main__':main()
