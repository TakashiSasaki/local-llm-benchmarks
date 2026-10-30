"""Copy the study into a publication draft without changing original evidence."""
import argparse,collections,datetime,gzip,hashlib,io,json,os,pathlib,re,urllib.request,zipfile
P=pathlib.Path
ap=argparse.ArgumentParser();ap.add_argument('--destination',required=True);args=ap.parse_args()
ROOT=P(r'C:\LocalLLM');DEST=P(args.destination).resolve();BASE=DEST/'artifacts/local-llm'
DEST.mkdir(parents=True,exist_ok=True)
assert DEST.is_relative_to(ROOT/'publication'), 'Use a task-owned publication directory'
records=[];omitted=[];changes=collections.Counter()
username=os.environ.get('USERNAME') or P(os.environ['USERPROFILE']).name
host=os.environ.get('COMPUTERNAME','')
orgs=[x.name for x in P(os.environ['USERPROFILE']).glob('OneDrive - *') if x.is_dir()]
private_markers=[username]+orgs+([host] if len(host)>7 else [])
badext={'.gguf','.safetensors','.pt','.pth','.onnx','.bin','.exe','.dll','.pyd','.so','.dylib','.whl','.pyc','.ttf','.otf'}
skipnames={'.env','auth.json','config.yaml','executor-config.json','jobs-registry.json','goal-objective.md','AGENTS.md'}
def sha(b):return hashlib.sha256(b).hexdigest()
def clean(s):
    before=s
    s=re.sub(r'(?i)([a-z]:[\\/]+Users[\\/]+)'+re.escape(username)+r'(?=[\\/"\s]|$)',lambda m:m[1]+'benchmark',s)
    for org in orgs:
        for variant in [org,json.dumps(org,ensure_ascii=True)[1:-1]]:s=s.replace(variant,'OneDrive - ORGANIZATION')
    if len(host)>7:s=s.replace(host,'BENCHMARK-PC')
    if s!=before:changes['text_path_or_host_redactions']+=1
    return s
def eligible(name,size=0):
    p=pathlib.PurePosixPath(name.replace('\\','/'))
    if p.is_absolute() or '..' in p.parts:return False,'unsafe archive path'
    if any(x in p.parts for x in ['.git','__pycache__','node_modules','.venv']):return False,'cache or repository internals'
    if p.name in skipnames or p.name.startswith('.env.'):return False,'private/unrelated configuration or instruction snapshot'
    if p.suffix.lower() in badext:return False,'model/runtime/font/cache binary'
    if p.suffix.lower()=='.jinja':return False,'model-supplied template (hash and upstream model revision retained)'
    if size>20_000_000:return False,'unexpected large asset; not needed for this study'
    return True,None
def scrub_object(value,where,events):
    if isinstance(value,dict):
        out={}
        for key,item in value.items():
            name=clean(key)
            if key in {'chat_template','chat_template_tool_use','chat_template_default'} and isinstance(item,str):
                digest=sha(item.encode());out[name]='[Model-provided template omitted from publication; SHA256 '+digest+']'
                events.append({'field':where+'/'+key,'action':'omit_model_template','original_sha256':digest});changes['model_template_fields_omitted']+=1
            else:out[name]=scrub_object(item,where+'/'+key,events)
        return out
    if isinstance(value,list):return [scrub_object(v,where+'/'+str(i),events) for i,v in enumerate(value)]
    return clean(value) if isinstance(value,str) else value
