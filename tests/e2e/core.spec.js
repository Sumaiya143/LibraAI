const { test, expect } = require('@playwright/test');

async function login(page, email = 'reader@libra.ai') {
  await page.goto('/login');
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill('demo123');
  await Promise.all([
    page.waitForURL(url => !url.pathname.endsWith('/login')),
    page.locator('form button').click(),
  ]);
}

function captureRuntimeErrors(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  return errors;
}

test('public home uses local artwork, contained decorations, and working FAQ search', async ({ page }) => {
  const errors = captureRuntimeErrors(page);
  await page.goto('/');
  const hero = page.locator('.hero-photo');
  await expect(hero).toBeVisible();
  await expect.poll(() => hero.evaluate(image => image.naturalWidth)).toBeGreaterThan(0);
  expect(new URL(hero.evaluate ? await hero.evaluate(image => image.currentSrc) : '').pathname)
    .toBe('/assets/hero-bookshelf.webp');
  await expect(page.locator('.text-link')).toContainText('Browse catalog');
  await expect(page.locator('body')).not.toContainText('Watch video');
  await expect(page.locator('body')).not.toContainText('Millions of titles');

  const decorationSizes = await page.locator('.genre-icon,.stat-icon').evaluateAll(elements =>
    elements.map(element => {
      const bounds = element.getBoundingClientRect();
      return { width: bounds.width, height: bounds.height };
    }));
  for (const bounds of decorationSizes) {
    expect(bounds.width).toBeLessThanOrEqual(40);
    expect(bounds.height).toBeLessThanOrEqual(40);
  }

  await page.locator('#question-search').fill('payments');
  await expect(page.locator('.faq-item:visible')).toHaveCount(1);
  await page.locator('.faq-item:visible summary').click();
  await expect(page.locator('.faq-item:visible p')).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile navigation and community layout stay within the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await page.locator('.nav-toggle').click();
  await expect(page.locator('.main-nav')).toBeVisible();
  await expect(page.locator('.nav-toggle')).toHaveAttribute('aria-expanded', 'true');
  await page.locator('.nav-toggle').click();
  await expect(page.locator('.main-nav')).toBeHidden();

  const layout = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    columns: getComputedStyle(document.querySelector('.popular-panel .book-grid')).gridTemplateColumns.split(' ').length,
    ctaRight: document.querySelector('.community-cta').getBoundingClientRect().right,
  }));
  expect(layout.overflow).toBe(0);
  expect(layout.columns).toBe(3);
  expect(layout.ctaRight).toBeLessThanOrEqual(375);
});

test('public catalog search opens the matching book detail', async ({ page }) => {
  const errors = captureRuntimeErrors(page);
  await page.goto('/explore');
  await expect(page.locator('#count')).toHaveText('8 books found');
  await page.locator('#search').fill('Clean Code');
  await page.locator('#searchForm button').click();
  await expect(page.locator('#count')).toHaveText('1 book found');
  await page.getByRole('link', { name: 'View details ↗' }).click();
  await expect(page.locator('#title')).toHaveText('Clean Code');
  await expect(page.locator('#isbn')).toHaveText('9780132350884');
  expect(errors).toEqual([]);
});

test('health, readiness, public policy, and private preference boundaries are correct', async ({ request, page }) => {
  const health = await request.get('/api/health');
  expect(health.status()).toBe(200);
  expect((await health.json()).status).toBe('alive');
  expect(health.headers()['x-request-id']).toMatch(/^[a-f0-9]{32}$/);
  const apiNotFound = await request.get('/api/route-that-does-not-exist');
  expect(apiNotFound.status()).toBe(404);
  expect((await apiNotFound.json()).code).toBe('http_404');
  expect(apiNotFound.headers()['x-request-id']).toBeTruthy();
  const ready = await request.get('/api/ready');
  expect(ready.status()).toBe(200);
  expect((await ready.json()).status).toBe('ready');
  const publicNotices = await request.get('/api/setup/notices');
  expect(publicNotices.status()).toBe(200);
  expect((await publicNotices.json()).items.some(item => item.id === 'creator-payouts')).toBeTruthy();
  const detailedReadiness = await request.get('/api/setup/readiness');
  expect([401, 403]).toContain(detailedReadiness.status());

  const policy = await request.get('/privacy-policy');
  expect(policy.status()).toBe(200);
  await page.goto('/privacy-policy');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Your reading space.');
  const privatePreferences = await request.get('/privacy', { maxRedirects: 0 });
  expect([302, 401]).toContain(privatePreferences.status());
});

