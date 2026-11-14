# Provider security policy

## Owner data rule

Only engineering facts may leave this application for an AI provider. Project names,
owner or utility names, site identifiers, equipment identifiers, title-block text,
source filenames, contract excerpts and other confidential content must not be sent.
Consent to upload a document is not permission to forward it to a provider.

Drawings and contracts normally contain identifiers. Keep their processing local.
Before any future provider call, use structured engineering entry or a locally
redacted extraction followed by an explicit engineering-facts-only projection.
Do not rely on instructions asking a remote model to ignore identifiers: that
already transmits them. Do not send raw files, images, OCR or contract text.

## Current enforced boundary

All public drawing extraction, requirements extraction and paid protection-option
routes return HTTP 403 before their request body is consumed. Both status routes
report configured=false even if credentials are accidentally present. There is no
environment switch that enables these routes. Manual entry and deterministic
analysis remain available. Inherited provider helpers are dormant implementation,
not approved integration; do not invoke them with real credentials or documents.

Keep ANTHROPIC_API_KEY and OPENAI_API_KEY absent or blank in both original and
staging services. Never store credentials in source, browser code, images or logs.
A cleared deployment key does not revoke that key at the provider.

## Reopening requirements (not implemented)

Before changing the denial gate, implement and verify all of the following:

- Authenticated access, project ownership checks and explicit per-call consent.
- A strict allowlisted engineering schema rejecting unknown fields and free-form
  identifiers, with local redaction/review and tests proving confidential sentinel
  values never reach outbound payloads, logs, caches or error messages.
- Separate credentials and provider workspaces per environment, least privilege,
  provider-enforced spend limits, usage alerts, request/token/rate limits and
  auditable usage without retaining confidential source content.
- An independent review of the complete outbound path. Approved engineering
  answers must still pass deterministic engineering checks and user review.

Until then, do not install replacement provider credentials on either service.

## Deployment and credential response

Clear deployed credentials first and wait for the new deployment to be live;
verify status endpoints and denied routes on both environments without paid calls.
Review Anthropic usage from service creation (2026-11-08), revoke the old key in
the Anthropic console, and create a replacement only when secure storage and the
reopening controls are ready. Do not infer absence of abuse from missing logs.

Set Render auto-deploy to After CI Checks Pass for main and staging/release,
and health check path to /api/health. Main must have a passing verification job;
staging/release must carry checks on that exact revision, not merely its source
branch. Confirm deployed commit IDs and route behavior after every release.
