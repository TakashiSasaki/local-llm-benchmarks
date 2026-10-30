"""Deterministic fixtures and Japanese instructions; no expected answers in prompts."""
import base64, hashlib, json, pathlib, shutil, time
from server import ROOT

TASKS={
'PS1':'input内の.txtだけを調べ、本文が「採用:」で始まるファイルを選んでください。名前は日本語・空白・角括弧を含みます。selected.jsonに、ファイル名の昇順で [{"name":相対ファイル名,"text":元の全文}] をUTF-8で保存してください。対象外を変更しないでください。',
'PS2':'orders.csvとrules.jsonを読み、statusがpaidかつcategoryがrulesのallowed_categoriesに含まれる注文を集計してください。summary.jsonにorders（対象行数）、quantity（個数合計）、total（quantity×unit_priceの合計を小数2桁に丸めた数値。中間値は0から遠い方へ丸める）、selected_ids（idの昇順）をUTF-8で保存してください。入力は変更しないでください。',
'PS3':'app.ps1を別のPowerShellプロセスで実行し、失敗の原因を調べてください。config.jsonのinput_fileだけを修正し、入力numbers.csvとfactorに従うresult.csvを正常に生成してください。app.ps1とnumbers.csvは変更しないでください。',
'PS4':'Get-WeightedTotal.ps1のバグを修正してください。-InputPathのCSVのpaid行のみを対象にquantity×unit_priceを数値で集計し、-OutputPathのJSONにcountとtotal（小数2桁、中間値は0から遠い方へ丸めた数値）を保存する仕様です。正常データと空データは終了0、数量が数値でない行や必須列不足は終了非0で、結果を作らない仕様です。出力はUTF-8。正常系と失敗系を自分でも実行して確かめてください。',
'B1':'SSH先のaccess.logを読み、level=ERRORの行だけをservice別に数えてcounts.json（キーがservice、値が件数）とcounts.tsv（service\tcountのheader、service昇順）を作ってください。empty.logにも同じ処理を適用しempty.json={}とheaderだけのempty.tsvを作ってください。入力を変更しないでください。',
'B2':'SSH先のinput内にある全ての通常ファイルについてSHA-256を計算し、hashes.jsonを [{"name":相対ファイル名,"sha256":小文字hex}] のファイル名昇順（Unicodeコードポイント順。LC_ALL=CのUTF-8バイト順と同じ）で作ってください。空白・日本語・引用符を含む名前を欠落・分割しないでください。入力は変更しないでください。',
'B3':'SSH先のbroken.shが実行できない原因（改行、shebang、実行権限）を修正し、./broken.sh を直接実行してresult.txtを生成してください。input.txtの内容を行順に保ち、各行に固定の接頭辞OK:を付ける仕様です。input.txtは変更しないでください。',
'B4':'SSH先のfilter.shを修正してください。./filter.sh 入力 出力 で、ERRORを含む行を出力し、正常時と0件時は終了0にしてください。入力が存在しない・引数不足の場合は終了非0で、出力を作らない仕様です。pipelineの終了コードを正しく扱い、正常系とエラー系を確認してください。',
'S1':'WindowsとSSH先の両方にsame.txtがあります。SSH先のsame.txtだけを「変更済み remote\n」に書き換えてください。Windows側same.txtは一切変更しないでください。両方の内容を確認してください。',
'S2':'SSH先で複数のrun_ssh_bash呼び出しを使って、step1.sh、step2.shの順に処理してください。各呼び出しのcwd引数にworkの絶対パス、env引数にBUILD_LABEL="日本語 label"、REGION="test-east"を明示してください。前のtoolのcdやenvは次のtoolに引き継がれません。result.jsonを完成させてください。スクリプトは変更しないでください。',
'S3':'SSH先のlong.shを一度だけ起動し、job_idをpollして実際の完了を確認してください。処理には約12秒かかります。二重起動は禁止です。完成したartifact.txtをWindows作業ディレクトリのrecovered.txtに回収し、内容を確認してください。long.shは変更しないでください。',
'S4':'transfer_fileのuploadを使って、Windowsのsource 日本語.txtをSSH先のremote copy 日本語.txtへ転送し、内容とSHA-256の一致を確認してください。transfer_fileのdownloadでWindowsのroundtrip 日本語.txtへ回収し、元ファイルとのバイト単位の一致を確認してください。元ファイルは変更しないでください。'
}

