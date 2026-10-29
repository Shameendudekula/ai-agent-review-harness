import { useState } from 'react'

const STORAGE_KEY = 'review-harness.reviewer'
const DEFAULT_REVIEWER = 'demo-reviewer'
// Mirrors the backend's validation pattern for the reviewer label.
const VALID = /^[A-Za-z0-9 ._@-]{1,80}$/

/** Current reviewer label, read at call time so changes in the header apply everywhere. */
export function currentReviewer(): string {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored && VALID.test(stored) ? stored : DEFAULT_REVIEWER
  } catch {
    return DEFAULT_REVIEWER
  }
}

/** The reviewer label is a self-declared name for the audit trail, not an authenticated identity. */
export function useReviewer(): [string, (name: string) => boolean] {
  const [name, setName] = useState(currentReviewer)
  const update = (value: string) => {
    if (!VALID.test(value)) return false
    setName(value)
    try {
      window.localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // Storage may be unavailable (private mode); the name still applies for this session.
    }
    return true
  }
  return [name, update]
}
