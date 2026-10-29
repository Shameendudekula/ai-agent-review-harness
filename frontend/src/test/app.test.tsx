import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import { ActionCard } from '../components/ActionCard'
import { TaskDetailPage } from '../pages/TaskDetailPage'
import { TaskListPage } from '../pages/TaskListPage'
import { action, mockFetch, task } from './fixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/tasks/task-1']}>
      <Routes>
        <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('API client', () => {
  it('turns backend error bodies into ApiError with code and field errors', async () => {
    mockFetch([{
      method: 'POST', path: '/api/v1/tasks', status: 422,
      body: { error: { code: 'validation_error', message: 'Request validation failed',
                       details: [{ location: ['body', 'title'], message: 'String should have at least 1 character' }] } },
    }])
    const error = await api.createTask('', 'd', 'STRUCTURED').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('validation_error')
    expect((error as ApiError).fieldErrors()).toEqual({ title: 'String should have at least 1 character' })
  })

  it('reports network failures distinctly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.listTasks()).rejects.toMatchObject({ code: 'network_error', status: 0 })
  })
})

describe('ActionCard', () => {
  const noop = () => {}

  it('keeps review, authorization, execution and verification distinct', () => {
    render(<ActionCard action={action({ review_state: 'APPROVED' })} showRisk canApprove={false} canReject={false} busy={false} onApprove={noop} onReject={noop} />)
    const stages = screen.getByRole('list', { name: 'Action progress' })
    expect(within(stages).getByText('Approved')).toBeInTheDocument()
    expect(within(stages).getByText('Not evaluated')).toBeInTheDocument()
    expect(within(stages).getByText('Not executed')).toBeInTheDocument()
    expect(within(stages).getByText('Not verified')).toBeInTheDocument()
  })

  it('explains why review is needed and flags an under-estimated risk', () => {
    render(<ActionCard action={action()} showRisk canApprove canReject busy={false} onApprove={noop} onReject={noop} />)
    expect(screen.getByText('Why it needs review')).toBeInTheDocument()
    expect(screen.getByText(/The agent rated this action medium risk/)).toBeInTheDocument()
  })

  it('requires a rationale before rejecting', async () => {
    const onReject = vi.fn()
    render(<ActionCard action={action()} showRisk canApprove canReject busy={false} onApprove={noop} onReject={onReject} />)
    await userEvent.click(screen.getByRole('button', { name: 'Reject action' }))
    const confirm = screen.getByRole('button', { name: 'Confirm rejection' })
    expect(confirm).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Why reject this action?'), 'Retention is 365 days')
    await userEvent.click(confirm)
    expect(onReject).toHaveBeenCalledWith('Retention is 365 days')
  })

  it('shows blocked actions as never executable and without review buttons', () => {
    render(<ActionCard action={action({ review_state: 'BLOCKED', risk_level: 'FORBIDDEN', review_required: false, review_reasons: ['TOOL_NOT_ALLOWLISTED'] })}
      showRisk canApprove canReject busy={false} onApprove={noop} onReject={noop} />)
    expect(screen.getByText('Why it is blocked')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve action' })).not.toBeInTheDocument()
    expect(screen.getByText(/can never execute/)).toBeInTheDocument()
  })
})

describe('TaskDetailPage', () => {
  it('renders server state and sends an approval for the selected action', async () => {
    const approved = task(
      { available_operations: ['execute', 'request_revision', 'request_clarification', 'cancel'] },
      [action({ review_state: 'APPROVED' })],
    )
    const calls = mockFetch([
      { path: '/api/v1/tasks/task-1', body: task() },
      { path: '/api/v1/tasks/task-1/events', body: [] },
      { method: 'POST', path: '/api/v1/tasks/task-1/reviews', body: approved },
    ])
    renderDetail()
    expect(await screen.findByText('Billing events older than 30 days are no longer needed.')).toBeInTheDocument()
    expect(screen.getByText('Unsupported')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Approve action' }))
    await screen.findByRole('button', { name: 'Run approved actions' })

    const post = calls.find((c) => c.method === 'POST')
    expect(post?.body).toMatchObject({ decision: 'APPROVE', action_id: 'act-1', reviewer: 'demo-reviewer' })
    // Approval does not claim execution.
    expect(screen.getByText('Not executed')).toBeInTheDocument()
  })

  it('shows a conflict from the server and reloads the real state', async () => {
    const calls = mockFetch([
      { path: '/api/v1/tasks/task-1', body: task() },
      { path: '/api/v1/tasks/task-1/events', body: [] },
      { method: 'POST', path: '/api/v1/tasks/task-1/reviews', status: 409,
        body: { error: { code: 'already_decided', message: 'This action has already been decided (APPROVED)' } } },
    ])
    renderDetail()
    await userEvent.click(await screen.findByRole('button', { name: 'Approve action' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already been decided')
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith('/tasks/task-1')).length).toBe(2))
  })

  it('blocks approval while the agent has open questions', async () => {
    const withQuestions = task({ available_operations: ['reject_action', 'request_revision', 'request_clarification', 'cancel'] })
    withQuestions.current_run!.open_questions = ['Which channel should receive the announcement?']
    mockFetch([
      { path: '/api/v1/tasks/task-1', body: withQuestions },
      { path: '/api/v1/tasks/task-1/events', body: [] },
    ])
    renderDetail()
    expect(await screen.findByText('Which channel should receive the announcement?')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve action' })).not.toBeInTheDocument()
  })

  it('hides risk details in baseline review and offers approve or stop', async () => {
    mockFetch([
      { path: '/api/v1/tasks/task-1', body: task({ review_mode: 'BASELINE', available_operations: ['approve_plan', 'reject_plan', 'cancel'] }) },
      { path: '/api/v1/tasks/task-1/events', body: [] },
    ])
    renderDetail()
    expect(await screen.findByRole('button', { name: 'Approve and run plan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop task' })).toBeInTheDocument()
    expect(screen.queryByText('Assumptions')).not.toBeInTheDocument()
    expect(screen.queryByText('High risk')).not.toBeInTheDocument()
  })

  it('explains planning failures and offers a retry', async () => {
    mockFetch([
      { path: '/api/v1/tasks/task-1', body: task({ status: 'FAILED', failure_stage: 'PLANNING', failure_reason: 'Agent output failed schema validation', available_operations: ['retry_planning'] }) },
      { path: '/api/v1/tasks/task-1/events', body: [] },
    ])
    renderDetail()
    expect(await screen.findByText(/planning can be retried safely/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry planning' })).toBeInTheDocument()
  })

  it('shows a not-found message for a missing task', async () => {
    mockFetch([])
    renderDetail()
    expect(await screen.findByRole('alert')).toHaveTextContent('This task does not exist.')
  })
})

describe('TaskListPage', () => {
  function renderList() {
    return render(<MemoryRouter><TaskListPage /></MemoryRouter>)
  }

  it('shows an empty state', async () => {
    mockFetch([{ path: /\/api\/v1\/tasks\?/, body: { items: [], total: 0, limit: 20, offset: 0 } }])
    renderList()
    expect(await screen.findByText(/No tasks yet/)).toBeInTheDocument()
  })

  it('validates the form before calling the API', async () => {
    const calls = mockFetch([{ path: /\/api\/v1\/tasks\?/, body: { items: [], total: 0, limit: 20, offset: 0 } }])
    renderList()
    await userEvent.click(screen.getByRole('button', { name: 'Create task and generate plan' }))
    expect(screen.getByText('Enter a title.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('shows an API error with a retry for the list', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    renderList()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('could not be reached')
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
