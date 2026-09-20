import { test, expect } from '@playwright/test'

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8000'

test.beforeEach(async ({ request }) => {
  await request.post(`${api}/api/reset`)
})

test('the site loads and routes to the control room', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))

  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Let agents act/ })).toBeVisible()
  await expect(page.getByText('Make authority explicit.')).toBeVisible()
  await expect(page.getByText('₹2,000').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('site-hero.png') })

  await page.getByRole('link', { name: 'Explore the demo' }).first().click()

  await expect(page.getByRole('heading', { name: 'Action stream' })).toBeVisible()
  await expect(page.locator('.console-bar')).toContainText('CONTROL ROOM')
  expect(errors).toEqual([])
})

test('the control room loads clean and selecting a scenario changes nothing', async ({ page }, testInfo) => {
  const mutations: string[] = []
  page.on('request', (request) => {
    // Clicking around must not propose anything. Only Run may do that.
    if (request.url().includes('/api/') && request.method() !== 'GET') mutations.push(request.url())
  })

  await page.goto('/#/control')
  await expect(page.locator('.console-status.connected')).toBeVisible()
  await expect(page.getByText('No tool calls yet.')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('control-room-desktop.png'), fullPage: true })

  const scenarioA = page.getByRole('button', { name: /SCENARIO A/ })
  await scenarioA.click()
  await expect(scenarioA).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: /SCENARIO C/ }).click()
  await expect(scenarioA).toHaveAttribute('aria-pressed', 'false')

  expect(mutations).toEqual([])
})

test('API failure is visible and disables running, then refresh restores it', async ({ page }) => {
  await page.route('**/api/health', (route) => route.abort('connectionrefused'))
  await page.goto('/#/control')

  await expect(page.locator('.console-status.offline')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run scenario' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Reset' })).toBeDisabled()

  await page.unroute('**/api/health')
  await page.getByRole('button', { name: 'Refresh API connection' }).click()

  await expect(page.locator('.console-status.connected')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run scenario' })).toBeEnabled()
})

test('an invalid health response cannot turn the status green', async ({ page }) => {
  await page.route('**/api/health', (route) => route.fulfill({ json: { status: 'ok' } }))
  await page.goto('/#/control')

  await expect(page.locator('.console-status.offline')).toBeVisible()
  await expect(page.locator('.console-status.connected')).toHaveCount(0)
})

test('mobile controls fit the viewport and remain usable', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/control')
  await expect(page.locator('.console-status.connected')).toBeVisible()

  await page.getByRole('button', { name: /SCENARIO B/ }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()

  // The decision panel is the point of the demo; it must be usable on a phone.
  await expect(page.locator('.decision-amount')).toHaveText('₹8,499')
  await expect(page.getByRole('button', { name: /^Approve/ })).toBeVisible()

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await page.screenshot({ path: testInfo.outputPath('control-room-mobile.png'), fullPage: true })
})

test('the landing page fits a phone without horizontal scroll', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Let agents act/ })).toBeVisible()

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await page.screenshot({ path: testInfo.outputPath('site-mobile.png'), fullPage: true })
})
