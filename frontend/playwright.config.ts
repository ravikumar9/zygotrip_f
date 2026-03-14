import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const backendPython = path.resolve(__dirname, '../venv/Scripts/python.exe');
const backendManagePy = path.resolve(__dirname, '../manage.py');

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${backendPython}" "${backendManagePy}" runserver 127.0.0.1:8000 --noreload`,
      cwd: __dirname,
      url: 'http://127.0.0.1:8000/admin/login/',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev:next',
      cwd: __dirname,
      url: 'http://127.0.0.1:3000',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});