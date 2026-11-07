"""Generate preliminary options from an anonymized study and curated evidence."""

import json
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .engine import analyze

EVIDENCE = json.loads(Path(__file__).with_name("option_evidence.json").read_text(encoding="utf-8"))
OUTPUT_TOKENS = 1400
PROMPT = (
    "Propose up to three distinct preliminary protection options using the provided evidence. "
    "Compare separate 87T/87B, separate zones in shared hardware, and combined differential where relevant. "
    "If the POI-side CT is absent and alternatives exist, compare transformer-side breaker and bushing locations, "
    "including breaker/lead coverage and any change to the illustrative 87L overlap. "
    "For each option choose one HV boundary and cite only supplied evidence IDs. "
    "Keep all prose fields to one short sentence each. Distinguish Main A/Main B from delayed backup. "
    "Treat relay feasibility, owner approval, CT core assignments, trip paths and remote 87L data as unresolved. "
    "Do not give settings, invent equipment or claim approved coverage."
)

ShortText = Annotated[str, Field(min_length=1, max_length=240)]


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme: Literal["dedicated", "shared", "combined"]
    hv_boundary: Literal["poi", "breaker_transformer", "bushing"]
    rationale: ShortText
    redundancy: ShortText
    backup: ShortText
    open_item: ShortText
    evidence: Annotated[list[str], Field(min_length=1, max_length=3)]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    options: Annotated[list[Option], Field(min_length=1, max_length=3)]


class OptionsError(Exception):
    pass


def compact_study(study):
    result = analyze(study)
    groups = Counter(
        (len(area["circuits"]), *(item["state"] for item in area["measurements"]))
        for area in result["feeder_areas"]
    )
    return {
        "kv": [study["hv_kv"], study["mv_kv"]],
        "selected_hv": study["hv_boundary"],
        "hv_cts": {item["id"]: item["state"] for item in result["hv_boundaries"]},
        "lv_incomer_ct": result["zones"][0]["boundaries"][1]["state"],
        "collector_groups": [
            {"circuits_per_breaker": circuits, "pv_ct": pv, "bus_ct": bus, "breakers": count}
            for (circuits, pv, bus), count in sorted(groups.items())
        ],
        "auxiliary": study["auxiliary"],
        "poi_line": study["include_poi_line"],
    }


def provider_schema():
    schema = Proposal.model_json_schema()
    for fields in (schema["properties"], schema["$defs"]["Option"]["properties"]):
        for field in fields.values():
            for constraint in ("minLength", "maxLength", "minItems", "maxItems"):
                field.pop(constraint, None)
    return schema


@lru_cache(maxsize=32)
def request_options(summary: str, model: str):
    station = json.loads(summary)
    evidence = {key: value for key, value in EVIDENCE.items() if key != "L_87L" or station["poi_line"]}
    payload = {
        "model": model,
        "system": PROMPT,
        "max_tokens": OUTPUT_TOKENS,
        "messages": [{"role": "user", "content": json.dumps({
            "station": station,
            "evidence": {key: value["note"] for key, value in evidence.items()},
        }, separators=(",", ":"))}],
        "output_config": {"format": {"type": "json_schema", "schema": provider_schema()}},
    }
    request = Request("https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json",
        "x-api-key": os.environ["ANTHROPIC_API_KEY"].strip(),
        "anthropic-version": "2023-06-01",
    })
    try:
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
        text = next(part["text"] for part in result["content"] if part["type"] == "text")
        proposal = Proposal.model_validate_json(text)
        if result.get("stop_reason") != "end_turn" or any(
            set(option.evidence) - evidence.keys() for option in proposal.options
        ):
            raise OptionsError("Claude returned incomplete options or unsupported evidence references.")
        return proposal, result.get("usage", {})
    except (URLError, TimeoutError):
        raise OptionsError("Claude could not generate options. Check the API key, model access, and connection.") from None
    except (ValidationError, ValueError, KeyError, StopIteration):
        raise OptionsError("Claude returned an incomplete or invalid option comparison.") from None


def generate_options(study):
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        raise OptionsError("Set ANTHROPIC_API_KEY on the server to generate AI protection options.")
    summary = json.dumps(compact_study(study), sort_keys=True, separators=(",", ":"))
    model = os.getenv("RELAY_OPTIONS_MODEL") or "claude-sonnet-4-6"
    proposal, usage = request_options(summary, model)
    options = []
    for option in proposal.options:
        checked = analyze({**study, "hv_boundary": option.hv_boundary})
        candidate = next(item for item in checked["candidates"] if item["id"] == option.scheme)
        boundary = next(item for item in checked["hv_boundaries"] if item["id"] == option.hv_boundary)
        options.append({
            **option.model_dump(),
            "check": candidate,
            "boundary": boundary,
            "poi_line": checked["poi_line"],
            "sources": [ref for key in option.evidence for ref in EVIDENCE[key]["sources"]],
        })
    return {"options": options, "usage": {key: usage.get(key) for key in ("input_tokens", "output_tokens")}}
