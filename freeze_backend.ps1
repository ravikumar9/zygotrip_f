Write-Host "======================================"
Write-Host "Zygotrip Backend Cleanup + Freeze Tool"
Write-Host "======================================"

$root = Get-Location

Write-Host ""
Write-Host "Step 1: Removing Python cache folders..."

Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue


Write-Host ""
Write-Host "Step 2: Removing compiled python files..."

Get-ChildItem -Recurse -Include *.pyc,*.pyo -File -ErrorAction SilentlyContinue |
Remove-Item -Force


Write-Host ""
Write-Host "Step 3: Removing development junk folders..."

$junkDirs = @(
".claude",
".idea",
".vscode",
"logs"
)

foreach ($dir in $junkDirs) {
    Get-ChildItem -Recurse -Directory -Filter $dir -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}


Write-Host ""
Write-Host "Step 4: Removing temporary audit reports..."

$junkFiles = @(
"*AUDIT_REPORT*.md",
"*FREEZE_REPORT*.md",
"*CODEBASE_AUDIT*.md"
)

foreach ($pattern in $junkFiles) {
    Get-ChildItem -Filter $pattern -ErrorAction SilentlyContinue |
    Remove-Item -Force
}


Write-Host ""
Write-Host "Step 5: Creating .gitignore..."

@"
# Python
__pycache__/
*.pyc
*.pyo

# Virtual env
venv/

# Logs
logs/
*.log

# Local env
.env
.env.local

# Node
node_modules/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
"@ | Out-File .gitignore -Encoding utf8


Write-Host ""
Write-Host "Step 6: Initializing Git repository..."

if (!(Test-Path ".git")) {
    git init
}


Write-Host ""
Write-Host "Step 7: Adding project files..."

git add .


Write-Host ""
Write-Host "Step 8: Creating backend freeze commit..."

git commit -m "Backend Freeze v1 - OTA architecture stable"


Write-Host ""
Write-Host "Step 9: Creating version tag..."

git tag backend-freeze-v1


Write-Host ""
Write-Host "======================================"
Write-Host "Backend successfully frozen"
Write-Host "======================================"