def transform(data,name,depth=0):
    events=[];suffix=P(name).suffix.lower()
    if suffix=='.zip':
        assert depth<5
        target=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as zin,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.is_dir():continue
                member=item.filename.replace('\\','/');okay,reason=eligible(member,item.file_size)
                if not okay:
                    omitted.append({'path':clean(name+'!'+member),'reason':reason});continue
                original=zin.read(item);exported,inner=transform(original,name+'!'+member,depth+1)
                info=zipfile.ZipInfo(clean(member),date_time=item.date_time);info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=item.external_attr
                zout.writestr(info,exported)
                records.append({'path':clean(name+'!'+member),'kind':'archive_member','original_sha256':sha(original),'exported_sha256':sha(exported),'changed':original!=exported,'changes':inner})
        events.append({'action':'archive_repacked','note':'Members filtered/redacted; original ZIP metadata not copied.'})
        return target.getvalue(),events
    if suffix in ['.png','.jpg','.jpeg','.webp','.gz']:
        return data,events
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:
        omitted.append({'path':clean(name),'reason':'unknown binary excluded'});return None,[{'action':'exclude_unknown_binary'}]
    if suffix=='.json':
        try:
            obj=json.loads(text)
            if P(name.split('!')[-1]).name=='installation.json' and isinstance(obj,dict):
                keep={'hermes_version','hermes_commit','hermes_source','hermes_home','endpoint','server_driver','server_profile','server_profile_name','advanced_server_profile','daily_model'}
                dropped=sorted(set(obj)-keep);obj={k:v for k,v in obj.items() if k in keep}
                if dropped:events.append({'action':'installation_fields_omitted','keys':dropped})
            out=json.dumps(scrub_object(obj,'',events),ensure_ascii=False,indent=2)+'\n'
            return out.encode(),events
        except (json.JSONDecodeError,UnicodeError):pass
    if suffix=='.jsonl':
        out=[]
        try:
            for line in text.splitlines():
                if line.strip():out.append(json.dumps(scrub_object(json.loads(line),'',events),ensure_ascii=False))
            return ('\n'.join(out)+'\n').encode(),events
        except json.JSONDecodeError:pass
    cleaned=clean(text)
    if cleaned!=text:events.append({'action':'local_identity_paths_redacted'})
    return cleaned.encode(),events
selected={}
def add(path):
    if path.is_file():selected[path.relative_to(ROOT).as_posix()]=path
    elif path.is_dir():
        for f in path.rglob('*'):
            if f.is_file():selected[f.relative_to(ROOT).as_posix()]=f
for name in ['scripts','profiles','hermes/profiles','hermes/benchmarks']:add(ROOT/name)
run_names=['bench64k-output-20261030-141002','benchmark-matrix-20261030-194424','legacy-models-64k-20261030-180109','lfm3-bench-20261030-132439','lfm3-q8-20261030-130924','lfm3-setup-20261030-125557','lfm3-vl-20261030-131519','qwen35-bfcl-thinking-20261030-194028','truncation-audit-20261030-191839']
for name in run_names:add(ROOT/'runs'/name)
for name in ['README.md','comparison.md','model-manifest.json','runtime-manifest.json','runtime-current.json','run-lfm3.ps1','run-qwen.ps1','run-lfm.ps1','run-glm.ps1','hermes/model-manifest.json','hermes/installation.json','hermes/server.py','bin/b11960-cuda12.4/runtime-manifest.json']:add(ROOT/name)
for p in (ROOT/'docs').glob('benchmark-input-*.txt'):add(p)
for p in (ROOT/'docs').glob('*gguf*.json'):add(p)
audit=json.loads((ROOT/'runs/truncation-audit-20261030-191839/audit.json').read_text(encoding='utf-8'))
for path in audit['source_sha256']:
    p=P(path)
    if p.is_file() and p.is_relative_to(ROOT):
        add(p)
        prefix=p.name.removesuffix('.summary.json').removesuffix('.jsonl')
        if prefix.startswith(('PS4-','diagnostic-PS4-')):
            for sibling in p.parent.glob(prefix+'*'):add(sibling)
for pattern in ['capacity-32k-20261028-194457*','capacity-64k-20261028-213856*','*-capacity32k-20261028-194457.memory.jsonl','*-capacity64k-20261028-213856.memory.jsonl']:
    for p in (ROOT/'runs').glob(pattern):add(p)
for name in ['20261028-152903-qwen','20261028-154654-glm','20261028-155442-qwen']:add(ROOT/'workspace'/name)
for rel,path in sorted(selected.items()):
    okay,reason=eligible(rel,path.stat().st_size)
    if not okay:omitted.append({'path':clean(rel),'reason':reason});continue
    raw=path.read_bytes();exported,events=transform(raw,'artifacts/local-llm/'+rel)
    if exported is None:continue
    target=BASE/clean(rel);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(exported)
    records.append({'path':target.relative_to(DEST).as_posix(),'kind':'file','original_sha256':sha(raw),'exported_sha256':sha(exported),'bytes':len(exported),'changed':raw!=exported,'changes':events})
notes=P(os.environ['USERPROFILE'])/'.codex/skills/local-llm-agent-harness/references'
for name in ['lfm3-windows.md','lfm3-text-benchmarks.md','lfm3-64k-output-benchmarks.md','legacy-b11960-benchmarks.md','tool-thinking-matrix.md','benchmark-comparison.md']:
    raw=(notes/name).read_bytes();out,events=transform(raw,'docs/notes/'+name);dest=DEST/'docs/notes'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(out)
    records.append({'path':dest.relative_to(DEST).as_posix(),'kind':'file','original_sha256':sha(raw),'exported_sha256':sha(out),'bytes':len(out),'changed':raw!=out,'changes':events})
