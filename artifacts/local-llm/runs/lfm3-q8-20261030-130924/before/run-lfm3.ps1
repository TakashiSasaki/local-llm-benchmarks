param([switch]$Stop, [switch]$Status)
$ErrorActionPreference = 'Stop'
$python = 'C:\Users\benchmark\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$root = 'C:\LocalLLM'
$profile = Get-Content -LiteralPath (Join-Path $root 'profiles\lfm3.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$statePath = Join-Path $root 'server-state.json'

if ($Status) {
    try {
        $props = Invoke-RestMethod -Uri ($profile.base_url + '/props') -TimeoutSec 3
        [pscustomobject]@{
            running = $true
            selected_model = ($props.model_alias -eq $profile.profile_id)
            model = $props.model_alias
            runtime = $props.build_info
            context_per_slot = $props.default_generation_settings.n_ctx
            slots = $props.total_slots
        } | ConvertTo-Json
    } catch {
        [pscustomobject]@{ running = $false; selected_model = $false } | ConvertTo-Json
    }
    exit 0
}

if ($Stop) {
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($state.profile -ne 'lfm3') {
            throw 'Another profile owns the managed server. Stop it with its original launcher.'
        }
    }
    & $python (Join-Path $root 'scripts\server.py') stop
    exit $LASTEXITCODE
}

$models = @(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe' OR Name='llama-cli.exe' OR Name='llama.exe'")
if ($models.Count -gt 0) {
    throw 'A local model is already running. Stop it with its original launcher before starting LFM3.'
}
& $python (Join-Path $root 'scripts\server.py') start 'lfm3'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ('LFM3 web chat: ' + $profile.base_url)
Write-Host ('OpenAI-compatible API: ' + $profile.base_url + '/v1')
Write-Host 'Stop: C:\LocalLLM\run-lfm3.ps1 -Stop'
exit 0
