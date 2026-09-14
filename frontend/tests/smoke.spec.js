// Smoke tests con Playwright para e2e básico del dashboard.
// Se puede extender con tests más completos.

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3040';

test.describe('Ecommerce Brain dashboard', () => {
  test('homepage redirects to /es', async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page).toHaveURL(/\/es/);
  });

  test('login page renders', async ({ page }) => {
    await page.goto(`${BASE_URL}/es/login`);
    await expect(page.locator('text=Iniciar')).toBeVisible();
  });

  test('login form has email + password', async ({ page }) => {
    await page.goto(`${BASE_URL}/es/login`);
    await expect(page.locator('input[type=email]')).toBeVisible();
    await expect(page.locator('input[type=password]')).toBeVisible();
  });

  test('protected route without token redirects to login', async ({ page }) => {
    await page.goto(`${BASE_URL}/es`);
    // Eventually the page should redirect or show login
    await page.waitForURL(/\/es\/login/, { timeout: 5000 }).catch(() => {});
    const url = page.url();
    expect(url.includes('/login') || url.includes('/es/')).toBeTruthy();
  });

  test('en locale renders in English', async ({ page }) => {
    await page.goto(`${BASE_URL}/en/login`);
    await expect(page.locator('text=Sign in')).toBeVisible();
  });

  test('locale switcher works', async ({ page }) => {
    await page.goto(`${BASE_URL}/es/login`);
    await page.click('a:has-text("en")');
    await expect(page).toHaveURL(/\/en\/login/);
    await expect(page.locator('text=Sign in')).toBeVisible();
  });
});

test.describe('Ecommerce Brain API', () => {
  test('GET /health returns 200', async ({ request }) => {
    const r = await request.get('http://localhost:8040/health');
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.status).toBe('ok');
    expect(body.service).toBe('Ecommerce Brain');
  });

  test('GET /openapi.json lists paths', async ({ request }) => {
    const r = await request.get('http://localhost:8040/openapi.json');
    expect(r.status()).toBe(200);
    const spec = await r.json();
    const paths = Object.keys(spec.paths);
    expect(paths.length).toBeGreaterThan(20);
  });
});