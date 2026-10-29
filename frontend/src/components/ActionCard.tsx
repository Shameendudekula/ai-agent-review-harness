import { useState } from 'react'

import type { ProposedAction } from '../api/types'
import { useReasonText } from '../lib/catalog'
import { AUTHORIZATION, EXECUTION, REVIEW, RISK, VERIFICATION } from '../lib/labels'
import { Badge, Button, JsonBlock } from './ui'

interface Props {
  action: ProposedAction
  showRisk: boolean
  canApprove: boolean
  canReject: boolean
  busy: boolean
  onApprove: () => void
  onReject: (rationale: string) => void
}

function Stage({ name, label, tone }: { name: string; label: string; tone: Parameters<typeof Badge>[0]['tone'] }) {
  return (
    <li className="flex flex-col gap-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{name}</span>
      <Badge tone={tone}>{label}</Badge>
    </li>
  )
}

export function ActionCard({ action, showRisk, canApprove, canReject, busy, onApprove, onReject }: Props) {
  const reasonText = useReasonText()
  const [rejecting, setRejecting] = useState(false)
  const [rationale, setRationale] = useState('')
  const pending = action.review_state === 'PENDING'
  const risk = RISK[action.risk_level]
  const agentUnderestimated = action.agent_risk_estimate !== action.risk_level

  return (
    <article
      aria-labelledby={`action-${action.id}`}
      className={`rounded-lg border bg-white p-4 ${pending ? 'border-amber-400 ring-1 ring-amber-200' : 'border-slate-200'}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-slate-500">Step {action.sequence}</p>
          <h3 id={`action-${action.id}`} className="font-semibold text-slate-900">{action.description}</h3>
          <p className="mt-0.5 font-mono text-xs text-slate-600">{action.tool_name}</p>
        </div>
        {showRisk && <Badge tone={risk.tone}>{risk.label}</Badge>}
      </header>

      <ol className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Action progress">
        <Stage name="Review" {...REVIEW[action.review_state]} />
        <Stage name="Authorization" {...AUTHORIZATION[action.authorization_state]} />
        <Stage name="Execution" {...EXECUTION[action.execution_state]} />
        <Stage name="Verification" {...VERIFICATION[action.verification_state]} />
      </ol>

      {showRisk && (
        <div className="mt-3 text-sm">
          <p className="font-medium text-slate-800">
            {action.review_state === 'BLOCKED'
              ? 'Why it is blocked'
              : action.review_required
                ? 'Why it needs review'
                : 'Why no review is needed'}
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-700">
            {action.review_reasons.map((reason) => (
              <li key={reason}>{reasonText(reason)}</li>
            ))}
          </ul>
          {agentUnderestimated && (
            <p className="mt-1 text-xs text-slate-600">
              The agent rated this action {RISK[action.agent_risk_estimate].label.toLowerCase()}. The policy uses its own assessment.
            </p>
          )}
        </div>
      )}

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium text-blue-800">Details: arguments, rationale, success criteria</summary>
        <dl className="mt-2 space-y-2">
          <div><dt className="text-slate-500">Rationale</dt><dd>{action.rationale}</dd></div>
          <div><dt className="text-slate-500">Expected outcome</dt><dd>{action.expected_outcome}</dd></div>
          {action.depends_on_assumptions.length > 0 && (
            <div><dt className="text-slate-500">Depends on assumptions</dt><dd>{action.depends_on_assumptions.join(', ')}</dd></div>
          )}
          <div><dt className="text-slate-500">Arguments</dt><dd><JsonBlock value={action.arguments} /></dd></div>
          <div>
            <dt className="text-slate-500">Success criteria</dt>
            <dd>
              <ul className="list-disc pl-5 font-mono text-xs">
                {action.verification_criteria.map((c, i) => (
                  <li key={i}>{c.path} {c.operator} {c.operator === 'exists' ? '' : JSON.stringify(c.expected)}</li>
                ))}
              </ul>
            </dd>
          </div>
        </dl>
      </details>

      {action.authorization_reason && (
        <p className="mt-3 text-xs text-slate-600">
          Authorization decision: <span className="font-mono">{action.authorization_reason}</span>
        </p>
      )}
      {action.execution_error && (
        <p className="mt-2 rounded bg-red-50 px-3 py-2 text-sm text-red-900">Error: {action.execution_error}</p>
      )}
      {action.execution_result && (
        <div className="mt-2 text-sm">
          <p className="text-slate-500">Result{action.execution_result.simulated ? ' (simulated, no real system changed)' : ''}</p>
          <JsonBlock value={action.execution_result} />
        </div>
      )}
      {action.verification_details && (
        <ul className="mt-2 space-y-1 text-xs">
          {action.verification_details.map((check, i) => (
            <li key={i} className={check.passed ? 'text-emerald-800' : 'text-red-800'}>
              {check.passed ? '✓' : '✗'} {check.path} {check.operator} {JSON.stringify(check.expected)}: actual{' '}
              {JSON.stringify(check.actual)}
            </li>
          ))}
        </ul>
      )}

      {pending && (canApprove || canReject) && (
        <div className="mt-4 border-t border-slate-200 pt-3">
          {rejecting ? (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (rationale.trim()) onReject(rationale.trim())
              }}
              className="space-y-2"
            >
              <label htmlFor={`reject-${action.id}`} className="block text-sm font-medium">Why reject this action?</label>
              <textarea
                id={`reject-${action.id}`}
                rows={2}
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <div className="flex gap-2">
                <Button type="submit" variant="danger" disabled={busy || !rationale.trim()}>Confirm rejection</Button>
                <Button onClick={() => setRejecting(false)} disabled={busy}>Back</Button>
              </div>
            </form>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {canApprove && <Button variant="success" disabled={busy} onClick={onApprove}>Approve action</Button>}
              {canReject && <Button variant="danger" disabled={busy} onClick={() => setRejecting(true)}>Reject action</Button>}
              <span className="text-xs text-slate-600">Approving records a decision. It does not run the action.</span>
            </div>
          )}
        </div>
      )}
      {!pending && action.review_state === 'BLOCKED' && (
        <p className="mt-3 text-xs text-red-800">This action can never execute, whatever a reviewer decides.</p>
      )}
    </article>
  )
}
