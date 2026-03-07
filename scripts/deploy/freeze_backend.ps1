Write-Host "==========================================="
Write-Host "Zygotrip Repository Structure Cleanup"
Write-Host "==========================================="

# ------------------------------------------------
# Create clean structure
# ------------------------------------------------

Write-Host "Creating folders..."

$folders = @(
"docs",
"docs/archive",
"scripts",
"scripts/dev",
"scripts/deploy",
"archive"
)

foreach ($folder in $folders) {
    if (!(Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder | Out-Null
    }
}

# ------------------------------------------------
# Move unnecessary markdown reports
# ------------------------------------------------

Write-Host "Moving audit and temporary documentation..."

Get-ChildItem -Filter "*REPORT*.md" -ErrorAction SilentlyContinue | Move-Item -Destination "docs/archive" -Force
Get-ChildItem -Filter "*AUDIT*.md" -ErrorAction SilentlyContinue | Move-Item -Destination "docs/archive" -Force
Get-ChildItem -Filter "*FREEZE*.md" -ErrorAction SilentlyContinue | Move-Item -Destination "docs/archive" -Force

# ------------------------------------------------
# Move development scripts
# ------------------------------------------------

Write-Host "Organizing scripts..."

$devScripts = @(
"cleanup_playwright.ps1",
"check-api-contract.ps1",
"fix_frontend_tailwind.ps1",
"start-dev.ps1"
)

foreach ($script in $devScripts) {
    if (Test-Path $script) {
        Move-Item $script "scripts/dev/" -Force
    }
}

$deployScripts = @(
"bootstrap_FULL_OTA.ps1",
"freeze_backend.ps1"
)

foreach ($script in $deployScripts) {
    if (Test-Path $script) {
        Move-Item $script "scripts/deploy/" -Force
    }
}

# ------------------------------------------------
# Remove temporary tools
# ------------------------------------------------

Write-Host "Removing temporary scripts..."

$tempScripts = @(
"tree_view.ps1",
"create_full_audit_zip.ps1"
)

foreach ($script in $tempScripts) {
    if (Test-Path $script) {
        Remove-Item $script -Force
    }
}

# ------------------------------------------------
# Archive legacy UI
# ------------------------------------------------

Write-Host "Archiving legacy UI..."

if (Test-Path "legacy_ui") {
    Move-Item "legacy_ui" "archive/legacy_ui"
}

# ------------------------------------------------
# Move project tree file
# ------------------------------------------------

if (Test-Path "PROJECT_TREE.txt") {
    Move-Item "PROJECT_TREE.txt" "docs/archive/"
}

# ------------------------------------------------
# Git commit cleanup
# ------------------------------------------------

Write-Host "Adding cleanup changes to git..."

git add .

git commit -m "Repository cleanup: organize docs, scripts, archive legacy UI"

Write-Host "==========================================="
Write-Host "Repository structure cleaned successfully"
Write-Host "Backend frozen and ready for frontend work"
Write-Host "==========================================="