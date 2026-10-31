import { defineConfig, devices } from '@playwright/test';

const storage = `./data/file-tools-e2e-${Date.now()}`;
export default defineConfig({
  testDir: './tests/file-tools',
  workers: 1,
  timeout: 45000,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: process.platform === 'win32' ? {
    executablePath: process.env.PLAYWRIGHT_BROWSER_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  } : {} } }],
  webServer: {
    command: process.platform === 'win32' ? '"../backend/.venv/Scripts/python.exe" ../dev.py' : '../backend/.venv/bin/python ../dev.py',
    env: { DATABASE_URL: `sqlite:///${storage}/app.sqlite3`, GRAPH_CHECKPOINT_DB: `${storage}/graph.sqlite3`,
      FILE_GRAPH_CHECKPOINT_DB: `${storage}/file-graph.sqlite3`, STORAGE_ROOT: `${storage}/files`,
      APP_ENV: 'demo', AGENT_FILE_TOOLS: '1', MODEL_API_KEY: '', MODEL_NAME: '',
      ALLOWED_ORIGINS: 'http://127.0.0.1:5173', DEMO_EMAIL: 'demo@navowork.local', DEMO_PASSWORD: 'ChangeMe123!' },
    url: 'http://127.0.0.1:5173', reuseExistingServer: false, timeout: 60000,
  },
});
