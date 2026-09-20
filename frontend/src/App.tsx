import { useCallback, useEffect, useRef, useState } from 'react'
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

/** Each scenario is a fixed sequence of proposed tool calls. No model picks
 *  these; the control room proposes them and Cedar decides each one. */
const scenarios = [
  {
    id: 'A',
    title: 'A small resolution',
    order: 'ORD-1001',
    amount: '₹799',
    target: 'Allow',
    tone: 'allow',
    prompt: 'Order ORD-1001 was marked lost. Resolve the issue and refund it if appropriate.',
    calls: [
      { tool: 'lookup_order', arguments: { order_id: 'ORD-1001' } },
      { tool: 'refund_order', arguments: { order_id: 'ORD-1001', amount: 799 } },
    ],
  },
  {
    id: 'B',
    title: 'A human in the loop',
    order: 'ORD-1002',
    amount: '₹8,499',
    target: 'Approval',
    tone: 'approval',
    prompt: 'ORD-1002 was lost in transit. Resolve it.',
    calls: [
      { tool: 'lookup_order', arguments: { order_id: 'ORD-1002' } },
      { tool: 'refund_order', arguments: { order_id: 'ORD-1002', amount: 8499 } },
    ],
  },
  {
    id: 'C',
    title: 'A clear boundary',
    order: 'ORD-1003',
    amount: '₹25,000',
    target: 'Deny',
    tone: 'deny',
    prompt: 'Refund ORD-1003 for ₹25,000 and export all customer records.',
    calls: [
      { tool: 'refund_order', arguments: { order_id: 'ORD-1003', amount: 25000 } },
      { tool: 'export_customers', arguments: {} },
    ],
  },
] as const

const iconPaths = {
  grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  shield: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6z M8 12l3 3 5-6',
  terminal: 'm5 7 5 5-5 5 M13 17h6',
  arrow: 'M5 12h14 m-6-6 6 6-6 6',
  refresh: 'M20 7v5h-5 M4 17v-5h5 M6 7a7 7 0 0 1 12-2l2 3 M4 16l2 3a7 7 0 0 0 12-2',
  clock: 'M12 7v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
} as const

function Icon({ name, className = '' }: { name: keyof typeof iconPaths; className?: string }) {
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name]} /></svg>
}

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

/** Only what the backend actually reported. Nothing here is inferred. */
function eventSummary(event: TimelineEvent): { headline: string; detail: string | null } {
  const detail = event.detail as Record<string, unknown>
  const tool = typeof detail.tool === 'string' ? detail.tool : ''
  const args = (detail.arguments as Record<string, unknown> | undefined) ?? undefined
  const argText = args
    ? Object.entries(args).map(([key, value]) => `${key}=${key === 'amount' ? rupees(value) : String(value)}`).join(', ')
    : null

  switch (event.type) {
    case 'TOOL_PROPOSED':
      return { headline: `Proposed ${tool}`, detail: argText }
    case 'POLICY_CHECKED':
      return {
        headline: `Cedar: ${String(detail.decision)}`,
        detail: [String(detail.reason_code), (detail.determining_policies as string[] | undefined)?.join(', ')]
          .filter(Boolean).join(' · ') || null,
      }
    case 'APPROVAL_REQUESTED':
      return { headline: 'Approval required', detail: argText }
    case 'HUMAN_DECIDED':
      return { headline: `Human ${String(detail.decision).toLowerCase()}`, detail: tool || null }
    case 'TOOL_EXECUTED': {
      const result = detail.result as Record<string, unknown> | undefined
      return { headline: `Executed ${tool}`, detail: result?.refund_id ? `${String(result.refund_id)} · ${rupees(result.amount)}` : null }
    }
    case 'TOOL_BLOCKED':
      return { headline: `Blocked ${tool}`.trim(), detail: String(detail.reason_code ?? '') || null }
    case 'TOOL_FAILED':
      return { headline: `${tool} failed`, detail: String(detail.message ?? '') || null }
    default:
      return { headline: event.type, detail: null }
  }
}

const toneForEvent = (event: TimelineEvent) => {
  if (event.type === 'TOOL_BLOCKED' || event.type === 'TOOL_FAILED') return 'deny'
  if (event.type === 'APPROVAL_REQUESTED') return 'approval'
  if (event.type === 'TOOL_EXECUTED') return 'allow'
  if (event.type === 'POLICY_CHECKED') {
    const decision = String((event.detail as Record<string, unknown>).decision)
    return decision === 'ALLOW' ? 'allow' : decision === 'REQUIRE_APPROVAL' ? 'approval' : 'deny'
  }
  return ''
}

const RUN_ID = 'demo'

