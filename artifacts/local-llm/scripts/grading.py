"""Private expected results and model-independent validators."""
import base64, csv, hashlib, io, json, pathlib, subprocess, tempfile
from decimal import Decimal
from strict_json import loads as strict_json_loads, equal as json_equal
from fixtures import definitions
from server import ROOT

def data(files,name): return base64.b64decode(files[name]['base64'])
def text(files,name): return data(files,name).decode('utf-8-sig')
def js(files,name): return strict_json_loads(text(files,name))
def snapshot(directory):
    result={}
    for p in pathlib.Path(directory).rglob('*'):
        if p.is_file():
            if p.is_symlink(): raise ValueError('Symlink in fixture')
            content=p.read_bytes()
            result[p.relative_to(directory).as_posix()]={'base64':base64.b64encode(content).decode(),'sha256':hashlib.sha256(content).hexdigest(),'executable':False}
    return result

def static_grade(task,local,remote,running=False,lock_valid=True):
    checks={}
    checks['no_running_jobs']=not running; checks['grader_unchanged']=lock_valid
    fixture=definitions(task)
    # Every immutable fixture must still exist with exactly its initial bytes.
    for host,files in [('local',local),('remote',remote)]:
        for name,initial in fixture[host].items():
            mutable=name in fixture['mutable'] or host+':'+name in fixture['mutable']
            if mutable: continue
            checks[host+':unchanged:'+name]=name in files and data(files,name)==base64.b64decode(initial)
    try:
        if task=='PS1':
            expected=[{'name':name.removeprefix('input/'),'text':base64.b64decode(value).decode()} for name,value in fixture['local'].items() if name.endswith('.txt') and base64.b64decode(value).decode().startswith('採用:')]
            checks['selected_files']=json_equal(js(local,'selected.json'),sorted(expected,key=lambda r:r['name']))
        elif task=='PS2': checks['aggregate']=json_equal(js(local,'summary.json'),{'orders':3,'quantity':13,'total':742.25,'selected_ids':['A01','A04','A05']})
        elif task=='PS3':
            checks['config']=json_equal(js(local,'config.json'),{'input_file':'numbers.csv','factor':3})
            rows=list(csv.DictReader(io.StringIO(text(local,'result.csv'))))
            checks['output']=len(rows)==3 and [(r['id'],Decimal(r['value'])) for r in rows]==[('x',Decimal(12)),('y',Decimal(21)),('z',Decimal(-6))]
        elif task=='PS4': checks['script_present']='Get-WeightedTotal.ps1' in local
        elif task=='B1':
            checks['counts']=json_equal(js(remote,'counts.json'),{'api':2,'db':1})
            checks['tsv']=text(remote,'counts.tsv').splitlines()==['service\tcount','api\t2','db\t1']
            checks['empty_json']=json_equal(js(remote,'empty.json'),{})
            checks['empty_tsv']=text(remote,'empty.tsv').splitlines()==['service\tcount']
        elif task=='B2':
            expected=[{'name':name.removeprefix('input/'),'sha256':hashlib.sha256(base64.b64decode(value)).hexdigest()} for name,value in fixture['remote'].items()]
            checks['hashes']=json_equal(js(remote,'hashes.json'),sorted(expected,key=lambda r:r['name']))
        elif task=='B3':
            script=data(remote,'broken.sh'); checks['lf_shebang']=b'\r' not in script and script.startswith((b'#!/bin/bash\n',b'#!/usr/bin/env bash\n'))
            checks['executable']=remote['broken.sh']['executable']
            checks['output']=data(remote,'result.txt')=='OK:alpha\nOK:日本語 空白\n'.encode()
        elif task=='B4': checks['script_present']='filter.sh' in remote and remote['filter.sh']['executable']
        elif task=='S1': checks['correct_host']=data(remote,'same.txt')=='変更済み remote\n'.encode()
        elif task=='S2':
            checks['result']=json_equal(js(remote,'work/result.json'),{'label':'日本語 label','region':'test-east','stage':'complete'})
            checks['stage']=data(remote,'work/stage.txt')=='日本語 label|test-east\n'.encode()
        elif task=='S3':
            expected='完了 artifact\nline two\n'.encode()
            checks['one_attempt']=data(remote,'attempts.log')==b'attempted\n'
            checks['once']=data(remote,'starts.log')==b'started\n'
            checks['remote_artifact']=data(remote,'artifact.txt')==expected
            checks['retrieved']=data(local,'recovered.txt')==expected
        elif task=='S4':
            original=base64.b64decode(fixture['local']['source 日本語.txt'])
            checks['remote_bytes']=data(remote,'remote copy 日本語.txt')==original
            checks['roundtrip_bytes']=data(local,'roundtrip 日本語.txt')==original
        # All JSON outputs must be valid UTF-8; decoding with sig allows a UTF-8 BOM.
        for files in [local,remote]:
            for name in files:
                if name.endswith('.json'): js(files,name)
    except Exception as e: checks['output_readable']=False; checks['output_error']=str(e)
    return {'passed':all(v is True for k,v in checks.items() if k!='output_error'),'checks':checks}

