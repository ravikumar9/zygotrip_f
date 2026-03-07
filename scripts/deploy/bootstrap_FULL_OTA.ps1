Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " ZygoTrip FULL OTA Bootstrap (PRODUCTION)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

$PROJECT_ROOT = Get-Location

$env:DJANGO_SECRET_KEY="dev-secret-key"
$env:DEBUG="true"
$env:POSTGRES_DB="zygotrip"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="postgres"
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"

# --------------------------------------------------
# STEP 1 — PYTHON ENVIRONMENT
# --------------------------------------------------

Write-Host "`n[1/7] Setting up Python environment..." -ForegroundColor Yellow

if (!(Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip wheel setuptools

# --------------------------------------------------
# STEP 2 — INSTALL BACKEND DEPENDENCIES
# --------------------------------------------------

Write-Host "`n[2/7] Installing backend dependencies..." -ForegroundColor Yellow

pip install -r requirements.txt

pip install `
djangorestframework-simplejwt `
psycopg2-binary `
pillow `
faker `
python-dotenv `
django-cors-headers

# --------------------------------------------------
# STEP 3 — DATABASE MIGRATIONS
# --------------------------------------------------

Write-Host "`n[3/7] Running migrations..." -ForegroundColor Yellow

python manage.py migrate --noinput

# --------------------------------------------------
# STEP 4 — CREATE ADMIN USER
# --------------------------------------------------

Write-Host "`n[4/7] Creating admin user..." -ForegroundColor Yellow

python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
email='admin@zygotrip.com';
password='Admin@123';
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email,password=password);
    print('Admin created');
else:
    print('Admin already exists');
"

# --------------------------------------------------
# STEP 5 — SEED OTA DATA
# --------------------------------------------------

Write-Host "`n[5/7] Seeding OTA hotels..." -ForegroundColor Yellow

python manage.py shell -c "

import random
from faker import Faker
from apps.hotels.models import Property
fake = Faker()

if Property.objects.count()==0:
    cities=[
        ('Bangalore',12.9716,77.5946),
        ('Hyderabad',17.3850,78.4867),
        ('Mumbai',19.0760,72.8777),
        ('Delhi',28.7041,77.1025),
        ('Chennai',13.0827,80.2707)
    ]

    for city,lat,lng in cities:
        for i in range(10):
            Property.objects.create(
                name=fake.company()+' Hotel',
                city=city,
                latitude=lat+random.uniform(-0.05,0.05),
                longitude=lng+random.uniform(-0.05,0.05),
                address=fake.address(),
                description=fake.text(),
                is_active=True
            )

    print('OTA hotels seeded')
else:
    print('Hotels already exist')
"

# --------------------------------------------------
# STEP 6 — FRONTEND INSTALL
# --------------------------------------------------

Write-Host "`n[6/7] Installing frontend dependencies..." -ForegroundColor Yellow

if (Test-Path "frontend") {

    Push-Location frontend

    if (!(Test-Path "node_modules")) {

        npm install

    }

    Pop-Location

}

# --------------------------------------------------
# STEP 7 — START SERVERS
# --------------------------------------------------

Write-Host "`n[7/7] Starting servers..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList "-NoExit","-Command",".\.venv\Scripts\Activate.ps1; python manage.py runserver"

Start-Sleep -Seconds 3

if (Test-Path "frontend") {

Start-Process powershell -ArgumentList "-NoExit","-Command","cd frontend; npm run dev"

}

# --------------------------------------------------
# COMPLETE
# --------------------------------------------------

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " ZygoTrip OTA READY" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "Frontend: http://localhost:3000"
Write-Host "Admin: http://127.0.0.1:8000/admin"
Write-Host ""
Write-Host "Login:"
Write-Host "admin@zygotrip.com"
Write-Host "Admin@123"
Write-Host ""