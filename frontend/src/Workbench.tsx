import {
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import {
  activatePolicy,
  apiBase,
  apiDocsUrl,
  createPolicy,
  draftPolicy,
  evaluateAction,
  fetchPolicies,
  type EvaluationRequest,
  type EvaluationResponse,
  type PolicyDefinition,
  type PolicyDraft,
} from './api'


type PolicyForm =
  Omit<
    PolicyDefinition,
    'id' | 'active'
  >


const blankPolicy: PolicyForm = {
  name: '',
  principal_type: 'Agent',
  principal_id: 'support-agent',
  action: 'refund_order',
  resource_type: 'Order',
  decision: 'ALLOW',
  context_field: 'amount',
  allow_threshold: 2000,
  approval_threshold: 10000,
}


type PlaygroundPreset = {
  name: string
  payload: EvaluationRequest
}


const presets: PlaygroundPreset[] = [
  {
    name: 'Support refund ₹8,499',
    payload: {
      principal: {
        type: 'Agent',
        id: 'support-agent',
      },
      action: 'refund_order',
      resource: {
        type: 'Order',
        id: 'ORD-1',
      },
      context: {
        amount: 8499,
      },
    },
  },
  {
    name: 'Finance refund ₹8,499',
    payload: {
      principal: {
        type: 'Agent',
        id: 'finance-agent',
      },
      action: 'refund_order',
      resource: {
        type: 'Order',
        id: 'ORD-1',
      },
      context: {
        amount: 8499,
      },
    },
  },
  {
    name: 'Production deployment',
    payload: {
      principal: {
        type: 'Agent',
        id: 'deployment-agent',
      },
      action: 'deploy_production',
      resource: {
        type: 'Environment',
        id: 'production',
      },
      context: {},
    },
  },
  {
    name: 'Destructive production action',
    payload: {
      principal: {
        type: 'Agent',
        id: 'deployment-agent',
      },
      action: 'delete_production_database',
      resource: {
        type: 'Database',
        id: 'production',
      },
      context: {},
    },
  },
  {
    name: 'Unknown agent',
    payload: {
      principal: {
        type: 'Agent',
        id: 'unknown-agent',
      },
      action: 'lookup_order',
      resource: {
        type: 'Order',
        id: 'ORD-1',
      },
      context: {
        order_id: 'ORD-1',
      },
    },
  },
]


function Section({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="workbench-section">
      <div className="workbench-title">
        <span className="micro">
          {title}
        </span>
      </div>

      {children}
    </section>
  )
}


export function Playground() {
  const [
    payload,
    setPayload,
  ] = useState<EvaluationRequest>(
    presets[0].payload,
  )

  const [
    contextText,
    setContextText,
  ] = useState(
    JSON.stringify(
      presets[0].payload.context,
      null,
      2,
    ),
  )

  const [
    result,
    setResult,
  ] = useState<EvaluationResponse | null>(
    null,
  )

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  )

  const [
    busy,
    setBusy,
  ] = useState(false)


  const choose = (
    index: number,
  ) => {
    const next =
      presets[index].payload

    setPayload(next)

    setContextText(
      JSON.stringify(
        next.context,
        null,
        2,
      ),
    )

    setResult(null)
    setError(null)
  }


  const evaluate =
    async () => {
      setBusy(true)
      setError(null)
      setResult(null)

      try {
        const parsed: unknown =
          JSON.parse(
            contextText,
          )

        if (
          parsed === null ||
          typeof parsed !== 'object' ||
          Array.isArray(parsed)
        ) {
          throw new Error(
            'Context JSON must be an object.',
          )
        }

        const response =
          await evaluateAction({
            ...payload,
            context:
              parsed as Record<
                string,
                unknown
              >,
          })

        setResult(response)
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught.message
            : 'Evaluation failed.',
        )
      } finally {
        setBusy(false)
      }
    }


  return (
    <Section title="Policy playground">
      <p className="workbench-copy">
        Ask the live Cedar-backed gate about any
        principal, action, resource, and context.
      </p>


      <div className="preset-row">
        {presets.map(
          (
            preset,
            index,
          ) => (
            <button
              key={preset.name}
              className="btn-ghost"
              onClick={() =>
                choose(index)
              }
            >
              {preset.name}
            </button>
          ),
        )}
      </div>


      <div className="field-grid">
        <label>
          Principal type

          <input
            value={
              payload.principal.type
            }
            readOnly
          />
        </label>


        <label>
          Principal id

          <input
            value={
              payload.principal.id
            }

            onChange={
              (event) =>
                setPayload({
                  ...payload,
                  principal: {
                    ...payload.principal,
                    id:
                      event.target.value,
                  },
                })
            }
          />
        </label>


        <label>
          Action

          <input
            value={
              payload.action
            }

            onChange={
              (event) =>
                setPayload({
                  ...payload,
                  action:
                    event.target.value,
                })
            }
          />
        </label>


        <label>
          Resource type

          <input
            value={
              payload.resource.type
            }

            onChange={
              (event) =>
                setPayload({
                  ...payload,
                  resource: {
                    ...payload.resource,
                    type:
                      event.target.value,
                  },
                })
            }
          />
        </label>


        <label>
          Resource id

          <input
            value={
              payload.resource.id
            }

            onChange={
              (event) =>
                setPayload({
                  ...payload,
                  resource: {
                    ...payload.resource,
                    id:
                      event.target.value,
                  },
                })
            }
          />
        </label>


        <label className="field-wide">
          Context JSON

          <textarea
            rows={4}
            value={contextText}
            onChange={
              (event) =>
                setContextText(
                  event.target.value,
                )
            }
          />
        </label>
      </div>


      <button
        className="btn-solid"
        onClick={() =>
          void evaluate()
        }
        disabled={busy}
      >
        {busy
          ? 'Evaluating…'
          : 'Evaluate'}
      </button>


      {error && (
        <div
          className="banner-error"
          role="alert"
        >
          {error}
        </div>
      )}


      {result && (
        <div
          className={
            `playground-result ${
              result.decision.toLowerCase()
            }`
          }
        >
          <strong>
            {result.decision}
          </strong>

          <dl>
            <div>
              <dt>
                Matched policy
              </dt>

              <dd>
                {result.matched_policy ??
                  'None'}
              </dd>
            </div>

            <div>
              <dt>
                Reason
              </dt>

              <dd>
                {result.reason}
              </dd>
            </div>

            <div>
              <dt>
                Reason code
              </dt>

              <dd>
                {result.reason_code}
              </dd>
            </div>

            <div>
              <dt>
                Principal
              </dt>

              <dd>
                {result.principal}
              </dd>
            </div>

            <div>
              <dt>
                Action
              </dt>

              <dd>
                {result.action}
              </dd>
            </div>

            <div>
              <dt>
                Context
              </dt>

              <dd>
                <code>
                  {contextText}
                </code>
              </dd>
            </div>
          </dl>
        </div>
      )}
    </Section>
  )
}


