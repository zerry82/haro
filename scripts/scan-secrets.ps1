param(
    [switch]$Staged,
    [switch]$All
)

$ErrorActionPreference = "SilentlyContinue"

$secretPatterns = @(
    @{ Name = "google_api_key"; Regex = "AIza[0-9A-Za-z\-_]{35}" },
    @{ Name = "openai_api_key"; Regex = "sk-[A-Za-z0-9_-]{20,}" },
    @{ Name = "anthropic_api_key"; Regex = "sk-ant-[A-Za-z0-9_-]{20,}" },
    @{ Name = "github_token"; Regex = "gh[pousr]_[A-Za-z0-9_]{36,}" },
    @{ Name = "slack_token"; Regex = "xox[baprs]-[A-Za-z0-9-]{20,}" },
    @{ Name = "npm_token"; Regex = "npm_[A-Za-z0-9]{36,}" },
    @{ Name = "huggingface_token"; Regex = "hf_[A-Za-z0-9]{30,}" },
    @{ Name = "aws_access_key_id"; Regex = "(?:AKIA|ASIA)[A-Z0-9]{16}" },
    @{ Name = "stripe_secret_key"; Regex = "sk_live_[0-9A-Za-z]{24,}" },
    @{ Name = "sendgrid_api_key"; Regex = "SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}" },
    @{ Name = "private_key_block"; Regex = "-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----" },
    @{ Name = "jwt_like_token"; Regex = "eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}" }
)

$assignmentRegex = "^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*(?:API[_-]?KEY|SECRET|PASSWORD|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET)[A-Za-z0-9_]*)\s*=\s*['""]?([^'""#\r\n]+)"
$placeholderRegex = "^(|0|1|false|true|null|none|secret|client-secret|client_secret|changeme|change[-_]?me|example|dummy|test|testing|placeholder|replace[-_]?me|your.*|<.*>|x{3,}|\*{3,}|dev-secret-key|your-secret-key-change-in-production)$"
$referenceRegex = '(os\.getenv|process\.env|import\.meta\.env|\$env:|getenv\(|Field\(|Depends\(|settings\.|config\.|BaseSettings|SecretStr|tokens?\[|data\[|params\[|self\.|_require|dict\()'
$nonSecretNameRegex = '(?i)(TOKEN_URL|TOKEN_STORE_DIR|PAGE_TOKEN|RAW_TOKENS?)$'

function Get-RelativePath([string]$Path) {
    $resolved = Resolve-Path -LiteralPath $Path
    if (-not $resolved) {
        return $Path
    }
    return Resolve-Path -Relative -LiteralPath $resolved.Path
}

function Get-LineNumber([string]$Text, [int]$Index) {
    if ($Index -le 0) {
        return 1
    }
    return ($Text.Substring(0, $Index).Split("`n").Count)
}

function Test-ProbablyText([byte[]]$Bytes) {
    if ($Bytes.Length -eq 0) {
        return $true
    }
    $limit = [Math]::Min($Bytes.Length, 4096)
    for ($i = 0; $i -lt $limit; $i++) {
        if ($Bytes[$i] -eq 0) {
            return $false
        }
    }
    return $true
}

function Get-CandidateFiles {
    if ($Staged) {
        return @(git diff --cached --name-only --diff-filter=ACMRT)
    }

    if ($All) {
        $tracked = @(git ls-files)
        $untracked = @(git ls-files --others --exclude-standard)
        return @($tracked + $untracked | Sort-Object -Unique)
    }

    return @(git ls-files)
}

function Scan-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }

    $item = Get-Item -LiteralPath $Path
    if ($item.Length -gt 5242880) {
        return @()
    }

    $bytes = [System.IO.File]::ReadAllBytes($item.FullName)
    if (-not (Test-ProbablyText $bytes)) {
        return @()
    }

    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    $hits = @()

    foreach ($pattern in $secretPatterns) {
        foreach ($match in [regex]::Matches($text, $pattern.Regex)) {
            $hits += [pscustomobject]@{
                Path = Get-RelativePath $Path
                Line = Get-LineNumber $text $match.Index
                Rule = $pattern.Name
            }
        }
    }

    $lines = $text -split "`r?`n"
    for ($lineIndex = 0; $lineIndex -lt $lines.Count; $lineIndex++) {
        $line = $lines[$lineIndex]
        $match = [regex]::Match($line, $assignmentRegex, "IgnoreCase")
        if (-not $match.Success) {
            continue
        }

        $name = $match.Groups[1].Value
        $value = $match.Groups[2].Value.Trim().Trim('"', "'", " ")
        if ([regex]::IsMatch($name, $nonSecretNameRegex)) {
            continue
        }
        if (-not $value) {
            continue
        }
        if ($value -match "^https?://") {
            continue
        }
        if ([regex]::IsMatch($value, $placeholderRegex, "IgnoreCase")) {
            continue
        }
        if ([regex]::IsMatch($value, $referenceRegex, "IgnoreCase")) {
            continue
        }
        if (($value.Length -lt 12) -and ($name -notmatch "(?i)(API[_-]?KEY|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET)")) {
            continue
        }

        $hits += [pscustomobject]@{
            Path = Get-RelativePath $Path
            Line = $lineIndex + 1
            Rule = "sensitive_assignment:$name"
        }
    }

    return $hits
}

$findings = @()
foreach ($file in Get-CandidateFiles) {
    $findings += Scan-File $file
}

if ($findings.Count -gt 0) {
    Write-Host "Possible secrets found. Values are intentionally omitted."
    $findings | Sort-Object Path, Line, Rule | Format-Table -AutoSize
    exit 1
}

Write-Host "No secret patterns found."
