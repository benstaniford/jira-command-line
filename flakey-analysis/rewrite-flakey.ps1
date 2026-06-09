$inputPath = 'C:\Users\ckershaw\jira-command-line\flakey.md'
$lines = Get-Content -Path $inputPath -Encoding UTF8

$fixedTests = @(
    'DriverBasedHookExclusion_DefaultArchitectureX64Process_FullPath',
    'DriverBasedHookExclusion_DefaultArchitectureX64Process_PartialPath',
    'Identity_MFACanBePassedWithChangedUserEmailAfterGroupRefresh',
    'JITAdmin_Auditing_GeneralRules_198',
    'JITAdmin_Auditing_OnDemand_101'
)

$inSummary = $false
$inDetail = $false
$skipDetailBlock = $false
$summaryNum = 0
$detailNum = 0
$out = New-Object System.Collections.ArrayList

foreach ($line in $lines) {
    # Top-N heading rewrite (defer count - placeholder)
    if ($line -match '^## Top \d+ Flakey Tests') {
        [void]$out.Add('## Top {DETAIL_COUNT} Flakey Tests - Regression Run Links')
        continue
    }

    # Divider between summary and detail
    if ($line -eq '---') {
        $inSummary = $false
        $inDetail = $true
        $skipDetailBlock = $false
        [void]$out.Add($line)
        continue
    }

    # Summary header
    if ($line -match '^\| # \| Failures') {
        $inSummary = $true
        [void]$out.Add($line)
        continue
    }

    # Summary separator row
    if ($inSummary -and $line -match '^\|---') {
        [void]$out.Add($line)
        continue
    }

    # Summary data row
    if ($inSummary -and $line -match '^\| \d+ \|') {
        $skip = $false
        foreach ($t in $fixedTests) {
            if ($line -like "*| $t |*") { $skip = $true; break }
        }
        if (-not $skip) {
            $summaryNum++
            $newLine = $line -replace '^\| \d+ \|', "| $summaryNum |"
            [void]$out.Add($newLine)
        }
        continue
    }

    # Detail section heading
    if ($inDetail -and $line -match '^### (\d+)\. (\S+) ') {
        $name = $matches[2]
        $skipDetailBlock = $fixedTests -contains $name
        if (-not $skipDetailBlock) {
            $detailNum++
            $newLine = $line -replace '^### \d+\.', "### $detailNum."
            [void]$out.Add($newLine)
        }
        continue
    }

    # Detail section body
    if ($inDetail -and $skipDetailBlock) {
        continue
    }

    # Update timestamp
    if ($line -match '^\*Generated ') {
        $now = (Get-Date -Format 'yyyy-MM-dd HH:mm')
        [void]$out.Add("*Generated $now UTC (filtered: 5 fixed tests removed)*")
        continue
    }

    [void]$out.Add($line)
}

# Build final content
$result = ($out -join "`r`n") -replace '\{DETAIL_COUNT\}', $detailNum

# Insert Fixed Tests section before the timestamp
$fixedSection = @"
---

## Fixed Tests (Removed from Report)

The following tests were removed because a fix was identified after their last failure:

| Test | Last Failure | Fix | Fix Date | Reference |
|------|-------------|-----|----------|-----------|
| DriverBasedHookExclusion_DefaultArchitectureX64Process_FullPath | 2026-04-08 | PR | 2026-04-13 | [#3649](https://github.com/BeyondTrust/epm-windows/pull/3649) |
| DriverBasedHookExclusion_DefaultArchitectureX64Process_PartialPath | 2026-04-08 | PR | 2026-04-13 | [#3649](https://github.com/BeyondTrust/epm-windows/pull/3649) |
| Identity_MFACanBePassedWithChangedUserEmailAfterGroupRefresh | 2026-04-08 | PR | 2026-04-13 | [#3652](https://github.com/BeyondTrust/epm-windows/pull/3652) |
| JITAdmin_Auditing_GeneralRules_198 | 2026-03-27 | PR | 2026-03-31 | [#3550](https://github.com/BeyondTrust/epm-windows/pull/3550) |
| JITAdmin_Auditing_OnDemand_101 | 2026-03-27 | Jira | 2026-04-02 | [EPM-51855](https://beyondtrust.atlassian.net/browse/EPM-51855) |

"@

$result = $result -replace '(?=\*Generated )', "$fixedSection`r`n"

Set-Content -Path $inputPath -Value $result -Encoding UTF8 -NoNewline

Write-Host "Summary rows kept: $summaryNum"
Write-Host "Detail sections kept: $detailNum"
