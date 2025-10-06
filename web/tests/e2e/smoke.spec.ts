import { test, expect, type Page } from '@playwright/test';

const TEST_USER = process.env.PLAYWRIGHT_SMOKE_USER ?? 'demo_user';

async function selectActiveUser(page: Page) {
  const userSwitcher = page.locator('#user-switcher-input');
  await expect(userSwitcher).toBeVisible();
  await userSwitcher.fill(TEST_USER);
  const option = page
    .locator('#user-switcher-listbox [role="option"]')
    .filter({ hasText: TEST_USER })
    .first();
  await expect(option).toBeVisible();
  await option.click();
}

test.describe('Head Coach smoke flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('hc_intro_seen', 'true');
    });
  });

  test('core user journey', async ({ page }) => {
    test.setTimeout(60_000);
    await page.goto('/');

    await selectActiveUser(page);

    const composer = page.locator('[data-testid="hc-composer"]');
    await expect(composer).toBeVisible();

    const message = `Smoke run ${Date.now()}`;
    await page.getByLabel('Compose message for Head Coach').fill(message);
    await page.getByRole('button', { name: /send message/i }).click();

    const messageEntry = page
      .locator('[data-testid="transcript-message"]').filter({ hasText: message })
      .first();
    await expect(messageEntry).toBeVisible({ timeout: 15000 });

    const pinButton = messageEntry.locator('[data-testid="transcript-pin-button"]');
    await pinButton.click();
    await expect(pinButton).toHaveText(/Pinned/i);

    const searchInput = page.getByTestId('transcript-search-input');
    await searchInput.fill(message.split(' ')[0]);
    await expect(page.locator('span').filter({ hasText: /Match 1 of 1/ })).toBeVisible();
    await page.getByTestId('transcript-search-clear').click();

    await page.getByTestId('persona-button-padna').click();
    await expect(page.getByRole('heading', { name: 'PaDNA Media Tools' })).toBeVisible();

    const jsonInput = page.locator('input[type="file"][accept="application/json,.json"]');
    await jsonInput.setInputFiles('tests/e2e/fixtures/padna-smoke.json');

    const mediaCard = page.getByRole('button', { name: /padna-smoke\.json/i }).first();
    await expect(mediaCard).toBeVisible();
    await mediaCard.click();

    const renderButton = page.getByRole('button', { name: /Render bundle/i });
    await renderButton.click();
    await expect(page.getByText('Render complete', { exact: false })).toBeVisible({ timeout: 20000 });

    await page.getByRole('button', { name: 'Snapshots' }).click();
    await expect(page.getByRole('heading', { name: 'Snapshots' })).toBeVisible();
  });
});
