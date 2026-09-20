import { useEffect, useState } from 'react'

/** The product site. Everything it claims is something the demo actually does;
 *  where the prototype stops, it says so rather than implying more. */

function GateMark() {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path d="M5 26V6h8v6H9v14M27 26V6h-8v6h4v14M13 18h6v8h-6z" fill="currentColor" />
    </svg>
  )
}

/** Decorative pixel cluster, the site's recurring motif. */
function Pixels({ tone, className }: { tone: 'green' | 'violet' | 'amber' | 'grey'; className?: string }) {
  const cells = [
    [1, 0], [2, 0], [0, 1], [1, 1], [3, 1], [1, 2], [2, 2], [3, 2], [0, 3], [2, 3],
  ]
  return (
    <svg className={`pixels ${tone} ${className ?? ''}`} viewBox="0 0 4 4" aria-hidden="true">
      {cells.map(([x, y]) => <rect key={`${x}-${y}`} x={x} y={y} width="0.72" height="0.72" />)}
    </svg>
  )
}

const nav = [
  { href: '#product', label: 'Product' },
  { href: '#scenarios', label: 'Demo scenarios' },
  { href: '#how', label: 'How it works' },
  { href: '#limits', label: 'Policy limits' },
  { href: '#about', label: 'About' },
]

const scenarios = [
  {
    id: 'A',
    amount: '₹799',
    order: 'ORD-1001',
    decision: 'ALLOW',
    tone: 'allow',
    title: 'A small resolution',
    body: 'Inside the agent’s own refund limit. Cedar allows it and the refund executes, with a receipt to prove it.',
  },
  {
    id: 'B',
    amount: '₹8,499',
    order: 'ORD-1002',
    decision: 'REQUIRE APPROVAL',
    tone: 'approval',
    title: 'A human in the loop',
    body: 'Above the autonomous limit. The run pauses before any mutation, and a person authorizes this exact call — once.',
  },
  {
    id: 'C',
    amount: '₹25,000',
    order: 'ORD-1003',
    decision: 'DENY',
    tone: 'deny',
    title: 'A clear boundary',
    body: 'Past the ceiling a human may authorize, alongside a forbidden customer export. Neither reaches a tool.',
  },
]

const steps = [
  {
    n: 'STEP 1',
    title: 'Agent proposes',
    body: 'A support agent investigates an order and proposes a tool call with explicit arguments.',
  },
  {
    n: 'STEP 2',
    title: 'Cedar evaluates',
    body: 'AgentGate checks execution permission, then eligibility for human approval. No LLM makes this decision.',
  },
  {
    n: 'STEP 3',
    title: 'Route the decision',
    body: 'Allow the call, pause for approval of this exact action, or deny it before the business tool runs.',
  },
]

