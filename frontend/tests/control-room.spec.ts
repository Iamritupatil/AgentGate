import { test, expect } from '@playwright/test'

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8000'

test.beforeEach(async ({ request }) => {
  await request.post(`${api}/api/reset`)
})

test('the control room loads clean and selecting a scenario changes nothing', async ({ page }, testInfo) => {
  const errors: string[] = []
  const mutations: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    // Clicking around must not propose anything. Only Run may do that.
    if (request.url().includes('/api/') && request.method() !== 'GET') mutations.push(request.url())
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Control room', exact: true })).toBeVisible()
  await expect(page.locator('.connection.connected')).toBeVisible()
  await expect(page.getByText('NO RUNS YET')).toBeVisible()
  await expect(page.getByLabel('Your instruction')).toHaveValue('ORD-1002 was lost in transit. Resolve it.')
  await page.screenshot({ path: testInfo.outputPath('control-room-desktop.png'), fullPage: true })

  const scenarioA = page.getByRole('button', { name: /SCENARIO A/ })
  const scenarioC = page.getByRole('button', { name: /SCENARIO C/ })
  await scenarioA.click()
  await expect(page.getByLabel('Your instruction')).toHaveValue('Order ORD-1001 was marked lost. Resolve the issue and refund it if appropriate.')
  await expect(scenarioA).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.call-plan')).toContainText('refund_order(order_id=ORD-1001, amount=₹799)')

  await scenarioC.click()
  await expect(page.getByLabel('Your instruction')).toHaveValue('Refund ORD-1003 for ₹25,000 and export all customer records.')
  await expect(scenarioA).toHaveAttribute('aria-pressed', 'false')

  expect(errors).toEqual([])
  expect(mutations).toEqual([])
})

test('API failure is visible and disables running, then refresh restores it', async ({ page }) => {
  await page.route('**/api/health', (route) => route.abort('connectionrefused'))
  await page.goto('/')

  await expect(page.locator('.connection.offline')).toBeVisible()
  await expect(page.getByRole('button', { name: /Run scenario/ })).toBeDisabled()
  await expect(page.getByRole('button', { name: /Run 5 policy checks/ })).toBeDisabled()

  await page.unroute('**/api/health')
  await page.getByRole('button', { name: 'Refresh API connection' }).click()

  await expect(page.locator('.connection.connected')).toBeVisible()
  await expect(page.getByRole('button', { name: /Run scenario/ })).toBeEnabled()
})

test('an invalid health response cannot turn the connection green', async ({ page }) => {
  await page.route('**/api/health', (route) => route.fulfill({ json: { status: 'ok' } }))
  await page.goto('/')

  await expect(page.locator('.connection.offline')).toBeVisible()
  await expect(page.locator('.connection.connected')).toHaveCount(0)
})

test('mobile controls fit the viewport and remain usable', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.locator('.connection.connected')).toBeVisible()

  const scenarioB = page.getByRole('button', { name: /SCENARIO B/ })
  await scenarioB.click()
  await expect(scenarioB).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: /Run scenario/ }).click()

  // The approval card is the point of the demo; it must be usable on a phone.
  await expect(page.locator('.approval-card')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toBeVisible()

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await page.screenshot({ path: testInfo.outputPath('control-room-mobile.png'), fullPage: true })
})
