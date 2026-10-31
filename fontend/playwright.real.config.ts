import { defineConfig, devices } from '@playwright/test';
const testStorage = `./data/e2e-${Date.now()}`;

export default defineConfig({
  testDir: './tests/real',
  workers: 1,
  timeout: 45000,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5178', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: process.platform === 'win32' ? { executablePath: process.env.PLAYWRIGHT_BROWSER_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' } : {} } }],
  webServer: {
    command: 'python ../dev.py',
    env: { DATABASE_URL: `sqlite:///${testStorage}/app.sqlite3`, GRAPH_CHECKPOINT_DB: `${testStorage}/graph.sqlite3`,
      STORAGE_ROOT: `${testStorage}/files`, APP_ENV: 'demo', MODEL_API_KEY: '', MODEL_NAME: '',
      APP_API_PORT: '8011', APP_UI_PORT: '5178',
      ALLOWED_ORIGINS: 'http://127.0.0.1:5178', DEMO_EMAIL: 'demo@navowork.local', DEMO_PASSWORD: 'ChangeMe123!' },
    url: 'http://127.0.0.1:5178',
    reuseExistingServer: false,
    timeout: 60000,
  },
});
