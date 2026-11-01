import { defineConfig, devices } from '@playwright/test';
const testStorage = `./data/e2e-${Date.now()}`;

export default defineConfig({
  testDir: './tests/real',
  outputDir: './test-results/real',
  workers: 1,
  timeout: 45000,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
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
  webServer: {
    command: 'python ../dev.py',
    env: {
      DATABASE_URL: `sqlite:///${testStorage}/app.sqlite3`,
      GRAPH_CHECKPOINT_DB: `${testStorage}/graph.sqlite3`,
      STORAGE_ROOT: `${testStorage}/files`,
      APP_ENV: 'demo',
      MODEL_API_KEY: '',
      MODEL_NAME: '',
      ALLOWED_ORIGINS: 'http://127.0.0.1:5173',
      DEMO_EMAIL: 'demo@navowork.local',
      DEMO_PASSWORD: 'ChangeMe123!',
    },
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: false,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 10000 },
    timeout: 60000,
  },
});
