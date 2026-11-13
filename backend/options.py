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
from .relay_catalog import HIGH_IMPEDANCE, screen_devices

EVIDENCE = json.loads(Path(__file__).with_name("option_evidence.json").read_text(encoding="utf-8"))
API_OUTPUT_CEILING = 4096
PROMPT = (
    "Propose up to three distinct preliminary protection options using the provided evidence. "
    "Compare separate 87T/87B, separate zones in shared hardware, and combined differential where relevant. "
    "If the POI-side CT is absent and alternatives exist, compare transformer-side breaker and bushing locations, "
    "including breaker/lead coverage and any change to the illustrative 87L overlap. "
    "For each option choose one HV boundary and cite only supplied evidence IDs. "
    "Aim for 300–600 output tokens total. Use fewer when sufficient and exceed the target to finish valid JSON. "
    "Use short phrases, ideally 5–12 words per text field, and cite one evidence ID unless another is needed. "
    "Only include options with a material tradeoff. Skip introductions, repeated facts, CT status, trip lists and "
    "coverage details that the app calculates. In rationale, state the decisive tradeoff. In open_item, "
    "give the single most important unresolved question. Primary covers the transformer with 87T or combined 87TB. "
    "In transformer_main_b_hv, propose the transformer-only 87T secondary HV boundary when both its HV and LV CT banks are available, "
    "otherwise return unresolved. A combined primary still permits 87T secondary when its own CT banks are available. "
    "For shared hardware, consolidate primary protection and 87B only; secondary has a separate IED. "
    "Treat relay feasibility, owner approval, CT core assignments, trip paths and remote 87L data as unresolved. "
    "Do not give settings, invent equipment or claim approved coverage."
)

ShortText = Annotated[str, Field(min_length=1)]


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme: Literal["dedicated", "shared", "combined"]
    hv_boundary: Literal["poi", "breaker_transformer", "bushing"]
    rationale: ShortText
    transformer_main_b_hv: Literal["poi", "breaker_transformer", "bushing", "unresolved"]
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
        "max_tokens": API_OUTPUT_CEILING,
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
        stop_reason = result.get("stop_reason")
        if stop_reason in ("max_tokens", "model_context_window_exceeded"):
            raise OptionsError("Claude ran out of response space before finishing the comparison.")
        if stop_reason == "refusal":
            raise OptionsError("Claude declined to generate protection options for this study.")
        if stop_reason != "end_turn":
            raise OptionsError("Claude stopped before completing the comparison.")
        text = next(part["text"] for part in result["content"] if part["type"] == "text")
        proposal = Proposal.model_validate_json(text)
        if any(set(option.evidence) - evidence.keys() for option in proposal.options):
            raise OptionsError("Claude cited evidence outside the supplied research excerpts.")
        return proposal, result.get("usage", {})
    except (URLError, TimeoutError):
        raise OptionsError("Claude could not generate options. Check the API key, model access, and connection.") from None
    except ValidationError:
        raise OptionsError("Claude completed the response, but it did not match the protection option format.") from None
    except (ValueError, KeyError, StopIteration):
        raise OptionsError("Claude did not return a readable comparison.") from None


def main_coverage(study, option, main_a_analysis):
    zones = {zone["id"]: zone for zone in main_a_analysis["zones"]}
    combined = option.scheme == "combined"
    transformer_a = zones["combined" if combined else "transformer"]
    bus = zones["combined" if combined else "bus"]
    main_b_hv = option.transformer_main_b_hv
    main_b_location = next(
        (boundary for boundary in main_a_analysis["hv_boundaries"] if boundary["id"] == main_b_hv), None
    )
    transformer_b = None
    lv_boundary = zones["transformer"]["boundaries"][1]
    if main_b_hv != "unresolved":
        main_b_analysis = analyze({**study, "hv_boundary": main_b_hv})
        transformer_b = next(zone for zone in main_b_analysis["zones"] if zone["id"] == "transformer")

    return {
        "transformer_a": {"function": "87TB" if combined else "87T", "status": transformer_a["status"]},
        "transformer_b": {
            "function": "87T",
            "hv_boundary": main_b_hv,
            "status": transformer_b["status"] if transformer_b else (
                "Missing measurement" if lv_boundary["state"] == "absent" else "Unresolved"
            ),
            "boundaries": transformer_b["boundaries"] if transformer_b else [lv_boundary],
            "coverage": main_b_location["coverage"] if main_b_location else None,
            "alternatives": [
                boundary["id"] for boundary in main_a_analysis["hv_boundaries"] if boundary["state"] == "present"
            ] if main_b_hv == "unresolved" and lv_boundary["state"] == "present" else [],
        },
        "bus": {"function": "87TB (shared with transformer primary)" if combined else "87B", "status": bus["status"]},
    }


