Write-Host ""
Write-Host "Starting FULL audit ZIP creation..." -ForegroundColor Cyan

Add-Type -AssemblyName System.IO.Compression.FileSystem

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = "zygotrip_FULL_AUDIT_$timestamp.zip"
$tempDir = "zygotrip_full_audit_temp"

# Exclude junk folders
$excludeDirs = @(
    ".venv",
    ".claude",
    ".git",
    ".pytest_cache",
    "__pycache__",
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
    ".cache",
    "frontend\src"
)

# Include production folders
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

# Include production root files
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

# Clean previous temp
if (Test-Path $tempDir) {
    Write-Host "Removing old temp directory..."
    Remove-Item $tempDir -Recurse -Force
}

New-Item -ItemType Directory -Path $tempDir | Out-Null

# Safe copy function
function Copy-Safe($sourceDir) {

    Write-Host "Scanning: $sourceDir"

    Get-ChildItem -Path $sourceDir -Recurse -Force | ForEach-Object {

        $fullPath = $_.FullName

        foreach ($exclude in $excludeDirs) {

            if ($fullPath -like "*\$exclude*") {
                return
            }
        }

        $destPath = $fullPath.Replace((Get-Location).Path, "$tempDir")

        if ($_.PSIsContainer) {

            if (!(Test-Path $destPath)) {
                New-Item -ItemType Directory -Path $destPath -Force | Out-Null
            }

        } else {

            $parent = Split-Path $destPath -Parent

            if (!(Test-Path $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }

            Copy-Item $fullPath $destPath -Force
        }
    }
}

# Copy directories
Write-Host ""
Write-Host "Copying production directories..." -ForegroundColor Yellow

foreach ($dir in $includeDirs) {

    if (Test-Path $dir) {

        Write-Host "Including directory: $dir"
        Copy-Safe $dir

    } else {

        Write-Host "Skipping missing directory: $dir"
    }
}

# Copy root files
Write-Host ""
Write-Host "Copying root files..." -ForegroundColor Yellow

foreach ($file in $includeFiles) {

    if (Test-Path $file) {

        Write-Host "Including file: $file"
        Copy-Item $file "$tempDir\$file" -Force

    } else {

        Write-Host "Skipping missing file: $file"
    }
}

# Compress ZIP
Write-Host ""
Write-Host "Creating ZIP archive..." -ForegroundColor Yellow

[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $zipPath)

# Cleanup
Remove-Item $tempDir -Recurse -Force

Write-Host ""
Write-Host "SUCCESS: Audit ZIP created:" -ForegroundColor Green
Write-Host $zipPath
Write-Host ""