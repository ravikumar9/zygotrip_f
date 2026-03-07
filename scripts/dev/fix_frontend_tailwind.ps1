Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " ZygoTrip Frontend Tailwind FULL FIX" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$frontendPath = ".\frontend"

if (!(Test-Path $frontendPath)) {
    Write-Host "ERROR: frontend folder not found!" -ForegroundColor Red
    exit
}

Set-Location $frontendPath

Write-Host ""
Write-Host "[1/5] Fixing Tailwind config..." -ForegroundColor Yellow

$tailwindConfig = @"
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}",
  ],

  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        secondary: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5f5",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
        }
      }
    }
  },

  plugins: []
}
"@

$tailwindConfig | Out-File -Encoding utf8 tailwind.config.js -Force

Write-Host "Tailwind config fixed" -ForegroundColor Green


Write-Host ""
Write-Host "[2/5] Fixing globals.css..." -ForegroundColor Yellow

$globalsCssPath = ".\app\globals.css"

if (!(Test-Path ".\app")) {
    New-Item -ItemType Directory -Path ".\app"
}

$globalsCss = @"
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {

.btn-primary {
    @apply inline-flex items-center justify-center px-5 py-2.5 rounded-xl
           bg-primary-600 text-white font-semibold text-sm
           hover:bg-primary-700 active:bg-primary-800;
}

}
"@

$globalsCss | Out-File -Encoding utf8 $globalsCssPath -Force

Write-Host "globals.css fixed" -ForegroundColor Green


Write-Host ""
Write-Host "[3/5] Cleaning Next.js cache..." -ForegroundColor Yellow

if (Test-Path ".next") {
    Remove-Item ".next" -Recurse -Force
}

Write-Host "Cache cleaned" -ForegroundColor Green


Write-Host ""
Write-Host "[4/5] Installing dependencies..." -ForegroundColor Yellow

npm install


Write-Host ""
Write-Host "[5/5] Starting frontend..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList "npm run dev"


Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " FRONTEND FIX COMPLETE" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Open browser:" -ForegroundColor Cyan
Write-Host "http://localhost:3000" -ForegroundColor White
Write-Host ""