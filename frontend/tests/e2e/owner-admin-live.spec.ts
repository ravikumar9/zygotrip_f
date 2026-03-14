import { expect, test } from '@playwright/test';

async function signIntoDashboard(page: Parameters<typeof test>[0]['page'], email: string, password: string) {
  await page.goto('/account/login?next=/dashboard');

  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);

  const loginResponsePromise = page
    .waitForResponse(
      (response) => response.url().includes('/api/v1/auth/login/') && response.request().method() === 'POST',
      { timeout: 15000 },
    )
    .catch(() => null);
  await page.getByRole('button', { name: 'Sign In' }).click();
  const loginResponse = await loginResponsePromise;
  if (loginResponse) {
    expect(loginResponse.ok()).toBeTruthy();
  }

  await page.waitForLoadState('networkidle');
  if (!/\/dashboard$/.test(page.url())) {
    await page.goto('/dashboard');
  }
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function signIntoOwnerPortal(page: Parameters<typeof test>[0]['page'], email: string, password: string) {
  await page.goto('http://127.0.0.1:8000/login/?next=/owner/dashboard/');
  await page.locator('input[name="username"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForLoadState('networkidle');
  if (!/\/owner\/dashboard\/?$/.test(page.url())) {
    await page.goto('http://127.0.0.1:8000/owner/dashboard/');
  }
  await expect(page).toHaveURL(/\/owner\/dashboard\/?$/);
}

test('live property owner can sign in and view hotel inventory on dashboard', async ({ page }) => {
  await signIntoDashboard(page, 'owner-live@example.com', 'OwnerPass123');
  await expect(page.getByRole('heading', { name: 'Owner Dashboard' })).toBeVisible();
  await expect(page.getByText('Owner Live · property owner')).toBeVisible();
  await expect(page.getByText('Inventory Calendar')).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Deluxe Room' }).first()).toBeVisible();
});

test('live admin can inspect all operator tabs in Next dashboard', async ({ page }) => {
  await signIntoDashboard(page, 'admin-live@example.com', 'AdminPass123');
  await expect(page.getByText('Admin Live · admin')).toBeVisible();

  await page.getByRole('button', { name: 'Bus' }).click();
  await expect(page.getByText('Top Routes')).toBeVisible();
  await expect(page.getByText('Bangalore → Chennai')).toBeVisible();

  await page.getByRole('button', { name: 'Cab Fleet' }).click();
  await expect(page.getByText('Driver Performance')).toBeVisible();
  await expect(page.getByText('Driver Live')).toBeVisible();

  await page.getByRole('button', { name: 'Packages' }).click();
  await expect(page.getByText('Popular Packages')).toBeVisible();
  await expect(page.getByText('Coorg Escape Live')).toBeVisible();
});

test('live admin can access Django admin property and user changelists', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/admin/login/?next=/admin/');

  await page.locator('input[name="username"]').fill('admin-live@example.com');
  await page.locator('input[name="password"]').fill('AdminPass123');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page).toHaveURL(/\/admin\/$/);
  await page.goto('http://127.0.0.1:8000/admin/hotels/property/');
  await expect(page.getByText('Skyline Suites Live')).toBeVisible();

  await page.goto('http://127.0.0.1:8000/admin/accounts/user/');
  await expect(page.getByRole('link', { name: 'owner-live@example.com' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'admin-live@example.com' })).toBeVisible();
});

test('live admin can update property commission in Django admin', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/admin/login/?next=/admin/');

  await page.locator('input[name="username"]').fill('admin-live@example.com');
  await page.locator('input[name="password"]').fill('AdminPass123');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page).toHaveURL(/\/admin\/$/);
  await page.goto('http://127.0.0.1:8000/admin/hotels/property/');
  await page.getByRole('link', { name: 'Skyline Suites Live' }).click();

  const commissionField = page.locator('input[name="commission_percentage"]');
  await commissionField.fill('18.50');
  await page.locator('input[name="_save"]').click();

  await expect(page.getByText('was changed successfully')).toBeVisible();
  const propertyRow = page.locator('tr', {
    has: page.getByRole('link', { name: 'Skyline Suites Live' }),
  }).first();
  await expect(propertyRow.locator('td.field-commission_display')).toHaveText('18.50%');
});

