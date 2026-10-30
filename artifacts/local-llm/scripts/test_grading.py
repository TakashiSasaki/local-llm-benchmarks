"""Synthetic golden/negative validator checks; separate from real model trials."""
import base64, copy, hashlib, json, pathlib, tempfile
from fixtures import TASKS, definitions, write_files
from grading import capture_lock, freeze, grade_ps4, snapshot, static_grade
from server import ROOT

def item(content,executable=False):
    b=content if isinstance(content,bytes) else content.encode('utf-8')
    return {'base64':base64.b64encode(b).decode(),'sha256':hashlib.sha256(b).hexdigest(),'executable':executable}

GOOD_PS4=r'''param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
try {
 $header=(Get-Content -LiteralPath $InputPath -TotalCount 1).TrimStart([char]0xfeff).Split(',')
 foreach($required in @('status','quantity','unit_price')) { if ($required -notin $header) { throw 'missing column' } }
 $rows=@(Import-Csv -LiteralPath $InputPath)
 [decimal]$total=0; [int]$count=0
 foreach($row in $rows) {
  [decimal]$quantity=0; [decimal]$price=0
  if (-not [decimal]::TryParse($row.quantity,[Globalization.NumberStyles]::Number,[Globalization.CultureInfo]::InvariantCulture,[ref]$quantity)) { throw 'invalid quantity' }
  if (-not [decimal]::TryParse($row.unit_price,[Globalization.NumberStyles]::Number,[Globalization.CultureInfo]::InvariantCulture,[ref]$price)) { throw 'invalid price' }
  if ($row.status -eq 'paid') { $count++; $total+=$quantity*$price }
 }
 @{count=$count;total=[math]::Round($total,2,[MidpointRounding]::AwayFromZero)} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding utf8
 exit 0
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
'''

def golden(task):
    d=definitions(task); local={k:item(base64.b64decode(v)) for k,v in d['local'].items()}; remote={k:item(base64.b64decode(v),k in d['executable']) for k,v in d['remote'].items()}
    if task=='PS1':
        rows=[{'name':k.removeprefix('input/'),'text':base64.b64decode(v).decode()} for k,v in d['local'].items() if k.endswith('.txt') and base64.b64decode(v).decode().startswith('採用:')]
        local['selected.json']=item(json.dumps(sorted(rows,key=lambda r:r['name']),ensure_ascii=False))
    elif task=='PS2': local['summary.json']=item('{"orders":3,"quantity":13,"total":742.25,"selected_ids":["A01","A04","A05"]}')
    elif task=='PS3': local.update({'config.json':item('{"input_file":"numbers.csv","factor":3}'),'result.csv':item('id,value\nx,12\ny,21\nz,-6\n')})
    elif task=='PS4': local['Get-WeightedTotal.ps1']=item(GOOD_PS4)
    elif task=='B1': remote.update({'counts.json':item('{"api":2,"db":1}'),'counts.tsv':item('service\tcount\napi\t2\ndb\t1\n'),'empty.json':item('{}'),'empty.tsv':item('service\tcount\n')})
    elif task=='B2': remote['hashes.json']=item(json.dumps(sorted([{'name':k.removeprefix('input/'),'sha256':hashlib.sha256(base64.b64decode(v)).hexdigest()} for k,v in d['remote'].items()],key=lambda r:r['name']),ensure_ascii=False))
    elif task=='B3': remote.update({'broken.sh':item('#!/usr/bin/env bash\nwhile IFS= read -r line; do printf "OK:%s\\n" "$line"; done < input.txt > result.txt\n',True),'result.txt':item('OK:alpha\nOK:日本語 空白\n')})
    elif task=='B4': remote['filter.sh']=item('#!/usr/bin/env bash\nset -euo pipefail\n[[ $# -eq 2 && -f "$1" ]] || exit 2\ngrep ERROR "$1" > "$2" || [[ $? -eq 1 ]]\n',True)
    elif task=='S1': remote['same.txt']=item('変更済み remote\n')
    elif task=='S2': remote.update({'work/result.json':item('{"label":"日本語 label","region":"test-east","stage":"complete"}'),'work/stage.txt':item('日本語 label|test-east\n')})
    elif task=='S3': remote.update({'attempts.log':item('attempted\n'),'starts.log':item('started\n'),'artifact.txt':item('完了 artifact\nline two\n')}); local['recovered.txt']=item('完了 artifact\nline two\n')
    elif task=='S4': b=base64.b64decode(d['local']['source 日本語.txt']); remote['remote copy 日本語.txt']=item(b); local['roundtrip 日本語.txt']=item(b)
    return local,remote

def run():
    results=[]
    def check(name,passed):
        results.append({'name':name,'passed':bool(passed)})
        if not passed: raise AssertionError(name)
    for task in TASKS:
        local,remote=golden(task)
        check(task+':golden_snapshot',static_grade(task,local,remote)['passed'])
        check(task+':running_rejected',not static_grade(task,local,remote,running=True)['passed'])
        check(task+':changed_grader_rejected',not static_grade(task,local,remote,lock_valid=False)['passed'])
        check(task+':empty_output_rejected',not static_grade(task,{}, {})['passed'])
    local,remote=golden('S1'); local['same.txt']=item('変更済み remote\n')
    check('S1:wrong_host_rejected',not static_grade('S1',local,remote)['passed'])
    local,remote=golden('S4'); remote['remote copy 日本語.txt']=item('corrupted')
    check('S4:content_corruption_rejected',not static_grade('S4',local,remote)['passed'])
    local,remote=golden('S3'); remote['starts.log']=item('started\nstarted\n')
    check('S3:duplicate_run_rejected',not static_grade('S3',local,remote)['passed'])
    config=json.loads((ROOT/'executor-config.json').read_text(encoding='utf-8-sig'))
    (ROOT/'validation').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='grader-selftest-',dir=ROOT/'validation') as temp:
        p=pathlib.Path(temp); script=p/'Get-WeightedTotal.ps1'; script.write_text(GOOD_PS4,encoding='utf-8-sig')
        dynamic=grade_ps4(p,config['powershell']); check('PS4:actual_good_script',dynamic['passed'])
        script.write_bytes(base64.b64decode(definitions('PS4')['local']['Get-WeightedTotal.ps1']))
        check('PS4:actual_buggy_script_rejected',not grade_ps4(p,config['powershell'])['passed'])
    freeze(); locked=capture_lock(); check('suite:initial_lock',locked())
    path=ROOT/'validation/suite-lock.json'; saved=path.read_bytes()
    try: path.write_bytes(saved+b' '); check('suite:lock_file_tamper_rejected',not locked())
    finally: path.write_bytes(saved)
    check('suite:restored_lock',locked())
    return results

if __name__=='__main__':
    results=run(); (ROOT/'runs/grader-selftest.json').write_text(json.dumps({'type':'model_free_and_synthetic','results':results,'ssh_executed':False},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(results),'ssh_executed':False,'model_trials':0},ensure_ascii=False))
