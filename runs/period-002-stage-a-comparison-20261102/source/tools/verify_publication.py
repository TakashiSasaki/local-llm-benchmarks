"""Verify exported evidence and regrade 1,280 BFCL outputs without inference or code execution."""
import argparse,ast,collections,copy,gzip,hashlib,io,json,pathlib,re,sys,types,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/local-llm'
MATRIX=ART/'runs/benchmark-matrix-20261030-194424'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(b):return hashlib.sha256(b).hexdigest()
def verify():
    manifest=read(ROOT/'publication/export-manifest.json');member_hashes={};file_count=0
    def archive(raw,prefix):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            assert z.testzip() is None
            for n in z.namelist():
                if n.endswith('/'):continue
                member=pathlib.PurePosixPath(n.replace('\\','/'))
                assert not member.is_absolute() and '..' not in member.parts and not re.match(r'^[A-Za-z]:',n)
                b=z.read(n);member_hashes[prefix+'!'+n]=digest(b)
                if n.endswith('.zip'):archive(b,prefix+'!'+n)
    for item in manifest['entries']:
        if item['kind']!='file':continue
        p=ROOT/item['path'];raw=p.read_bytes();assert digest(raw)==item['exported_sha256'],item['path'];file_count+=1
        if p.suffix=='.zip':archive(raw,item['path'])
    for item in manifest['entries']:
        if item['kind']=='archive_member':assert member_hashes[item['path']]==item['exported_sha256'],item['path']
    he_manifest=read(ROOT/'data/dataset-manifest.json')['humaneval']
    assert digest((ROOT/he_manifest['file']).read_bytes())=='b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef'
    assert len(gzip.decompress((ROOT/he_manifest['file']).read_bytes()).splitlines())==164
    base6=ART/'runs/bench64k-output-20261030-141002';base2=ART/'runs/legacy-models-64k-20261030-180109'
    six=read(base6/'results.json');two=read(base2/'results.json');models={**six['models'],**two['models']}
    bf=ART/'hermes/benchmarks/bfcl'
    for path,expected in six['bfcl_data_hashes'].items():assert digest((bf/path).read_bytes())==expected,path
    sys.path.insert(0,str(bf))
    registry=types.ModuleType('bfcl_eval.constants.model_config');registry.MODEL_CONFIG_MAPPING={'local':types.SimpleNamespace(underscore_to_dot=True)};sys.modules[registry.__name__]=registry
    from bfcl_eval.constants.enums import Language
    from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker
    source=(bf/'run_comparison.py').read_text(encoding='utf-8');tree=ast.parse(source)
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'check','golden'}]
    assert len(funcs)==2
    ns={'copy':copy,'Language':Language,'ast_checker':ast_checker};exec(compile(ast.Module(body=funcs,type_ignores=[]),'frozen_bfcl_functions.py','exec'),ns)
    selected=read(ART/'runs/qwen35-bfcl-thinking-20261030-194028/selected-bfcl.json');assert len(selected)==80
    assert len({c['problem']['id'] for c in selected})==80
    for c in selected:
        assert ns['check'](c,ns['golden'](c))['valid']
        assert not ns['check'](c,[{'not_a_valid_function':{}}] if c['category']=='irrelevance' else [])['valid']
    data=read(MATRIX/'matrix-data.json');assert data['conditions_complete']==32 and data['new_bfcl_on_done']==640
    result_count=0;he_count=0;table=[]
    for m in data['models']:
        key=m['key'];baseline=models[key];base=base2 if key in two['models'] else base6
        ondir=ART/'runs/qwen35-bfcl-thinking-20261030-194028' if key=='qwen-large' else MATRIX/key
        on=read(ondir/'results.json');assert len(on['on'])==80 and on['runtime']==baseline['runtime']
        assert on['profile']['model_hash']==baseline['profile']['model_hash']
        for mode in ['off','on']:
            he=baseline['human_eval'][mode];assert len(he)==20
            assert [x['task_id'] for x in he]==six['human_eval_ids']
            assert sum(x['passed'] for x in he)==m['metrics']['he_'+mode]['passed'];he_count+=20
        off_entries=baseline['bfcl'];on_entries=on['on']
        for c,a,b in zip(selected,off_entries,on_entries):
            cid=c['problem']['id'];assert a['id']==b['id']==cid
            old=read(base/(key+'-bfcl-'+cid+'.json'));new=read(ondir/('on-'+cid+'.json'))
            expected=copy.deepcopy(old['request']);expected['chat_template_kwargs']['enable_thinking']=True;expected['model']=on['profile']['profile_id']
            assert new['request']==expected
            assert old['request']['model']==expected['model'] or key=='lfm'
            assert new['request']['max_tokens']==64000
            for mode,raw,record in [('off',old,a),('on',new,b)]:
                response=raw['response'];message=response['choices'][0]['message'];decoded=[]
                try:
                    for call in message.get('tool_calls') or []:
                        params=json.loads(call['function']['arguments'])
                        if not isinstance(params,dict):raise ValueError('Non-object arguments')
                        decoded.append({call['function']['name']:params})
                    valid=ns['check'](c,decoded)['valid']
                except (ValueError,KeyError,TypeError):valid=False
                assert valid==record['passed'] and decoded==record['decoded'],(key,mode,cid)
                assert response['usage']==record['usage']
                assert response['usage']['total_tokens']<=65536
                assert bool(message.get('reasoning_content') or message.get('reasoning'))==(mode=='on')
                result_count+=1
        for mode,entries in [('off',off_entries),('on',on_entries)]:
            assert sum(x['passed'] for x in entries)==m['metrics']['bfcl_'+mode]['passed']
            assert sum(x['finish_reason']=='length' for x in entries)==m['metrics']['bfcl_'+mode]['caps']
        for suite,rows in m['cases'].items():
            for row in rows:
                for mode in ['off','on']:assert (MATRIX/row[mode+'_raw']).is_file()
        table.append({'model':m['name'],'quantization':m['quant'],'bfcl_off':m['metrics']['bfcl_off']['passed'],'bfcl_on':m['metrics']['bfcl_on']['passed']})
    assert result_count==1280 and he_count==320
    for p in ROOT.rglob('*'):
        if any(x in p.parts for x in ['.git','__pycache__','.local','.cache','.venv','node_modules']):continue
        assert not(p.is_file() and p.suffix.lower() in {'.gguf','.safetensors','.exe','.dll','.pyd','.pyc','.pth','.pt','.onnx','.bin'}),str(p)
    return {'passed':True,'python_version':sys.version,'exported_files_verified':file_count,'archive_members_verified':len(member_hashes),'official_humaneval_dataset_sha256_verified':True,'official_bfcl_dataset_hashes_verified':True,'bfcl_positive_negative_controls':80,'bfcl_raw_outputs_regraded':result_count,'humaneval_saved_records_checked':he_count,'generated_humaneval_code_executed':False,'model_inference_performed':False,'conditions_complete':32,'total_answers':1600,'bfcl_scores':table}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--report',type=pathlib.Path);args=ap.parse_args();result=verify()
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
