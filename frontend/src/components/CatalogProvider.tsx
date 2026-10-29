import { useEffect, useState, type ReactNode } from 'react'

import { api } from '../api/client'
import type { Catalog } from '../api/types'
import { CatalogContext } from '../lib/catalog'

/** Loads reference data (reason explanations, example tasks) once. The UI works without it. */
export function CatalogProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => setCatalog(null))
  }, [])
  return <CatalogContext.Provider value={catalog}>{children}</CatalogContext.Provider>
}
