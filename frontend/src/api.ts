export interface Health {
  status: 'ok'
  service: string
  version: string
  environment: 'development' | 'test' | 'production'
  phase: 'authority'
  policy_engine: 'cedar'
}

export type Decision =
  | 'ALLOW'
  | 'REQUIRE_APPROVAL'
  | 'DENY'

export interface Outcome {
  decision: Decision
  reason_code: string
  executed: boolean
  result: Record<string, unknown> | null
  pending_id: string | null
  determining_policies: string[]
  error: {
    code: string
    message: string
  } | null
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

export type Actor =
  | 'OPERATOR'
  | 'AGENT'
  | 'CEDAR'
  | 'HUMAN'
  | 'TOOL'

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

export interface EvaluationRequest {
  principal: {
    type: 'Agent'
    id: string
  }

  action: string

  resource: {
    type: string
    id: string
  }

  context: Record<string, unknown>
}

export interface EvaluationResponse {
  decision: Decision
  principal: string
  action: string
  resource: string
  reason: string
  reason_code: string
  matched_policy: string | null
}

export interface PolicyDefinition {
  id: string
  name: string
  principal_type: 'Agent'
  principal_id: string
  action: string
  resource_type: string
  decision: Decision
  context_field: string | null
  allow_threshold: number | null
  approval_threshold: number | null
  active: boolean
}

export interface PolicyDraft {
  draft: PolicyDefinition
  cedar_preview: string
  active: boolean
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

export interface Refund {
  refund_id: string
  order_id: string
  amount: number
  currency: string
}

export interface RecordedEmail {
  email_id: string
  customer_id: string
  to: string
  subject: string
  body: string
}

export interface BusinessState {
  orders: Order[]
  refunds: Refund[]
  emails: RecordedEmail[]
}

/*
 * IMPORTANT:
 *
 * Browser ALWAYS talks to the same HTTPS Vercel origin:
 *
 *   /api/...
 *
 * Vercel then proxies those requests server-side to EC2.
 *
 * Never put the EC2 HTTP address here.
 */
export const apiBase = '/api'

export const apiDocsUrl = '/api/docs'

export const apiOpenApiUrl = '/api/openapi.json'

async function readResponse(
  response: Response,
): Promise<unknown> {
  if (response.status === 204) {
    return null
  }

  const contentType =
    response.headers.get('content-type') ?? ''

  if (
    contentType.includes('application/json')
  ) {
    return response.json()
  }

  return response.text()
}

function getErrorMessage(
  status: number,
  body: unknown,
): string {
  if (
    body &&
    typeof body === 'object' &&
    'detail' in body
  ) {
    const detail = (
      body as {
        detail?: unknown
      }
    ).detail

    if (typeof detail === 'string') {
      return detail
    }

    if (detail !== undefined) {
      try {
        return JSON.stringify(detail)
      } catch {
        // fallback below
      }
    }
  }

  if (
    typeof body === 'string' &&
    body.trim()
  ) {
    return body
  }

  return `The API returned HTTP ${status}.`
}

async function call<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${apiBase}${path}`

  let response: Response

  try {
    response = await fetch(url, {
      ...init,

      cache: 'no-store',

      signal:
        init?.signal ??
        AbortSignal.timeout(10000),

      headers: {
        Accept: 'application/json',

        ...(init?.body
          ? {
              'Content-Type':
                'application/json',
            }
          : {}),

        ...init?.headers,
      },
    })
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === 'TimeoutError'
    ) {
      throw new Error(
        `AgentGate API timed out at ${url}.`,
      )
    }

    throw new Error(
      `Unable to reach AgentGate API at ${url}.`,
      {
        cause: error,
      },
    )
  }

  const body =
    await readResponse(response)

  if (!response.ok) {
    throw new Error(
      getErrorMessage(
        response.status,
        body,
      ),
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  return body as T
}

export async function fetchHealth(
  signal?: AbortSignal,
): Promise<Health> {
  const url = `${apiBase}/health`

  let response: Response

  try {
    response = await fetch(url, {
      cache: 'no-store',

      signal:
        signal ??
        AbortSignal.timeout(5000),

      headers: {
        Accept: 'application/json',
      },
    })
  } catch (error) {
    throw new Error(
      `Unable to reach AgentGate API at ${url}.`,
      {
        cause: error,
      },
    )
  }

  if (!response.ok) {
    throw new Error(
      `The API returned HTTP ${response.status}.`,
    )
  }

  const payload: unknown =
    await response.json()

  if (
    !payload ||
    typeof payload !== 'object'
  ) {
    throw new Error(
      'The API returned an unexpected health response.',
    )
  }

  const health =
    payload as Partial<Health>

  if (
    health.status !== 'ok' ||
    typeof health.service !== 'string' ||
    !health.service ||
    typeof health.version !== 'string' ||
    !health.version ||
    ![
      'development',
      'test',
      'production',
    ].includes(
      String(health.environment),
    ) ||
    health.phase !== 'authority' ||
    health.policy_engine !== 'cedar'
  ) {
    throw new Error(
      'The API returned an unexpected health response.',
    )
  }

  return payload as Health
}

export const proposeAction = (
  tool: string,
  args: Record<string, unknown>,
  runId: string,
) =>
  call<Outcome>(
    '/actions',
    {
      method: 'POST',

      body: JSON.stringify({
        tool,
        arguments: args,
        run_id: runId,
      }),
    },
  )

export const decidePending = (
  pendingId: string,
  decision: 'approve' | 'deny',
  version: number,
) =>
  call<Outcome>(
    `/pending/${encodeURIComponent(
      pendingId,
    )}`,
    {
      method: 'POST',

      body: JSON.stringify({
        decision,
        version,
      }),
    },
  )

export const fetchPending = () =>
  call<Pending[]>(
    '/pending',
  )

export const fetchTimeline = (
  runId?: string,
) =>
  call<TimelineEvent[]>(
    runId
      ? `/timeline?run_id=${encodeURIComponent(
          runId,
        )}`
      : '/timeline',
  )

export const fetchState = () =>
  call<BusinessState>(
    '/state',
  )

export const runPolicyBench = () =>
  call<BenchResult>(
    '/policy-test',
    {
      method: 'POST',
    },
  )

export const resetDemo = () =>
  call<{
    status: string
  }>(
    '/reset',
    {
      method: 'POST',
    },
  )

export const evaluateAction = (
  payload: EvaluationRequest,
) =>
  call<EvaluationResponse>(
    '/gate/evaluate',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )

export const fetchPolicies = () =>
  call<PolicyDefinition[]>(
    '/policies',
  )

export type CreatePolicyPayload =
  Omit<
    PolicyDefinition,
    'id' | 'active'
  >

export const createPolicy = (
  payload: CreatePolicyPayload,
) =>
  call<PolicyDefinition>(
    '/policies',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )

export const activatePolicy = (
  id: string,
) =>
  call<PolicyDefinition>(
    `/policies/${encodeURIComponent(
      id,
    )}/activate`,
    {
      method: 'POST',
    },
  )

export const deletePolicy = (
  id: string,
) =>
  call<void>(
    `/policies/${encodeURIComponent(
      id,
    )}`,
    {
      method: 'DELETE',
    },
  )

export const draftPolicy = (
  description: string,
) =>
  call<PolicyDraft>(
    '/policies/draft',
    {
      method: 'POST',

      body: JSON.stringify({
        description,
      }),
    },
  )