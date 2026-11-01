const { test, expect } = require('@playwright/test');

const smokeRoutes = [
  '/', '/library', '/pricing', '/community', '/about', '/features', '/help',
  '/login', '/signup', '/privacy', '/terms', '/workspace/audiobooks',
  '/workspace/ecosystem-hub', '/ecosystem', '/dashboard',
];

test('homepage exposes the shared shell, accessible AI launcher, and main CTA', async ({ page }) => {
  const runtimeErrors = [];
  page.on('pageerror', error => runtimeErrors.push(error.message));
  const response = await page.goto('/');
  expect(response && response.status()).toBe(200);
  await expect(page.locator('.topbar')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /open libraai ai chatbot/i })).toBeVisible();
  await expect(page.getByRole('link', { name: /explore books/i })).toBeVisible();
  await page.getByRole('button', { name: /open libraai ai chatbot/i }).click();
  await expect(page.getByRole('dialog', { name: /libraai ai assistant/i })).toBeVisible();
  await page.getByRole('button', { name: /close ai assistant/i }).click();
  expect(runtimeErrors).toEqual([]);
});

test('floating launch notice explains external actions for signed-out visitors', async ({ page }) => {
  await page.goto('/');
  const launcher = page.getByRole('button', { name: /open libraai launch readiness checklist/i });
  await expect(launcher).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('dialog', { name: /libraai launch checklist/i })).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#launch-readiness-panel')).toContainText(/creator payouts require an approved provider/i);
  await expect(page.locator('#launch-readiness-panel')).toContainText(/publisher and audiobook rights/i);
});

test('primary application routes render without server errors', async ({ page }) => {
  for (const route of smokeRoutes) {
    const response = await page.goto(route);
    expect(response, `No HTTP response for ${route}`).not.toBeNull();
    expect(response.status(), `${route} returned ${response.status()}`).toBeLessThan(500);
    await expect(page.locator('body')).not.toBeEmpty();
    await expect(page.locator('body')).not.toContainText('Application error: a client-side exception has occurred');
  }
});

test('mobile navigation opens and can be dismissed with Escape', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  const menu = page.getByRole('button', { name: /open navigation/i });
  await expect(menu).toBeVisible();
  await menu.click();
  await expect(page.locator('#primary-navigation')).toBeVisible();
  await expect(page.getByRole('button', { name: /close navigation/i })).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(page.locator('#primary-navigation')).not.toHaveClass(/nav-open/);
  const width = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(width, 'mobile page should not overflow horizontally').toBeLessThanOrEqual(2);
});

test('frontend responds with baseline browser security headers', async ({ request }) => {
  const response = await request.get('/');
  expect(response.status()).toBe(200);
  const headers = response.headers();
  expect(headers['x-content-type-options']).toBe('nosniff');
  expect(headers['x-frame-options']).toBe('DENY');
  expect(headers['content-security-policy']).toContain("frame-ancestors 'none'");
  expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin');
  expect(headers['permissions-policy']).toContain('camera=()');
});

test('keyboard navigation and dialog semantics remain usable on desktop and mobile', async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    const launcher = page.getByRole('button', { name: /open libraai ai chatbot/i });
    await expect(launcher).toBeVisible();
    await launcher.focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog', { name: /libraai ai assistant/i });
    await expect(dialog).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(2);
  }
});

test('sign-up form exposes labels and native validation constraints', async ({ page }) => {
  await page.goto('/signup');
  await expect(page.locator('#signup-name')).toHaveAttribute('required', '');
  await expect(page.locator('#signup-email')).toHaveAttribute('type', 'email');
  await expect(page.locator('#signup-password')).toHaveAttribute('minlength', '12');
  await expect(page.locator('#signup-email')).toHaveAccessibleName(/email address/i);
});
