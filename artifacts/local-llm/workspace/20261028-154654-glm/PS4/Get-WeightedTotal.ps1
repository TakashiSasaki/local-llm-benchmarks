param(
    [string]$InputPath,
    [string]$OutputPath
)

try {
    # CSVファイルの読み込み
    $rows = Import-Csv -LiteralPath $InputPath -Encoding UTF8
    
    # 必須列のチェック
    if ($rows.Count -eq 0) {
        # 空データの場合は終了0で成功
        @{count=0;total=0} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
        exit 0
    }
    
    if ($rows[0].PSObject.Properties.Name -notcontains "paid" -or $rows[0].PSObject.Properties.Name -notcontains "quantity" -or $rows[0].PSObject.Properties.Name -notcontains "unit_price") {
        Write-Error "必須列が不足しています: paid, quantity, unit_price"
        exit 1
    }
    
    $total = 0
    $count = 0
    
    foreach ($row in $rows) {
        # paid列が"paid"または"Paid"の場合のみ処理
        if ($row.paid -eq "paid" -or $row.paid -eq "Paid") {
            # 数値チェック
            if ([string]::IsNullOrWhiteSpace($row.quantity) -or [string]::IsNullOrWhiteSpace($row.unit_price)) {
                Write-Error "数量または単価が指定されていません"
                exit 1
            }
            
            # 数値変換（安全な方法）
            $quantity = 0
            $unitPrice = 0
            $quantityValid = [double]::TryParse($row.quantity, [ref]$quantity)
            $unitPriceValid = [double]::TryParse($row.unit_price, [ref]$unitPrice)
            
            if (-not $quantityValid -or -not $unitPriceValid) {
                Write-Error "数量または単価が数値ではありません"
                exit 1
            }
            
            # 計算
            $value = $quantity * $unitPrice
            
            # 0から遠い方へ丸める（小数点以下2桁）
            if ($value -eq 0) {
                $roundedValue = 0
            } else {
                if ([Math]::Abs($value) -ge [Math]::Abs($value * 100)) {
                    # 0に近い方へ丸める
                    $roundedValue = [Math]::Round($value * 100) / 100
                } else {
                    # 0から遠い方へ丸める
                    $roundedValue = [Math]::Round($value - 0.005, 2)
                }
            }
            
            $total += $roundedValue
            $count++
        }
    }
    
    # 結果の保存
    @{count=$count;total=$total} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    
    exit 0
}
catch {
    Write-Error "エラーが発生しました: $_"
    exit 1
}
