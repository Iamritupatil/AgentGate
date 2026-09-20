import { test, expect } from '@playwright/test'

/** Drives the real control room against the real API. These are the exact
 *  clicks the demo makes, so if this passes, the demo works. */

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8000'

test.beforeEach(async ({ request }) => {
  await request.post(`${api}/api/reset`)
})

test('Scenario A: a small refund executes without a human', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /SCENARIO A/ }).click()
  await page.getByRole('button', { name: /Run scenario/ }).click()

  await expect(page.getByText('Executed refund_order')).toBeVisible()
  await expect(page.locator('.state-strip div.refunded').filter({ hasText: 'ORD-1001' })).toContainText('refunded ₹799')
  await expect(page.locator('.approval-card')).toHaveCount(0)
})

test('Scenario B: the refund pauses, a human approves, and it executes once', async ({ page }, testInfo) => {
  await page.goto('/')
  await page.getByRole('button', { name: /SCENARIO B/ }).click()
  await page.getByRole('button', { name: /Run scenario/ }).click()

  const card = page.locator('.approval-card')
  await expect(card).toBeVisible()
  await expect(card).toContainText('refund_order')
  await expect(card).toContainText('₹8,499')

  // Nothing has moved yet. This is the whole point of the scenario.
  await expect(page.locator('.state-strip div').filter({ hasText: 'ORD-1002' })).toContainText('untouched')
  await page.screenshot({ path: testInfo.outputPath('scenario-b-paused.png'), fullPage: true })

  await page.getByRole('button', { name: 'Approve', exact: true }).click()

  await expect(page.getByText('Human approved')).toBeVisible()
  await expect(page.locator('.state-strip div.refunded').filter({ hasText: 'ORD-1002' })).toContainText('refunded ₹8,499')
  await expect(card).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('scenario-b-approved.png'), fullPage: true })
})

test('Scenario B denied: nothing is refunded', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /SCENARIO B/ }).click()
  await page.getByRole('button', { name: /Run scenario/ }).click()

  await expect(page.locator('.approval-card')).toBeVisible()
  await page.getByRole('button', { name: 'Deny', exact: true }).click()

  await expect(page.getByText('Human denied')).toBeVisible()
  await expect(page.locator('.state-strip div').filter({ hasText: 'ORD-1002' })).toContainText('untouched')
})

test('Scenario C: both dangerous actions are blocked and visible', async ({ page }, testInfo) => {
  await page.goto('/')
  await page.getByRole('button', { name: /SCENARIO C/ }).click()
  await page.getByRole('button', { name: /Run scenario/ }).click()

  await expect(page.getByText('Blocked refund_order')).toBeVisible()
  await expect(page.getByText('Blocked export_customers')).toBeVisible()
  await expect(page.locator('.timeline').getByText('EXPLICIT_FORBID').first()).toBeVisible()
  await expect(page.locator('.state-strip div').filter({ hasText: 'ORD-1003' })).toContainText('untouched')
  await page.screenshot({ path: testInfo.outputPath('scenario-c-blocked.png'), fullPage: true })
})

test('the timeline attributes proposals to OPERATOR, not AGENT', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /SCENARIO A/ }).click()
  await page.getByRole('button', { name: /Run scenario/ }).click()

  await expect(page.locator('.actor-chip.actor-operator').first()).toBeVisible()
  await expect(page.locator('.actor-chip.actor-cedar').first()).toBeVisible()
  await expect(page.locator('.actor-chip.actor-agent')).toHaveCount(0)
})

test('the policy test bench reports 5/5 from real evaluations', async ({ page }, testInfo) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Run 5 policy checks/ }).click()

  await expect(page.locator('.bench-score')).toHaveText('5 / 5 passed')
  await expect(page.locator('.bench-score')).toHaveClass(/pass/)
  await expect(page.locator('.bench-list li.fail')).toHaveCount(0)
  // The bench must not have refunded anything to prove refunds are allowed.
  await expect(page.locator('.state-strip div.refunded')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('policy-bench.png'), fullPage: true })
})

test('Reset restores the demo to a clean state', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /SCENARIO A/ }).click()
  await page.getByRole('button', { name: /Run scenario/ }).click()
  await expect(page.locator('.state-strip div.refunded')).toHaveCount(1)

  await page.getByRole('button', { name: 'Reset' }).click()

  await expect(page.locator('.state-strip div.refunded')).toHaveCount(0)
  await expect(page.getByText('Every decision leaves a trail.')).toBeVisible()
})
