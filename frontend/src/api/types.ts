// Types mirroring the backend API (backend/app/api/schemas.py).

export type TaskStatus =
  | 'CREATED'
  | 'PLANNING'
  | 'AWAITING_REVIEW'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'

export type ReviewMode = 'STRUCTURED' | 'BASELINE'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'FORBIDDEN'
export type ReviewState = 'NOT_REQUIRED' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'BLOCKED' | 'SUPERSEDED'
export type AuthorizationState = 'NOT_EVALUATED' | 'GRANTED' | 'DENIED'
export type ExecutionState = 'NOT_STARTED' | 'SUCCEEDED' | 'FAILED' | 'SKIPPED'
export type VerificationState = 'NOT_RUN' | 'PASSED' | 'FAILED'
export type AssumptionBasis = 'STATED' | 'INFERRED' | 'UNSUPPORTED'
export type DecisionType = 'APPROVE' | 'REJECT' | 'REQUEST_CLARIFICATION' | 'REQUEST_REVISION'
export type FailureStage = 'PLANNING' | 'EXECUTION' | 'VERIFICATION' | 'AUTHORIZATION'

export type Operation =
  | 'plan'
  | 'cancel'
  | 'approve_plan'
  | 'reject_plan'
  | 'approve_action'
  | 'reject_action'
  | 'execute'
  | 'request_revision'
  | 'request_clarification'
  | 'retry_planning'

export interface Assumption {
  id: string
  key: string
  statement: string
  basis: AssumptionBasis
  evidence: string | null
  consequence_if_wrong: string
}

export interface VerificationCheck {
  path: string
  operator: string
  expected: unknown
  actual: unknown
  passed: boolean
}

export interface ProposedAction {
  id: string
  sequence: number
  key: string
  description: string
  tool_name: string
  arguments: Record<string, unknown>
  rationale: string
  expected_outcome: string
  verification_criteria: Array<{ path: string; operator: string; expected: unknown }>
  depends_on_assumptions: string[]
  agent_risk_estimate: RiskLevel
  risk_level: RiskLevel
  risk_factors: string[]
  review_required: boolean
  review_reasons: string[]
  review_state: ReviewState
  authorization_state: AuthorizationState
  authorization_reason: string | null
  execution_state: ExecutionState
  execution_result: Record<string, unknown> | null
  execution_error: string | null
  verification_state: VerificationState
  verification_details: VerificationCheck[] | null
}

export interface RunSummary {
  id: string
  attempt_number: number
  trigger: 'INITIAL' | 'REVISION' | 'CLARIFICATION' | 'RETRY'
  reviewer_input: string | null
  planner: string
  status: 'SUCCEEDED' | 'FAILED'
  error: string | null
  created_at: string
}

export interface Run extends RunSummary {
  summary: string | null
  steps: string[]
  open_questions: string[]
  run_metadata: Record<string, unknown>
  assumptions: Assumption[]
  actions: ProposedAction[]
}

export interface Decision {
  id: string
  agent_run_id: string
  action_id: string | null
  decision: DecisionType
  rationale: string | null
  reviewer: string
  created_at: string
}

export interface TaskSummary {
  id: string
  title: string
  review_mode: ReviewMode
  status: TaskStatus
  failure_stage: FailureStage | null
  created_at: string
  updated_at: string
}

export interface Task extends TaskSummary {
  description: string
  failure_reason: string | null
  current_run: Run | null
  runs: RunSummary[]
  decisions: Decision[]
  available_operations: Operation[]
}

export interface TaskList {
  items: TaskSummary[]
  total: number
  limit: number
  offset: number
}

export interface AuditEvent {
  sequence: number
  event_type: string
  actor: 'SYSTEM' | 'AGENT' | 'POLICY' | 'REVIEWER'
  agent_run_id: string | null
  action_id: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface Catalog {
  planner: string
  tools: Array<{ name: string; description: string; side_effect: string; external: boolean }>
  reason_explanations: Record<string, string>
  authorization_reasons: string[]
  example_tasks: Array<{ scenario: string; title: string; description: string }>
}

export interface ReviewRequest {
  decision: DecisionType
  action_id?: string
  rationale?: string
  reviewer: string
}