test('live owner can register and configure a resort across owner control pages', async ({ page }) => {
  const uniqueSuffix = Date.now().toString().slice(-6);
  const propertyName = `Playwright Valley Resort ${uniqueSuffix}`;
  const roomName = `Forest Villa ${uniqueSuffix}`;

  await signIntoOwnerPortal(page, 'owner-live@example.com', 'OwnerPass123');
  await page.goto('http://127.0.0.1:8000/owner/dashboard/properties/add/');

  const firstCityValue = await page.locator('#id_city option:not([value=""])').first().getAttribute('value');
  expect(firstCityValue).toBeTruthy();

  await page.locator('#id_name').fill(propertyName);
  await page.locator('#id_property_type').fill('Resort');
  await page.locator('#id_city').selectOption(firstCityValue!);
  await page.locator('#id_area').fill('Valley Ridge');
  await page.locator('#id_landmark').fill('Near Pine Forest Gate');
  await page.locator('#id_address').fill('88 Valley Ridge Road, Bengaluru');
  await page.locator('#id_description').fill('A hillside resort with spa, forest decks, and premium villa stays.');
  await page.locator('#id_place_id').fill(`playwright-place-${uniqueSuffix}`);
  await page.locator('#id_formatted_address').fill('88 Valley Ridge Road, Bengaluru, Karnataka, India');
  await page.locator('#id_latitude').fill('12.971600');
  await page.locator('#id_longitude').fill('77.594600');
  await page.locator('#id_country').fill('India');
  await page.locator('#image_url').fill('https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80');
  await page.getByRole('button', { name: 'Create Property' }).click();

  await expect(page.getByText('Property created. Continue with gallery, rooms, and inventory to complete setup.')).toBeVisible();
  const propertyCard = page.locator('.property-card').filter({ hasText: propertyName }).first();
  await expect(propertyCard).toBeVisible();

  await propertyCard.getByRole('link', { name: 'Edit' }).click();
  await page.locator('#id_property_type').fill('Luxury Resort');
  await page.locator('#id_tags').fill('Spa Resort, Valley View, Couple Friendly');
  await page.locator('textarea[name="amenities_list"]').fill('Infinity Pool\nSpa\nKids Club');
  await page.getByRole('button', { name: 'Save Changes' }).click();
  await expect(page.getByText('Property features updated successfully!')).toBeVisible();

  const updatedCard = page.locator('.property-card').filter({ hasText: propertyName }).first();
  await updatedCard.getByRole('link', { name: 'Gallery' }).click();
  await page.locator('input[name="image_url"]').fill('https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=80');
  await page.locator('input[name="caption"]').fill('Sunrise deck view');
  await page.locator('input[name="is_featured"]').check();
  await page.getByRole('button', { name: 'Upload Image' }).click();
  await expect(page.getByText('Image uploaded successfully.')).toBeVisible();

  const galleryCard = page.locator('.property-card').filter({ hasText: propertyName }).first();
  await expect(galleryCard).toContainText('2 photos');
  await galleryCard.getByRole('link', { name: 'Rooms' }).click();
  await page.locator('input[name="name"]').fill(roomName);
  await page.locator('textarea[name="description"]').fill('Private villa with deck, rainfall shower, and valley-facing balcony.');
  await page.locator('input[name="base_price"]').fill('6999');
  await page.locator('input[name="max_guests"]').fill('4');
  await page.locator('input[name="available_count"]').fill('5');
  await page.locator('input[name="bed_type"]').fill('King Bed');
  await page.locator('input[name="room_size_sqm"]').fill('46');
  await page.getByRole('button', { name: 'Create Room Type' }).click();
  await expect(page.getByText('Room added.')).toBeVisible();

  const roomCard = page.locator('.property-card').filter({ hasText: propertyName }).first();
  await expect(roomCard).toContainText('1 rooms');
  await roomCard.getByRole('link', { name: 'Inventory' }).click();
  await page.locator('#bulk_property').selectOption({ label: propertyName });
  await page.locator('#bulk_start_date').fill('2026-04-10');
  await page.locator('#bulk_end_date').fill('2026-04-11');
  await page.locator('#bulk_room_type').selectOption({ label: roomName });
  await page.locator('#bulk_rooms').fill('5');
  await page.locator('#bulk_price').fill('6999');
  await page.getByRole('button', { name: 'Apply Bulk Update' }).click();

  const inventoryRow = page.locator('.inventory-table tbody tr').filter({ hasText: roomName }).first();
  await expect(inventoryRow).toBeVisible();
  await expect(inventoryRow).toContainText('₹6999');
});

test('live hotel details page renders core Goibibo-style sections cleanly', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/hotels/hotel-details/?property=skyline-suites-live&checkin=2026-04-10&checkout=2026-04-12&rooms=1&adults=2');

  await expect(page.getByRole('heading', { name: 'Skyline Suites Live' })).toBeVisible();
  await expect(page.getByText('Available Rooms')).toBeVisible();
  await expect(page.getByText('Amenities')).toBeVisible();
  await expect(page.getByText('Policies')).toBeVisible();
  await expect(page.getByText('Guest Reviews')).toBeVisible();
  await expect(page.getByText('Check-in')).toBeVisible();
  await expect(page.getByText('Deluxe Room')).toBeVisible();
});