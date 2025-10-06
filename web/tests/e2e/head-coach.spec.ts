import { test, expect, Page, Request } from '@playwright/test';
import { Buffer } from 'buffer';

const MOCK_PERSONAS = [
  { key: 'head_coach', label: 'Head Coach (Orchestrator)', icon: '🧭', enabled: true },
  { key: 'relationship_coach', label: 'Relationship Coach', icon: '💞', enabled: true },
  { key: 'padna', label: 'PaDNA Coach', icon: '🧬', enabled: true },
  { key: 'photo', label: 'Photo Coach', icon: '📸', enabled: true },
] as const;

const MOCK_ASK = {
  id: 'ask-1',
  container: 'core',
  phrasing_stub: 'Check-in on PaDNA preferences',
  confidence: 0.87,
  ttl_minutes: 45,
  snooze_minutes: 120,
  ask_type: 'PROACTIVE',
  sensitivity: false,
  status: 'pending',
  policy: {
    approve: { allowed: true },
    snooze: { allowed: false, reason: 'Snooze cooling down for this ask.' },
    skip: { allowed: true },
  },
};

const MOCK_NUDGE = {
  id: 'nudge-1',
  kind: 'follow_up',
  text: 'Share current relationship insights.',
  created_ts: '2024-04-01T12:00:00Z',
  status: 'pending',
  ttl_minutes: 30,
};

const MOCK_AGGREGATES = {
  observation_count: 12,
  dialog_acts: {
    latest: 'coaching',
    distribution: {
      coaching: 7,
      informative: 5,
    },
  },
  cadence: {
    latest_bucket: 'Daily',
    histogram: {
      Daily: 7,
      Weekly: 5,
    },
  },
  latency: {
    median_ms: 420,
    mean_ms: 480,
    histogram: {
      '0-1s': 5,
      '1-2s': 4,
      '2-3s': 3,
    },
  },
};

const MOCK_UNABRIDGED = {
  user_id: 'TEST',
  count: 2,
  traits: [
    {
      trait_id: 'PaDNA.HairDNA.Color',
      value: 'Brunette',
      ucn: 92,
      reasons: ['Member self-report'],
      badges: ['sensitive'],
    },
    {
      trait_id: 'HeadCoach.SyncScore',
      value: 0.81,
      ucn: 75,
      reasons: ['Planner evaluation'],
      badges: ['observational'],
    },
  ],
};

async function primeMockRoutes(page: Page) {
  await page.route('**/ui/personas', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ personas: MOCK_PERSONAS }),
    });
  });

  await page.route('**/ui/media/list?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    });
  });

  await page.route('**/ui/asks', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ asks: [MOCK_ASK] }),
    });
  });

  await page.route('**/ui/observations/aggregates', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_AGGREGATES),
    });
  });

  await page.route('**/ui/unabridged', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_UNABRIDGED),
    });
  });

  await page.route('**/ui/nudges', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ nudges: [MOCK_NUDGE] }),
    });
  });

  await page.route('**/ui/asks/act', async (route) => {
    const request = route.request();
    const payload = request.postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: payload.action === 'approve', ask: MOCK_ASK }),
    });
  });

  await page.route('**/ui/chat/send', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        message_id: 'msg-123',
        persona: 'head_coach',
        text: 'All set! ✅',
        ts: Date.now(),
      }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await primeMockRoutes(page);
});

test('composer stays anchored near the viewport bottom', async ({ page }) => {
  await page.goto('/');
  const composer = page.locator('[data-testid="hc-composer"]');
  await expect(composer).toBeVisible();
  const bottomGap = await composer.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return Math.abs(window.innerHeight - rect.bottom);
  });
  expect(bottomGap).toBeLessThan(32);
});

test('persona changes update the assistant bubble label and icon', async ({ page }) => {
  await page.goto('/');
  const relationshipChip = page.locator('[data-testid="persona-button-relationship_coach"]');
  await relationshipChip.click();
  const bubble = page.locator('[data-testid="persona-bubble-label"]');
  await expect(bubble).toContainText('Relationship Coach');
});

test('user switcher combobox meets ARIA expectations', async ({ page }) => {
  await page.goto('/');
  const combobox = page.locator('#user-switcher-input');
  await combobox.focus();
  await expect(combobox).toHaveAttribute('role', 'combobox');
  await expect(combobox).toHaveAttribute('aria-controls', 'user-switcher-listbox');
  await expect(combobox).toHaveAttribute('aria-expanded', 'true');
  const listbox = page.locator('#user-switcher-listbox');
  await expect(listbox).toBeVisible();
  const options = listbox.locator('[role="option"]');
  await expect(options.first()).toHaveAttribute('id', /user-switcher-option-/);
});

test('persona router swaps to PaDNA and Photo panels', async ({ page }) => {
  await page.goto('/');
  await page.locator('[data-testid="persona-button-padna"]').click();
  await expect(page.getByRole('heading', { name: 'PaDNA Media Tools' })).toBeVisible();
  await page.locator('[data-testid="persona-button-photo"]').click();
  await expect(page.getByRole('heading', { name: 'Photo Coach Refinement' })).toBeVisible();
});

test('unabridged nav jump updates the hash and focuses the panel', async ({ page }) => {
  await page.goto('/');
  await page.locator('[data-testid="nav-unabridged"]').click();
  await page.waitForFunction(() => window.location.hash === '#unabridged');
  await expect(page.locator('#unabridged')).toBeVisible();
});

