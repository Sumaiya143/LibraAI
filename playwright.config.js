const { defineConfig } = require('@playwright/test');
const fs = require('fs');

// Use Playwright's managed browser by default. The system Chromium fallback
// keeps the suite runnable in minimal Linux CI containers.
const systemChromium = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  || (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);

module.exports = defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  timeout: 45_000,
  use: {
    baseURL: process.env.LIBRAAI_BASE_URL || 'http://127.0.0.1:5000',
    launchOptions: { executablePath: systemChromium },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    reducedMotion: 'reduce',
  },
  webServer: process.env.LIBRAAI_SKIP_WEBSERVER ? undefined : {
    command: process.env.LIBRAAI_START_COMMAND || 'python3 app.py',
    url: process.env.LIBRAAI_BASE_URL || 'http://127.0.0.1:5000/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      LIBRAAI_ENV: 'development',
      LIBRAAI_DB_PATH: process.env.LIBRAAI_DB_PATH || './libraai-e2e.db',
      SECRET_KEY: process.env.SECRET_KEY || 'local-e2e-only-secret-key-change-before-production-12345',
      PORT: '5000',
    },
  },
});
