Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ZygoTrip FULL Production Audit ZIP Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Add-Type -AssemblyName System.IO.Compression.FileSystem

$ErrorActionPreference = "Stop"

$root = Get-Location
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$zipName = "zygotrip_FULL_AUDIT_$timestamp.zip"
$tempDir = Join-Path $root "zygotrip_full_audit_temp"

# EXCLUDE ONLY NON-PRODUCTION / HEAVY / CACHE
$excludeDirs = @(
    ".venv",
    ".git",
    ".claude",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
    "logs",
    "staticfiles",
    "test-results",
    "playwright-report",
    "playwright",
    "e2e_artifacts",
    "e2e_screenshots",
    "e2e_videos",
    ".turbo",
    ".cache"
)

# INCLUDE ALL CORE APP DIRECTORIES
$includeDirs = @(
    "apps",
    "frontend",
    "zygotrip_project",
    "deployment",
    "templates",
    "static",
    "utils",
    "validators",
    "tools"
)

# INCLUDE ROOT PRODUCTION FILES
$includeFiles = @(
    "manage.py",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    ".env.example",
    ".env.production.template",
    "README.md",
    "package.json",
    "postcss.config.js"
)

# CLEAN OLD TEMP
if (Test-Path $tempDir)
{
    Write-Host "Removing previous temp directory..."
    Remove-Item $tempDir -Recurse -Force
}

New-Item -ItemType Directory -Path $tempDir | Out-Null

function Is-Excluded($path)
{
    foreach ($exclude in $excludeDirs)
    {
        if ($path -match [regex]::Escape($exclude))
        {
            return $true
        }
    }
    return $false
}

function Copy-DirectorySafe($sourceDir)
{
    Write-Host "Scanning directory: $sourceDir" -ForegroundColor Yellow

    Get-ChildItem -Path $sourceDir -Recurse -Force | ForEach-Object {

        $fullPath = $_.FullName

        if (Is-Excluded $fullPath)
        {
            return
        }

        $relativePath = $fullPath.Substring($root.Path.Length).TrimStart("\")
        $destPath = Join-Path $tempDir $relativePath

        if ($_.PSIsContainer)
        {
            if (!(Test-Path $destPath))
            {
                New-Item -ItemType Directory -Path $destPath | Out-Null
            }
        }
        else
        {
            $destFolder = Split-Path $destPath -Parent

            if (!(Test-Path $destFolder))
            {
                New-Item -ItemType Directory -Path $destFolder -Force | Out-Null
            }

            Copy-Item $fullPath $destPath -Force
        }
    }
}

Write-Host ""
Write-Host "Copying application directories..." -ForegroundColor Cyan

foreach ($dir in $includeDirs)
{
    $fullDir = Join-Path $root $dir

    if (Test-Path $fullDir)
    {
        Write-Host "Including: $dir"
        Copy-DirectorySafe $fullDir
    }
    else
    {
        Write-Host "Skipping missing directory: $dir" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "Copying root files..." -ForegroundColor Cyan

foreach ($file in $includeFiles)
{
    $fullFile = Join-Path $root $file

    if (Test-Path $fullFile)
    {
        Write-Host "Including file: $file"
        Copy-Item $fullFile (Join-Path $tempDir $file) -Force
    }
}

Write-Host ""
Write-Host "Creating ZIP archive..." -ForegroundColor Cyan

$zipPath = Join-Path $root $zipName

if (Test-Path $zipPath)
{
    Remove-Item $zipPath -Force
}

[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $zipPath)

Write-Host "Cleaning temp files..."
Remove-Item $tempDir -Recurse -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SUCCESS: Audit ZIP created" -ForegroundColor Green
Write-Host $zipPath -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
Write-Host ""