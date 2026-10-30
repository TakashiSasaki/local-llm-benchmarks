"""Pinned official VL quantizations and actual image API smoke tests."""
import base64, concurrent.futures, datetime, json, pathlib, re, secrets, shutil, socket, sys, urllib.request, zipfile
from PIL import Image, ImageDraw, ImageFont
import memory, server
from client import Client
from install_lfm3_runtime import ROOT, save, sha256, utc


def ranged_fetch(item):
    target=pathlib.Path(item['path'])
    if target.exists():
        assert target.stat().st_size==item['bytes'] and sha256(target)==item['sha256']
        return
    part=target.with_suffix(target.suffix+'.part')
    offset=part.stat().st_size if part.exists() else 0
    while offset<item['bytes']:
        end=min(offset+32*1024*1024,item['bytes'])-1
        req=urllib.request.Request(item['url'],headers={'Range':f'bytes={offset}-{end}'})
        with urllib.request.urlopen(req,timeout=90) as response:
            expected=f"bytes {offset}-{end}/{item['bytes']}"
            if response.status!=206 or response.headers.get('Content-Range')!=expected:raise RuntimeError('Unexpected download range')
            data=response.read(end-offset+2)
        if len(data)!=end-offset+1:raise RuntimeError('Incomplete download range')
        with part.open('ab') as stream:stream.write(data)
        offset=end+1
        print(json.dumps({'event':'download_progress','file':target.name,'mib':round(offset/1048576,1),'percent':round(100*offset/item['bytes'],1)}),flush=True)
    if sha256(part)!=item['sha256']:raise RuntimeError('SHA-256 mismatch')
    part.rename(target)
    print(json.dumps({'event':'verified','file':target.name}),flush=True)


def get(url):
    with urllib.request.urlopen(url, timeout=45) as response:
        return json.load(response)


def prepare(run):
    run.mkdir(exist_ok=True)
    metadata = get('https://huggingface.co/api/models/LiquidAI/LFM3-VL-2B-GGUF?blobs=true')
    save(run/'model-metadata.json', metadata)
    names=['LFM3-VL-2B-QAD-Q4_0.gguf','LFM3-VL-2B-Q8_0.gguf','mmproj-LFM3-VL-2B-F16.gguf']
    assets=[]
    for name in names:
        f=next(f for f in metadata['siblings'] if f['rfilename']==name)
        assets.append({'path':str(ROOT/'models'/name),'url':f"https://huggingface.co/{metadata['id']}/resolve/{metadata['sha']}/{name}",'bytes':f['size'],'sha256':f['lfs']['sha256']})
    save(run/'download-plan.json',assets)
    baseline=[]
    for p in [ROOT/'model-manifest.json',ROOT/'runtime-current.json',ROOT/'runtime-manifest.json']+list((ROOT/'profiles').glob('*.json'))+list((ROOT/'hermes/profiles').glob('*.json')):
        dest=run/'before'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        baseline.append({'path':str(p),'sha256':sha256(p)})
    save(run/'preserved-before.json',baseline)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(ranged_fetch,assets))
    manifest=json.loads((ROOT/'model-manifest.json').read_text(encoding='utf-8'))
    records=[]
    for a in assets:
        record={'repo':metadata['id'],'revision':metadata['sha'],'filename':pathlib.Path(a['path']).name,**{k:a[k] for k in ['url','bytes','sha256']},'verified_utc':utc()}
        if any(m['filename']==record['filename'] for m in manifest):raise RuntimeError('Asset already registered; inspect existing installation')
        records.append(record)
    save(ROOT/'model-manifest.json',manifest+records)
    for quant,suffix,asset in [('QAD-Q4_0','q4',assets[0]),('Q8_0','q8',assets[1])]:
        p=json.loads((ROOT/'profiles/lfm3.json').read_text(encoding='utf-8'))
        p.update(profile_id='lfm3-vl-2b-'+suffix+'-64k',model='models/'+pathlib.Path(asset['path']).name,model_hash=asset['sha256'],status='VL image verification pending',sampling={'temperature':0.1,'top_p':1.0,'top_k':50,'min_p':0.0,'repeat_penalty':1.1})
        p.pop('verification_record',None)
        p['server_args']+=['--mmproj',assets[2]['path'],'--mmproj-offload','--no-reasoning-preserve','--temp','0.1','--top-p','1','--top-k','50','--min-p','0','--repeat-penalty','1.1']
        path=ROOT/'profiles'/('lfm3-vl-'+suffix+'.json')
        if path.exists():raise RuntimeError('VL profile already exists')
        save(path,p)
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',38)
    code=secrets.token_hex(3).upper()
    im=Image.new('RGB',(768,512),'white');d=ImageDraw.Draw(im)
    for y,text in [(30,'INVOICE'),(115,'Code: '+code),(205,'Item: Apples'),(285,'Quantity: 3'),(385,'Total: 582 JPY')]:d.text((45,y),text,fill='black',font=font)
    im.save(run/'receipt.png')
    im=Image.new('RGB',(768,512),'white');d=ImageDraw.Draw(im)
    d.ellipse((45,155,215,325),fill=(220,30,30));d.rectangle((295,155,465,325),fill=(20,70,220));d.polygon([(625,140),(530,325),(720,325)],fill=(20,150,40));im.save(run/'shapes.png')
    fixtures=[{'name':'receipt','image':'receipt.png','prompt':'画像の伝票を読み取ってください。code、quantity、totalの3キーだけのJSONを返してください。codeは文字列、quantityとtotalは整数にしてください。','expected':{'code':code,'quantity':3,'total':582}},
              {'name':'shapes','image':'shapes.png','prompt':'画像を見て、左の図形、中央の色、右の図形を答えてください。left_shape、middle_color、right_shapeの3キーだけのJSONで、値は英語の小文字にしてください。','expected':{'left_shape':'circle','middle_color':'blue','right_shape':'triangle'}}]
    save(run/'fixtures.json',fixtures)
    print(json.dumps({'event':'vl_prepared','run_dir':str(run),'assets':records}),flush=True)


