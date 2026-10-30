param([string]$InputPath,[string]$OutputPath)

# Check if file exists
if (-not (Test-Path $InputPath)) {
    Write-Error "Input file not found"
    exit 1
}

$rows = Import-Csv -LiteralPath $InputPath

# Handle empty data (no rows)
if ($rows.Count -eq 0) {
    @{count=0;total=0} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    exit 0
}

# Check required columns exist
$requiredColumns = @('status', 'quantity', 'unit_price')
$actualColumns = $rows[0].PSObject.Properties.Name
foreach ($col in $requiredColumns) {
    if ($actualColumns -notcontains $col) {
        Write-Error "Missing required column: $col"
        exit 1
    }
}

# Filter paid rows and validate, calculate total
$total = 0
$count = 0
$invariant = [Globalization.CultureInfo]::InvariantCulture

foreach ($row in $rows) {
    if ($row.status -eq 'paid') {
        # Validate quantity is numeric
        $qty = 0
        if (-not [double]::TryParse($row.quantity, [Globalization.NumberStyles]::Any, $invariant, [ref]$qty)) {
            Write-Error "quantity is not numeric: $($row.quantity)"
            exit 1
        }
        # Validate unit_price is numeric
        $price = 0
        if (-not [double]::TryParse($row.unit_price, [Globalization.NumberStyles]::Any, $invariant, [ref]$price)) {
            Write-Error "unit_price is not numeric: $($row.unit_price)"
            exit 1
        }
        $total += $qty * $price
        $count++
    }
}

# Round to 2 decimal places, away from zero
$roundedTotal = [Math]::Round($total, 2, [MidpointRounding]::AwayFromZero)

# Output
@{count=$count;total=$roundedTotal} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding UTF8

exit 0
