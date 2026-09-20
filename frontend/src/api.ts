export interface Health {
  status: 'ok'
  service: string
  version: string
  environment: 'development' | 'test' | 'production'
  phase: 'authority'
  policy_engine: 'cedar'
}

export type Decision = 'ALLOW' | 'REQUIRE_APPROVAL' | 'DENY'

export interface Outcome {
  decision: Decision
  reason_code: string
  executed: boolean
  result: Record<string, unknown> | null
  pending_id: string | null
  determining_policies: string[]
  error: { code: string; message: string } | null
}

export interface Pending {
  pending_id: string
  run_id: string
  tool: string
  arguments: Record<string, unknown>
  arguments_sha256: string
  policy_reason_code: string
  version: number
  created_at: string
}

export type Actor = 'OPERATOR' | 'AGENT' | 'CEDAR' | 'HUMAN' | 'TOOL'

export interface TimelineEvent {
  sequence: number
  run_id: string
  actor: Actor
  type: string
  detail: Record<string, unknown>
  at: string
}

export interface BenchCase {
  name: string
  tool: string
  arguments: Record<string, unknown>
  expected: string
  actual: string
  passed: boolean
  determining_policies: string[]
}

export interface BenchResult {
  passed: number
  total: number
  all_passed: boolean
  cases: BenchCase[]
}

export interface Order {
  order_id: string
  customer_id: string
  amount: number
  payment_status: string
  shipping_status: string
  refunded_amount: number
  currency: string
}

export interface BusinessState {
  orders: Order[]
  refunds: { refund_id: string; order_id: string; amount: number; currency: string }[]
  emails: { email_id: string; customer_id: string; to: string; subject: string; body: string }[]
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    signal: AbortSignal.timeout(10000),
    cache: 'no-store',
    headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
  })
  if (!response.ok) {
    throw new Error(`The API returned HTTP ${response.status}.`)
  }
  return (await response.json()) as T
}

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

export const proposeAction = (tool: string, args: Record<string, unknown>, runId: string) =>
  call<Outcome>('/actions', {
    method: 'POST',
    body: JSON.stringify({ tool, arguments: args, run_id: runId }),
  })

/** Carries only an id, a version and a decision. Never the arguments. */
export const decidePending = (pendingId: string, decision: 'approve' | 'deny', version: number) =>
  call<Outcome>(`/pending/${encodeURIComponent(pendingId)}`, {
    method: 'POST',
    body: JSON.stringify({ decision, version }),
  })

export const fetchPending = () => call<Pending[]>('/pending')
export const fetchTimeline = (runId?: string) =>
  call<TimelineEvent[]>(runId ? `/timeline?run_id=${encodeURIComponent(runId)}` : '/timeline')
export const fetchState = () => call<BusinessState>('/state')
export const runPolicyBench = () => call<BenchResult>('/policy-test', { method: 'POST' })
export const resetDemo = () => call<{ status: string }>('/reset', { method: 'POST' })
