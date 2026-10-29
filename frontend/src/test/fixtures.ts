import type { ProposedAction, Task } from '../api/types'

export function action(overrides: Partial<ProposedAction> = {}): ProposedAction {
  return {
    id: 'act-1',
    sequence: 1,
    key: 'delete',
    description: 'Permanently delete billing events older than 30 days.',
    tool_name: 'delete_records',
    arguments: { dataset: 'billing-events', older_than_days: 30 },
    rationale: 'Frees storage.',
    expected_outcome: 'Old events removed.',
    verification_criteria: [{ path: 'deleted_count', operator: 'gte', expected: 1 }],
    depends_on_assumptions: ['A1'],
    agent_risk_estimate: 'MEDIUM',
    risk_level: 'HIGH',
    risk_factors: ['IRREVERSIBLE_EFFECT'],
    review_required: true,
    review_reasons: ['IRREVERSIBLE_EFFECT'],
    review_state: 'PENDING',
    authorization_state: 'NOT_EVALUATED',
    authorization_reason: null,
    execution_state: 'NOT_STARTED',
    execution_result: null,
    execution_error: null,
    verification_state: 'NOT_RUN',
    verification_details: null,
    ...overrides,
  }
}

export function task(overrides: Partial<Task> = {}, actions: ProposedAction[] = [action()]): Task {
  return {
    id: 'task-1',
    title: 'Clean up billing events',
    description: 'Clean up old billing events to free storage.',
    review_mode: 'STRUCTURED',
    status: 'AWAITING_REVIEW',
    failure_stage: null,
    failure_reason: null,
    created_at: '2026-10-29T12:00:00Z',
    updated_at: '2026-10-29T12:00:00Z',
    current_run: {
      id: 'run-1',
      attempt_number: 1,
      trigger: 'INITIAL',
      reviewer_input: null,
      planner: 'mock',
      status: 'SUCCEEDED',
      error: null,
      created_at: '2026-10-29T12:00:00Z',
      summary: 'Free storage by removing old billing events.',
      steps: ['Permanently delete billing events older than 30 days.'],
      open_questions: [],
      run_metadata: {},
      assumptions: [
        {
          id: 'as-1',
          key: 'A1',
          statement: 'Billing events older than 30 days are no longer needed.',
          basis: 'UNSUPPORTED',
          evidence: null,
          consequence_if_wrong: 'Records would be lost.',
        },
      ],
      actions,
    },
    runs: [],
    decisions: [],
    available_operations: ['approve_action', 'reject_action', 'request_revision', 'request_clarification', 'cancel'],
    ...overrides,
  }
}

type Route = { method?: string; path: string | RegExp; status?: number; body: unknown }

/** Installs a fetch mock answering from a route table and records requests. */
export function mockFetch(routes: Route[]) {
  const calls: Array<{ method: string; url: string; body: unknown }> = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const route = routes.find(
      (r) => (r.method ?? 'GET') === method && (typeof r.path === 'string' ? url.endsWith(r.path) : r.path.test(url)),
    )
    if (!route) return new Response(JSON.stringify({ error: { code: 'not_found', message: 'Not mocked' } }), { status: 404 })
    return new Response(JSON.stringify(route.body), { status: route.status ?? 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}