test('ask action buttons reflect policy enablement', async ({ page }) => {
  await page.goto('/');
  const approveButton = page.locator('[data-testid="a[REDACTED]"]');
  const snoozeButton = page.locator('[data-testid="ask-action-snooze-ask-1"]');
  const skipButton = page.locator('[data-testid="ask-action-skip-ask-1"]');

  await expect(approveButton).toBeEnabled();
  await expect(snoozeButton).toBeDisabled();
  await expect(skipButton).toBeEnabled();
});

test('snapshot export hits the endpoint and returns bundle payload', async ({ page }) => {
  const snapshotCalls: Request[] = [];
  await page.route('**/ui/snapshot', async (route) => {
    snapshotCalls.push(route.request());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        path: '/tmp/checkpoints/TEST/bundle-20240401T120000.json',
        version: 'v1',
        bundle: { example: true },
      }),
    });
  });

  await page.goto('/');
  const dialogPromise = page.waitForEvent('dialog');
  await page.locator('[data-testid="snapshot-export"]');
  const snapshotButton = page.locator('[data-testid="snapshot-export"]');
  await snapshotButton.click();

  const dialog = await dialogPromise;
  expect(dialog.message()).toContain('Snapshot saved');
  await dialog.dismiss();

  expect(snapshotCalls).toHaveLength(1);
  const requestJson = snapshotCalls[0].postDataJSON();
  expect(requestJson.user_id).toBe('TEST');
});

test('photo persona handles upload and delete flows', async ({ page }) => {
  const uploadCalls: Array<{ user_id?: string }> = [];
  const deleteCalls: Request[] = [];

  await page.route('**/ui/media/upload', async (route) => {
    const request = route.request();
    const formData = await request.formData();
    uploadCalls.push({ user_id: formData.get('user_id') as string | undefined });
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        media: {
          id: 'media-new',
          original_name: 'sample.jpg',
          filename: 'media-new_sample.jpg',
          content_type: 'image/jpeg',
          size: 12345,
          uploaded_ts: new Date().toISOString(),
          download_url: '/ui/media/download/TEST/media-new',
        },
      }),
    });
  });

  await page.route('**/ui/media/delete?**', async (route) => {
    deleteCalls.push(route.request());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, removed: true, media_id: 'media-new' }),
    });
  });

  await page.goto('/');
  await page.locator('[data-testid="persona-button-photo"]').click();

  const uploadInput = page.locator('input[type="file"][accept*="image"]');
  const mockImage = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=',
    'base64'
  );

  await uploadInput.setInputFiles({ name: 'sample.png', mimeType: 'image/png', buffer: mockImage });

  await expect.poll(() => uploadCalls.length).toBe(1);
  expect(uploadCalls[0].user_id).toBe('TEST');
  const photoCard = page.locator('[data-testid="photo-card"]').first();
  await expect(photoCard).toBeVisible();

  await photoCard.click();
  await page.getByRole('button', { name: 'Delete reference' }).click();

  await expect.poll(() => deleteCalls.length).toBe(1);
  expect(deleteCalls[0].url()).toContain('media_id=media-new');
  await expect(page.locator('[data-testid="photo-card"]')).toHaveCount(0);
});

test('transcript search and pin survives reload', async ({ page }) => {
  await page.goto('/');

  const composer = page.getByLabel('Compose message for Head Coach');
  await composer.fill('Pin-worthy insight');
  await composer.press('Enter');

  const assistantBubble = page.locator('[data-testid="transcript-message"]').filter({ hasText: 'All set! ✅' });
  await expect(assistantBubble).toBeVisible();

  const searchInput = page.locator('[data-testid="transcript-search-input"]');
  await searchInput.fill('All set');
  await expect(page.locator('text=Match 1 of 1')).toBeVisible();
  await page.locator('[data-testid="transcript-search-clear"]').click();

  await assistantBubble.click();
  await assistantBubble.getByRole('button', { name: 'Pin' }).click();
  await expect(assistantBubble.getByText('Pinned')).toBeVisible();

  const pinToggle = page.locator('[data-testid="transcript-pins-toggle"]');
  await expect(pinToggle).toContainText('Pinned (1)');
  await pinToggle.click();
  await expect(assistantBubble).toBeVisible();

  await page.reload();

  const postReloadToggle = page.locator('[data-testid="transcript-pins-toggle"]');
  await expect(postReloadToggle).toContainText('Pinned (1)');
  await postReloadToggle.click();
  await expect(page.locator('[data-testid="transcript-message"]').filter({ hasText: 'All set! ✅' }).getByText('Pinned')).toBeVisible();
});

test('settings persist theme, density, and enter-to-send preference', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Settings' }).click();
  const settingsModal = page.locator('#hc-settings-modal');
  await expect(settingsModal).toBeVisible();

  await settingsModal.getByLabel('Press Enter to send').uncheck();
  await settingsModal.getByLabel('Compact density').check();
  await settingsModal.getByLabel('Light').check();

  await settingsModal.getByRole('button', { name: 'Close' }).click();

  await page.reload();

  await expect(page.locator('body')).toHaveAttribute('data-hc-theme', 'light');
  await expect(page.locator('body')).toHaveAttribute('data-hc-density', 'compact');

  await page.getByRole('button', { name: 'Settings' }).click();
  const reopenedModal = page.locator('#hc-settings-modal');
  await expect(reopenedModal.getByLabel('Press Enter to send')).not.toBeChecked();
  await expect(reopenedModal.getByLabel('Compact density')).toBeChecked();
  await expect(reopenedModal.getByLabel('Light')).toBeChecked();
  await reopenedModal.getByRole('button', { name: 'Close' }).click();
});
