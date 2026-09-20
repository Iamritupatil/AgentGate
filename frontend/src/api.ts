export interface Health {
  status: 'ok'
  service: string
  version: string
  environment: 'development' | 'test' | 'production'
  phase: 'authority'
  policy_engine: 'cedar'
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const timeout = AbortSignal.timeout(5000)
  const response = await fetch(`${apiBase}/health`, {
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`The API returned HTTP ${response.status}.`)
  }

  const payload: unknown = await response.json()
  if (
    !payload ||
    typeof payload !== 'object' ||
    !('status' in payload) || payload.status !== 'ok' ||
    !('service' in payload) || typeof payload.service !== 'string' || !payload.service ||
    !('version' in payload) || typeof payload.version !== 'string' || !payload.version ||
    !('environment' in payload) ||
    !['development', 'test', 'production'].includes(String(payload.environment)) ||
    !('phase' in payload) || payload.phase !== 'authority' ||
    !('policy_engine' in payload) || payload.policy_engine !== 'cedar'
  ) {
    throw new Error('The API returned an unexpected health response.')
  }

  return payload as Health
}
