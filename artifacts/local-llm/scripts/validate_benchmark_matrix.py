"""Validate complete or partial dashboard data against all saved source cases."""
import csv,hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(r'C:\LocalLLM');OUT=Path(sys.argv[1]);d=json.loads((OUT/'matrix-data.json').read_text(encoding='utf-8'))
assert len(d['models'])==8 and d['conditions_expected']==32
complete=sum(s['complete'] for m in d['models'] for s in m['metrics'].values())
assert complete==d['conditions_complete']
records={}
for base in ['bench64k-output-20261030-141002','legacy-models-64k-20261030-180109']:
    p=ROOT/'runs'/base/'results.json';r=json.loads(p.read_text(encoding='utf-8'));records.update(r['models'])
old=0;new=0;audits=[]
for m in d['models']:
    source=records[m['key']]
    assert len(m['cases']['he'])==20 and len(m['cases']['bfcl'])==80
    for pair in m['cases']['he']+m['cases']['bfcl']:
        for mode in ['off','on']:
            if pair[mode]:assert pair[mode+'_raw'] and (OUT/pair[mode+'_raw']).exists()
    for mode in ['off','on']:
        for row,raw in zip(m['cases']['he'],source['human_eval'][mode]):
            assert row['id']==raw['task_id'] and row[mode]['passed']==raw['passed'] and row[mode]['usage']==raw['usage']
        assert m['metrics']['he_'+mode]['passed']==sum(x['passed'] for x in source['human_eval'][mode]);old+=20
    for row,raw in zip(m['cases']['bfcl'],source['bfcl']):
        assert row['id']==raw['id'] and row['off']['passed']==raw['passed'] and row['off']['usage']==raw['usage']
    old+=80
    on=[x['on'] for x in m['cases']['bfcl'] if x['on']];new+=len(on)
    s=m['metrics']['bfcl_on'];assert s['attempted']==len(on) and s['passed']==sum(x['passed'] for x in on)
    assert s['complete']==(len(on)==80)
    assert (s['rate'] is not None)==s['complete']
    if s['complete']:
        path=Path(d['orchestration']['qwen35_directory']) if m['key']=='qwen-large' else OUT/m['key']
        audit=path/'independent-audit.json'
        assert audit.exists(),str(audit)
        detail=json.loads(audit.read_text(encoding='utf-8'));assert detail['passed']
        audits.append({'key':m['key'],'audit':str(audit),'sha256':hashlib.sha256(audit.read_bytes()).hexdigest()})
assert old==960 and new==d['new_bfcl_on_done']
with (OUT/'conditions.csv').open(encoding='utf-8-sig',newline='') as f:csvrows=list(csv.DictReader(f))
assert len(csvrows)==32
assert sum(row['complete']=='True' for row in csvrows)==complete
truncated=json.loads((OUT/'truncations.json').read_text(encoding='utf-8'))
assert len(truncated)==sum(s['caps'] for m in d['models'] for s in m['metrics'].values())
assert all(x['completion_tokens']==64000 and x['total_tokens']<65536 for x in truncated)
if '--complete' in sys.argv:assert complete==32 and new==640 and len(audits)==8
result={'passed':True,'complete':complete==32,'condition_count':32,'conditions_complete':complete,'reused_answers':old,'new_bfcl_on_answers':new,'total_answers':old+new,'complete_model_audits':audits,'partial_scores_not_presented_as_final':True,'csv_rows':len(csvrows)}
(OUT/'matrix-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='complete_model_audits'}))
if complete==32:
    sources=['benchmark_qwen_tool_thinking.py','benchmark_model_tool_thinking.py','audit_qwen_tool_thinking.py','run_tool_benchmark_matrix.py','build_benchmark_matrix.py','benchmark_matrix_template.html','check_benchmark_matrix_ui.cjs','validate_benchmark_matrix.py']
    with zipfile.ZipFile(OUT/'dashboard-sources.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in sources:z.write(ROOT/'scripts'/name,'scripts/'+name)
        for name in ['auditor-before-model-prefix-fix.py','orchestrator-started.py']:
            if (OUT/name).exists():z.write(OUT/name,'history/'+name)
