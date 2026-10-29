import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import type { AuditEvent, DecisionType, Task } from '../api/types'
import { ActionCard } from '../components/ActionCard'
import { AuditTimeline } from '../components/AuditTimeline'
import { Badge, Button, Card, ErrorBanner, Notice, Spinner } from '../components/ui'
import { BASIS, DECISION_LABEL, FAILURE_HELP, TASK_STATUS, formatTime } from '../lib/labels'
import { currentReviewer } from '../lib/reviewer'

const LIFECYCLE = ['CREATED', 'PLANNING', 'AWAITING_REVIEW', 'RUNNING', 'COMPLETED'] as const

function Lifecycle({ task }: { task: Task }) {
  const terminalOther = task.status === 'FAILED' || task.status === 'CANCELLED'
  const current = LIFECYCLE.indexOf(task.status as (typeof LIFECYCLE)[number])
  return (
    <ol className="flex flex-wrap items-center gap-1 text-xs" aria-label="Task lifecycle">
      {LIFECYCLE.map((state, i) => {
        const active = state === task.status
        const done = !terminalOther && current > i
        return (
          <li key={state} className="flex items-center gap-1">
            <span
              aria-current={active ? 'step' : undefined}
              className={`rounded px-2 py-1 ${active ? 'bg-blue-800 font-semibold text-white' : done ? 'bg-blue-100 text-blue-900' : 'bg-slate-100 text-slate-500'}`}
            >
              {TASK_STATUS[state].label}
            </span>
            {i < LIFECYCLE.length - 1 && <span aria-hidden className="text-slate-400">›</span>}
          </li>
        )
      })}
      {terminalOther && (
        <li className="ml-2">
          <Badge tone={TASK_STATUS[task.status].tone}>{TASK_STATUS[task.status].label}</Badge>
        </li>
      )}
    </ol>
  )
}

function FeedbackForm({
  busy,
  onSubmit,
}: {
  busy: boolean
  onSubmit: (decision: DecisionType, message: string) => void
}) {
  const [kind, setKind] = useState<'REQUEST_REVISION' | 'REQUEST_CLARIFICATION'>('REQUEST_REVISION')
  const [message, setMessage] = useState('')
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (message.trim()) onSubmit(kind, message.trim())
      }}
    >
      <fieldset className="flex flex-wrap gap-4 text-sm">
        <legend className="sr-only">Feedback type</legend>
        <label className="flex items-center gap-2">
          <input type="radio" checked={kind === 'REQUEST_REVISION'} onChange={() => setKind('REQUEST_REVISION')} />
          Request revision
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" checked={kind === 'REQUEST_CLARIFICATION'} onChange={() => setKind('REQUEST_CLARIFICATION')} />
          Answer or ask (clarification)
        </label>
      </fieldset>
      <label htmlFor="feedback" className="sr-only">Message to the agent</label>
      <textarea
        id="feedback"
        rows={2}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder={kind === 'REQUEST_REVISION' ? 'What should change in the plan?' : 'Answer the agent’s question, e.g. “Use #billing-team”'}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      />
      <Button type="submit" disabled={busy || !message.trim()}>Send and re-plan</Button>
      <p className="text-xs text-slate-600">The current plan is superseded and the agent plans again. Earlier decisions stay in the history.</p>
    </form>
  )
}

