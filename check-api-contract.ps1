Write-Host ""
Write-Host "OTA ARCHITECTURE VERIFICATION"
Write-Host ""

# Check inventory model
$inventory = Select-String -Path ".\apps\**\*.py" -Pattern "RoomInventory"

if (-not $inventory) {
 Write-Host "ERROR: RoomInventory model missing" -ForegroundColor Red
}

# Check booking context
$context = Select-String -Path ".\apps\**\*.py" -Pattern "BookingContext"

if (-not $context) {
 Write-Host "ERROR: BookingContext model missing" -ForegroundColor Red
}

# Check promo engine
$promo = Select-String -Path ".\apps\**\*.py" -Pattern "PromoCode"

if (-not $promo) {
 Write-Host "ERROR: PromoCode model missing" -ForegroundColor Red
}

# Check price intelligence
$intel = Select-String -Path ".\apps\**\*.py" -Pattern "CompetitorPrice"

if (-not $intel) {
 Write-Host "WARNING: price intelligence missing"
}

# Check filter_counts
$filters = Select-String -Path ".\apps\**\*.py" -Pattern "filter_counts"

if (-not $filters) {
 Write-Host "ERROR: filter_counts not implemented" -ForegroundColor Red
}

Write-Host ""
Write-Host "Verification complete."