export function PolicyStudio() {
  const [
    form,
    setForm,
  ] = useState<PolicyForm>(
    blankPolicy,
  )

  const [
    description,
    setDescription,
  ] = useState(
    'Support agents may refund up to ₹2,000 automatically. Between ₹2,000 and ₹10,000 ask me for approval. Deny anything higher.',
  )

  const [
    draft,
    setDraft,
  ] = useState<PolicyDraft | null>(
    null,
  )

  const [
    policies,
    setPolicies,
  ] = useState<
    PolicyDefinition[]
  >([])

  const [
    message,
    setMessage,
  ] = useState<string | null>(
    null,
  )

  const [
    busy,
    setBusy,
  ] = useState(false)


  const refresh =
    async () => {
      const items =
        await fetchPolicies()

      setPolicies(items)
    }


  useEffect(() => {
    void refresh().catch(
      () => undefined,
    )
  }, [])


  const update = <
    K extends keyof PolicyForm,
  >(
    key: K,
    value: PolicyForm[K],
  ) => {
    setForm({
      ...form,
      [key]: value,
    })
  }


  const save =
    async () => {
      setBusy(true)
      setMessage(null)

      try {
        await createPolicy(form)

        setMessage(
          'Draft saved. Activate it when you are ready.',
        )

        await refresh()
      } catch (caught) {
        setMessage(
          caught instanceof Error
            ? caught.message
            : 'Could not save policy.',
        )
      } finally {
        setBusy(false)
      }
    }


  const generate =
    async () => {
      setBusy(true)
      setMessage(null)

      try {
        const generated =
          await draftPolicy(
            description,
          )

        setDraft(generated)
      } catch (caught) {
        setMessage(
          caught instanceof Error
            ? caught.message
            : 'Could not generate draft.',
        )
      } finally {
        setBusy(false)
      }
    }


  const activateDraft =
    async () => {
      if (!draft) {
        return
      }

      setBusy(true)
      setMessage(null)

      try {
        const definition = {
          name:
            draft.draft.name,

          principal_type:
            draft.draft
              .principal_type,

          principal_id:
            draft.draft
              .principal_id,

          action:
            draft.draft.action,

          resource_type:
            draft.draft
              .resource_type,

          decision:
            draft.draft
              .decision,

          context_field:
            draft.draft
              .context_field,

          allow_threshold:
            draft.draft
              .allow_threshold,

          approval_threshold:
            draft.draft
              .approval_threshold,
        }

        const created =
          await createPolicy(
            definition,
          )

        await activatePolicy(
          created.id,
        )

        setMessage(
          'Human activation complete. Cedar is now evaluating this policy.',
        )

        setDraft(null)

        await refresh()
      } catch (caught) {
        setMessage(
          caught instanceof Error
            ? caught.message
            : 'Activation failed.',
        )
      } finally {
        setBusy(false)
      }
    }


  const activate =
    async (
      policy:
        PolicyDefinition,
    ) => {
      setBusy(true)
      setMessage(null)

      try {
        await activatePolicy(
          policy.id,
        )

        setMessage(
          `${policy.name} is active.`,
        )

        await refresh()
      } catch (caught) {
        setMessage(
          caught instanceof Error
            ? caught.message
            : 'Activation failed.',
        )
      } finally {
        setBusy(false)
      }
    }


  return (
    <Section title="Policy studio">
      <p className="workbench-copy">
        Create a policy, preview its Cedar
        representation, and explicitly activate it.
      </p>


      <div className="studio-columns">
        <div className="studio-pane">
          <h2>
            Describe your policy
          </h2>

          <textarea
            rows={5}
            value={description}
            onChange={
              (event) =>
                setDescription(
                  event.target.value,
                )
            }
          />

          <button
            className="btn-solid"
            onClick={() =>
              void generate()
            }
            disabled={busy}
          >
            {busy
              ? 'Working…'
              : 'Generate structured draft'}
          </button>


          {draft && (
            <div className="draft-preview">
              <strong>
                Draft preview · not active
              </strong>

              <pre>
                {JSON.stringify(
                  draft.draft,
                  null,
                  2,
                )}
              </pre>

              <pre>
                {draft.cedar_preview}
              </pre>

              <button
                className="btn-solid"
                onClick={() =>
                  void activateDraft()
                }
                disabled={busy}
              >
                Activate draft
              </button>
            </div>
          )}
        </div>


        <div className="studio-pane">
          <h2>
            Build directly
          </h2>

          <div className="field-grid">
            <label>
              Policy name

              <input
                value={form.name}
                onChange={
                  (event) =>
                    update(
                      'name',
                      event.target.value,
                    )
                }
              />
            </label>


            <label>
              Principal type

              <input
                value={
                  form.principal_type
                }
                readOnly
              />
            </label>


            <label>
              Principal id

              <input
                value={
                  form.principal_id
                }
                onChange={
                  (event) =>
                    update(
                      'principal_id',
                      event.target.value,
                    )
                }
              />
            </label>


            <label>
              Action

              <input
                value={form.action}
                onChange={
                  (event) =>
                    update(
                      'action',
                      event.target.value,
                    )
                }
              />
            </label>


            <label>
              Resource type

              <input
                value={
                  form.resource_type
                }
                onChange={
                  (event) =>
                    update(
                      'resource_type',
                      event.target.value,
                    )
                }
              />
            </label>


            <label>
              Decision

              <select
                value={form.decision}
                onChange={
                  (event) =>
                    update(
                      'decision',
                      event.target.value as
                        PolicyForm['decision'],
                    )
                }
              >
                <option value="ALLOW">
                  ALLOW
                </option>

                <option value="REQUIRE_APPROVAL">
                  REQUIRE_APPROVAL
                </option>

                <option value="DENY">
                  DENY
                </option>
              </select>
            </label>


            <label>
              Context field

              <input
                value={
                  form.context_field ??
                  ''
                }
                onChange={
                  (event) =>
                    update(
                      'context_field',
                      event.target.value ||
                        null,
                    )
                }
              />
            </label>


            <label>
              ALLOW threshold

              <input
                type="number"
                min="0"
                value={
                  form.allow_threshold ??
                  ''
                }
                onChange={
                  (event) =>
                    update(
                      'allow_threshold',
                      event.target.value
                        ? Number(
                            event.target.value,
                          )
                        : null,
                    )
                }
              />
            </label>


            <label>
              APPROVAL threshold

              <input
                type="number"
                min="0"
                value={
                  form.approval_threshold ??
                  ''
                }
                onChange={
                  (event) =>
                    update(
                      'approval_threshold',
                      event.target.value
                        ? Number(
                            event.target.value,
                          )
                        : null,
                    )
                }
              />
            </label>
          </div>


          <button
            className="btn-solid"
            onClick={() =>
              void save()
            }
            disabled={busy}
          >
            Save policy draft
          </button>
        </div>
      </div>


      {message && (
        <div
          className="banner-info"
          role="status"
        >
          {message}
        </div>
      )}


      <div className="policy-list">
        <span className="micro">
          PERSISTED POLICIES
        </span>

        {policies.length === 0 ? (
          <p>
            No Studio policies yet.
          </p>
        ) : (
          policies.map(
            (policy) => (
              <div
                key={policy.id}
                className="policy-row"
              >
                <div>
                  <strong>
                    {policy.name}
                  </strong>

                  <small>
                    {policy.principal_id}
                    {' · '}
                    {policy.action}
                    {' · '}
                    {policy.decision}
                  </small>
                </div>

                {policy.active ? (
                  <span className="pill allow">
                    ACTIVE
                  </span>
                ) : (
                  <button
                    className="btn-ghost"
                    onClick={() =>
                      void activate(
                        policy,
                      )
                    }
                    disabled={busy}
                  >
                    Activate
                  </button>
                )}
              </div>
            ),
          )
        )}
      </div>
    </Section>
  )
}


