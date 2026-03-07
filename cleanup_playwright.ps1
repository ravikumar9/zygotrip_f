$root = Get-Location
$frontend = Join-Path $root "frontend"
$automation = Join-Path $root "automation\e2e"

Write-Host "Starting Playwright cleanup..."

# create automation folders

if (!(Test-Path $automation)) {
New-Item -ItemType Directory -Path $automation -Force | Out-Null
}

# possible playwright artifacts

$paths = @(
"playwright.config.ts",
"playwright.config.js",
"tests",
"test-results",
"playwright-report"
)

foreach ($p in $paths) {

$src = Join-Path $frontend $p

if (Test-Path $src) {

Write-Host "Moving $p to automation\e2e"

Move-Item $src $automation -Force
}
}

Write-Host ""
Write-Host "Uninstalling Playwright from frontend..."

Set-Location $frontend

npm uninstall @playwright/test playwright playwright-core 2>$null

Write-Host ""
Write-Host "Initializing automation Playwright environment..."

Set-Location $automation

if (!(Test-Path "package.json")) {
npm init -y | Out-Null
}

npm install -D @playwright/test | Out-Null

Write-Host ""
Write-Host "Installing Playwright browsers..."

npx playwright install | Out-Null

Set-Location $root

Write-Host ""
Write-Host "Playwright environment organized successfully."
Write-Host "Automation tests now live in: automation\e2e"
