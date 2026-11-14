import json
import os
from pathlib import Path
from typing import Annotated, Literal, Optional
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from .drawing import CLAUDE_IMAGE_BYTES, FILE_TYPES, MAX_DRAWING_BYTES, ExtractionError, drawing_provider, extract_drawing
from .engine import analyze
from .options import OptionsError, generate_options, preview_options
from .project_requirements import MAX_BYTES, RequirementError, extract_requirements, source_pages

from .models import Bay, CtCount, CtInventory, CtProvenance, Study
from .projects import MAX_PROJECT_BYTES, validate_project, project_role_keys
from pydantic import ValidationError
from uuid import NAMESPACE_URL, uuid5


app = FastAPI(title="Relay Selection Wizard")
# The shared alpha deliberately has no public route to paid providers. Re-enable
# only with the access, ownership, consent and cost controls of the pilot gate.
PROVIDER_PATHS = frozenset({
    "/api/protection-options", "/api/drawing/extract", "/api/requirements/extract",
})


@app.middleware("http")
async def provider_guard(request: Request, call_next):
    from fastapi.responses import JSONResponse
    if request.url.path.rstrip("/") in PROVIDER_PATHS:
        return JSONResponse(status_code=403, content={
            "detail": "Provider operations are disabled in this alpha. Use manual entry and station checks.",
        })
    return await call_next(request)


FIXTURE = Path(__file__).with_name("fixture.json")
FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@app.get("/api/health")
def health():
    return {"status": "ok", "revision": os.getenv("RENDER_GIT_COMMIT") or os.getenv("APP_REVISION") or "local",
            "provider_operations": "disabled", "release_gate": "foundation_alpha"}


@app.get("/api/study")
def reference_study():
    seed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seed['uid'] = str(uuid5(NAMESPACE_URL, 'relay-wizard/reference-station'))
    for bay in seed['bays']:
        bay['uid'] = str(uuid5(NAMESPACE_URL, f"relay-wizard/reference-station/{bay['id']}"))
    study = Study.model_validate(seed).model_dump()
    return {"study": study, "analysis": analyze(study)}


@app.post("/api/projects/validate")
async def validate_portable_project(request: Request):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_PROJECT_BYTES:
            raise HTTPException(413, 'Project files must be no larger than 2 MiB.')
        data.extend(chunk)
    try:
        decoded = json.loads(data)
        return validate_project(decoded)
    except (ValueError, RecursionError, UnicodeDecodeError, ValidationError):
        raise HTTPException(422, 'Invalid project file: check its version, identities, counts and decision references. No current work has been replaced.') from None


@app.post("/api/analyze")
def analyze_study(study: Study):
    return {**analyze(study.model_dump()), "role_keys": project_role_keys(study.model_dump())}


@app.post("/api/protection-preview")
def protection_preview(study: Study):
    return preview_options(study.model_dump())


@app.post("/api/protection-options")
def protection_options(study: Study):
    try:
        return generate_options(study.model_dump())
    except OptionsError as error:
        raise HTTPException(502, str(error)) from error


@app.get("/api/drawing/status")
def drawing_status():
    return {"configured": False, "provider": None, "reason": "Provider operations disabled in this alpha."}


@app.post("/api/drawing/extract")
async def extract_single_line(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    signature = FILE_TYPES.get(content_type)
    if signature is None:
        raise HTTPException(415, "Choose a PDF, PNG, or JPEG drawing.")

    provider = drawing_provider()
    limit = CLAUDE_IMAGE_BYTES if provider == "Claude" and content_type != "application/pdf" else MAX_DRAWING_BYTES
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            detail = (
                "Claude’s inline image limit is 7.5 MB before encoding. Use the upload screen to send it as a PDF."
                if limit == CLAUDE_IMAGE_BYTES else "Choose a drawing no larger than 20 MiB."
            )
            raise HTTPException(413, detail)
        data.extend(chunk)
    if not data.startswith(signature):
        raise HTTPException(422, "The drawing bytes do not match the selected file type.")
    if provider is None:
        raise HTTPException(503, "Drawing extraction is unconfigured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY on the server, or enter the topology manually.")

    try:
        return await run_in_threadpool(extract_drawing, bytes(data), content_type)
    except ExtractionError as error:
        raise HTTPException(502, str(error)) from error


@app.get("/api/requirements/status")
def requirements_status():
    return {"configured": False, "reason": "Provider operations disabled in this alpha."}


@app.post("/api/requirements/extract")
async def extract_project_requirements(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in ("application/pdf", "text/plain"):
        raise HTTPException(415, "Choose a PDF or UTF-8 text excerpt.")
    if not requirements_status()["configured"]:
        raise HTTPException(503, "Set ANTHROPIC_API_KEY on the server to extract project requirements.")
    raw_roles = request.headers.get("x-relay-roles", "[]")
    try:
        roles = json.loads(unquote(raw_roles))
        if not isinstance(roles, list) or len(roles) > 50 or any(
            not isinstance(role, str) or not role.strip() or len(role) > 200 for role in roles
        ):
            raise ValueError
    except (ValueError, RecursionError) as error:
        raise HTTPException(422, "Invalid relay roles for requirements extraction.") from error
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Choose an excerpt no larger than 5 MiB.")
        data.extend(chunk)
    if not data:
        raise HTTPException(422, "Choose a file or paste a requirement.")
    try:
        pages = await run_in_threadpool(source_pages, bytes(data), content_type)
    except RequirementError as error:
        raise HTTPException(422, str(error)) from error
    try:
        return await run_in_threadpool(extract_requirements, pages, roles)
    except RequirementError as error:
        raise HTTPException(502, str(error)) from error


if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
