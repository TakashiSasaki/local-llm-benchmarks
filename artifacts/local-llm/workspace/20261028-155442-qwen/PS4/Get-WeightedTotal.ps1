param([string]$InputPath, [string]$OutputPath)

# Check if file exists
if (-not (Test-Path $InputPath)) {
    Write-Error "Input file not found: $InputPath"
    exit 1
}

$rows = Import-Csv -LiteralPath $InputPath

# Check required columns exist (use first row's property names)
$colNames = if ($rows.Count -gt 0) { $rows[0].PSObject.Properties.Name } else { @() }
if (-not ($colNames -contains 'quantity') -or
    -not ($colNames -contains 'unit_price') -or
    -not ($colNames -contains 'paid')) {
    Write-Error "Missing required columns"
    exit 1
}

# Validate all quantity values are numeric
foreach ($row in $rows) {
    $num = $null
    if (-not [double]::TryParse($row.quantity.Trim(), [ref]$num)) {
        Write-Error "Non-numeric quantity: $($row.quantity)"
        exit 1
    }
}

# Filter paid rows (paid == 'true')
$paidRows = $rows | Where-Object { $_.paid.Trim() -eq 'true' }

# Calculate total for paid rows
$total = 0
$count = 0
foreach ($row in $paidRows) {
    $qty = [double]$row.quantity.Trim()
    $price = [double]$row.unit_price.Trim()
    $total += $qty * $price
    $count++
}

# Round total to 2 decimal places, rounding half away from zero
$roundedTotal = [Math]::Round($total, 2, [MidpointRounding]::AwayFromZero)

# Output JSON with UTF-8 encoding
@{count=$count; total=$roundedTotal} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding utf8

exit 0
