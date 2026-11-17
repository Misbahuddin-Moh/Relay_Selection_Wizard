import { catalogEvidenceLabel, catalogSourceUrl } from './catalogReadiness'

export interface CatalogProductReadiness {
  adapter_version: string
  contract_version: number
  requested_model: string
  catalog_model: string | null
  source_release_sha: string | null
  product_sha256: string | null
  tracks: Record<'code_layout' | 'hardware_compatibility' | 'application_review', {
    status: 'blocked' | 'evidence_recorded'
    blocker_codes: string[]
  }>
  blockers: {code: string; path: string; message: string; tracks: string[]}[]
  catalog_evidence_only: true
  complete_fit: false
  procurement_ready: false
  order_code: null
  limitation: string
}
export interface CatalogReadinessResult {
  contract_version: number
  source_release_sha: string | null
  source_url: string
  fingerprint: string
  role_mapping: 'not_performed'
  complete_fit: false
  procurement_ready: false
  basis: string
  products: CatalogProductReadiness[]
}

const trackLabels = {
  code_layout: 'Code layout evidence',
  hardware_compatibility: 'Hardware compatibility evidence',
  application_review: 'Application review evidence',
} as const

export function CatalogReadiness({ assessment }: {assessment: CatalogReadinessResult}) {
  const source = catalogSourceUrl(assessment.source_url)
  return <section className="detail-block catalog-readiness" aria-label="Catalog package readiness">
    <h3>Catalog package readiness</h3>
    <p>Read-only catalog evidence for the exact products listed below. This does not select a relay variant, establish application suitability, or validate the partial analog and digital budgets above.</p>
    <p>Source release: <code>{assessment.source_release_sha || 'Unknown · not reviewed'}</code>{source && <> · <a href={source} target="_blank" rel="noreferrer">Pinned catalog source ↗</a></>}</p>
    <p>{assessment.basis}</p>
    <p><strong>No role-to-product mapping has been performed.</strong> These packages do not imply selection or approval for the current relay role.</p>
    {!assessment.products.length && <p>No product packages assessed. Catalog availability remains unresolved.</p>}
    <div className="comparison-zone-grid">{assessment.products.map((product, index) => <article key={`${product.requested_model}/${index}`} className="comparison-zone" data-catalog-product={product.requested_model}>
      <h4>{product.requested_model}</h4>
      <p>Catalog product: <strong>{product.catalog_model || 'Unknown · no exact product package'}</strong></p>
      <p><strong>Evidence only · No complete fit or order code</strong></p>
      <dl>{(Object.keys(trackLabels) as (keyof typeof trackLabels)[]).map(track => {
        const result = product.tracks?.[track]
        return <div key={track} data-catalog-track={track}>
          <dt>{trackLabels[track]}</dt>
          <dd>{result?.status === 'evidence_recorded' ? 'Evidence recorded · not independently authenticated or approved'
            : result?.status === 'blocked' ? 'Blocked · evidence gaps remain' : 'Unknown · not reviewed'}
            {!!result?.blocker_codes.length && <> · {result.blocker_codes.length} blocker categories</>}
          </dd>
        </div>
      })}</dl>
      {product.blockers.length > 0 ? <details><summary>Inspect {product.blockers.length} evidence blockers</summary><ul>{product.blockers.map((blocker, blockerIndex) => <li key={`${blocker.code}/${blocker.path}/${blockerIndex}`} data-catalog-blocker={blocker.code}>
        <strong>{catalogEvidenceLabel(blocker.code)}</strong>: {blocker.message}
        <br /><small>Catalog path: {blocker.path || 'Unspecified'} · affected tracks: {blocker.tracks.map(catalogEvidenceLabel).join(', ') || 'Unknown'}</small>
      </li>)}</ul></details> : <p>No package blockers reported. Application approval remains unavailable.</p>}
      <p>{product.limitation}</p>
      <details><summary>Package provenance</summary>
        <p>Release: <code>{product.source_release_sha || 'Unknown'}</code></p>
        <p>Product SHA-256: <code>{product.product_sha256 || 'Unknown'}</code></p>
        <p>Adapter: {product.adapter_version} · contract {product.contract_version}</p>
      </details>
    </article>)}</div>
  </section>
}
