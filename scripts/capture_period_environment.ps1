param(
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][string]$BenchmarkPython,
    [Parameter(Mandatory=$true)][string]$MaintenancePython,
    [string]$HermesSource,
    [string]$ObservationScope='End-of-period observation; not proof these OS/driver/power settings were constant during every historical run'
)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $Output){throw 'Environment snapshot already exists; use a new output file'}
$os=Get-CimInstance Win32_OperatingSystem
$cs=Get-CimInstance Win32_ComputerSystem
$win=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$pythonInfo='import sys,platform,hashlib,importlib.metadata,json,pathlib; root=pathlib.Path(sys.executable).parent; print(json.dumps({"version":sys.version,"implementation":platform.python_implementation(),"binary_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/"python.exe",root/"python3.dll",root/("python"+str(sys.version_info.major)+str(sys.version_info.minor)+".dll")] if p.exists()},"packages":sorted([{"name":d.metadata["Name"],"version":d.version} for d in importlib.metadata.distributions()],key=lambda x:x["name"].lower())}))'
$pyBenchmark=(& $BenchmarkPython -c $pythonInfo | ConvertFrom-Json)
if($LASTEXITCODE){throw 'Benchmark Python inspection failed'}
$pyMaintenance=(& $MaintenancePython -c $pythonInfo | ConvertFrom-Json)
if($LASTEXITCODE){throw 'Maintenance Python inspection failed'}
$gpu=(& nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap,vbios_version,power.limit --format=csv,noheader,nounits)
if($LASTEXITCODE){throw 'GPU inspection failed'}
$scheme=[regex]::Match((& powercfg /getactivescheme | Out-String),'[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}').Value
$result=[ordered]@{
    captured_at_utc=(Get-Date).ToUniversalTime().ToString('o')
    scope=$ObservationScope
    os=[ordered]@{caption=$os.Caption;version=$os.Version;build=$os.BuildNumber;ubr=$win.UBR;display_version=$win.DisplayVersion;architecture=$os.OSArchitecture;timezone=(Get-TimeZone).Id;culture=(Get-Culture).Name}
    computer=[ordered]@{manufacturer=$cs.Manufacturer;model=$cs.Model;physical_memory_bytes=$cs.TotalPhysicalMemory;automatic_managed_pagefile=$cs.AutomaticManagedPagefile}
    cpu=@(Get-CimInstance Win32_Processor | Select-Object Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed)
    memory=@(Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer,Capacity,Speed,ConfiguredClockSpeed,SMBIOSMemoryType)
    gpu=[ordered]@{fields=@('name','driver_version','memory_total_mib','compute_capability','vbios_version','power_limit_watts');rows=@($gpu)}
    display_driver=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,DriverDate)
    storage=@(Get-CimInstance Win32_DiskDrive | Select-Object Model,InterfaceType,Size,FirmwareRevision)
    disk_at_capture=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace,FileSystem)
    pagefile=@(Get-CimInstance Win32_PageFileUsage | Select-Object AllocatedBaseSize,CurrentUsage,PeakUsage)
    power_scheme_guid=$scheme
    power_settings_query=@(& powercfg /query SCHEME_CURRENT | Select-Object -Skip 1)
    battery_at_capture=@(Get-CimInstance Win32_Battery | Select-Object BatteryStatus,EstimatedChargeRemaining)
    python=[ordered]@{benchmark=$pyBenchmark;maintenance=$pyMaintenance}
    powershell=$PSVersionTable.PSVersion.ToString()
    git=(& git --version)
    curl=(@(& curl.exe --version)[0])
    relevant_environment=[ordered]@{}
    active_model_processes=@(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe' OR Name='llama-cli.exe'" | Select-Object Name)
    limitations=@('No host/user names, serials, MAC/IP addresses, credentials or full environment dump collected','Clock, thermal and AC/battery state during each past request were not recorded; identical throughput is not guaranteed','Current Python package inventory is an end observation; historical interpreter version is also recorded in original results')
}
foreach($key in @('CUDA_VISIBLE_DEVICES','GGML_CUDA_FORCE_MMQ','GGML_CUDA_FORCE_CUBLAS','OMP_NUM_THREADS','LLAMA_ARG_THINK','PYTHONUTF8','PYTHONIOENCODING')){
    $result.relevant_environment[$key]=[Environment]::GetEnvironmentVariable($key)
}
if($HermesSource){
    $files=@{}
    foreach($name in @('pyproject.toml','uv.lock')){if(Test-Path -LiteralPath (Join-Path $HermesSource $name)){$files[$name]=(Get-FileHash -LiteralPath (Join-Path $HermesSource $name) -Algorithm SHA256).Hash.ToLowerInvariant()}}
    $changed=@(& git -C $HermesSource -c core.longpaths=true diff --name-only)
    if($LASTEXITCODE){throw 'Hermes source inspection failed'}
    $result.hermes=[ordered]@{commit=(& git -C $HermesSource rev-parse HEAD);changed_tracked_paths=$changed;dependency_file_sha256=$files;scope='Source identity only; user configuration and state database are not exported'}
}
$parent=Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Output -Encoding utf8
Write-Output 'Captured allowlisted end-of-period environment'