export function TaskDetailPage() {
  const { taskId = '' } = useParams()
  const [task, setTask] = useState<Task | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loadError, setLoadError] = useState<unknown>(null)
  const [actionError, setActionError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(() => {
    Promise.all([api.getTask(taskId), api.events(taskId)])
      .then(([t, e]) => {
        setTask(t)
        setEvents(e)
        setLoadError(null)
      })
      .catch(setLoadError)
  }, [taskId])
  useEffect(load, [load])

  async function run(label: string, fn: () => Promise<Task>) {
    setBusy(true)
    setActionError(null)
    setMessage(null)
    try {
      const updated = await fn()
      setTask(updated)
      setMessage(`${label}. Task status: ${TASK_STATUS[updated.status].label}.`)
      setEvents(await api.events(taskId))
    } catch (err) {
      setActionError(err)
      // The server state may have changed (e.g. a concurrent decision); show what it actually is.
      if (err instanceof ApiError && err.status === 409) load()
    } finally {
      setBusy(false)
    }
  }

  const review = (decision: DecisionType, extra: { action_id?: string; rationale?: string } = {}) =>
    api.review(taskId, { decision, reviewer: currentReviewer(), ...extra })

  if (loadError) {
    const notFound = loadError instanceof ApiError && (loadError.status === 404 || loadError.status === 422)
    return (
      <div className="space-y-3">
        <ErrorBanner error={notFound ? new Error('This task does not exist.') : loadError} onRetry={notFound ? undefined : load} />
        <Link to="/" className="text-sm text-blue-800 underline">Back to tasks</Link>
      </div>
    )
  }
  if (!task) return <Spinner label="Loading task…" />

  const ops = new Set(task.available_operations)
  const run_ = task.current_run
  const structured = task.review_mode === 'STRUCTURED'
  const baselineReview = !structured && task.status === 'AWAITING_REVIEW'
  const pendingCount = run_?.actions.filter((a) => a.review_state === 'PENDING').length ?? 0

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-blue-800 underline underline-offset-2">← All tasks</Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold">{task.title}</h1>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{task.description}</p>
            <p className="mt-1 text-xs text-slate-500">
              {structured ? 'Structured review' : 'Baseline review (approve or stop)'} · created {formatTime(task.created_at)}
            </p>
          </div>
          <Badge tone={TASK_STATUS[task.status].tone}>{TASK_STATUS[task.status].label}</Badge>
        </div>
        <div className="mt-3"><Lifecycle task={task} /></div>
      </div>

      <div aria-live="polite" className="space-y-2">
        {message && <Notice tone="success">{message}</Notice>}
        <ErrorBanner error={actionError} />
      </div>

      {task.status === 'FAILED' && (
        <Notice tone="danger">
          <p className="font-medium">Failed during {task.failure_stage?.toLowerCase()}: {task.failure_reason}</p>
          {task.failure_stage && <p className="mt-1">{FAILURE_HELP[task.failure_stage]}</p>}
        </Notice>
      )}

      {/* ---------------------------------------------------------------- next steps */}
      {(ops.size > 0 || task.status === 'PLANNING' || task.status === 'RUNNING') && (
        <Card title="Next step">
          <div className="space-y-4">
            {ops.has('plan') && (
              <Button variant="primary" disabled={busy} onClick={() => run('Plan generated', () => api.plan(taskId))}>
                Generate plan
              </Button>
            )}
            {ops.has('retry_planning') && (
              <Button variant="primary" disabled={busy} onClick={() => run('Planning retried', () => api.retryPlanning(taskId))}>
                Retry planning
              </Button>
            )}
            {(task.status === 'PLANNING' || task.status === 'RUNNING') && (
              <div className="flex items-center gap-3">
                <Spinner label={`Task is ${TASK_STATUS[task.status].label.toLowerCase()}…`} />
                <Button onClick={load}>Refresh</Button>
              </div>
            )}

            {baselineReview && (
              <div className="space-y-2">
                <p className="text-sm text-slate-700">
                  Baseline mode: approve the whole plan to run it, or stop the task. Assumptions and per-action risk are not shown in this mode.
                </p>
                <div className="flex flex-wrap gap-2">
                  {ops.has('approve_plan') && (
                    <Button variant="success" disabled={busy} onClick={() => run('Plan approved', () => review('APPROVE'))}>
                      Approve and run plan
                    </Button>
                  )}
                  {ops.has('reject_plan') && (
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={() => run('Task stopped', () => review('REJECT', { rationale: 'Stopped by reviewer' }))}
                    >
                      Stop task
                    </Button>
                  )}
                </div>
              </div>
            )}

            {structured && task.status === 'AWAITING_REVIEW' && (
              <>
                {run_?.open_questions.length ? (
                  <Notice tone="warning">
                    <p className="font-medium">The agent needs information before anything can run:</p>
                    <ul className="mt-1 list-disc pl-5">
                      {run_.open_questions.map((q) => <li key={q}>{q}</li>)}
                    </ul>
                    <p className="mt-1">Answer with “clarification” below. Approval is unavailable until then.</p>
                  </Notice>
                ) : pendingCount > 0 ? (
                  <p className="text-sm text-slate-700">
                    {pendingCount} action{pendingCount > 1 ? 's need' : ' needs'} a decision. Review each one below, then run the plan.
                  </p>
                ) : null}
                {ops.has('execute') ? (
                  <div className="flex flex-wrap items-center gap-3">
                    <Button variant="primary" disabled={busy} onClick={() => run('Execution finished', () => api.execute(taskId))}>
                      Run approved actions
                    </Button>
                    <span className="text-xs text-slate-600">The backend authorizes each action again immediately before it runs.</span>
                  </div>
                ) : (
                  pendingCount === 0 && !run_?.open_questions.length && (
                    <p className="text-sm text-slate-700">Nothing in this plan can run. Request a revision or cancel the task.</p>
                  )
                )}
                {(ops.has('request_revision') || ops.has('request_clarification')) && (
                  <FeedbackForm busy={busy} onSubmit={(decision, text) => run('Feedback sent', () => review(decision, { rationale: text }))} />
                )}
              </>
            )}

            {ops.has('cancel') && (
              <div>
                <Button variant="danger" disabled={busy} onClick={() => run('Task cancelled', () => api.cancel(taskId, 'Cancelled from the UI'))}>
                  Cancel task
                </Button>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ---------------------------------------------------------------- plan */}
      {run_ && (
        <Card
          title={`Plan, attempt ${run_.attempt_number}`}
          actions={<span className="text-xs text-slate-500">planner: {run_.planner}</span>}
        >
          {run_.status === 'FAILED' ? (
            <p className="text-sm text-red-800">This planning attempt failed: {run_.error}</p>
          ) : (
            <div className="space-y-4">
              {run_.reviewer_input && (
                <Notice tone="info">This plan was produced after reviewer input: “{run_.reviewer_input}”</Notice>
              )}
              <p className="text-sm">{run_.summary}</p>
              <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-800">
                {run_.steps.map((step, i) => <li key={i}>{step}</li>)}
              </ol>

              {structured && run_.assumptions.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold">Assumptions</h3>
                  <ul className="mt-2 space-y-2">
                    {run_.assumptions.map((a) => (
                      <li key={a.id} className="rounded-md border border-slate-200 p-3 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-slate-500">{a.key}</span>
                          <Badge tone={BASIS[a.basis].tone} title={BASIS[a.basis].help}>{BASIS[a.basis].label}</Badge>
                        </div>
                        <p className="mt-1">{a.statement}</p>
                        {a.evidence && <p className="mt-1 text-slate-600">Evidence: {a.evidence}</p>}
                        <p className="mt-1 text-slate-600">If wrong: {a.consequence_if_wrong}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h3 className="text-sm font-semibold">Proposed actions</h3>
                {baselineReview ? (
                  <p className="mt-1 text-sm text-slate-600">
                    {run_.actions.length} action(s). Per-action details appear after the plan is approved or stopped.
                  </p>
                ) : (
                  <div className="mt-2 space-y-3">
                    {run_.actions.map((action) => (
                      <ActionCard
                        key={action.id}
                        action={action}
                        showRisk={structured}
                        canApprove={structured && ops.has('approve_action')}
                        canReject={structured && ops.has('reject_action')}
                        busy={busy}
                        onApprove={() => run('Action approved', () => review('APPROVE', { action_id: action.id }))}
                        onReject={(rationale) => run('Action rejected', () => review('REJECT', { action_id: action.id, rationale }))}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* ---------------------------------------------------------------- history */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Review decisions">
          {task.decisions.length === 0 ? (
            <p className="text-sm text-slate-600">No decisions recorded.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {task.decisions.map((d) => {
                const attempt = task.runs.find((r) => r.id === d.agent_run_id)?.attempt_number
                return (
                  <li key={d.id} className="rounded-md border border-slate-200 p-2">
                    <span className="font-medium">{DECISION_LABEL[d.decision]}</span>{' '}
                    <span className="text-slate-600">
                      {d.action_id ? 'an action' : 'the plan'} in attempt {attempt} by {d.reviewer}
                    </span>
                    {d.rationale && <p className="text-slate-700">“{d.rationale}”</p>}
                    <time className="text-xs text-slate-500" dateTime={d.created_at}>{formatTime(d.created_at)}</time>
                  </li>
                )
              })}
            </ul>
          )}
          {task.runs.length > 1 && (
            <p className="mt-3 text-xs text-slate-600">
              Planning attempts: {task.runs.map((r) => `#${r.attempt_number} ${r.trigger.toLowerCase()} (${r.status.toLowerCase()})`).join(', ')}
            </p>
          )}
        </Card>
        <Card title="Audit trail">
          <AuditTimeline events={events} />
        </Card>
      </div>
    </div>
  )
}
