Write-Host "==========================================="
Write-Host "Zygotrip Repo Cleanup Before Git Push"
Write-Host "==========================================="

Write-Host ""
Write-Host "Step 1: Remove Next.js build artifacts (.next)"

if (Test-Path "frontend/.next") {
    git rm -r --cached frontend/.next 2>$null
    Remove-Item -Recurse -Force frontend/.next
}

Write-Host ""
Write-Host "Step 2: Remove Node modules"

if (Test-Path "frontend/node_modules") {
    git rm -r --cached frontend/node_modules 2>$null
    Remove-Item -Recurse -Force frontend/node_modules
}

Write-Host ""
Write-Host "Step 3: Remove Python virtual environment"

if (Test-Path "venv") {
    git rm -r --cached venv 2>$null
}

Write-Host ""
Write-Host "Step 4: Remove Python cache files"

Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -Recurse -Include *.pyc,*.pyo -File -ErrorAction SilentlyContinue |
Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Step 5: Remove deprecated / backup files"

Get-ChildItem -Recurse -Include *.bak,*.old,*DEPRECATED* -File -ErrorAction SilentlyContinue |
Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Step 6: Clean logs"

if (Test-Path "logs") {
    Remove-Item -Recurse -Force logs
}

Write-Host ""
Write-Host "Step 7: Recreate .gitignore"

@"
# ================================
# Python
# ================================
venv/
__pycache__/
*.pyc
*.pyo

# ================================
# Node
# ================================
node_modules/
frontend/node_modules/

# ================================
# Next.js
# ================================
.next/
frontend/.next/

# ================================
# Logs
# ================================
logs/
*.log

# ================================
# Environment
# ================================
.env
.env.local

# ================================
# IDE
# ================================
.vscode/
.idea/
.claude/

# ================================
# OS
# ================================
.DS_Store
Thumbs.db

# ================================
# Build
# ================================
dist/
build/
out/
"@ | Out-File .gitignore -Encoding utf8

Write-Host ""
Write-Host "Step 8: Remove ignored files from Git index"

git rm -r --cached . 2>$null

Write-Host ""
Write-Host "Step 9: Re-add clean project files"

git add .

Write-Host ""
Write-Host "Step 10: Commit cleanup"

git commit -m "Repository cleanup before push - remove build artifacts and junk"

Write-Host ""
Write-Host "==========================================="
Write-Host "Repository cleaned successfully"
Write-Host "Safe to push to GitHub now"
Write-Host "==========================================="