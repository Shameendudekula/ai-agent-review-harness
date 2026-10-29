import type { AuditEvent } from '../api/types'
import { formatTime, humanize, type Tone } from '../lib/labels'
import { Badge } from './ui'

const ACTOR_TONE: Record<AuditEvent['actor'], Tone> = {
  SYSTEM: 'neutral',
  AGENT: 'info',
  POLICY: 'warning',
  REVIEWER: 'success',
}

function summarize(event: AuditEvent): string | null {
  const p = event.payload
  switch (event.event_type) {
    case 'TASK_STATUS_CHANGED':
      return `${p.from} → ${p.to}`
    case 'REVIEW_DECISION_RECORDED':
      return [p.decision, p.action_key ? `on ${p.action_key}` : 'on plan', p.rationale ? `: "${p.rationale}"` : '']
        .filter(Boolean)
        .join(' ')
    case 'AUTHORIZATION_GRANTED':
    case 'AUTHORIZATION_DENIED':
      return `${p.tool}: ${p.reason}`
    case 'ACTION_PROPOSED':
      return `${p.key} (${p.tool})`
    case 'ACTION_BLOCKED':
      return Array.isArray(p.reasons) ? p.reasons.join(', ') : null
    case 'EXECUTION_FAILED':
    case 'PLANNING_FAILED':
      return String(p.error ?? '')
    case 'TASK_FAILED':
      return `${p.stage}: ${p.reason}`
    case 'REVIEW_REQUESTED':
      return Array.isArray(p.reasons) && p.reasons.length ? p.reasons.join(', ') : null
    case 'ASSUMPTION_RECORDED':
      return `${p.key} (${p.basis})`
    default:
      return null
  }
}

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-slate-600">No events recorded.</p>
  return (
    <ol className="space-y-2" aria-label="Audit events">
      {events.map((event) => {
        const detail = summarize(event)
        return (
          <li key={event.sequence} className="flex gap-3 text-sm">
            <span className="w-8 shrink-0 text-right font-mono text-xs text-slate-500">{event.sequence}</span>
            <div className="min-w-0 flex-1 border-l border-slate-200 pl-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{humanize(event.event_type)}</span>
                <Badge tone={ACTOR_TONE[event.actor]}>{humanize(event.actor)}</Badge>
                <time className="text-xs text-slate-500" dateTime={event.created_at}>{formatTime(event.created_at)}</time>
              </div>
              {detail && <p className="break-words text-slate-700">{detail}</p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
