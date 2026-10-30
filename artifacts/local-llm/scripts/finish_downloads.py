"""Continue this authorized download batch after the in-flight Qwen verifies."""
import json, subprocess, sys, time
from server import ROOT

qwen=ROOT/'models/Qwen3.6-35B-A3B-UD-Q3_K_M.gguf'
deadline=time.monotonic()+7200
print(json.dumps({'event':'waiting_for_verified_qwen','maximum_wait_seconds':7200}),flush=True)
while not qwen.exists() and time.monotonic()<deadline: time.sleep(2)
if not qwen.exists(): raise TimeoutError('Qwen was not verified; batch halted')
for name in ['qwen','lfm','glm']:
    subprocess.run([sys.executable,str(ROOT/'scripts/download.py'),name],check=True)
print(json.dumps({'event':'all_three_models_verified'}),flush=True)
