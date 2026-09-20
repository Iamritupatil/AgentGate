import { test, expect } from '@playwright/test'

/** Drives the real control room against the real API. These are the exact
 *  clicks the demo makes, so if this passes, the demo works. */

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8000'

test.beforeEach(async ({ request }) => {
  await request.post(`${api}/api/reset`)
})

const pick = (id: string) => new RegExp(`SCENARIO ${id}`)
import type { Page } from '@playwright/test'
const ledger = (page: Page, orderId: string) =>
  page.locator('.ledger > div > div').filter({ hasText: orderId })

test('Scenario A: a small refund executes without a human', async ({ page }) => {
  await page.goto('/#/control')
  await page.getByRole('button', { name: pick('A') }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()

  await expect(page.locator('.calls tbody tr', { hasText: 'refund_order' })).toHaveClass(/allow/)
  await expect(page.locator('.pill.allow').first()).toBeVisible()
  await expect(ledger(page, 'ORD-1001')).toContainText('refunded ₹799')
  await expect(page.locator('.decision-amount')).toHaveCount(0)
})

test('Scenario B: the refund pauses, a human approves, and it executes once', async ({ page }, testInfo) => {
  await page.goto('/#/control')
  await page.getByRole('button', { name: pick('B') }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()

  // The decision panel is the centrepiece.
  await expect(page.locator('.decision-head.approval')).toBeVisible()
  await expect(page.locator('.decision-amount')).toHaveText('₹8,499')
  await expect(page.locator('.decision-target')).toContainText('refund_order / ORD-1002')
  await expect(page.locator('.pill.approval')).toBeVisible()

  // Nothing has moved yet. This is the whole point of the scenario.
  await expect(ledger(page, 'ORD-1002')).toContainText('untouched')
  await expect(page.locator('.evaluation')).toContainText('can_request_approval')
  await page.screenshot({ path: testInfo.outputPath('scenario-b-paused.png'), fullPage: true })

  await page.getByRole('button', { name: /^Approve/ }).click()

  await expect(ledger(page, 'ORD-1002')).toContainText('refunded ₹8,499')
  await expect(page.locator('.decision-head.idle')).toBeVisible()
  // A human sat between Cedar and the tool, and the row says so.
  await expect(page.locator('.calls .actor-human').first()).toBeVisible()
  await expect(page.locator('.calls .actor-tool').last()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('scenario-b-approved.png'), fullPage: true })
})

test('Scenario B denied: nothing is refunded', async ({ page }) => {
  await page.goto('/#/control')
  await page.getByRole('button', { name: pick('B') }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()
  await expect(page.locator('.decision-head.approval')).toBeVisible()

  await page.getByRole('button', { name: 'Deny', exact: true }).click()

  await expect(page.locator('.decision-head.idle')).toBeVisible()
  await expect(ledger(page, 'ORD-1002')).toContainText('untouched')
  await expect(page.locator('.ledger .refunded')).toHaveCount(0)
})

test('Scenario C: both dangerous actions are blocked and visible', async ({ page }, testInfo) => {
  await page.goto('/#/control')
  await page.getByRole('button', { name: pick('C') }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()

  await expect(page.locator('.pill.deny')).toHaveCount(2)
  await expect(page.locator('.calls tbody tr', { hasText: 'export_customers' })).toHaveClass(/deny/)
  await expect(page.locator('.evaluation')).toContainText('EXPLICIT_FORBID')
  await expect(page.locator('.tally div', { hasText: 'DENIED' })).toContainText('02')
  await expect(ledger(page, 'ORD-1003')).toContainText('untouched')
  await expect(page.locator('.ledger .refunded')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('scenario-c-blocked.png'), fullPage: true })
})

test('the timeline attributes proposals to OPERATOR, not AGENT', async ({ page }) => {
  await page.goto('/#/control')
  await page.getByRole('button', { name: pick('A') }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()

  await expect(page.locator('.actor-operator').first()).toBeVisible()
  await expect(page.locator('.actor-cedar').first()).toBeVisible()
  await expect(page.locator('.actor-agent')).toHaveCount(0)
})

test('the policy test bench reports 5/5 from real evaluations', async ({ page }, testInfo) => {
  await page.goto('/#/control')
  await page.getByRole('button', { name: /Policy test bench/ }).click()
  await page.getByRole('button', { name: /Run 5 policy checks/ }).click()

  await expect(page.locator('.bench-score')).toContainText('5 / 5')
  await expect(page.locator('.bench-score')).toHaveClass(/pass/)
  await expect(page.locator('.calls.bench .pill.deny')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('policy-bench.png'), fullPage: true })

  // The bench must not have refunded anything to prove refunds are allowed.
  await page.getByRole('button', { name: /Action stream/ }).click()
  await expect(page.locator('.ledger .refunded')).toHaveCount(0)
})

test('Reset restores the demo to a clean state', async ({ page }) => {
  await page.goto('/#/control')
  await page.getByRole('button', { name: pick('A') }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()
  await expect(page.locator('.ledger .refunded')).toHaveCount(1)

  await page.getByRole('button', { name: 'Reset' }).click()

  await expect(page.locator('.ledger .refunded')).toHaveCount(0)
  await expect(page.getByText('No tool calls yet.')).toBeVisible()
  await expect(page.locator('.tally div', { hasText: 'ALLOWED' })).toContainText('00')
})
