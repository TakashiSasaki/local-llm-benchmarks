"""Publish a new nine-configuration comparison without editing the historical matrix."""
import argparse,copy,csv,datetime,json,os,pathlib,statistics,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,validate_run

def rel(p,base):return os.path.relpath(p,base).replace('\\','/')
def metric(entries,expected):
    timings=[e['timings'] for e in entries if e.get('timings')];ms=sum(t.get('predicted_ms',0) for t in timings)
    return {'passed':sum(e['passed'] for e in entries),'attempted':len(entries),'expected':expected,'complete':len(entries)==expected,'rate':100*sum(e['passed'] for e in entries)/expected,'median_seconds':statistics.median(e['seconds'] for e in entries),'max_seconds':max(e['seconds'] for e in entries),'total_seconds':sum(e['seconds'] for e in entries),'tokens_per_second':sum(t.get('predicted_n',0) for t in timings)*1000/ms if ms else None,'caps':sum(e['finish_reason']=='length' for e in entries),'reasoning':sum(e['reasoning_observed'] for e in entries),'source':'IQ3_M新規測定','total_completion_tokens':sum(e['usage']['completion_tokens'] for e in entries)}

def build(study_id):
    parent=ROOT/'runs'/study_id;mfest=validate_run(parent);assert mfest['status']=='complete'
    out=ROOT/'reports'/study_id;out.mkdir(parents=True,exist_ok=True)
    original=ROOT/'artifacts/local-llm/runs/benchmark-matrix-20261030-194424';data=load(original/'matrix-data.json')
    for m in data['models']:
        for key in ['source_report','on_report','on_validation']:
            if m.get(key):m[key]=rel(original/m[key],out)
        for rows in m['cases'].values():
            for c in rows:
                for key in ['off_raw','on_raw']:
                    if c.get(key):c[key]=rel(original/c[key],out)
    config=mfest['config'];new=copy.deepcopy(next(m for m in data['models'] if m['key']=='qwen-large'))
    new.update(key='qwen-large-iq3m',quant='IQ3_M',model_file=config['model']['filename'],mode_note='GGUF enable_thinking true / false。Bartowski IQ3_MとUnsloth UD-Q3_K_Mでは変換・較正も異なります。',source_report=rel(ROOT/'reports'/(study_id+'-humaneval-off')/'index.html',out),on_report=rel(ROOT/'reports'/(study_id+'-bfcl-on')/'index.html',out),on_validation=rel(parent/'summary.json',out),memory_scope='IQ3_M新規全測定',on_error=None,metrics={},cases={},categories={})
    new['placement']='先頭30 MoE層のexpertをCPU配置';new['threads']='8'
    new['on_validation']=rel(parent/'summaries/independent-verification.json',out)
    new['mode_note']+=' HumanEval ONの1件はtype()の許可制限で主採点では不正解。同じ補助採点ポリシーでは20/20。主集計は19/20を維持。'
    memory=load(parent/'summaries/memory.json');new['on_memory']={'minimum_available_ram_gib':memory['minimum_available_ram_bytes']/2**30,'peak_system_gpu_mib':memory['peak_gpu_used_mib_system_total']}
    for suite,short,count in [('humaneval','he',20),('bfcl','bfcl',80)]:
        modes={};paths={}
        for mode in ['off','on']:
            folder=ROOT/'runs'/(study_id+'-'+suite+'-'+mode);validate_run(folder)
            entries=load(folder/('summaries/cases.json' if suite=='humaneval' else 'summaries/bfcl-cases.json'));modes[mode]=[];paths[mode]={}
            for item in entries:
                cid=item.get('id') or item['task_id'];raw_path=folder/'raw'/(cid.replace('/','_')+'.json');raw=load(raw_path);response=raw['response'];message=response['choices'][0]['message']
                item.update(timings=response.get('timings'),reasoning_characters=len(message.get('reasoning_content') or message.get('reasoning') or ''),final_content_characters=len(message.get('content') or ''),tool_call_count=len(message.get('tool_calls') or []));modes[mode].append(item);paths[mode][cid]=rel(raw_path,out)
            new['metrics'][short+'_'+mode]=metric(modes[mode],count)
        new['cases'][short]=[]
        for a,b in zip(modes['off'],modes['on']):
            cid=a.get('id') or a['task_id'];assert cid==(b.get('id') or b['task_id'])
            new['cases'][short].append({'id':cid,'category':a.get('category','he'),'off':a,'on':b,'off_raw':paths['off'][cid],'on_raw':paths['on'][cid]})
        if suite=='bfcl':
            for cat in ['simple_python','multiple','parallel','irrelevance']:new['categories'][cat]={mode:metric([e for e in entries if e['category']==cat],20) for mode,entries in modes.items()}
    cases=new['cases']['bfcl'];new.update(improved=[c['id'] for c in cases if not c['off']['passed'] and c['on']['passed']],regressed=[c['id'] for c in cases if c['off']['passed'] and not c['on']['passed']],failed_both=[c['id'] for c in cases if not c['off']['passed'] and not c['on']['passed']])
    data['models'].append(new);data.update(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),conditions_complete=36,conditions_expected=36,new_bfcl_on_done=720,new_bfcl_on_expected=720,old_result_count=1080,orchestration={'status':'complete','new_study':study_id},comparison_limitations=config['limitations'])
    save(out/'matrix-data.json',data);save(out/'orchestration.json',data['orchestration'])
    template=(ROOT/'artifacts/local-llm/scripts/benchmark_matrix_template.html').read_text(encoding='utf-8')
    template=template.replace('8構成','9構成').replace('32条件','36条件').replace('${D.conditions_complete} / 32','${D.conditions_complete} / ${D.conditions_expected}').replace('D.conditions_complete/32','D.conditions_complete/D.conditions_expected').replace('${D.new_bfcl_on_done} / 640回答','${D.new_bfcl_on_done} / ${D.new_bfcl_on_expected}回答')
    template=template.replace('HumanEvalのON／OFFとBFCLのOFF、合計960回答は保存済みのb11960測定を再利用。BFCLのON、合計640回答を追加しています。','既存8構成・1,600回答は保存済みのb11960測定を再利用。IQ3_Mの4条件・200回答を新規に追加しました。IQ3_MとUD-Q3_K_Mは配布元・較正等も異なるため、量子化形式だけの効果とは断定できません。HumanEvalの実行順序は旧測定が問題ごとのON/OFF交互、IQ3_Mがモードごとの連続実行です。')
    template=template.replace('BFCL ONのサンプル：','${m.memory_scope||\'BFCL ON\'}のサンプル：')
    page=template.replace('__BENCHMARK_DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
    audit=ROOT/'runs'/(study_id+'-he-policy-audit')/'summaries/results.json'
    if audit.exists():
        note='<section class="panel"><h2>IQ3_Mの追加測定とHermes</h2><p>IQ3_MはHumanEval OFF/ONが19/20・19/20、BFCL OFF/ONが74/80・72/80。全200回答で出力打ち切り0件でした。Hermesの実read_file・terminal・write_file往復も成功（約66秒）しています。</p><p>HumanEval ONの1件は、従来の採点器が組み込み関数type()を許可しないため失敗。同じ補助採点ポリシーではIQ3_M ONは20/20、UD-Q3_K_M ONも20/20です。上の主集計は従来ポリシーの数値を維持しています。</p><p><a href="'+rel(audit,out)+'">補助採点の全記録</a> · <a href="'+rel(ROOT/'reports'/(study_id+'-hermes')/'index.html',out)+'">Hermesの実ツール検証</a> · <a href="'+rel(ROOT/'docs/IQ3_M.md',out)+'">条件と比較の詳細</a></p></section>'
        page=page.replace('<footer class="footer">',note+'<footer class="footer">')
    (out/'index.html').write_text(page,encoding='utf-8')
    with (out/'conditions.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['model','quantization','condition','passed','attempted','median_seconds','max_seconds','total_seconds','tokens_per_second','caps']);writer.writeheader()
        for m in data['models']:
            for key,v in m['metrics'].items():writer.writerow({'model':m['name'],'quantization':m['quant'],'condition':key,**{k:v[k] for k in writer.fieldnames[3:]}})
    with (out/'truncations.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['model','quantization','suite','mode','problem','passed','completion_tokens','prompt_tokens','raw'])
        for m in data['models']:
            for suite,rows in m['cases'].items():
                for row in rows:
                    for mode in ['off','on']:
                        v=row[mode]
                        if v['finish_reason']=='length':writer.writerow([m['name'],m['quant'],suite,mode,row['id'],v['passed'],v['usage']['completion_tokens'],v['usage']['prompt_tokens'],row[mode+'_raw']])
    mfest['report']=rel(out/'index.html',ROOT);save(parent/'manifest.json',mfest)
    print(json.dumps({'report':mfest['report'],'models':9,'conditions':36,'new_answers':200}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);build(p.parse_args().study)
