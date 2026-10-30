"""Model -> actual PowerShell -> model, independently verified; excluded from P5."""
import argparse, datetime, hashlib, json, uuid
from agent import run
from grading import capture_lock
from server import ROOT

def test(name,diagnostic=None):
    directory=ROOT/'workspace'/('real-tool-smoke-'+uuid.uuid4().hex[:10]); directory.mkdir(parents=True)
    filename='[日本語] 空白 メモ.txt'; token='REAL-'+uuid.uuid4().hex[:12]; expected='実行確認 '+token+'\n'
    script="$path='"+filename+"'\n$content=\"実行確認 "+token+"`n\"\nSet-Content -LiteralPath $path -Value $content -Encoding utf8NoBOM -NoNewline\nGet-Content -LiteralPath $path -Raw\n(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()"
    prompt='実際のrun_powershell toolを一度使ってください。cwdを '+str(directory)+' に明示し、script引数には次のPowerShellコードブロックの中身をそのまま渡してください。フェンスは含めず、行間は実際のLF、最終行の後ろには改行を加えません。\n```powershell\n'+script+'\n```\nこれは実行系の疎通試験です。結果を受け取ってから、stdoutに現れた確認コードとSHA-256を最終回答に含めてください。'
    check=capture_lock()
    def validate(events):
        path=directory/filename; actual=path.read_bytes() if path.exists() else None
        wanted=hashlib.sha256(expected.encode()).hexdigest()
        tool_hash=any(wanted.lower() in e['result'].get('stdout','').lower() for e in events)
        exact_args=any(e['call']['function']['name']=='run_powershell' and json.loads(e['call']['function']['arguments']).get('script')==script and json.loads(e['call']['function']['arguments']).get('cwd')==str(directory) for e in events)
        return {'passed':actual==expected.encode() and tool_hash and exact_args and check(),'test_version':'fixed-script-v3-fenced','script_argument_exact':exact_args,'file_exact':actual==expected.encode(),'sha256_in_actual_tool_output':tool_hash,'expected_sha256':wanted,'lock_unchanged':check()}
    result=run(name,prompt,directory,limit=180,validator=validate,lock_check=check,diagnostic_profile=diagnostic)
    (ROOT/'runs'/('real-tool-smoke-'+result['run_id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('profile',choices=['qwen','lfm','glm']); ap.add_argument('--diagnostic-profile'); a=ap.parse_args()
    result=test(a.profile,a.diagnostic_profile)
    raise SystemExit(0 if result['success'] else 1)
