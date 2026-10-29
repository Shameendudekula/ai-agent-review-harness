import { useState } from 'react'
import { Link, Route, Routes } from 'react-router-dom'

import { useCatalog } from './lib/catalog'
import { useReviewer } from './lib/reviewer'
import { TaskDetailPage } from './pages/TaskDetailPage'
import { TaskListPage } from './pages/TaskListPage'

function ReviewerField() {
  const [reviewer, setReviewer] = useReviewer()
  const [draft, setDraft] = useState(reviewer)
  const valid = /^[A-Za-z0-9 ._@-]{1,80}$/.test(draft)
  return (
    <label className="flex items-center gap-2 text-sm text-blue-100">
      Reviewer
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => setReviewer(draft)}
        aria-invalid={!valid}
        className="w-36 rounded border border-blue-300 bg-blue-950 px-2 py-1 text-white"
      />
    </label>
  )
}

export function App() {
  const catalog = useCatalog()
  return (
    <div className="min-h-screen">
      <header className="bg-blue-900 text-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="font-semibold tracking-tight">Agent Review Harness</Link>
          <ReviewerField />
        </div>
      </header>
      <div className="border-b border-amber-200 bg-amber-50">
        <p className="mx-auto max-w-5xl px-4 py-2 text-xs text-amber-900">
          Demonstration environment. The agent is {catalog?.planner === 'mock' || !catalog ? 'a deterministic mock' : `an LLM (${catalog.planner})`},
          and every tool is simulated: nothing real is changed, deleted or sent. Data you enter here is visible to other visitors.
        </p>
      </div>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/" element={<TaskListPage />} />
          <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
          <Route path="*" element={<p className="text-sm">Page not found. <Link className="text-blue-800 underline" to="/">Go to tasks</Link></p>} />
        </Routes>
      </main>
    </div>
  )
}
