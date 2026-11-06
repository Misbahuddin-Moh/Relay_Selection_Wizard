import json
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .drawing import FILE_TYPES, MAX_DRAWING_BYTES, ExtractionError, extract_drawing
from .engine import analyze

Measurement = Literal["unknown", "present", "absent"]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Bay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Label
    branches: Annotated[list[Label], Field(min_length=1, max_length=30)]
    ct: Measurement


class Study(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Label
    hv_kv: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    mv_kv: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    lv_ct: Measurement
    hv_ct: Measurement
    bays: Annotated[list[Bay], Field(min_length=1, max_length=40)]
    auxiliary: Literal["unknown", "included", "excluded"]

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
    return {"configured": bool(os.getenv("OPENAI_API_KEY", "").strip())}


@app.post("/api/drawing/extract")
async def extract_single_line(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    signature = FILE_TYPES.get(content_type)
    if signature is None:
        raise HTTPException(415, "Choose a PDF, PNG, or JPEG drawing.")

    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_DRAWING_BYTES:
            raise HTTPException(413, "Choose a drawing no larger than 8 MiB.")
        data.extend(chunk)
    if not data.startswith(signature):
        raise HTTPException(422, "The drawing bytes do not match the selected file type.")
    if not drawing_status()["configured"]:
        raise HTTPException(503, "Drawing extraction is unconfigured. Set OPENAI_API_KEY on the server or enter the topology manually.")

    try:
        return await run_in_threadpool(extract_drawing, bytes(data), content_type)
    except ExtractionError as error:
        raise HTTPException(502, str(error)) from error


if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
