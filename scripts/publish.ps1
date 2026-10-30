param([Parameter(Mandatory=$true)][string]$Message,[switch]$Push)
$ErrorActionPreference='Stop'
$studyRoot=Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $studyRoot
try {
    python -B tools/verify_publication.py
    if($LASTEXITCODE -ne 0){throw 'Archived evidence verification failed'}
    python -B integrations/hermes/scripts/verify_saved_evidence.py
    if($LASTEXITCODE -ne 0){throw 'Hermes evidence verification failed'}
    python -B scripts/check_repository.py
    if($LASTEXITCODE -ne 0){throw 'Run/data/privacy checks failed'}
    python -B -m unittest discover -s tests -v
    if($LASTEXITCODE -ne 0){throw 'Maintained tool tests failed'}
    python -B scripts/refresh_reports.py
    if($LASTEXITCODE -ne 0){throw 'Report update failed'}
    python -B tools/make_checksums.py
    if($LASTEXITCODE -ne 0){throw 'Checksum update failed'}
    git add --all
    if($LASTEXITCODE -ne 0){throw 'git add failed'}
    git commit -m $Message
    if($LASTEXITCODE -ne 0){throw 'git commit failed'}
    if($Push){git push -u origin main; if($LASTEXITCODE -ne 0){throw 'git push failed'}}
} finally { Pop-Location }
