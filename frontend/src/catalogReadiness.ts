/** Display backend evidence states without promoting them to application approval. */
export function catalogEvidenceLabel(state: unknown): string {
  if (typeof state !== 'string' || !state.trim()) return 'Unknown · not reviewed'
  return state.replaceAll('_', ' ').replaceAll('-', ' ')
}

/** Catalog citations are links, never executable markup or local resource paths. */
export function catalogSourceUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch { return null }
}