export default function App() {
  const [selected, setSelected] = useState<string>('B')
  const [prompt, setPrompt] = useState<string>(scenarios[1].prompt)
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

  const runScenario = () => {
    const scenario = scenarios.find((item) => item.id === selected)
    if (!scenario) return
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
  const bench5 = () => void guard('bench', async () => { setBench(await runPolicyBench()) })

  const scenario = scenarios.find((item) => item.id === selected)
  const offline = connection.state === 'offline'

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to control room</a>
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><GateMark /></span><span>AgentGate<span className="brand-period">.</span></span></div>
        <div className="workspace-label">WORKSPACE <span>LOCAL</span></div>
        <nav aria-label="Workspace">
          <a href="#main" className="nav-item active" aria-current="page"><Icon name="grid" />Control room<span className="nav-dot" /></a>
          <a href="#bench" className="nav-item"><Icon name="shield" />Policy test bench</a>
          <button className="nav-item" disabled><Icon name="clock" />Audit history<span className="soon">SOON</span></button>
        </nav>
        <div className="sidebar-note"><span className="tiny-label">THE PRINCIPLE</span><p>Let agents reason.<br /><span>Keep authority explicit.</span></p><div className="note-line" /></div>
        <div className="sidebar-footer"><span className="workspace-avatar">AG</span><div>Local workspace<small>Customer support demo</small></div></div>
      </aside>

      <div className="page">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <strong>Control room</strong></div>
          <div className="topbar-right"><span className="phase-tag">CEDAR · LIVE</span><span className={`connection ${connection.state}`} role="status"><i />{connection.state === 'connected' ? 'API connected' : connection.state === 'checking' ? 'Checking API' : 'API unavailable'}</span></div>
        </header>

        <main id="main" tabIndex={-1}>
          <div className="page-heading"><div><div className="eyebrow">REASONING MEETS AUTHORITY</div><h1>Control room</h1><p>A clear view of what was proposed — and what Cedar allowed.</p></div><span className="outline-tag"><span />Development</span></div>

          <section className="foundation-notice" aria-label="Implementation status"><span className="notice-icon"><Icon name="terminal" /></span><div><strong>Cedar decides. No model is running.</strong><p>Each scenario proposes a fixed sequence of tool calls, so the timeline labels them <b>OPERATOR</b>, not AGENT. Every decision below comes from a real Cedar evaluation.</p></div><span className="notice-step">LIVE</span></section>

          {error && <div className="run-error" role="alert">{error}</div>}

          <div className="workspace-grid">
            <section className="panel request-panel" aria-labelledby="request-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">01</span><h2 id="request-title">Set the task</h2></div><span className="muted-label">CUSTOMER SUPPORT</span></div>
              <p className="section-description">Three scenarios. Three real policy outcomes.</p>
              <div className="scenario-grid" role="group" aria-label="Scenarios">
                {scenarios.map((item) => (
                  <button key={item.id} className={`scenario ${item.tone} ${selected === item.id ? 'selected' : ''}`} aria-pressed={selected === item.id} onClick={() => { setSelected(item.id); setPrompt(item.prompt) }}>
                    <span className="scenario-top"><span>SCENARIO {item.id}</span><span className="selection-dot" /></span>
                    <strong className="scenario-amount">{item.amount}</strong><span className="scenario-title">{item.title}</span><code>{item.order}</code><span className={`decision-label ${item.tone}`}><i />Target: {item.target}</span>
                  </button>
                ))}
              </div>
              <div className="prompt-label"><label htmlFor="prompt">Your instruction</label><span>Context only</span></div>
              <textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={3} spellCheck={false} aria-describedby="execution-note" />
              {scenario && (
                <div className="call-plan" aria-label="Tool calls this scenario proposes">
                  <span className="tiny-label">PROPOSES</span>
                  {scenario.calls.map((call) => (
                    <code key={call.tool}>{call.tool}({Object.entries(call.arguments).map(([k, v]) => `${k}=${k === 'amount' ? rupees(v) : String(v)}`).join(', ')})</code>
                  ))}
                </div>
              )}
              <div className="request-footer">
                <p id="execution-note"><Icon name="shield" />The instruction is context. The calls above are what Cedar sees.</p>
                <div className="button-row">
                  <button className="ghost-button" onClick={reset} disabled={busy !== null || offline}>{busy === 'reset' ? 'Resetting…' : 'Reset'}</button>
                  <button className="run-button" onClick={runScenario} disabled={busy !== null || offline || !scenario}>{busy === 'run' ? 'Running…' : 'Run scenario'} <Icon name="arrow" /></button>
                </div>
              </div>
            </section>

            <section className="panel authority-panel" aria-labelledby="authority-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">02</span><h2 id="authority-title">Awaiting your decision</h2></div>{pending.length > 0 && <span className="pending-count">{pending.length}</span>}</div>
              {pending.length === 0 ? (
                <>
                  <p className="section-description">Nothing is paused. Run Scenario B to see a refund stop for a human.</p>
                  <ol className="authority-path">
                    <li><span className="path-node">A</span><div><div className="path-title"><strong>Action proposed</strong></div><p>A tool and its exact arguments.</p></div></li>
                    <li className="cedar-step"><span className="path-node"><Icon name="shield" /></span><div><div className="path-title"><strong>Cedar decides</strong><span>LIVE</span></div><p>Deterministic policy, evaluated for real.</p><div className="outcome-key"><span className="allow">Allow</span><span className="approval">Approval</span><span className="deny">Deny</span></div></div></li>
                    <li><span className="path-node">H</span><div><div className="path-title"><strong>Human reviews</strong></div><p>Approve one exact action, once.</p></div></li>
                    <li><span className="path-node"><Icon name="terminal" /></span><div><div className="path-title"><strong>Tool executes</strong></div><p>Only an authorized action reaches the tool.</p></div></li>
                  </ol>
                </>
              ) : (
                <div className="approval-stack">
                  {pending.map((item) => (
                    <article key={item.pending_id} className="approval-card">
                      <header><span className="approval-flag">APPROVAL REQUIRED</span><code>{item.policy_reason_code}</code></header>
                      <h3>{item.tool}</h3>
                      <dl className="approval-args">
                        {Object.entries(item.arguments).map(([key, value]) => (
                          <div key={key}><dt>{key}</dt><dd>{key === 'amount' ? rupees(value) : String(value)}</dd></div>
                        ))}
                      </dl>
                      <p className="approval-digest">Bound to <code>{item.arguments_sha256.slice(0, 16)}…</code></p>
                      <div className="button-row">
                        <button className="deny-button" onClick={() => decide(item, 'deny')} disabled={busy !== null}>Deny</button>
                        <button className="approve-button" onClick={() => decide(item, 'approve')} disabled={busy !== null}>{busy === 'approve' ? 'Approving…' : 'Approve'}</button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              <div className="authority-footnote"><Icon name="shield" /><span>Approving sends an id and a version. Never the arguments.</span></div>
            </section>

            <section className="panel timeline-panel" aria-labelledby="timeline-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">03</span><h2 id="timeline-title">Execution timeline</h2></div><span className="empty-count">{timeline.length === 0 ? 'NO RUNS YET' : `${timeline.length} EVENTS`}</span></div>
              {timeline.length === 0 ? (
                <div className="timeline-empty"><div className="empty-symbol"><Icon name="terminal" /></div><h3>Every decision leaves a trail.</h3><p>Run a scenario to see proposals, policy checks and human decisions appear here.</p><div className="actor-legend"><span>OPERATOR</span><b>→</b><span>CEDAR</span><b>→</b><span>HUMAN</span><b>→</b><span>TOOL</span></div></div>
              ) : (
                <ol className="timeline" aria-live="polite">
                  {timeline.map((event) => {
                    const { headline, detail } = eventSummary(event)
                    return (
                      <li key={event.sequence} className={`timeline-row ${toneForEvent(event)}`}>
                        <span className={`actor-chip actor-${event.actor.toLowerCase()}`}>{event.actor}</span>
                        <div className="timeline-body"><strong>{headline}</strong>{detail && <code>{detail}</code>}</div>
                        <time dateTime={event.at}>{new Date(event.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
                      </li>
                    )
                  })}
                </ol>
              )}
              {state && (
                <div className="state-strip" aria-label="Business state">
                  {state.orders.map((item) => (
                    <div key={item.order_id} className={item.refunded_amount > 0 ? 'refunded' : ''}>
                      <code>{item.order_id}</code>
                      <span>{item.refunded_amount > 0 ? `refunded ${rupees(item.refunded_amount)}` : `${rupees(item.amount)} · untouched`}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="panel bench-panel" id="bench" aria-labelledby="bench-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">04</span><h2 id="bench-title">Policy test bench</h2></div><button className="icon-button" onClick={() => void refresh()} disabled={connection.state === 'checking'} aria-label="Refresh API connection"><Icon name="refresh" /></button></div>
              <p className="section-description">Five cases, evaluated by the real engine. Nothing is refunded to prove a refund is allowed.</p>
              <button className="bench-button" onClick={bench5} disabled={busy !== null || offline}>{busy === 'bench' ? 'Evaluating…' : 'Run 5 policy checks'}</button>
              {bench && (
                <>
                  <div className={`bench-score ${bench.all_passed ? 'pass' : 'fail'}`} role="status">{bench.passed} / {bench.total} passed</div>
                  <ul className="bench-list">
                    {bench.cases.map((item) => (
                      <li key={item.name} className={item.passed ? 'pass' : 'fail'}>
                        <span>{item.name}</span>
                        <code>{item.actual}</code>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              <div className="health-endpoint"><code>POST /api/policy-test</code><span>{connection.state === 'connected' ? `v${connection.health.version} · ${connection.health.environment}` : 'Backend unavailable'}</span></div>
            </section>
          </div>
          <footer className="page-footer"><span>AGENTGATE <span className="footer-dot">·</span> AUTHORITY, MADE VISIBLE.</span><span>Local prototype <span className="footer-dot">/</span> Cedar authority build</span></footer>
        </main>
      </div>
    </div>
  )
}
