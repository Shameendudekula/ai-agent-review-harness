import type { AuditEvent, Catalog, ReviewMode, ReviewRequest, Task, TaskList } from './types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

/** Any failed API call: HTTP errors carry the backend's error code; network failures use `network_error`. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  /** Field-level messages from a 422 validation error, keyed by the last location segment. */
  fieldErrors(): Record<string, string> {
    if (this.code !== 'validation_error' || !Array.isArray(this.details)) return {}
    const result: Record<string, string> = {}
    for (const item of this.details as Array<{ location?: unknown[]; message?: string }>) {
      const field = String(item.location?.[item.location.length - 1] ?? 'form')
      result[field] ??= item.message ?? 'Invalid value'
    }
    return result
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, 'network_error', 'The API could not be reached. Check that the backend is running.')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'http_error',
      error?.message ?? `Request failed with status ${response.status}`,
      error?.details ?? null,
    )
  }
  return body as T
}

const post = <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  catalog: () => request<Catalog>('/api/v1/catalog'),
  listTasks: (offset = 0, limit = 20) => request<TaskList>(`/api/v1/tasks?limit=${limit}&offset=${offset}`),
  getTask: (id: string) => request<Task>(`/api/v1/tasks/${encodeURIComponent(id)}`),
  events: (id: string) => request<AuditEvent[]>(`/api/v1/tasks/${encodeURIComponent(id)}/events`),
  createTask: (title: string, description: string, review_mode: ReviewMode) =>
    post<Task>('/api/v1/tasks', { title, description, review_mode }),
  plan: (id: string) => post<Task>(`/api/v1/tasks/${encodeURIComponent(id)}/plan`),
  review: (id: string, body: ReviewRequest) => post<Task>(`/api/v1/tasks/${encodeURIComponent(id)}/reviews`, body),
  execute: (id: string) => post<Task>(`/api/v1/tasks/${encodeURIComponent(id)}/execute`),
  retryPlanning: (id: string) => post<Task>(`/api/v1/tasks/${encodeURIComponent(id)}/retry-planning`),
  cancel: (id: string, reason?: string) => post<Task>(`/api/v1/tasks/${encodeURIComponent(id)}/cancel`, { reason }),
}