def grade_ps4(directory,powershell):
    script=pathlib.Path(directory)/'Get-WeightedTotal.ps1'
    cases=[('normal','status,quantity,unit_price\npaid,2,1.25\ncancelled,9,10\npaid,3,2.50\n',0,{'count':2,'total':10}),
           ('decimal','status,quantity,unit_price\npaid,10,0.1\npaid,1,2.345\n',0,{'count':2,'total':3.35}),
           ('empty','status,quantity,unit_price\n',0,{'count':0,'total':0}),
           ('invalid','status,quantity,unit_price\npaid,wrong,2\n',1,None),
           ('missing_column','status,quantity\npaid,2\n',1,None)]
    details=[]
    with tempfile.TemporaryDirectory(prefix='ps4-',dir=ROOT/'validation') as temp:
        for name,content,exit_kind,expected in cases:
            src=pathlib.Path(temp)/(name+'.csv'); dst=pathlib.Path(temp)/(name+'.json'); src.write_text(content,encoding='utf-8')
            try:
                p=subprocess.run([powershell,'-NoProfile','-NonInteractive','-File',str(script),'-InputPath',str(src),'-OutputPath',str(dst)],capture_output=True,timeout=15,cwd=directory)
                ok=(p.returncode==0 and dst.exists() and json_equal(strict_json_loads(dst.read_text(encoding='utf-8-sig')),expected)) if exit_kind==0 else p.returncode!=0 and not dst.exists()
                details.append({'case':name,'passed':ok,'exit_code':p.returncode})
            except Exception as e: details.append({'case':name,'passed':False,'error':str(e)})
    return {'passed':all(x['passed'] for x in details),'cases':details}

def grade_b4(bridge,directory):
    # Output names are validation-owned and fresh, so stale files cannot pass.
    import uuid
    token='validator-'+uuid.uuid4().hex
    cases=[('normal.log',token+'-normal.out',0,'ERROR first\nERROR second\n'),('empty.log',token+'-empty.out',0,''),('missing-'+token,token+'-missing.out',1,None)]
    details=[]
    for src,dst,kind,expected in cases:
        r=bridge({'action':'invoke','directory':directory,'script':'filter.sh','args':[src,dst]})
        files=bridge({'action':'snapshot','directory':directory})['files']
        ok=(r['exit_code']==0 and dst in files and text(files,dst)==expected) if kind==0 else r['exit_code']!=0 and dst not in files
        details.append({'case':src,'passed':ok,'exit_code':r['exit_code']})
    r=bridge({'action':'invoke','directory':directory,'script':'filter.sh','args':[]})
    details.append({'case':'missing_arguments','passed':r['exit_code']!=0,'exit_code':r['exit_code']})
    return {'passed':all(x['passed'] for x in details),'cases':details}

def lock_files():
    files=sorted((ROOT/'scripts').glob('*.py'))+sorted((ROOT/'profiles').glob('*.json'))+[ROOT/'executor-config.json',ROOT/'runtime-manifest.json']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
def freeze():
    (ROOT/'validation').mkdir(exist_ok=True)
    (ROOT/'validation/suite-lock.json').write_text(json.dumps(lock_files(),indent=2),encoding='utf-8')
def lock_valid():
    try: return lock_files()==json.loads((ROOT/'validation/suite-lock.json').read_text())
    except Exception: return False

def capture_lock():
    if not lock_valid(): raise RuntimeError('Suite must be reviewed and frozen before evaluation')
    expected=lock_files()
    lock_path=ROOT/'validation/suite-lock.json'
    lock_hash=hashlib.sha256(lock_path.read_bytes()).hexdigest()
    def check():
        try: return lock_files()==expected and hashlib.sha256(lock_path.read_bytes()).hexdigest()==lock_hash
        except Exception: return False
    return check

if __name__=='__main__': freeze(); print('Evaluation scripts and configuration frozen.')