def device_requirements(study, scheme, analysis, coverage=None):
    """Count phase channels for the proposed hardwired layout before model screening."""
    rows = []
    zones = {zone["id"]: zone for zone in analysis["zones"]}
    transformer = zones["transformer"]["boundaries"]
    secondary = coverage["transformer_b"] if coverage else {
        "boundaries": transformer[1:], "hv_boundary": "unresolved",
    }
    secondary_sources = secondary["boundaries"]
    if secondary["hv_boundary"] == "unresolved":
        bushing = next(boundary for boundary in analysis["hv_boundaries"] if boundary["id"] == "bushing")
        secondary_sources = [{"label": f'{bushing["label"]} (candidate)', "state": bushing["state"]}, *secondary_sources]
    signals = {
        "shared": [*transformer, *zones["bus"]["boundaries"][1:]],
        "combined": zones["combined"]["boundaries"],
        "transformer": transformer,
        "bus": zones["bus"]["boundaries"],
        "line": [
            {"label": "Local line phase CT bank", "state": analysis["poi_line"]["local_ct"]},
            {"label": "Remote line phase CT bank · received over the 87L channel", "state": "unknown", "remote": True},
        ] if analysis["poi_line"] else [],
        "meter": [
            {"label": "Revenue metering phase CT bank", "state": "unknown"},
            {"label": "Revenue metering three-phase VT/CCVT bank", "state": "unknown"},
        ],
    }

    def add(kind, role, functions, banks, note, alternate_banks=None, measurement_sources=None):
        row = {
            "kind": kind,
            "role": role,
            "functions": functions,
            "phase_banks": banks,
            "alternate_phase_banks": alternate_banks,
            "note": note,
            "measurement_sources": measurement_sources if measurement_sources is not None else signals[kind],
        }
        scope = analysis["assessment"]["scope"]
        rows.append({**row,
                     "support": "reference" if scope["reference_hardware_supported"] else "unsupported",
                     "note": note if scope["reference_hardware_supported"] else " ".join(reason["message"] for reason in scope["reasons"]),
                     "candidates": screen_devices(row, study["auxiliary"]) if scope["reference_hardware_supported"] else []})

    bus_banks = analysis["counts"]["combined_required_banks"]
    if scheme == "shared":
        add("shared", "Transformer Primary + collector bus", "87T + 87B simultaneously", bus_banks + 1,
            "Lower count assumes both elements can use the same LV incomer input. Higher count uses separate inputs.",
            alternate_banks=bus_banks + 2)
    elif scheme == "combined":
        add("combined", "Transformer Primary + collector bus", "One extended 87TB element", bus_banks,
            "Verify compensation and source mapping for the extended zone.")
    else:
        add("transformer", "Transformer Primary", "87T", 2, "Selected HV CT and transformer LV CT.")
        add("bus", "Collector bus · single path", "87B", bus_banks, "LV incomer, collector boundaries and measured tap if applicable.")

    add("transformer", "Transformer Secondary", "87T", 2,
        "Separate IED. Verify its own HV/LV CT assignments and trip path.", measurement_sources=secondary_sources)
    for area in analysis["feeder_areas"]:
        _, bus_side_ct = area["measurements"]
        add("feeder", area["breaker"], "51P; evaluate 51G/51N and directionality", 1,
            f'Serves {", ".join(area["circuits"])}. Uses the bus-side phase CT bank. Verify the CT core and trip assignment.',
            measurement_sources=[bus_side_ct])
    if study["include_poi_line"]:
        add("line", "POI line · local terminal", "87L", 1,
            "The remote CT bank terminates at the remote relay. Verify the 87L current channel and any required DTT clearing path.")
    add("meter", "Revenue / power-quality meter · proposed POI", "Import/export energy and power quality", 1,
        "Metering CTs and a three-phase VT/CCVT source at the utility-designated metering point.")
    return rows


def generate_options(study):
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        raise OptionsError("Set ANTHROPIC_API_KEY on the server to generate AI protection options.")
    summary = json.dumps(compact_study(study), sort_keys=True, separators=(",", ":"))
    model = os.getenv("RELAY_OPTIONS_MODEL") or "claude-sonnet-4-6"
    proposal, usage = request_options(summary, model)
    return present_options(study, proposal.options, usage)


def preview_options(study):
    boundary = study.get("hv_boundary", "poi")
    return present_options(study, [
        Option(scheme=scheme, hv_boundary=boundary, rationale=rationale,
               transformer_main_b_hv="unresolved", open_item="Confirm independent secondary CT and trip assignments.",
               evidence=evidence)
        for scheme, rationale, evidence in (
            ("dedicated", "Separate transformer and bus protection devices.", ["T_SEPARATE", "B_FULL"]),
            ("shared", "Separate zones share a device for primary and bus protection.", ["SHARED_IED", "B_FULL"]),
            ("combined", "One extended primary differential zone covers transformer and bus.", ["TB_COMBINED"]),
        )
    ], {})


def present_options(study, proposals, usage):
    options = []
    for option in proposals:
        checked = analyze({**study, "hv_boundary": option.hv_boundary})
        candidate = next(item for item in checked["candidates"] if item["id"] == option.scheme)
        boundary = next(item for item in checked["hv_boundaries"] if item["id"] == option.hv_boundary)
        coverage = main_coverage(study, option, checked)
        options.append({
            **option.model_dump(),
            "assessment": checked["assessment"],
            "backup": "Time-graded overcurrent for coordination study. Project applicability remains open.",
            "check": candidate,
            "zones": checked["zones"],
            "main_coverage": coverage,
            "device_requirements": device_requirements(study, option.scheme, checked, coverage),
            "boundary": boundary,
            "poi_line": checked["poi_line"],
            "sources": [ref for key in option.evidence for ref in EVIDENCE[key]["sources"]],
        })
    return {"options": options, "high_impedance_bus": HIGH_IMPEDANCE if analyze(study)["assessment"]["scope"]["reference_hardware_supported"] else [], "usage": {key: usage.get(key) for key in ("input_tokens", "output_tokens")}}