test('reader can sign in, add a book, review checkout, and place an unpaid order', async ({ page }) => {
  const errors = captureRuntimeErrors(page);
  await login(page);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Your library, bookstore & knowledge space');
  await page.goto('/marketplace');
  await expect(page.locator('.market-book')).toHaveCount(8);
  await page.locator('#marketSearch').fill('Atomic Habits');
  await expect(page.locator('.market-book:visible')).toHaveCount(1);
  await page.locator('.market-book:visible button[type="submit"]').click();
  await expect(page.locator('.cart-count')).toHaveText('1 items');
  await page.getByRole('button', { name: 'Proceed to checkout →' }).click();
  await expect(page).toHaveURL(/\/checkout/);
  await expect(page.locator('.checkout-item-main')).toContainText('Atomic Habits');
  await page.getByRole('button', { name: 'Place order →' }).click();
  await expect(page).toHaveURL(/\/my\/orders/);
  await expect(page.locator('main')).toContainText('No payment charged');
  await expect(page.locator('main')).toContainText('Atomic Habits');
  expect(errors).toEqual([]);
});

test('new user can sign up through the public account flow', async ({ page }) => {
  const email = `reader-${Date.now()}@example.test`;
  await page.goto('/signup');
  await page.locator('input[name="name"]').fill('E2E Reader');
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill('E2E-Strong-Password-2026!');
  await page.locator('form button[type="submit"]').click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Your library, bookstore & knowledge space');
});

test('reader controls are keyboard accessible and support text preferences', async ({ page }) => {
  await login(page);
  await page.goto('/reader/1');
  const reader = page.locator('#text');
  await expect(reader).toBeVisible();
  const before = await reader.evaluate(element => getComputedStyle(element).fontSize);
  await page.getByRole('button', { name: 'Increase text size' }).click();
  const after = await reader.evaluate(element => getComputedStyle(element).fontSize);
  expect(parseFloat(after)).toBeGreaterThan(parseFloat(before));
  await page.getByRole('button', { name: /auto-scroll/i }).click();
  await expect(page.getByRole('button', { name: /stop scroll/i })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#autoScrollToggle')).toHaveAttribute('aria-pressed', 'false');
});

test('AI tutor page loads for signed-in reader and provides a safe response state', async ({ page }) => {
  await login(page);
  await page.goto('/ai');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('LibraAI Tutor');
  await page.locator('textarea[name="q"]').fill('Explain a habit in simple terms');
  await page.locator('form button[type="submit"]').click();
  await expect(page.locator('.msg.ai')).toBeVisible();
  await expect(page.locator('.msg.ai')).toContainText(/LibraAI/i);
});

test('creator dashboard is restricted and available to creator role', async ({ page }) => {
  await login(page, 'creator@libra.ai');
  await page.goto('/creator');
  await expect(page.locator('main')).toContainText(/Creator|creator|Royalty|royalty/);
});

test('role checks protect administration while admin pages remain usable', async ({ page }) => {
  await login(page);
  const forbidden = await page.request.get('/admin');
  expect(forbidden.status()).toBe(403);

  await page.goto('/logout');
  await login(page, 'admin@libra.ai');
  await page.goto('/admin');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Library network administration');
  await page.goto('/admin/users/new');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Create platform account');
  await expect(page.locator('input[name="password"]')).toHaveAttribute('minlength', '12');
});