/** A static picture of the real control room, used as the hero visual. */
function ConsolePanel() {
  return (
    <div className="console-shot" role="img" aria-label="AgentGate control room showing an allowed refund, a refund awaiting approval, and a denied export.">
      <div className="shot-bar">
        <span className="shot-brand"><span className="shot-mark"><GateMark /></span>AgentGate</span>
        <span className="shot-sep" />
        <span className="shot-label">CONTROL ROOM</span>
        <span className="shot-status"><i />POLICY ENGINE CONNECTED</span>
      </div>
      <div className="shot-body">
        <div className="shot-rail">
          <span className="shot-micro">WORKSPACE</span>
          <strong>Support agent</strong>
          <ol>
            <li className="on"><em>01</em>Action stream</li>
            <li><em>02</em>Approvals</li>
            <li><em>03</em>Cedar policies</li>
            <li><em>04</em>Policy test bench</li>
          </ol>
          <div className="shot-mode">
            <span className="shot-micro">EXECUTION MODE</span>
            <strong>Scoped authority</strong>
          </div>
        </div>

        <div className="shot-main">
          <h3>Action stream</h3>
          <p>Inspect intent. Evaluate policy. Control execution.</p>
          <div className="shot-tally">
            <div><span className="shot-micro"><i className="d allow" />ALLOWED</span><strong>01</strong></div>
            <div><span className="shot-micro"><i className="d approval" />AWAITING APPROVAL</span><strong>01</strong></div>
            <div><span className="shot-micro"><i className="d deny" />DENIED</span><strong>01</strong></div>
          </div>
          <span className="shot-micro shot-tablehead">RECENT TOOL CALLS</span>
          <table>
            <tbody>
              <tr className="allow"><td><code>refund_order</code><small>ORD-1001 · Lost order</small></td><td>₹799</td><td><span className="p allow">ALLOW</span></td></tr>
              <tr className="approval"><td><code>refund_order</code><small>ORD-1002 · Lost order</small></td><td>₹8,499</td><td><span className="p approval">REQUIRE APPROVAL</span></td></tr>
              <tr className="deny"><td><code>export_customers</code><small>Customer database · Restricted</small></td><td>—</td><td><span className="p deny">DENY</span></td></tr>
            </tbody>
          </table>
          <div className="shot-eval">
            <span className="shot-micro">POLICY EVALUATION</span>
            <pre>
              <span className="k">can_execute</span>          <span className="f">false</span>{'\n'}
              <span className="k">can_request_approval</span> <span className="t">true</span>{'\n'}
              <span className="c">↳ pause before tool execution</span>
            </pre>
          </div>
        </div>

        <div className="shot-side">
          <span className="shot-micro flag">HUMAN DECISION REQUIRED</span>
          <span className="shot-kind">Refund request</span>
          <strong className="shot-amount">₹8,499</strong>
          <code>refund_order / ORD-1002</code>
          <dl>
            <div><dt>Autonomous limit</dt><dd>₹2,000</dd></div>
            <div><dt>Approval limit</dt><dd>₹10,000</dd></div>
            <div><dt>Execution status</dt><dd>PAUSED</dd></div>
          </dl>
          <span className="shot-micro">WHY IT STOPPED</span>
          <p>Above the autonomous refund limit. A human must authorize this exact call.</p>
          <div className="shot-actions"><span className="ghost">Deny</span><span className="solid">Approve →</span></div>
        </div>
      </div>
    </div>
  )
}

