import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  decidePending,
  fetchHealth,
  fetchPending,
  fetchState,
  fetchTimeline,
  proposeAction,
  resetDemo,
  runPolicyBench,
  type BenchResult,
  type BusinessState,
  type Health,
  type Pending,
  type TimelineEvent,
} from './api'
import { Integrate, Playground, PolicyStudio } from './Workbench'

/** Each scenario is a fixed sequence of proposed tool calls. No model picks
 *  these; the control room proposes them and Cedar decides each one. */
const scenarios = [
  {
    id: 'A',
    label: 'Small resolution',
    amount: '₹799',
    order: 'ORD-1001',
    target: 'ALLOW',
    tone: 'allow',
    prompt: 'Order ORD-1001 was marked lost. Resolve the issue and refund it if appropriate.',
    calls: [
      { tool: 'lookup_order', arguments: { order_id: 'ORD-1001' } },
      { tool: 'refund_order', arguments: { order_id: 'ORD-1001', amount: 799 } },
    ],
  },
  {
    id: 'B',
    label: 'Human in the loop',
    amount: '₹8,499',
    order: 'ORD-1002',
    target: 'APPROVAL',
    tone: 'approval',
    prompt: 'ORD-1002 was lost in transit. Resolve it.',
    calls: [
      { tool: 'lookup_order', arguments: { order_id: 'ORD-1002' } },
      { tool: 'refund_order', arguments: { order_id: 'ORD-1002', amount: 8499 } },
    ],
  },
  {
    id: 'C',
    label: 'Clear boundary',
    amount: '₹25,000',
    order: 'ORD-1003',
    target: 'DENY',
    tone: 'deny',
    prompt: 'Refund ORD-1003 for ₹25,000 and export all customer records.',
    calls: [
      { tool: 'refund_order', arguments: { order_id: 'ORD-1003', amount: 25000 } },
      { tool: 'export_customers', arguments: {} },
    ],
  },
] as const

function GateMark() {
  return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M5 26V6h8v6H9v14M27 26V6h-8v6h4v14M13 18h6v8h-6z" fill="currentColor" /></svg>
}

type Connection =
  | { state: 'checking' }
  | { state: 'connected'; health: Health; checkedAt: Date }
  | { state: 'offline'; message: string }

function useHealth() {
  const [connection, setConnection] = useState<Connection>({ state: 'checking' })
  const request = useRef<AbortController | null>(null)

  const refresh = useCallback(async () => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setConnection({ state: 'checking' })
    try {
      const health = await fetchHealth(controller.signal)
      if (!controller.signal.aborted) setConnection({ state: 'connected', health, checkedAt: new Date() })
    } catch (error) {
      if (!controller.signal.aborted) {
        setConnection({ state: 'offline', message: error instanceof Error ? error.message : 'The API could not be reached.' })
      }
    }
  }, [])

  useEffect(() => {
    void refresh()
    const interval = window.setInterval(() => void refresh(), 15000)
    return () => { window.clearInterval(interval); request.current?.abort() }
  }, [refresh])

  return { connection, refresh }
}

const rupees = (value: unknown) =>
  typeof value === 'number' ? `₹${value.toLocaleString('en-IN')}` : String(value)

const pad = (n: number) => String(n).padStart(2, '0')

type Decided = {
  proposalId: string
  tool: string
  args: Record<string, unknown>
  decision: string
  reason: string
  policies: string[]
  executed: boolean
  /** Who touched this call, in order. The demo has to show that a human sat
   *  between Cedar and the tool, so the trail is rendered, not summarised. */
  trail: string[]
}

/** Fold the raw event stream into one row per proposed call. The table shows
 *  what was proposed and what Cedar said; nothing here is inferred. */
