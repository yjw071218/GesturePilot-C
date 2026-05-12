param(
    [string]$TargetDir = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")

if ([string]::IsNullOrWhiteSpace($TargetDir)) {
    $TargetDir = Join-Path $projectRoot "data\raw\sign-language-digits"
}

if (Test-Path $TargetDir) {
    Remove-Item -Recurse -Force $TargetDir
}

git clone --depth 1 https://github.com/ardamavi/Sign-Language-Digits-Dataset.git $TargetDir

if (Test-Path (Join-Path $TargetDir ".git")) {
    Remove-Item -Recurse -Force (Join-Path $TargetDir ".git")
}

Write-Output "Dataset downloaded to: $TargetDir"