export function Integrate() {
  const base =
    `${window.location.origin}${apiBase}`

  const example =
    JSON.stringify(
      {
        principal: {
          type: 'Agent',
          id: 'support-agent',
        },

        action:
          'refund_order',

        resource: {
          type: 'Order',
          id: 'ORD-1',
        },

        context: {
          amount: 8499,
        },
      },
      null,
      2,
    )


  return (
    <Section title="Integrate">
      <p className="workbench-copy">
        Any application can call the same authorization
        endpoint used by AgentGate's Playground.
      </p>


      <div className="integration-grid">
        <pre>
          <span>
            curl
          </span>

          {`
curl -X POST ${base}/gate/evaluate \\
  -H 'Content-Type: application/json' \\
  -d '${example.replaceAll(
    "'",
    "\\'",
  )}'`}
        </pre>


        <pre>
          <span>
            Python
          </span>

          {`
import requests

response = requests.post(
    "${base}/gate/evaluate",
    json=${example}
)

print(response.json())`}
        </pre>


        <pre>
          <span>
            JavaScript
          </span>

          {`
const response = await fetch(
  "${base}/gate/evaluate",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(${example})
  }
);

console.log(
  await response.json()
);`}
        </pre>
      </div>


      <a
        className="btn-link"
        href={apiDocsUrl}
        target="_blank"
        rel="noreferrer"
      >
        Open FastAPI docs
      </a>
    </Section>
  )
}