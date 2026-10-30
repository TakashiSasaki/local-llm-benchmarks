"""Run fixed reference solutions through the real executor and independent grader.

These checks validate infrastructure, not any language model. Never count as P5.
"""
import base64, json, pathlib, tempfile, time
from executor import Executor
from fixtures import definitions, write_files
from grading import grade_ps4, snapshot, static_grade
from server import ROOT
from test_grading import GOOD_PS4

SOLUTIONS={
'PS1':r'''$rows=@(Get-ChildItem -LiteralPath './input' -File | Where-Object Extension -eq '.txt' | ForEach-Object {
 $text=[IO.File]::ReadAllText($_.FullName,[Text.Encoding]::UTF8)
 if ($text.StartsWith('採用:')) { [pscustomobject]@{name=$_.Name;text=$text} }
} | Sort-Object -Property name)
ConvertTo-Json -InputObject $rows | Set-Content -LiteralPath './selected.json' -Encoding utf8
''',
'PS2':r'''$rules=Get-Content -LiteralPath './rules.json' -Raw | ConvertFrom-Json
$rows=@(Import-Csv -LiteralPath './orders.csv' | Where-Object { $_.status -eq 'paid' -and $_.category -in $rules.allowed_categories })
[decimal]$total=0; [int]$quantity=0
foreach($row in $rows) { $quantity += [int]$row.quantity; $total += [decimal]$row.quantity * [decimal]$row.unit_price }
[ordered]@{orders=$rows.Count;quantity=$quantity;total=[Math]::Round($total,2,[MidpointRounding]::AwayFromZero);selected_ids=@($rows.id | Sort-Object)} | ConvertTo-Json | Set-Content -LiteralPath './summary.json' -Encoding utf8
''',
'PS3':r'''$config=Get-Content -LiteralPath './config.json' -Raw | ConvertFrom-Json
$config.input_file='numbers.csv'
$config | ConvertTo-Json | Set-Content -LiteralPath './config.json' -Encoding utf8
& $env:REFERENCE_PWSH -NoProfile -NonInteractive -File './app.ps1'
'''
}

def execute(executor,directory,script):
    p=executor.execute('run_powershell',{'script':script,'cwd':str(directory),'env':{'REFERENCE_PWSH':executor.config['powershell']},'timeout':5})
    deadline=time.monotonic()+20
    while p['status']=='running' and time.monotonic()<deadline:
        time.sleep(.1); p=executor.execute('poll_process',{'job_id':p['job_id']})
    if p['status']=='running': executor.execute('stop_process',{'job_id':p['job_id']}); raise TimeoutError('Reference task did not finish')
    return p

def run():
    (ROOT/'validation').mkdir(exist_ok=True); checks=[]
    with tempfile.TemporaryDirectory(prefix='local-reference-',dir=ROOT/'validation') as temp:
        for task in ['PS1','PS2','PS3','PS4']:
            directory=pathlib.Path(temp)/task; definition=definitions(task); write_files(directory,definition['local']); executor=Executor(directory)
            if task=='PS3':
                failed=execute(executor,directory,"& $env:REFERENCE_PWSH -NoProfile -NonInteractive -File './app.ps1'")
                checks.append({'task':task,'check':'initial_external_failure','passed':failed['exit_code']!=0})
            if task=='PS4':
                (directory/'Get-WeightedTotal.ps1').write_text(GOOD_PS4,encoding='utf-8-sig')
                script="& './Get-WeightedTotal.ps1' -InputPath './data.csv' -OutputPath './result.json'"
            else: script=SOLUTIONS[task]
            result=execute(executor,directory,script)
            grade=static_grade(task,snapshot(directory),{})
            if task=='PS4':
                dynamic=grade_ps4(directory,executor.config['powershell']); grade['dynamic']=dynamic; grade['passed'] &= dynamic['passed']
            checks.append({'task':task,'check':'actual_executor_and_grader','passed':result['exit_code']==0 and grade['passed'],'executor_exit':result['exit_code'],'validator':grade})
            if task=='PS1':
                (directory/'selected.json').write_text('[]',encoding='utf-8')
                checks.append({'task':task,'check':'actual_output_corruption_rejected','passed':not static_grade(task,snapshot(directory),{})['passed']})
    report={'kind':'model_free_local_reference','model_trials':0,'ssh_trials':0,'checks':checks,'passed':all(x['passed'] for x in checks)}
    (ROOT/'runs/local-task-selftest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'check_count':len(checks),'model_trials':0,'checks':[{'task':x['task'],'check':x['check'],'passed':x['passed']} for x in checks]},ensure_ascii=False))
    if not report['passed']: raise AssertionError('Local reference task selftest failed')

if __name__=='__main__': run()
