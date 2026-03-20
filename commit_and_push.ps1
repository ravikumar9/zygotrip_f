# Run this from: C:\Users\ravi9\Downloads\Zygo\Copilot_code\deployment
# It updates .gitignore, stages everything safe, commits and pushes

$gitignoreAdditions = @"

# ── ZygoTrip: Never commit these ────────────────────────────────────────────
.env
.env.local
.env.production
.env.staging
*.env

# Temp/audit files
.tmp_*.py
zygotrip_full_audit_temp/
*.zip
ui_screenshots/
ui_screenshots.zip

# Logs
*.log
logs/
server.log
seed_*.log
seed_*.txt

# Python
venv/
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Node
node_modules/
.next/
frontend/.next/
frontend/node_modules/

# IDE
.claude/
.idea/
*.suo
*.user

# Media uploads (never commit user uploads)
media/

# Static collected files (generated on server)
staticfiles/
"@

# Append to .gitignore if not already there
$existing = Get-Content .gitignore -Raw -ErrorAction SilentlyContinue
if ($existing -notlike "*zygotrip_full_audit_temp*") {
    Add-Content .gitignore $gitignoreAdditions
    Write-Host "✅ .gitignore updated" -ForegroundColor Green
} else {
    Write-Host "✅ .gitignore already has entries" -ForegroundColor Yellow
}

# Stage everything (gitignore will exclude the dangerous files)
git add .

# Show what's staged (so you can verify)
Write-Host "`n📦 Files staged for commit:" -ForegroundColor Cyan
git diff --cached --name-only | Measure-Object | Select-Object -ExpandProperty Count | ForEach-Object { Write-Host "  Total files: $_" }
git diff --cached --name-only

# Commit
$commitMsg = "feat: complete platform - auth, checkout inventory fix, loyalty, notifications, referrals, support, tests, platform config, admin upgrades

- Fix: InventoryCalendar auto-init on checkout (root cause of 400 error)
- Fix: Profile API field name mismatch (full_name vs name)
- Add: Email+password login as primary auth (OTP cost optimization)
- Add: Loyalty, Notifications, Referrals, Support apps
- Add: Platform config API with correct Flutter response shape
- Add: Maintenance middleware, service guard, feature flags
- Add: Complete test suite (wallet, loyalty, pricing, booking saga)
- Add: Hotel detail page and checkout session page (Next.js)
- Fix: Same-day check-in date validation
- Fix: track-click 500 → always 200
- Add: init_inventory_calendar management command
- Add: seed_e2e now initializes InventoryCalendar rows"

git commit -m $commitMsg

# Push
Write-Host "`n🚀 Pushing to origin/main..." -ForegroundColor Cyan
git push origin main

Write-Host "`n✅ Done! Check https://github.com/ravikumar9/zygotrip_f" -ForegroundColor Green