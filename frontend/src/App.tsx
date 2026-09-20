import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHealth, type Health } from './api'

const scenarios = [
  { id: 'A', title: 'A small resolution', order: 'ORD-1001', amount: '₹799', target: 'Allow', tone: 'allow', prompt: 'Order ORD-1001 was marked lost. Resolve the issue and refund it if appropriate.' },
  { id: 'B', title: 'A human in the loop', order: 'ORD-1002', amount: '₹8,499', target: 'Approval', tone: 'approval', prompt: 'ORD-1002 was lost in transit. Resolve it.' },
  { id: 'C', title: 'A clear boundary', order: 'ORD-1003', amount: '₹25,000', target: 'Deny', tone: 'deny', prompt: 'Refund ORD-1003 for ₹25,000 and export all customer records.' },
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

export default function App() {
  const [selected, setSelected] = useState('B')
  const [prompt, setPrompt] = useState<string>(scenarios[1].prompt)
  const { connection, refresh } = useHealth()

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to control room</a>
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><GateMark /></span><span>AgentGate<span className="brand-period">.</span></span></div>
        <div className="workspace-label">WORKSPACE <span>LOCAL</span></div>
        <nav aria-label="Workspace">
          <a href="#main" className="nav-item active" aria-current="page"><Icon name="grid" />Control room<span className="nav-dot" /></a>
          <button className="nav-item" disabled><Icon name="shield" />Policy test bench<span className="soon">SOON</span></button>
          <button className="nav-item" disabled><Icon name="clock" />Audit history<span className="soon">SOON</span></button>
        </nav>
        <div className="sidebar-note"><span className="tiny-label">THE PRINCIPLE</span><p>Let agents reason.<br /><span>Keep authority explicit.</span></p><div className="note-line" /></div>
        <div className="sidebar-footer"><span className="workspace-avatar">AG</span><div>Local workspace<small>Customer support demo</small></div></div>
      </aside>

      <div className="page">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <strong>Control room</strong></div>
          <div className="topbar-right"><span className="phase-tag">PHASE 03 · AUTHORITY</span><span className={`connection ${connection.state}`} role="status"><i />{connection.state === 'connected' ? 'API connected' : connection.state === 'checking' ? 'Checking API' : 'API unavailable'}</span></div>
        </header>

        <main id="main" tabIndex={-1}>
          <div className="page-heading"><div><div className="eyebrow">REASONING MEETS AUTHORITY</div><h1>Control room</h1><p>A clear view of what your agent proposes — and what happens next.</p></div><span className="outline-tag"><span />Development</span></div>

          <section className="foundation-notice" aria-label="Implementation status"><span className="notice-icon"><Icon name="terminal" /></span><div><strong>Cedar now decides. The agent does not yet propose.</strong><p>The policy gate, approvals and the test bench run for real over the API. This screen still previews the scenarios rather than running them; wiring it to the live gate is the next build phase.</p></div><span className="notice-step">03 / 14</span></section>

          <div className="workspace-grid">
            <section className="panel request-panel" aria-labelledby="request-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">01</span><h2 id="request-title">Set the task</h2></div><span className="muted-label">CUSTOMER SUPPORT</span></div>
              <p className="section-description">Three scenarios. Three intended policy outcomes.</p>
              <div className="scenario-grid" role="group" aria-label="Scenario previews">
                {scenarios.map((scenario) => (
                  <button key={scenario.id} className={`scenario ${scenario.tone} ${selected === scenario.id ? 'selected' : ''}`} aria-pressed={selected === scenario.id} onClick={() => { setSelected(scenario.id); setPrompt(scenario.prompt) }}>
                    <span className="scenario-top"><span>SCENARIO {scenario.id}</span><span className="selection-dot" /></span>
                    <strong className="scenario-amount">{scenario.amount}</strong><span className="scenario-title">{scenario.title}</span><code>{scenario.order}</code><span className={`decision-label ${scenario.tone}`}><i />Target: {scenario.target}</span>
                  </button>
                ))}
              </div>
              <div className="prompt-label"><label htmlFor="prompt">Your instruction</label><span>Preview only</span></div>
              <textarea id="prompt" value={prompt} onChange={(event) => { setPrompt(event.target.value); setSelected('') }} rows={3} spellCheck={false} aria-describedby="execution-note" />
              <div className="request-footer"><p id="execution-note"><Icon name="shield" />Execution will be enabled after the policy gate is verified.</p><button className="run-button" disabled>Run agent <Icon name="arrow" /></button></div>
            </section>

            <section className="panel authority-panel" aria-labelledby="authority-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">02</span><h2 id="authority-title">The authority path</h2></div></div>
              <p className="section-description">Every action, through a deliberate boundary.</p>
              <ol className="authority-path">
                <li><span className="path-node">A</span><div><div className="path-title"><strong>Agent proposes</strong><span>PLANNED</span></div><p>Strands selects a tool and its arguments.</p></div></li>
                <li className="cedar-step"><span className="path-node"><Icon name="shield" /></span><div><div className="path-title"><strong>Cedar decides</strong><span>PLANNED</span></div><p>Deterministic policy checks the action.</p><div className="outcome-key"><span className="allow">Allow</span><span className="approval">Approval</span><span className="deny">Deny</span></div></div></li>
                <li><span className="path-node">H</span><div><div className="path-title"><strong>Human reviews</strong><span>PLANNED</span></div><p>When required, approve one exact action.</p></div></li>
                <li><span className="path-node"><Icon name="terminal" /></span><div><div className="path-title"><strong>Tool executes</strong><span>PLANNED</span></div><p>Only an authorized action reaches the tool.</p></div></li>
              </ol>
              <div className="authority-footnote"><Icon name="shield" /><span>The model proposes. Policy holds authority.</span></div>
            </section>

            <section className="panel timeline-panel" aria-labelledby="timeline-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">03</span><h2 id="timeline-title">Execution timeline</h2></div><span className="empty-count">NO RUNS YET</span></div>
              <div className="timeline-empty"><div className="empty-symbol"><Icon name="terminal" /></div><h3>Every decision will leave a trail.</h3><p>Tool proposals, policy checks and human decisions will appear here<br className="desktop-break" /> once the agent runtime is connected.</p><div className="actor-legend"><span>AGENT</span><b>→</b><span>CEDAR</span><b>→</b><span>HUMAN</span><b>→</b><span>TOOL</span></div></div>
            </section>

            <section className="panel health-panel" aria-labelledby="health-title">
              <div className="panel-heading"><div className="section-label"><span className="section-number">04</span><h2 id="health-title">Connection</h2></div><button className="icon-button" onClick={() => void refresh()} disabled={connection.state === 'checking'} aria-label="Refresh API connection"><Icon name="refresh" /></button></div>
              <div className="health-content" aria-live="polite">
                <div className={`health-indicator ${connection.state}`}><span className="health-dot" /><strong>{connection.state === 'connected' ? 'Backend is reachable' : connection.state === 'checking' ? 'Checking connection…' : 'Backend is unavailable'}</strong></div>
                {connection.state === 'connected' ? <><p>The API is responding. Agent and policy integrations are not connected yet.</p><dl><div><dt>Service</dt><dd>{connection.health.service}</dd></div><div><dt>Version</dt><dd>{connection.health.version}</dd></div><div><dt>Environment</dt><dd>{connection.health.environment}</dd></div><div><dt>Last checked</dt><dd>{connection.checkedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</dd></div></dl></> : connection.state === 'offline' ? <><p>Start the backend on port 8000, then refresh the connection. See the README for setup commands.</p><div className="connection-error">{connection.message}</div></> : <p>Requesting live health from the local API.</p>}
              </div><div className="health-endpoint"><code>GET /health</code><span>Checks every 15s</span></div>
            </section>
          </div>
          <footer className="page-footer"><span>AGENTGATE <span className="footer-dot">·</span> AUTHORITY, MADE VISIBLE.</span><span>Local prototype <span className="footer-dot">/</span> Foundation build</span></footer>
        </main>
      </div>
    </div>
  )
}
