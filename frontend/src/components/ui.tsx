import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { ApiError } from '../api/client'
import { TONE_CLASSES, type Tone } from '../lib/labels'

export function Badge({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  )
}

export function Card({ title, children, actions }: { title?: ReactNode; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {actions}
        </header>
      )}
      <div className="px-4 py-4">{children}</div>
    </section>
  )
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-sm text-slate-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-blue-700" aria-hidden />
      {label}
    </div>
  )
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  const code = error instanceof ApiError ? error.code : null
  return (
    <div role="alert" className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
      <p className="font-medium">{message}</p>
      {code && code !== 'network_error' && <p className="mt-1 font-mono text-xs text-red-700">{code}</p>}
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-2 font-medium underline underline-offset-2">
          Try again
        </button>
      )}
    </div>
  )
}

export function Notice({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) {
  return <div className={`rounded-md px-4 py-3 text-sm ring-1 ring-inset ${TONE_CLASSES[tone]}`}>{children}</div>
}

const BUTTON_STYLES = {
  primary: 'bg-blue-800 text-white hover:bg-blue-900 disabled:bg-blue-300',
  secondary: 'bg-white text-slate-800 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:text-slate-400',
  danger: 'bg-white text-red-800 ring-1 ring-inset ring-red-300 hover:bg-red-50 disabled:text-red-300',
  success: 'bg-emerald-700 text-white hover:bg-emerald-800 disabled:bg-emerald-300',
} as const

export function Button({
  variant = 'secondary',
  children,
  ...props
}: { variant?: keyof typeof BUTTON_STYLES } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex min-h-9 items-center justify-center rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700 disabled:cursor-not-allowed ${BUTTON_STYLES[variant]} ${props.className ?? ''}`}
    >
      {children}
    </button>
  )
}

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="overflow-x-auto rounded bg-slate-900 px-3 py-2 font-mono text-xs leading-relaxed text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}
