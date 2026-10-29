import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import type { ReviewMode, TaskList } from '../api/types'
import { Badge, Button, Card, ErrorBanner, Spinner } from '../components/ui'
import { useCatalog } from '../lib/catalog'
import { TASK_STATUS, formatTime } from '../lib/labels'

const PAGE_SIZE = 20

function CreateTaskForm() {
  const catalog = useCatalog()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [mode, setMode] = useState<ReviewMode>('STRUCTURED')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  async function submit(event: FormEvent) {
    event.preventDefault()
    const errors: Record<string, string> = {}
    if (!title.trim()) errors.title = 'Enter a title.'
    if (!description.trim()) errors.description = 'Describe the task.'
    setFieldErrors(errors)
    if (Object.keys(errors).length) return

    setSubmitting(true)
    setError(null)
    try {
      const task = await api.createTask(title.trim(), description.trim(), mode)
      // Planning is a separate backend step; start it right away so the reviewer sees a plan.
      try {
        await api.plan(task.id)
      } catch {
        // The task exists either way; its page shows the state and offers the next step.
      }
      navigate(`/tasks/${task.id}`)
    } catch (err) {
      if (err instanceof ApiError) setFieldErrors(err.fieldErrors())
      setError(err)
      setSubmitting(false)
    }
  }

  return (
    <Card title="New task">
      <form onSubmit={submit} noValidate className="space-y-4">
        {catalog && (
          <div>
            <p className="mb-2 text-sm text-slate-700">
              Example tasks. The mock agent has a scripted plan for each one:
            </p>
            <div className="flex flex-wrap gap-2">
              {catalog.example_tasks.map((example) => (
                <button
                  key={example.scenario}
                  type="button"
                  onClick={() => {
                    setTitle(example.title)
                    setDescription(example.description)
                  }}
                  className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 hover:border-blue-700 hover:text-blue-800"
                >
                  {example.title}
                </button>
              ))}
            </div>
          </div>
        )}

        <div>
          <label htmlFor="title" className="block text-sm font-medium text-slate-800">Title</label>
          <input
            id="title"
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            aria-invalid={Boolean(fieldErrors.title)}
            aria-describedby={fieldErrors.title ? 'title-error' : undefined}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          />
          {fieldErrors.title && <p id="title-error" className="mt-1 text-sm text-red-700">{fieldErrors.title}</p>}
        </div>

        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-800">Description</label>
          <textarea
            id="description"
            value={description}
            rows={3}
            maxLength={5000}
            onChange={(e) => setDescription(e.target.value)}
            aria-invalid={Boolean(fieldErrors.description)}
            aria-describedby={fieldErrors.description ? 'description-error' : undefined}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          />
          {fieldErrors.description && (
            <p id="description-error" className="mt-1 text-sm text-red-700">{fieldErrors.description}</p>
          )}
        </div>

        <fieldset>
          <legend className="text-sm font-medium text-slate-800">Review workflow</legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {([
              ['STRUCTURED', 'Structured', 'Per-action, risk-based review. Assumptions and reasons are shown; clarification and revision are available.'],
              ['BASELINE', 'Baseline', 'Approve or stop the whole plan. This is the comparison condition.'],
            ] as const).map(([value, label, help]) => (
              <label
                key={value}
                className={`flex cursor-pointer gap-3 rounded-md border p-3 text-sm ${mode === value ? 'border-blue-700 bg-blue-50' : 'border-slate-300'}`}
              >
                <input type="radio" name="mode" value={value} checked={mode === value} onChange={() => setMode(value)} className="mt-0.5" />
                <span>
                  <span className="font-medium">{label}</span>
                  <span className="block text-slate-600">{help}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <ErrorBanner error={error} />
        <Button type="submit" variant="primary" disabled={submitting}>
          {submitting ? 'Creating and planning…' : 'Create task and generate plan'}
        </Button>
      </form>
    </Card>
  )
}

function TaskTable() {
  const [data, setData] = useState<TaskList | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [offset, setOffset] = useState(0)

  const load = useCallback(() => {
    api.listTasks(offset, PAGE_SIZE).then(setData).catch(setError)
  }, [offset])
  useEffect(load, [load])
  const retry = () => {
    setError(null)
    load()
  }

  return (
    <Card title="Tasks">
      {error ? (
        <ErrorBanner error={error} onRetry={retry} />
      ) : !data ? (
        <Spinner label="Loading tasks…" />
      ) : data.items.length === 0 ? (
        <p className="py-4 text-sm text-slate-600">No tasks yet. Create one above, or pick an example task to start.</p>
      ) : (
        <>
          <ul className="divide-y divide-slate-200">
            {data.items.map((task) => (
              <li key={task.id}>
                <Link
                  to={`/tasks/${task.id}`}
                  className="flex flex-wrap items-center justify-between gap-2 py-3 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-blue-700"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-slate-900">{task.title}</span>
                    <span className="text-xs text-slate-600">
                      {task.review_mode === 'BASELINE' ? 'Baseline' : 'Structured'} · {formatTime(task.created_at)}
                    </span>
                  </span>
                  <Badge tone={TASK_STATUS[task.status].tone}>{TASK_STATUS[task.status].label}</Badge>
                </Link>
              </li>
            ))}
          </ul>
          {data.total > PAGE_SIZE && (
            <nav className="mt-3 flex items-center justify-between text-sm" aria-label="Pagination">
              <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
              <span className="text-slate-600">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
              </span>
              <Button disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</Button>
            </nav>
          )}
        </>
      )}
    </Card>
  )
}

export function TaskListPage() {
  return (
    <div className="space-y-6">
      <CreateTaskForm />
      <TaskTable />
    </div>
  )
}
