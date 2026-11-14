# Portable studies and recovery — schema 1

This slice adds persistent identities for a study and its collector breaker bays. `Bay.id` remains the editable engineering tag; `Bay.uid` is a separate UUID allocated when the bay is created. Reordering or renaming does not change it. Removing and re-adding a bay allocates a new UUID. Transformer, collector bus, local POI line and metering role identities are scoped singleton subjects within the study; feeder role identity uses its bay UUID. A deterministic UUID5 joins study identity, subject and role purpose. Manufacturer and list position do not enter it.

Protection alternatives use semantic keys such as `dedicated:poi`, not array indexes. Neutral/VT overrides use option + role identity. Ordering notes add the model. These decisions live above the component that rerenders after station changes. Active digital examples still use positional F1/F2/F3 endpoints, so changing breaker order or POI line scope deliberately clears edited signal rows with a notice; the wiring variant and spare policy survive. This is not a general equipment graph or complete per-signal identity migration.

## File contract

`POST /api/projects/validate` accepts at most 2 MiB of UTF-8 JSON. A schema-1 file explicitly contains `format: relay-wizard-project`, integer `schema_version: 1`, `project_id`, an analyzed `study`, optional pending `draft`, and typed `decisions`. All nested contracts reject extra fields. Versioned files require persistent study/bay identities. An older raw station object can migrate once: the service assigns identities and returns the normalized versioned file, which retains them on later loads.

The service validates shape, counts, identities, role references and supported decision keys, then calculates a fresh analysis. It never accepts imported analysis or approval fields. Unknown future versions fail; they are not coerced. Invalid requests return a safe error and do not change server or browser state. The endpoint stores nothing and calls no provider.

Only the active analyzed station and pending scenario inputs are retained. Earlier comparison history, source drawings, pasted source excerpts, AI responses, generated badges, credentials and provider permissions are excluded. First concept entry before its first successful analysis is not recovered. This boundary is shown in the save panel. Ordering text is an unverified request note; it cannot grant catalog validation or procurement release.

## Save, recover and switch

After first analysis, edits are saved after a short debounce. Each local entry is a versioned project plus writer and unique revision token. Browser Web Locks serialize cooperating writers; the token is compared again under the lock. An external storage change pauses autosave instead of overwriting it. The user can load the other version or save a separate copy. Storage errors keep work in memory and show an explicit warning; portable download remains available while storage is unavailable.

Reload first validates the last active saved project, recalculates results and then enables the workspace. Recovery does not run autosave over an unvalidated file. Corrupt entries remain untouched, with an error and a fresh-study path. Saved-study listing checks metadata types before rendering. Imports are staged and require Open imported copy; the imported copy gets a new project identity. Before switching/import/recovery, the current revision is validated and preserved under a lock. A conflicted tab's revision is preserved as a separate recovery copy before loading another tab's version.

Pending drafts can retain incomplete labels and zero/blank voltages while the last valid study remains separate. Their results stay visibly stale until Analyze scenario succeeds. Undo/redo cover pending scenario input actions and retain their CT provenance; history resets on successful analysis or project switching. Undo does not resurrect an old approval.

Remote model/CT facts are retained, but local compatibility/channel/DTT verification is requested again on recovery or station reanalysis. Removed-equipment input decisions and ordering notes are retained as retired records, visible for review and excluded from active screening. They can reactivate only when the original identity returns, not when a new bay reuses the display tag.

## Verification

Backend HTTP tests cover identities, rename/reorder/recreate, migration, strict schema/size/reference checks, malformed input, partial pending drafts, origin/null/zero preservation and digital edit invalidation. Frontend tests cover decision reconciliation and file allowlisting. Browser checks cover save/reload, portable transfer, identity-preserving edits, undo/redo, stale-evidence protection, corrupt/invalid files, tab conflicts and quota failures. Both browser suites are required by CI before the staging release branch advances.

Remaining work includes complete provenance history, project revision/audit history, complete equipment topology contracts, durable shared storage/authorization, a backend I/O allocator and manufacturer-validated configurations. This slice does not close G1 or imply a shared pilot is ready.