def definitions(task):
    local={}; remote={}; mutable=[]; executable=[]
    if task=='PS1':
        local={'input/日本語 メモ.txt':'採用:東京\n二行目\n','input/[2026] 報告.txt':'採用:大阪\n','input/対象 外.txt':'保留:札幌\n','input/採用.csv':'採用:除外\n','input/空.txt':''}
    elif task=='PS2':
        local={'orders.csv':'id,category,status,quantity,unit_price\nA01,book,paid,2,120.50\nA02,food,paid,3,99.90\nA03,book,cancelled,4,111.10\nA04,tool,paid,1,500.25\nA05,book,paid,10,0.10\n','rules.json':json.dumps({'allowed_categories':['book','tool']})}
    elif task=='PS3':
        local={'numbers.csv':'id,value\nx,4\ny,7\nz,-2\n','config.json':'{"input_file":"missing.csv","factor":3}',
               'app.ps1':'''$ErrorActionPreference='Stop'
$c=Get-Content -LiteralPath './config.json' -Raw | ConvertFrom-Json
$rows=Import-Csv -LiteralPath $c.input_file
$rows | ForEach-Object { [pscustomobject]@{id=$_.id;value=([decimal]$_.value * [decimal]$c.factor)} } | Export-Csv -LiteralPath './result.csv' -NoTypeInformation -Encoding utf8
'''}; mutable=['config.json']
    elif task=='PS4':
        local={'data.csv':'status,quantity,unit_price\npaid,2,1.25\ncancelled,9,10\npaid,3,2.50\n',
               'Get-WeightedTotal.ps1':'''param([string]$InputPath,[string]$OutputPath)
$rows=Import-Csv -LiteralPath $InputPath
$total=0
foreach($row in $rows) { $total += $row.quantity + $row.unit_price }
@{count=$rows.Count;total=$total} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath
'''}; mutable=['Get-WeightedTotal.ps1']
    elif task=='B1':
        remote={'access.log':'2026-10-28T00:00:00Z level=ERROR service=api msg=timeout\n2026-10-28T00:00:01Z level=INFO service=api msg=ok\n2026-10-28T00:00:02Z level=ERROR service=db msg=failed\n2026-10-28T00:00:03Z level=ERROR service=api msg=retry\n','empty.log':'2026-10-28T00:00:04Z level=INFO service=api msg=ok\n'}
    elif task=='B2':
        remote={'input/日本語 空白.txt':'日本語\n','input/quote\'name.txt':'single quote\n','input/double"name.txt':'double quote\n','input/[x].txt':'brackets\n'}
    elif task=='B3':
        remote={'broken.sh':b'#!/bin/not-bash\r\nwhile IFS= read -r line; do printf "OK:%s\\n" "$line"; done < input.txt > result.txt\r\n','input.txt':'alpha\n日本語 空白\n'}; mutable=['broken.sh']
    elif task=='B4':
        remote={'filter.sh':'#!/usr/bin/env bash\ngrep ERROR "$1" | cat > "$2"\nexit 0\n','normal.log':'INFO ok\nERROR first\nWARN ignore\nERROR second\n','empty.log':'INFO fine\n'}; mutable=['filter.sh']; executable=['filter.sh']
    elif task=='S1': local={'same.txt':'変更前 local\n'}; remote={'same.txt':'変更前 remote\n'}; mutable=['remote:same.txt']
    elif task=='S2':
        check='[[ "$PWD" == */work && "$BUILD_LABEL" == "日本語 label" && "$REGION" == "test-east" ]] || exit 41\n'
        remote={'work/step1.sh':'#!/usr/bin/env bash\nset -euo pipefail\n'+check+'printf "%s\\n" "$BUILD_LABEL|$REGION" > stage.txt\n',
                'work/step2.sh':'#!/usr/bin/env bash\nset -euo pipefail\n'+check+'[[ -s stage.txt ]] || exit 42\nprintf \'{"label":"%s","region":"%s","stage":"complete"}\\n\' "$BUILD_LABEL" "$REGION" > result.json\n'}; executable=['work/step1.sh','work/step2.sh']
    elif task=='S3':
        remote={'long.sh':'#!/usr/bin/env bash\nset -euo pipefail\nprintf "attempted\\n" >> attempts.log\nmkdir once.lock || exit 51\nprintf "started\\n" >> starts.log\nsleep 12\nprintf "完了 artifact\\nline two\\n" > artifact.txt\n'}; executable=['long.sh']
    elif task=='S4': local={'source 日本語.txt':'先頭 UTF-8\r\n日本語と "引用符" と空白\n終端\n'}
    else: raise ValueError(task)
    def encode(files): return {name:base64.b64encode(data if isinstance(data,bytes) else data.encode('utf-8')).decode('ascii') for name,data in files.items()}
    return {'local':encode(local),'remote':encode(remote),'mutable':mutable,'executable':executable}

def write_files(directory,files):
    directory.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        p=directory/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(base64.b64decode(data))

def prepare(task,run_id):
    d=ROOT/'workspace'/run_id/task
    if d.exists(): raise RuntimeError('Refusing to overwrite an existing trial')
    definition=definitions(task); write_files(d,definition['local'])
    return d,definition

def prompt(task,local,remote=None,host=None):
    return f'課題ID: {task}\nWindows作業ディレクトリ: {local}\nSSH host alias: {host}\nSSH作業ディレクトリ: {remote}\n'+TASKS[task]

if __name__=='__main__':
    print(json.dumps({k:definitions(k) for k in TASKS},ensure_ascii=False,indent=2))
