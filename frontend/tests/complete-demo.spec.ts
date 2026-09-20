import { test, expect } from '@playwright/test'

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8000'

test.beforeEach(async ({ request }) => {
  await request.post(`${api}/api/reset`)
})

test('generic workbench evaluates, drafts safely, and exposes integration examples', async ({ page }) => {
  await page.goto('/#/control')

  await page.getByRole('button', { name: 'Playground' }).click()
  await page.getByRole('button', { name: 'Production deployment' }).click()
  await page.getByRole('button', { name: 'Evaluate' }).click()
  await expect(page.locator('.playground-result')).toContainText('REQUIRE_APPROVAL')
  await expect(page.locator('.playground-result')).toContainText('APPROVAL_PERMITTED')

  await page.getByRole('button', { name: 'Policy Studio' }).click()
  await page.getByRole('button', { name: 'Generate structured draft' }).click()
  await expect(page.locator('.draft-preview')).toContainText('Draft preview')
  await expect(page.locator('.draft-preview')).toContainText('studio_draft')
  await expect(page.locator('.draft-preview')).toContainText('not active')
  await page.getByRole('button', { name: 'Activate draft' }).click()
  await expect(page.locator('.policy-list')).toContainText('ACTIVE')

  await page.getByRole('button', { name: 'Integrate' }).click()
  await expect(page.locator('.integration-grid')).toContainText('curl')
  await expect(page.locator('.integration-grid')).toContainText('/api/gate/evaluate')
})
