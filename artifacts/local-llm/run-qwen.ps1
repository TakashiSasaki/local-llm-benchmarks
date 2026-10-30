param([switch]$Stop)
$ErrorActionPreference='Stop'
$python='C:\Users\benchmark\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if ($Stop) { & $python 'C:\LocalLLM\scripts\server.py' stop } else { & $python 'C:\LocalLLM\scripts\server.py' start 'qwen' }
exit $LASTEXITCODE
