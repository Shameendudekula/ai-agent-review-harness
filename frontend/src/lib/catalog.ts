import { createContext, useContext } from 'react'

import type { Catalog } from '../api/types'

export const CatalogContext = createContext<Catalog | null>(null)

export function useCatalog(): Catalog | null {
  return useContext(CatalogContext)
}

export function useReasonText(): (code: string) => string {
  const catalog = useCatalog()
  return (code) => catalog?.reason_explanations[code] ?? code
}
