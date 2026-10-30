import json
from server import ROOT

common=['--device','CUDA0','-ngl','all','--cpu-moe','-t','8','-tb','8','-np','1','-c','16384',
        '-ctk','f16','-ctv','f16','-b','2048','-ub','512','-fa','auto','--cache-ram','0','--jinja','--perf',
        '--fit','off','--no-context-shift']
models=[('qwen','Qwen3.6-35B-A3B-UD-Q3_K_M.gguf','1b715841683f960bd9a49f008181bd910ee169b78d4cf465b6fde7f4d929ff99',
         {'temperature':.6,'top_p':.95,'top_k':20,'min_p':0,'presence_penalty':0,'repeat_penalty':1},{'enable_thinking':True}),
        ('lfm','LFM2.5-24B-A2B-QAD-Q4_0.gguf','d1c03f73ecaf61017d70419eec9e5dc0b05d50ae26c23d522829b934fbabf8a5',
         {'temperature':.1,'top_k':50,'repeat_penalty':1.05},{}),
        ('glm','GLM-4.7-Flash-Q4_K_M.gguf','29837ed2c0fc5f51981adf8ac8083fcf80743c598381f13e9f06cbad0498b174',
         {'temperature':.7,'top_p':1.0,'min_p':.01,'repeat_penalty':1},{'enable_thinking':True})]
for name,file,hash,sampling,kwargs in models:
    p={'profile_id':name+'-baseline-v1','status':'unvalidated-starting-profile','runtime_build':'b11946',
       'runtime_executable':'bin/b11946-cuda12.4/llama-server.exe','model':'models/'+file,'model_hash':hash,
       'port':8089,'base_url':'http://127.0.0.1:8089','server_args':common,
       'sampling':sampling,'chat_template_kwargs':kwargs,'parser':'runtime automatic from embedded Jinja; unverified',
       'max_tokens':4096,'seed':42,'context_tokens':16384,'history_policy':'preserve all; stop before context overflow; no silent truncation',
       'limits':{'normal_seconds':300,'long_seconds':480,'tool_calls':12},'metrics_unavailable':None}
    (ROOT/'profiles'/f'{name}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/f'run-{name}.ps1').write_text("param([switch]$Stop)\n$ErrorActionPreference='Stop'\n$python='C:\\Users\\benchmark\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'\nif ($Stop) { & $python 'C:\\LocalLLM\\scripts\\server.py' stop } else { & $python 'C:\\LocalLLM\\scripts\\server.py' start '"+name+"' }\nexit $LASTEXITCODE\n",encoding='utf-8-sig')
