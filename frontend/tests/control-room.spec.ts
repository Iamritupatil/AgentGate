import { test, expect } from '@playwright/test'

test('live API health, scenario selection and truthful authority-phase state', async ({ page }, testInfo) => {
  const errors: string[] = []
  const mutations: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    if (request.url().includes('/api/') && request.method() !== 'GET') mutations.push(request.url())
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Control room', exact: true })).toBeVisible()
  await expect(page.getByText('Backend is reachable')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run agent' })).toBeDisabled()
  await expect(page.getByText('NO RUNS YET')).toBeVisible()
  await expect(page.getByLabel('Your instruction')).toHaveValue('ORD-1002 was lost in transit. Resolve it.')
  await page.screenshot({ path: testInfo.outputPath('control-room-desktop.png'), fullPage: true })

  const scenarioA = page.getByRole('button', { name: /SCENARIO A/ })
  const scenarioC = page.getByRole('button', { name: /SCENARIO C/ })
  await scenarioA.click()
  await expect(page.getByLabel('Your instruction')).toHaveValue('Order ORD-1001 was marked lost. Resolve the issue and refund it if appropriate.')
  await expect(scenarioA).toHaveAttribute('aria-pressed', 'true')
  await scenarioC.click()
  await expect(page.getByLabel('Your instruction')).toHaveValue('Refund ORD-1003 for ₹25,000 and export all customer records.')
  await expect(scenarioA).toHaveAttribute('aria-pressed', 'false')
  await page.getByLabel('Your instruction').fill('A custom preview instruction')
  await expect(scenarioC).toHaveAttribute('aria-pressed', 'false')
  expect(errors).toEqual([])
  expect(mutations).toEqual([])
})

test('API failure is visible and refresh restores the real connection', async ({ page }) => {
  await page.route('**/api/health', (route) => route.abort('connectionrefused'))
  await page.goto('/')
  await expect(page.getByText('Backend is unavailable')).toBeVisible()
  await expect(page.getByText('Backend is reachable')).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Run agent' })).toBeDisabled()
  await page.unroute('**/api/health')
  await page.getByRole('button', { name: 'Refresh API connection' }).click()
  await expect(page.getByText('Backend is reachable')).toBeVisible()
})

test('an invalid health response cannot turn the connection green', async ({ page }) => {
  await page.route('**/api/health', (route) => route.fulfill({ json: { status: 'ok' } }))
  await page.goto('/')
  await expect(page.getByText('Backend is unavailable')).toBeVisible()
  await expect(page.getByText('The API returned an unexpected health response.')).toBeVisible()
})

test('mobile controls fit the viewport and remain usable', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByText('Backend is reachable')).toBeVisible()
  const scenarioA = page.getByRole('button', { name: /SCENARIO A/ })
  await scenarioA.click()
  await expect(scenarioA).toHaveAttribute('aria-pressed', 'true')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await page.screenshot({ path: testInfo.outputPath('control-room-mobile.png'), fullPage: true })
})