def trial(run,name):
    out=run/name;out.mkdir();p=server.load_profile(name);begin=datetime.datetime.now(datetime.timezone.utc);monitor=None;result={'profile':name,'tests':[]}
    def owned():
        path=ROOT/'server-state.json'
        if not path.exists():return None
        s=json.loads(path.read_text(encoding='utf-8'))
        return s if s['profile']==name and datetime.datetime.fromisoformat(s['started_utc'])>=begin else None
    try:
        server.start(name);state=owned()
        if not state:raise RuntimeError('Server ownership not confirmed')
        monitor=memory.Monitor(state['pid'],out/'memory.jsonl').start()
        props=get(p['base_url']+'/props');save(out/'server-props.json',props)
        assert props['model_alias']==p['profile_id'] and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
        result['served_context']=65536;result['load_seconds']=state['load_seconds']
        client=Client(p,out/'chat.jsonl')
        for fixture in json.loads((run/'fixtures.json').read_text(encoding='utf-8')):
            image=run/fixture['image'];encoded=base64.b64encode(image.read_bytes()).decode('ascii')
            response=client.chat([{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+encoded}},{'type':'text','text':fixture['prompt']}]}],max_tokens=4096,request_timeout=180)
            save(out/(fixture['name']+'-response.json'),response)
            content=response['message'].get('content','').strip();clean=re.sub(r'^```(?:json)?\s*|\s*```$','',content)
            try:parsed=json.loads(clean)
            except ValueError:parsed=None
            passed=response['finish_reason']=='stop' and parsed==fixture['expected']
            item={'name':fixture['name'],'passed':passed,'expected':fixture['expected'],'actual':parsed,'content':content,'finish_reason':response['finish_reason'],'usage':response['usage'],'timings':response['timings'],'wall_seconds':response['wall_seconds'],'image_sha256':sha256(image)}
            result['tests'].append(item);print(json.dumps({'event':'image_result','profile':name,**item},ensure_ascii=False),flush=True)
        log=pathlib.Path(state['log']).read_text(encoding='utf-8',errors='replace');(out/'server.log').write_text(log,encoding='utf-8')
        result['placement']=[line for line in log.splitlines() if any(s in line.lower() for s in ['offloaded','cuda0 model buffer','cuda0 kv buffer','compute buffer','vision model','clip_model_load','image processed','image embedding'])][:65]
        result['all_language_layers_on_gpu']=bool(re.search(r'offloaded (\d+)/(\1) layers to GPU',log))
        result['image_processing_log']=[line for line in log.splitlines() if 'image' in line.lower()][-25:]
        result['passed']=all(t['passed'] for t in result['tests']) and result['all_language_layers_on_gpu']
    except Exception as error:
        result['error']=repr(error);result['passed']=False
        print(json.dumps({'event':'vl_error','profile':name,'error':repr(error)}),flush=True)
    finally:
        if monitor:result['memory']=monitor.stop()
        if owned():server.stop();result['test_server_stopped']=True
        save(out/'verification.json',result)
        with zipfile.ZipFile(out/'source.zip','w',zipfile.ZIP_DEFLATED) as z:
            for path in [pathlib.Path(__file__),ROOT/'scripts/client.py',ROOT/'scripts/server.py',ROOT/'profiles'/(name+'.json'),run/'fixtures.json',run/'download-plan.json']:z.write(path,path.name)
    return result


if __name__=='__main__':
    run=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'runs'/('lfm3-vl-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    print(json.dumps({'event':'vl_run','run_dir':str(run)}),flush=True)
    prepare(run)
    results=[trial(run,name) for name in ['lfm3-vl-q4','lfm3-vl-q8']]
    preserved=json.loads((run/'preserved-before.json').read_text(encoding='utf-8'))
    unchanged=all(sha256(pathlib.Path(x['path']))==x['sha256'] for x in preserved if pathlib.Path(x['path']).name!='model-manifest.json')
    before=json.loads((run/'before/model-manifest.json').read_text(encoding='utf-8'));after=json.loads((ROOT/'model-manifest.json').read_text(encoding='utf-8'))
    report={'passed':all(r['passed'] for r in results),'results':results,'historical_profiles_unchanged':unchanged,'historical_models_unchanged':after[:len(before)]==before,'limits':['Two synthetic single-image questions per quantization; not a broad vision benchmark.','64K configured, not filled; no video, tools, Hermes or long-running stability test.','Identical F16 vision projector for both variants; 4/8bit refers to language weights.','Memory sampled after model readiness; can miss startup and instantaneous peaks.'],'evidence':str(run)}
    save(run/'report.json',report);print(json.dumps({'event':'vl_complete','run_dir':str(run),'passed':report['passed'],'results':results},ensure_ascii=False),flush=True)
