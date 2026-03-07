# ==============================
# ZygoTrip Full Dev Bootstrap
# ==============================

Write-Host ""
Write-Host "Bootstrapping ZygoTrip Full Stack..."
Write-Host ""

# ------------------------------
# Kill Ports 3000 & 8000
# ------------------------------

function Kill-Port($portNumber) {
    $connections = netstat -ano | Select-String ":$portNumber"
    if ($connections) {
        foreach ($line in $connections) {
            $parts = $line -split "\s+"
            $processId = $parts[-1]
            if ($processId -match "^\d+$") {
                Write-Host "Killing port $portNumber (PID $processId)"
                taskkill /PID $processId /F | Out-Null
            }
        }
    }
}

Kill-Port 3000
Kill-Port 8000

Start-Sleep -Seconds 2

# ------------------------------
# Ensure frontend dependencies
# ------------------------------

Write-Host "Checking frontend dependencies..."
if (!(Test-Path "$PSScriptRoot\frontend\node_modules")) {
    Write-Host "Installing frontend packages..."
    cd "$PSScriptRoot\frontend"
    npm install
    cd "$PSScriptRoot"
}

# ------------------------------
# Fix turbopack if present
# ------------------------------

$packageJsonPath = "$PSScriptRoot\frontend\package.json"
$packageJson = Get-Content $packageJsonPath -Raw

if ($packageJson -match "--turbopack") {
    Write-Host "Removing unsupported --turbopack flag..."
    $packageJson = $packageJson -replace "--turbopack", ""
    Set-Content $packageJsonPath $packageJson
}

# ------------------------------
# Start Django Backend
# ------------------------------

Write-Host "Starting Django backend on 127.0.0.1:8000"

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
"cd '$PSScriptRoot'; .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000"

Start-Sleep -Seconds 4

# ------------------------------
# Start Next Frontend (Fixed Port)
# ------------------------------

Write-Host "Starting Next frontend on localhost:3000"

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
"cd '$PSScriptRoot\frontend'; npx next dev -p 3000"

Start-Sleep -Seconds 6

# ------------------------------
# Open Browser
# ------------------------------

Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "ZygoTrip is running."
Write-Host "Frontend: http://localhost:3000"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host ""