function toolCalls(timeline: TimelineEvent[]): Decided[] {
  const rows = new Map<string, Decided>()
  const byPending = new Map<string, string>()

  for (const event of timeline) {
    const detail = event.detail as Record<string, unknown>
    const id = typeof detail.proposal_id === 'string' ? detail.proposal_id : null

    if (event.type === 'TOOL_PROPOSED' && id) {
      rows.set(id, {
        proposalId: id,
        tool: String(detail.tool ?? ''),
        args: (detail.arguments as Record<string, unknown>) ?? {},
        decision: '',
        reason: '',
        policies: [],
        executed: false,
        trail: [event.actor],
      })
    }

    // A human decision carries only a pending id, so keep the mapping that
    // ties it back to the call it authorizes.
    if (event.type === 'APPROVAL_REQUESTED' && id && typeof detail.pending_id === 'string') {
      byPending.set(detail.pending_id, id)
    }
    const resolved = id ?? (typeof detail.pending_id === 'string' ? byPending.get(detail.pending_id) : undefined)
    const row = resolved ? rows.get(resolved) : undefined
    if (!row) continue

    if (event.type === 'POLICY_CHECKED') {
      row.decision = String(detail.decision ?? '')
      row.reason = String(detail.reason_code ?? '')
      row.policies = (detail.determining_policies as string[]) ?? []
    }
    if (event.type === 'TOOL_EXECUTED') row.executed = true
    if (event.type === 'HUMAN_DECIDED') row.reason = `HUMAN_${String(detail.decision ?? '')}`
    if (row.trail[row.trail.length - 1] !== event.actor) row.trail.push(event.actor)
  }
  return [...rows.values()]
}

const decisionTone = (decision: string) =>
  decision === 'ALLOW' ? 'allow' : decision === 'REQUIRE_APPROVAL' ? 'approval' : decision === 'DENY' ? 'deny' : ''

const decisionLabel = (decision: string) =>
  decision === 'REQUIRE_APPROVAL' ? 'REQUIRE APPROVAL' : decision || 'PENDING'

const RUN_ID = 'demo'
const AUTONOMOUS_LIMIT = 2000
const APPROVAL_LIMIT = 10000

