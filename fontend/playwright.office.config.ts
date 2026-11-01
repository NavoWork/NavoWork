import { defineConfig, devices } from '@playwright/test';

// Run against an isolated real API + Vite process; no network mocks or fake Office files.
export default defineConfig({
  testDir: './tests/office',
  workers: 1,
  timeout: 60000,
  reporter: 'list',
  outputDir: './test-results/office',
  use: {
    baseURL: process.env.OFFICE_UI_URL || 'http://127.0.0.1:5187',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          executablePath:
            process.env.PLAYWRIGHT_BROWSER_PATH ||
            (process.platform === 'win32'
              ? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
              : undefined),
        },
      },
    },
  ],
});
