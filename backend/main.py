import json
from pathlib import Path
from typing import Annotated, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .drawing import CLAUDE_IMAGE_BYTES, FILE_TYPES, MAX_DRAWING_BYTES, ExtractionError, drawing_provider, extract_drawing
from .engine import analyze

Measurement = Literal["unknown", "present", "absent"]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Bay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Label
    branches: Annotated[list[Label], Field(min_length=1, max_length=30)]
    ct: Measurement


CtCount = Annotated[int, Field(strict=True, ge=0, le=99)]


class CtInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lv_breaker_135: Optional[CtCount] = Field(...)
    lv_breaker_246: Optional[CtCount] = Field(...)
    hv_breaker_135: Optional[CtCount] = Field(...)
    hv_breaker_246: Optional[CtCount] = Field(...)
    transformer_hv_phase: Optional[CtCount] = Field(...)
    transformer_lv_phase: Optional[CtCount] = Field(...)
    transformer_hv_neutral: Optional[CtCount] = Field(...)
    transformer_lv_neutral: Optional[CtCount] = Field(...)


class Study(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Label
    hv_kv: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    mv_kv: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    lv_ct: Measurement
    hv_ct: Measurement
    bays: Annotated[list[Bay], Field(min_length=1, max_length=40)]
    auxiliary: Literal["unknown", "included", "excluded"]
    ct_inventory: Optional[CtInventory] = None

    @model_validator(mode="after")
    def validate_equipment_ids(self):
        bay_ids = [bay.id.casefold() for bay in self.bays]
        if len(set(bay_ids)) != len(bay_ids):
            raise ValueError("Collector breaker IDs must be unique.")
        branch_ids = [branch.casefold() for bay in self.bays for branch in bay.branches]
        if len(set(branch_ids)) != len(branch_ids):
            raise ValueError("Outgoing branch IDs must be unique.")
        return self


app = FastAPI(title="Relay Selection Wizard")
FIXTURE = Path(__file__).with_name("fixture.json")
FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/study")
def reference_study():
    study = Study.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8"))).model_dump()
    return {"study": study, "analysis": analyze(study)}


@app.post("/api/analyze")
def analyze_study(study: Study):
    return analyze(study.model_dump())


@app.get("/api/drawing/status")
def drawing_status():
    provider = drawing_provider()
    return {"configured": provider is not None, "provider": provider}


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


if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