HE='b9453e8f1865df0a0057a1383767caa400acfbcf';BF='6ea57973c7a6097fd7c5915698c54c17c5b1b6c8'
licenses={'HumanEval-MIT.txt':f'https://raw.githubusercontent.com/openai/human-eval/{HE}/LICENSE','BFCL-Apache-2.0.txt':f'https://raw.githubusercontent.com/ShishirPatil/gorilla/{BF}/LICENSE','llama.cpp-MIT.txt':'https://raw.githubusercontent.com/ggml-org/llama.cpp/8642541b255bfb5dc39cd351a178be09013a55d6/LICENSE'}
for name,url in licenses.items():
    with urllib.request.urlopen(url) as f:raw=f.read()
    target=DEST/'third_party/licenses'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    records.append({'path':target.relative_to(DEST).as_posix(),'kind':'file','original_sha256':sha(raw),'exported_sha256':sha(raw),'bytes':len(raw),'changed':False,'upstream_url':url})
matrix=BASE/'runs/benchmark-matrix-20261030-194424'
page=(matrix/'index.html').read_text(encoding='utf-8').replace('<head>','<head><base href="./artifacts/local-llm/runs/benchmark-matrix-20261030-194424/">',1)
(DEST/'index.html').write_text(page,encoding='utf-8')
datasets={'humaneval':{'repository':'https://github.com/openai/human-eval','revision':HE,'license':'MIT','file':'artifacts/local-llm/hermes/benchmarks/HumanEval.jsonl.gz','sha256':sha((BASE/'hermes/benchmarks/HumanEval.jsonl.gz').read_bytes())},'bfcl':{'repository':'https://github.com/ShishirPatil/gorilla','revision':BF,'license':'Apache-2.0','directory':'artifacts/local-llm/hermes/benchmarks/bfcl/bfcl_eval','category_files':['BFCL_v4_simple_python.json','BFCL_v4_multiple.json','BFCL_v4_parallel.json','BFCL_v4_irrelevance.json']}}
(DEST/'data').mkdir(exist_ok=True);(DEST/'data/dataset-manifest.json').write_text(json.dumps(datasets,indent=2)+'\n',encoding='utf-8')
pub=DEST/'publication';pub.mkdir(exist_ok=True)
manifest={'created_at':datetime.datetime.now().astimezone().isoformat(),'scope':'2026-10-30 model comparison series plus its 2026-10-29 baseline and referenced historical context diagnostics','original_evidence_modified':False,'weights_and_runtime_binaries_included':False,'model_templates':'Model-provided template text and .jinja assets omitted; SHA256s/revisions retained. They can be recovered from the separately acquired exact GGUF.','historical_hashes':'Hash fields within historical evidence refer to originals before redaction. Use this manifest for exported-byte checks; do not silently treat original hashes as export hashes.','redactions':dict(changes),'omitted':omitted,'entries':records}
(pub/'export-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
suspects=[]
secret_patterns=[r'github_pat_[A-Za-z0-9_]{20,}',r'gh[pousr]_[A-Za-z0-9_]{20,}',r'hf_[A-Za-z0-9]{24,}',r'sk-(?:proj-)?[A-Za-z0-9_-]{25,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
def scan_bytes(raw,name):
    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            assert z.testzip() is None
            for entry in z.infolist():
                if not entry.is_dir():scan_bytes(z.read(entry),name+'!'+entry.filename)
        return
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError:return
    for marker in private_markers:
        if marker and marker.lower() in text.lower():suspects.append({'path':name,'kind':'local_identity_marker'})
    for pat in secret_patterns:
        if re.search(pat,text):suspects.append({'path':name,'kind':'credential_pattern'})
for p in DEST.rglob('*'):
    if p.is_file() and '.git' not in p.parts:scan_bytes(p.read_bytes(),p.relative_to(DEST).as_posix())
(pub/'privacy-scan.json').write_text(json.dumps({'passed':not suspects,'checked_nested_archives':True,'findings':suspects},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'destination':str(DEST),'exported_files':sum(x['kind']=='file' for x in records),'archive_members':sum(x['kind']=='archive_member' for x in records),'omitted':len(omitted),'redactions':dict(changes),'privacy_findings':len(suspects),'MB':round(sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())/1e6,2)}))
if suspects:print(json.dumps(suspects[:20]));raise SystemExit(2)
