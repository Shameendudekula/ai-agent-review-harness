import type {
  AssumptionBasis,
  AuthorizationState,
  ExecutionState,
  ReviewState,
  RiskLevel,
  TaskStatus,
  VerificationState,
} from '../api/types'

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'muted'

export const TONE_CLASSES: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-800 ring-slate-300',
  info: 'bg-blue-50 text-blue-800 ring-blue-300',
  success: 'bg-emerald-50 text-emerald-800 ring-emerald-300',
  warning: 'bg-amber-50 text-amber-900 ring-amber-300',
  danger: 'bg-red-50 text-red-800 ring-red-300',
  muted: 'bg-white text-slate-500 ring-slate-200',
}

type Label = { label: string; tone: Tone }

export const TASK_STATUS: Record<TaskStatus, Label> = {
  CREATED: { label: 'Created', tone: 'neutral' },
  PLANNING: { label: 'Planning', tone: 'info' },
  AWAITING_REVIEW: { label: 'Awaiting review', tone: 'warning' },
  RUNNING: { label: 'Running', tone: 'info' },
  COMPLETED: { label: 'Completed', tone: 'success' },
  FAILED: { label: 'Failed', tone: 'danger' },
  CANCELLED: { label: 'Cancelled', tone: 'muted' },
}

export const RISK: Record<RiskLevel, Label> = {
  LOW: { label: 'Low risk', tone: 'success' },
  MEDIUM: { label: 'Medium risk', tone: 'warning' },
  HIGH: { label: 'High risk', tone: 'danger' },
  FORBIDDEN: { label: 'Forbidden', tone: 'danger' },
}

export const REVIEW: Record<ReviewState, Label> = {
  NOT_REQUIRED: { label: 'No review needed', tone: 'muted' },
  PENDING: { label: 'Awaiting review', tone: 'warning' },
  APPROVED: { label: 'Approved', tone: 'success' },
  REJECTED: { label: 'Rejected', tone: 'danger' },
  BLOCKED: { label: 'Blocked by policy', tone: 'danger' },
  SUPERSEDED: { label: 'Superseded', tone: 'muted' },
}

export const AUTHORIZATION: Record<AuthorizationState, Label> = {
  NOT_EVALUATED: { label: 'Not evaluated', tone: 'muted' },
  GRANTED: { label: 'Authorized', tone: 'success' },
  DENIED: { label: 'Denied', tone: 'danger' },
}

export const EXECUTION: Record<ExecutionState, Label> = {
  NOT_STARTED: { label: 'Not executed', tone: 'muted' },
  SUCCEEDED: { label: 'Executed', tone: 'success' },
  FAILED: { label: 'Execution failed', tone: 'danger' },
  SKIPPED: { label: 'Skipped', tone: 'muted' },
}

export const VERIFICATION: Record<VerificationState, Label> = {
  NOT_RUN: { label: 'Not verified', tone: 'muted' },
  PASSED: { label: 'Verified', tone: 'success' },
  FAILED: { label: 'Verification failed', tone: 'danger' },
}

export const BASIS: Record<AssumptionBasis, Label & { help: string }> = {
  STATED: { label: 'Stated', tone: 'success', help: 'Given in the task or confirmed by a reviewer.' },
  INFERRED: { label: 'Inferred', tone: 'info', help: 'Derived from evidence the agent cites.' },
  UNSUPPORTED: { label: 'Unsupported', tone: 'warning', help: 'The agent has no evidence for this.' },
}

export const DECISION_LABEL: Record<string, string> = {
  APPROVE: 'Approved',
  REJECT: 'Rejected',
  REQUEST_CLARIFICATION: 'Clarification',
  REQUEST_REVISION: 'Revision requested',
}

export const FAILURE_HELP: Record<string, string> = {
  PLANNING: 'The agent could not produce a valid plan. Nothing was executed, so planning can be retried safely.',
  EXECUTION: 'A tool failed while running. Earlier steps may already have taken effect, so the task cannot be retried automatically.',
  VERIFICATION: 'A step ran but its result did not meet the plan’s success criteria.',
  AUTHORIZATION: 'The backend refused to authorize a step at execution time. The task stopped without running it.',
}

export function humanize(code: string): string {
  return code.charAt(0) + code.slice(1).toLowerCase().replaceAll('_', ' ')
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' })
}