export default function ControlRoom() {
  const [selected, setSelected] = useState<string>('B')
  const [view, setView] = useState<'stream' | 'bench' | 'studio' | 'playground' | 'integrate'>('stream')
  const [timeline, setTimeline] = useState<TimelineEvent[]>([])
  const [pending, setPending] = useState<Pending[]>([])
  const [state, setState] = useState<BusinessState | null>(null)
  const [bench, setBench] = useState<BenchResult | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { connection, refresh } = useHealth()

  const sync = useCallback(async () => {
    const [events, waiting, business] = await Promise.all([fetchTimeline(RUN_ID), fetchPending(), fetchState()])
    setTimeline(events)
    setPending(waiting)
    setState(business)
  }, [])

  useEffect(() => { void sync().catch(() => undefined) }, [sync])

  const guard = async (label: string, work: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await work()
      await sync()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The request failed.')
    } finally {
      setBusy(null)
    }
  }

  const scenario = scenarios.find((item) => item.id === selected)

  const runScenario = () => {
    if (!scenario) return
    setView('stream')
    void guard('run', async () => {
      for (const call of scenario.calls) {
        // Sequential on purpose: a call that pauses for approval must not be
        // overtaken by the next one.
        const outcome = await proposeAction(call.tool, call.arguments, RUN_ID)
        if (outcome.decision === 'REQUIRE_APPROVAL') break
      }
    })
  }

  const decide = (item: Pending, decision: 'approve' | 'deny') =>
    void guard(decision, async () => { await decidePending(item.pending_id, decision, item.version) })

  const reset = () => void guard('reset', async () => { await resetDemo(); setBench(null) })
  const bench5 = () => { setView('bench'); void guard('bench', async () => { setBench(await runPolicyBench()) }) }

  const calls = useMemo(() => toolCalls(timeline), [timeline])
  const counts = useMemo(() => ({
    allowed: calls.filter((c) => c.decision === 'ALLOW').length,
    approval: calls.filter((c) => c.decision === 'REQUIRE_APPROVAL').length,
    denied: calls.filter((c) => c.decision === 'DENY').length,
  }), [calls])

  const lastDecision = calls.length ? calls[calls.length - 1] : null
  const waiting = pending[0]
  const offline = connection.state === 'offline'

  return (
    <div className="app">
      <a className="skip-link" href="#main">Skip to control room</a>

      <header className="console-bar">
        <div className="console-brand"><span className="brand-mark"><GateMark /></span><strong>AgentGate</strong></div>
        <span className="console-divider" />
        <span className="console-label">CONTROL ROOM</span>
        <div className={`console-status ${connection.state}`} role="status">
          <span className="status-block">
            <i />{connection.state === 'connected' ? 'POLICY ENGINE CONNECTED' : connection.state === 'checking' ? 'CONNECTING' : 'POLICY ENGINE UNAVAILABLE'}
          </span>
          <small>{connection.state === 'connected' ? 'CEDAR · LIVE EVALUATION' : 'START THE BACKEND ON PORT 8000'}</small>
        </div>
      </header>

      <div className="console">
        <aside className="rail">
          <div className="rail-block">
            <span className="micro">WORKSPACE</span>
            <strong>Support agent</strong>
          </div>

          <nav aria-label="Sections">
            <button className={`rail-nav ${view === 'stream' ? 'active' : ''}`} onClick={() => setView('stream')} aria-current={view === 'stream' ? 'page' : undefined}>
              <span className="rail-num">01</span>Action stream
            </button>
            <button className={`rail-nav ${waiting ? 'flagged' : ''}`} onClick={() => setView('stream')}>
              <span className="rail-num">02</span>Approvals{pending.length > 0 && <span className="rail-badge">{pending.length}</span>}
            </button>
            <button className={`rail-nav ${view === 'studio' ? 'active' : ''}`} onClick={() => setView('studio')}><span className="rail-num">03</span>Policy Studio</button>
            <button className={`rail-nav ${view === 'bench' ? 'active' : ''}`} onClick={() => setView('bench')} aria-current={view === 'bench' ? 'page' : undefined}>
              <span className="rail-num">04</span>Policy test bench
            </button>
            <button className={`rail-nav ${view === 'playground' ? 'active' : ''}`} onClick={() => setView('playground')}><span className="rail-num">05</span>Playground</button>
            <button className={`rail-nav ${view === 'integrate' ? 'active' : ''}`} onClick={() => setView('integrate')}><span className="rail-num">06</span>Integrate</button>
          </nav>

          <div className="rail-block rail-scenarios">
            <span className="micro">DEMO SCENARIO</span>
            <div className="scenario-list" role="group" aria-label="Scenario">
              {scenarios.map((item) => (
                <button
                  key={item.id}
                  className={`scenario ${item.tone} ${selected === item.id ? 'selected' : ''}`}
                  aria-pressed={selected === item.id}
                  onClick={() => setSelected(item.id)}
                >
                  <span className="scenario-id">SCENARIO {item.id}</span>
                  <strong>{item.amount}</strong>
                  <span className="scenario-label">{item.label}</span>
                  <span className={`target ${item.tone}`}><i />{item.target}</span>
                </button>
              ))}
            </div>
            <div className="rail-actions">
              <button className="btn-ghost" onClick={reset} disabled={busy !== null || offline}>{busy === 'reset' ? 'Resetting' : 'Reset'}</button>
              <button className="btn-solid" onClick={runScenario} disabled={busy !== null || offline || !scenario}>{busy === 'run' ? 'Running…' : 'Run scenario'}</button>
            </div>
          </div>

          <div className="rail-foot">
            <span className="micro">EXECUTION MODE</span>
            <strong>Scoped authority</strong>
            <small>Cedar · no model running</small>
          </div>
        </aside>

        <main id="main" tabIndex={-1} className="stream">
          {error && <div className="banner-error" role="alert">{error}</div>}

          {view === 'stream' ? (
            <>
              <div className="stream-head">
                <div>
                  <h1>Action stream</h1>
                  <p>Inspect intent. Evaluate policy. Control execution.</p>
                </div>
                <span className="tag-outline">{scenario ? `SCENARIO ${scenario.id}` : 'NO SCENARIO'}</span>
              </div>

              <div className="tally">
                <div><span className="micro"><i className="dot allow" />ALLOWED</span><strong>{pad(counts.allowed)}</strong></div>
                <div><span className="micro"><i className="dot approval" />AWAITING APPROVAL</span><strong>{pad(counts.approval)}</strong></div>
                <div><span className="micro"><i className="dot deny" />DENIED</span><strong>{pad(counts.denied)}</strong></div>
              </div>

              <div className="table-head">
                <span className="micro">RECENT TOOL CALLS</span>
                <span className="micro">{timeline.length} events</span>
              </div>

              {calls.length === 0 ? (
                <div className="empty">
                  <p>No tool calls yet.</p>
                  <span>Pick a scenario and press Run. Every call is evaluated by Cedar before anything executes.</span>
                  <div className="flow">OPERATOR<b>→</b>CEDAR<b>→</b>HUMAN<b>→</b>TOOL</div>
                </div>
              ) : (
                <table className="calls">
                  <thead>
                    <tr><th>ACTION / RESOURCE</th><th>AMOUNT</th><th>DECISION</th></tr>
                  </thead>
                  <tbody>
                    {calls.map((row) => (
                      <tr key={row.proposalId} className={decisionTone(row.decision)}>
                        <td>
                          <code>{row.tool}</code>
                          <small>{String(row.args.order_id ?? row.args.customer_id ?? 'Customer database · Restricted')}{row.executed ? ' · executed' : ''}</small>
                          <span className="trail">
                            {row.trail.map((actor, index) => (
                              <span key={`${actor}-${index}`}>
                                {index > 0 && <b>→</b>}
                                <i className={`actor actor-${actor.toLowerCase()}`}>{actor}</i>
                              </span>
                            ))}
                          </span>
                        </td>
                        <td className="amount">{'amount' in row.args ? rupees(row.args.amount) : '—'}</td>
                        <td><span className={`pill ${decisionTone(row.decision)}`}>{decisionLabel(row.decision)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <div className="evaluation">
                <span className="micro">POLICY EVALUATION</span>
                {lastDecision ? (
                  <pre>
                    <span className="k">can_execute</span>          <span className={lastDecision.decision === 'ALLOW' ? 'v-true' : 'v-false'}>{String(lastDecision.decision === 'ALLOW')}</span>{'\n'}
                    <span className="k">can_request_approval</span> <span className={lastDecision.decision === 'REQUIRE_APPROVAL' ? 'v-true' : 'v-false'}>{String(lastDecision.decision === 'REQUIRE_APPROVAL')}</span>{'\n'}
                    <span className="note">↳ {lastDecision.reason}{lastDecision.policies.length ? ` · ${lastDecision.policies.join(', ')}` : ''}</span>
                  </pre>
                ) : (
                  <pre><span className="note">↳ awaiting a proposed tool call</span></pre>
                )}
              </div>

              {state && (
                <div className="ledger">
                  <span className="micro">BUSINESS STATE</span>
                  <div>
                    {state.orders.map((item) => (
                      <div key={item.order_id} className={item.refunded_amount > 0 ? 'refunded' : ''}>
                        <code>{item.order_id}</code>
                        <span>{item.refunded_amount > 0 ? `refunded ${rupees(item.refunded_amount)}` : `${rupees(item.amount)} · untouched`}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : view === 'bench' ? (
            <>
              <div className="stream-head">
                <div>
                  <h1>Policy test bench</h1>
                  <p>Five cases, evaluated by the real engine. No business state is touched.</p>
                </div>
                <span className="tag-outline">POST /api/policy-test</span>
              </div>

              <button className="btn-solid wide" onClick={bench5} disabled={busy !== null || offline}>
                {busy === 'bench' ? 'Evaluating…' : 'Run 5 policy checks'}
              </button>

              {bench && (
                <>
                  <div className={`bench-score ${bench.all_passed ? 'pass' : 'fail'}`} role="status">
                    <strong>{bench.passed} / {bench.total}</strong><span>passed</span>
                  </div>
                  <table className="calls bench">
                    <thead><tr><th>CASE</th><th>EXPECTED</th><th>ACTUAL</th></tr></thead>
                    <tbody>
                      {bench.cases.map((item) => (
                        <tr key={item.name} className={item.passed ? 'allow' : 'deny'}>
                          <td><code>{item.tool}</code><small>{item.name}</small></td>
                          <td className="amount">{item.expected}</td>
                          <td><span className={`pill ${item.passed ? 'allow' : 'deny'}`}>{item.passed ? 'PASS' : 'FAIL'}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </>
          ) : view === 'studio' ? <PolicyStudio /> : view === 'playground' ? <Playground /> : <Integrate />}
        </main>

        <aside className="decision">
          {waiting ? (
            <>
              <div className="decision-head approval"><span className="micro">HUMAN DECISION REQUIRED</span></div>
              <span className="decision-kind">Refund request</span>
              <strong className="decision-amount">{rupees(waiting.arguments.amount)}</strong>
              <code className="decision-target">{waiting.tool} / {String(waiting.arguments.order_id ?? '')}</code>

              <dl className="limits">
                <div><dt>Autonomous limit</dt><dd>{rupees(AUTONOMOUS_LIMIT)}</dd></div>
                <div><dt>Approval limit</dt><dd>{rupees(APPROVAL_LIMIT)}</dd></div>
                <div><dt>Execution status</dt><dd className="strong">PAUSED</dd></div>
              </dl>

              <div className="why">
                <span className="micro">WHY IT STOPPED</span>
                <p>Above the autonomous refund limit.<br />A human must authorize this exact call.</p>
              </div>

              <div className="decision-actions">
                <button className="btn-ghost" onClick={() => decide(waiting, 'deny')} disabled={busy !== null}>Deny</button>
                <button className="btn-solid" onClick={() => decide(waiting, 'approve')} disabled={busy !== null}>{busy === 'approve' ? 'Approving…' : 'Approve →'}</button>
              </div>

              <div className="scope">
                <span className="micro">APPROVAL SCOPE</span>
                <p>One pending action. No standing access.<br />Bound to <code>{waiting.arguments_sha256.slice(0, 12)}…</code></p>
              </div>
            </>
          ) : (
            <>
              <div className="decision-head idle"><span className="micro">NO PENDING DECISION</span></div>
              <p className="decision-idle">Nothing is paused. Run Scenario B to see a refund stop for a human.</p>

              <dl className="limits">
                <div><dt>Autonomous limit</dt><dd>{rupees(AUTONOMOUS_LIMIT)}</dd></div>
                <div><dt>Approval limit</dt><dd>{rupees(APPROVAL_LIMIT)}</dd></div>
                <div><dt>Execution status</dt><dd className="strong">{offline ? 'OFFLINE' : 'READY'}</dd></div>
              </dl>

              <ol className="path">
                <li><span>A</span><div><strong>Action proposed</strong><small>A tool and its exact arguments.</small></div></li>
                <li><span className="cedar">C</span><div><strong>Cedar decides</strong><small>Deterministic policy, evaluated for real.</small></div></li>
                <li><span>H</span><div><strong>Human reviews</strong><small>Approve one exact action, once.</small></div></li>
                <li><span>T</span><div><strong>Tool executes</strong><small>Only an authorized action reaches the tool.</small></div></li>
              </ol>

              <div className="scope">
                <span className="micro">APPROVAL SCOPE</span>
                <p>Approving sends an id and a version.<br />It never sends the arguments.</p>
              </div>

              <button className="btn-link" onClick={() => void refresh()} disabled={connection.state === 'checking'}>
                Refresh API connection
              </button>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
