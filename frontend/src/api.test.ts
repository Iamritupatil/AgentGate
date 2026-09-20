import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchHealth } from './api'

const healthy = {
  status: 'ok',
  service: 'AgentGate',
  version: '0.1.0',
  environment: 'test',
  phase: 'authority',
  policy_engine: 'cedar',
}

afterEach(() => vi.unstubAllGlobals())

describe('API health verification', () => {
  it('reads actual health through the API proxy without cached results', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json(healthy))
    vi.stubGlobal('fetch', fetch)
    await expect(fetchHealth()).resolves.toEqual(healthy)
    expect(fetch).toHaveBeenCalledWith('/api/health', expect.objectContaining({ cache: 'no-store' }))
  })

  it('rejects unsuccessful HTTP responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Unavailable', { status: 503 })))
    await expect(fetchHealth()).rejects.toThrow('HTTP 503')
  })

  it.each([null, {}, { ...healthy, status: 'error' }, { ...healthy, phase: 'foundation' }, { ...healthy, policy_engine: undefined }, { ...healthy, version: undefined }])(
    'does not claim connection for malformed health: %j',
    async (payload) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(payload)))
      await expect(fetchHealth()).rejects.toThrow('unexpected health response')
    },
  )

  it('propagates network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(fetchHealth()).rejects.toThrow('Failed to fetch')
  })

  it('rejects HTML instead of treating a fallback page as a healthy API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>fallback</html>')))
    await expect(fetchHealth()).rejects.toThrow()
  })

  it('passes cancellation to the request', async () => {
    const controller = new AbortController()
    const fetch = vi.fn().mockResolvedValue(Response.json(healthy))
    vi.stubGlobal('fetch', fetch)
    await fetchHealth(controller.signal)
    const requestSignal = fetch.mock.calls[0][1].signal as AbortSignal
    controller.abort()
    expect(requestSignal.aborted).toBe(true)
  })
})