export default function Landing() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="site">
      <a className="skip-link" href="#product">Skip to content</a>

      <header className={`site-nav ${scrolled ? 'scrolled' : ''}`}>
        <a className="site-brand" href="#top"><span className="site-mark"><GateMark /></span>AgentGate</a>
        <nav aria-label="Sections">
          {nav.map((item) => <a key={item.href} href={item.href}>{item.label}</a>)}
        </nav>
        <a className="cta-dark" href="#/control">Explore the demo</a>
      </header>

      <section className="hero" id="top">
        <div className="sky" aria-hidden="true">
          <span className="grid" />
          <span className="cloud c1" /><span className="cloud c2" /><span className="cloud c3" /><span className="cloud c4" />
          <span className="mark m1">+</span><span className="mark m2">+</span>
          <Pixels tone="grey" className="p1" />
          <Pixels tone="grey" className="p2" />
          <Pixels tone="violet" className="p3" />
        </div>

        <div className="hero-copy">
          <span className="bracket">Deterministic agent control</span>
          <h1>Let agents act.<br />Keep authority.</h1>
          <p>Let AI agents act without giving them unlimited authority. AgentGate checks tool calls against Cedar policies before execution.</p>
          <div className="hero-cta">
            <a className="cta-dark" href="#/control">Explore the demo</a>
            <a className="cta-light" href="#how">How it works</a>
          </div>
        </div>

        <div className="hero-console"><ConsolePanel /></div>
      </section>

      <section className="band" id="product">
        <div className="band-head">
          <span className="bracket">The problem</span>
          <h2>The model decides what it wants.<br />Cedar decides what it may.</h2>
          <p>Agents call tools that refund money, message customers and export data. AgentGate separates reasoning from authority, so a convincing argument is never the thing that unlocks an action.</p>
        </div>
        <div className="triple">
          <article><span className="bracket">Before execution</span><h3>Intercepted, not audited</h3><p>Every mutating call is evaluated before it runs. A denial leaves business state byte-for-byte unchanged.</p></article>
          <article><span className="bracket">Outside the prompt</span><h3>Limits live in policy files</h3><p>Empty the policy files and every allow becomes a deny. Nothing is hiding in application code.</p></article>
          <article><span className="bracket">Exactly once</span><h3>One approval, one action</h3><p>An approval is bound to the exact arguments by digest. Duplicates, replays and resets authorize nothing.</p></article>
        </div>
      </section>

      <section className="band tinted" id="scenarios">
        <div className="band-head">
          <span className="bracket">Demo scenarios</span>
          <h2>Three outcomes, one agent.</h2>
          <p>The same tool and the same agent. Only the amount changes — and the amount is what policy reads.</p>
        </div>
        <div className="triple cards">
          {scenarios.map((item) => (
            <article key={item.id} className={`scenario-card ${item.tone}`}>
              <header><span className="bracket">Scenario {item.id}</span><span className={`p ${item.tone}`}>{item.decision}</span></header>
              <strong className="scenario-amount">{item.amount}</strong>
              <code>{item.order}</code>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="band" id="how">
        <div className="band-head">
          <span className="bracket">How it works</span>
          <h2>A policy check between<br />intent and execution.</h2>
          <p>The agent proposes a tool call. Cedar evaluates it. AgentGate routes the decision before the business tool runs.</p>
        </div>
        <div className="steps">
          <div className="step-list">
            {steps.map((step, index) => (
              <article key={step.n} className={index === 0 ? 'on' : ''}>
                <span className="step-tag">{step.n}</span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </article>
            ))}
          </div>
          <div className="step-visual"><ConsolePanel /></div>
        </div>
      </section>

      <section className="band tinted" id="limits">
        <div className="band-head">
          <span className="bracket">Policy boundaries</span>
          <h2>Make authority explicit.</h2>
          <p>Concrete limits for the support-agent demo.<br />The language model never decides these boundaries.</p>
        </div>

        <div className="limits-grid">
          <article className="limits-lead">
            <span className="site-brand small"><span className="site-mark"><GateMark /></span>AGENTGATE</span>
            <div>
              <h3>Authority outside the model</h3>
              <p>The same principal, action, resource and context produce the same Cedar authorization result.</p>
              <p className="italic">A deterministic check before consequential actions.</p>
              <a className="cta-dark" href="#/control">Explore the demo</a>
            </div>
          </article>

          <div className="limits-right">
            <article className="limits-top">
              <Pixels tone="violet" />
              <div>
                <h3>Three-way authorization</h3>
                <p className="italic">Authorize execution first. If disallowed, check whether human approval may be requested.</p>
              </div>
            </article>
            <div className="limits-pair">
              <article>
                <span className="limit-label">AUTONOMOUS REFUND LIMIT</span>
                <strong>₹2,000</strong>
                <p>Refunds up to ₹2,000 can execute automatically under the demo policy.</p>
              </article>
              <article>
                <span className="limit-label">HUMAN APPROVAL LIMIT</span>
                <strong>₹10,000</strong>
                <p>Above ₹2,000 and up to ₹10,000, pause for human approval. Higher refunds are denied.</p>
              </article>
            </div>
            <article className="limits-deny">
              <h3>Denied means no execution</h3>
              <p className="italic">Customer exports are blocked. Read-only lookups are allowed.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="band closing" id="about">
        <div className="sky closing-sky" aria-hidden="true">
          <span className="grid" />
          <Pixels tone="green" className="p4" />
          <Pixels tone="violet" className="p5" />
          <Pixels tone="amber" className="p6" />
        </div>
        <div className="band-head">
          <span className="bracket">Reason freely. Act within policy.</span>
          <h2>Keep reasoning flexible.<br />Keep authority deterministic.</h2>
          <p>Explore a support agent whose actions are checked before execution.<br />Built for First Commit — Bharat Builds Tour 2026.</p>
          <div className="hero-cta">
            <a className="cta-dark" href="#/control">Explore the demo</a>
            <a className="cta-light" href="#how">How it works</a>
          </div>
        </div>
      </section>

      <footer className="site-foot">
        <div className="foot-top">
          <div>
            <span className="site-brand"><span className="site-mark"><GateMark /></span>AgentGate</span>
            <p>Let AI agents act without giving them unlimited authority. A prototype for deterministic authorization with Cedar.</p>
          </div>
          <div className="foot-cta">
            <span className="bracket">Explore the prototype</span>
            <a href="#/control">See the demo scenarios</a>
          </div>
        </div>
        <div className="foot-links">
          <div><span className="bracket">Resources</span><a href="#limits">Policy limits</a><a href="#scenarios">Demo scenarios</a><a href="#how">How it works</a></div>
          <div><span className="bracket">Navigation</span><a href="#product">Product</a><a href="#about">About</a><a href="#/control">Control room</a></div>
        </div>
        <div className="foot-base">
          <span>© 2026 AgentGate · Hackathon prototype</span>
          <span>Cedar · Strands · FastAPI · React</span>
        </div>
      </footer>
    </div>
  )
}
