import { expect, test } from '@playwright/test';

const ownerUser = {
  id: 101,
  email: 'owner-ui@example.com',
  full_name: 'Owner UI',
  phone: '9999999999',
  role: 'property_owner',
};

const adminUser = {
  id: 1,
  email: 'admin-ui@example.com',
  full_name: 'Admin UI',
  phone: '9999999998',
  role: 'admin',
};

async function mockCurrencyApis(page: Parameters<typeof test>[0]['page']) {
  await page.route('**/api/v1/currency/rates/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { base: 'INR', rates: { INR: 1 } } }),
    });
  });
  await page.route('**/api/v1/currency/supported/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: [{ code: 'INR', symbol: '₹', name: 'Indian Rupee' }] }),
    });
  });
  await page.route('**/api/v1/currency/detect/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { code: 'INR' } }),
    });
  });
}

async function mockOwnerDashboardApis(page: Parameters<typeof test>[0]['page']) {
  await mockCurrencyApis(page);
  await page.route('**/api/v1/users/me/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: ownerUser }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/summary/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_bookings: 42,
        confirmed_bookings: 39,
        total_revenue: '185000.00',
        avg_occupancy: 78.4,
        trend: [
          { date: '2026-03-01', bookings: 12, revenue: 50000 },
          { date: '2026-03-02', bookings: 9, revenue: 42000 },
        ],
      }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/analytics/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status_breakdown: [
          { status: 'confirmed', count: 39 },
          { status: 'cancelled', count: 3 },
        ],
        top_rooms: [
          { room: 'Deluxe Room', bookings: 20, revenue: 90000 },
          { room: 'Suite', bookings: 8, revenue: 55000 },
        ],
        repeat_rate: 32.5,
        avg_lead_time_days: 6,
        monthly_trend: [],
      }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/revenue/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        gross_revenue: '210000.00',
        commission: '25000.00',
        commission_rate: 11.9,
        gst_on_commission: '4500.00',
        gateway_fees: '1900.00',
        net_payout: '182600.00',
        pending_settlement: '32000.00',
        last_settlement_date: null,
      }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/inventory/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        inventory: [
          {
            date: '2026-03-15',
            room_type: 'Deluxe Room',
            total: 10,
            available: 6,
            booked: 4,
            held: 0,
            price: 4750,
          },
        ],
      }),
    });
  });
}

async function mockAdminDashboardApis(page: Parameters<typeof test>[0]['page']) {
  await mockCurrencyApis(page);
  await page.route('**/api/v1/users/me/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: adminUser }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/summary/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_bookings: 125,
        confirmed_bookings: 111,
        total_revenue: '605000.00',
        avg_occupancy: 81,
        trend: [],
      }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/analytics/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status_breakdown: [], top_rooms: [], repeat_rate: 24, avg_lead_time_days: 5, monthly_trend: [] }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/revenue/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        gross_revenue: '700000.00',
        commission: '70000.00',
        commission_rate: 10,
        gst_on_commission: '12600.00',
        gateway_fees: '8500.00',
        net_payout: '621500.00',
        pending_settlement: '58000.00',
        last_settlement_date: null,
      }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/inventory/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ inventory: [] }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/bus/dashboard/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_buses: 18,
        active_schedules: 26,
        total_bookings: 390,
        total_revenue: '980000.00',
        occupancy_rate: 73,
        routes: [{ route: 'Bangalore → Chennai', bookings: 120, revenue: 340000, occupancy: 79 }],
      }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/cab/dashboard/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_vehicles: 42,
        active_drivers: 31,
        total_trips: 516,
        total_revenue: '412000.00',
        avg_rating: 4.7,
        drivers: [{ name: 'Fleet Driver', trips: 48, rating: 4.9, earnings: 62000 }],
      }),
    });
  });
  await page.route('**/api/v1/dashboard/owner/package/dashboard/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_packages: 27,
        active_departures: 9,
        total_bookings: 133,
        total_revenue: '560000.00',
        popular_packages: [{ name: 'Coorg Escape', bookings: 28, revenue: 168000 }],
      }),
    });
  });
}

test('property owner can register and land on a working dashboard', async ({ page }) => {
  await mockOwnerDashboardApis(page);

  await page.route('**/api/v1/auth/register/', async (route) => {
    const request = route.request();
    const payload = request.postDataJSON();
    expect(payload.role).toBe('property_owner');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          user: ownerUser,
          tokens: {
            access: 'owner-access-token',
            refresh: 'owner-refresh-token',
          },
        },
      }),
    });
  });

  await page.goto('/account/register/property');
  await expect(page.getByText('🏨 Property Owner Account')).toBeVisible();

  const inputs = page.locator('input');
  await inputs.nth(0).fill('Owner UI');
  await inputs.nth(1).fill('owner-ui@example.com');
  await inputs.nth(2).fill('9999999999');
  await inputs.nth(4).fill('OwnerPass123');
  await page.getByRole('button', { name: 'Create Property Owner Account' }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: 'Owner Dashboard' })).toBeVisible();
  await expect(page.getByText('Owner UI · property owner')).toBeVisible();
  await expect(page.getByText('42')).toBeVisible();
  await expect(page.getByText('Revenue Breakdown')).toBeVisible();
  await expect(page.getByText('Inventory Calendar')).toBeVisible();
});

test('admin can switch across all owner control panels', async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('zygotrip_refresh', 'admin-refresh-token');
  });
  await mockAdminDashboardApis(page);

  await page.goto('/dashboard');

  await expect(page.getByText('Admin UI · admin')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Hotel' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Bus' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Cab Fleet' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Packages' })).toBeVisible();

  await page.getByRole('button', { name: 'Bus' }).click();
  await expect(page.getByText('Top Routes')).toBeVisible();
  await expect(page.getByText('Bangalore → Chennai')).toBeVisible();

  await page.getByRole('button', { name: 'Cab Fleet' }).click();
  await expect(page.getByText('Driver Performance')).toBeVisible();
  await expect(page.getByText('Fleet Driver')).toBeVisible();

  await page.getByRole('button', { name: 'Packages' }).click();
  await expect(page.getByText('Popular Packages')).toBeVisible();
  await expect(page.getByText('Coorg Escape')).toBeVisible();
});