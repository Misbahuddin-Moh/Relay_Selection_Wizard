"""Preliminary differential-protection screening for a single-MPT collector bus."""

from typing import Any, Optional


def phase_ct_status(count: Optional[int]) -> str:
    if count is None:
        return "unknown"
    return "present" if count > 0 else "absent"


def analyze(study: dict[str, Any]) -> dict[str, Any]:
    """Screen the modeled measurement boundaries and list provisional trip targets."""
    bays = study["bays"]
    hv_ct = study.get("hv_ct", "unknown")
    lv_ct = study.get("lv_ct", "unknown")
    inventory = study.get("ct_inventory")
    if inventory is not None:
        hv_ct = phase_ct_status(inventory["hv_breaker_135"])
        lv_ct = phase_ct_status(inventory["transformer_lv_phase"])
        collector_ct = phase_ct_status(inventory["lv_breaker_246"])
        bays = [{**bay, "ct": collector_ct} for bay in bays]

    auxiliary = study.get("auxiliary", "unknown")
    auxiliary_banks = int(auxiliary == "included")
    combined_banks = 1 + len(bays) + auxiliary_banks

    # Breaker positions determine this preliminary trip list. Outgoing branch
    # count has no bearing on it when several branches share the same breaker.
    trip_targets = ["HV breaker", *(bay["id"] for bay in bays)]
    trip_basis = (
        "Trip targets assume possible backfeed through every modeled collector bay "
        "and no transformer LV main breaker. Confirm actual source paths, "
        "auxiliary isolation, and breaker-failure actions."
    )

    hv_boundary = {"HV breaker POI-side phase CT bank": hv_ct}
    lv_boundary = {"Transformer LV phase CT bank": lv_ct}
    collector_boundaries = {
        f'{bay["id"]} PV circuit-side phase CT bank': bay.get("ct", "unknown")
        for bay in bays
    }
    if auxiliary != "excluded":
        collector_boundaries["Auxiliary tap phase CT bank"] = (
            "present" if auxiliary == "included" else "unknown"
        )
    combined_boundaries = {**hv_boundary, **collector_boundaries}
    separate_boundaries = {**combined_boundaries, **lv_boundary}

    def measurement_finding(boundaries: dict[str, str]) -> tuple[Optional[str], str]:
        absent = [name for name, status in boundaries.items() if status == "absent"]
        if absent:
            return (
                "Missing measurement",
                f"The modeled scheme requires a suitable measurement at {', '.join(absent)}.",
            )

        unknown = [name for name, status in boundaries.items() if status == "unknown"]
        if unknown:
            return "Conditional", f"Confirm {', '.join(unknown)}."
        return None, ""

    separate_status, separate_finding = measurement_finding(separate_boundaries)
    combined_status, combined_finding = measurement_finding(combined_boundaries)

    dedicated_reason = separate_finding or (
        "The modeled CTs provide separate transformer and collector bus boundaries. "
        "The LV CT creates a measurement boundary without providing a local isolation point. "
        "Verify CT performance, zone overlap, and owner requirements."
    )
    shared_reason = " ".join(
        part
        for part in (
            separate_finding,
            "Verify independent transformer and bus functions can run simultaneously "
            "with the intended measurement assignments and trip outputs in the selected IED.",
        )
        if part
    )
    bank_qualifier = "at least " if auxiliary == "unknown" else ""
    combined_reason = " ".join(
        part
        for part in (
            combined_finding,
            f"The combined zone spans the transformer and collector bus and requires "
            f"{bank_qualifier}{combined_banks} three-phase CT banks in this model. "
            "It reduces discrimination between transformer and bus faults. "
            "Verify relay support for grouping, transformer compensation, "
            "external-fault security, and internal-fault sensitivity.",
        )
        if part
    )

    questions = []
    if hv_ct == "unknown":
        questions.append(
            {
                "field": "hv_ct",
                "prompt": "How many phase CTs are on the POI side of the HV breaker?",
                "why": "It establishes the modeled HV measurement boundary and affects coverage around the breaker.",
            }
        )
    if lv_ct == "unknown":
        questions.append(
            {
                "field": "lv_ct",
                "prompt": "Is a suitable phase CT bank available on the transformer LV connection?",
                "why": "The proposed separate bus zone needs a transformer incomer measurement.",
            }
        )
    for bay in bays:
        if bay.get("ct", "unknown") == "unknown":
            questions.append(
                {
                    "field": f'bays.{bay["id"]}.ct',
                    "prompt": f'How many phase CTs are on the PV circuit side of {bay["id"]}?',
                    "why": "Shared breakers and split branches can have different measurement boundaries.",
                }
            )
    if auxiliary == "unknown":
        questions.append(
            {
                "field": "auxiliary",
                "prompt": "How does the auxiliary branch cross the proposed differential boundary?",
                "why": "A separately measured auxiliary boundary adds a phase CT bank to the input budget.",
            }
        )
    if inventory is not None:
        questions.append(
            {
                "field": "ct_inventory.boundaries",
                "prompt": "Which breaker terminal sides and transformer phase CTs serve each protection zone?",
                "why": "Inventory counts describe available CT positions. Confirm the terminal orientation, "
                "actual boundary location, and primary and backup CT assignments before sizing relay inputs.",
            }
        )
        questions.append(
            {
                "field": "ct_inventory.neutral",
                "prompt": "Which transformer winding neutrals are grounded, and how are their CTs assigned?",
                "why": "Verify each neutral CT location and the primary and backup ground differential or "
                "restricted earth fault scheme where applicable. Neutral CTs are separate from the phase bank budget.",
            }
        )
    questions.append(
        {
            "field": "source_paths",
            "prompt": "Which collector branches can supply a fault, and what clears them if a breaker fails?",
            "why": "Trip and breaker-failure actions need to remove every credible fault source.",
        }
    )

    zones = []
    for zone_id, title, boundaries in (
        ("transformer", "Transformer zone", {**hv_boundary, **lv_boundary}),
        ("bus", "Collector bus zone", {**lv_boundary, **collector_boundaries}),
        ("combined", "Combined zone", combined_boundaries),
    ):
        status, _ = measurement_finding(boundaries)
        zones.append({
            "id": zone_id,
            "title": title,
            "status": status or "Boundaries present",
            "boundaries": [{"label": label, "state": state} for label, state in boundaries.items()],
            "trip_targets": trip_targets,
        })

    return {
        "counts": {
            "breakers": len(bays),
            "branches": sum(len(bay["branches"]) for bay in bays),
            "confirmed_bay_cts": sum(bay.get("ct") == "present" for bay in bays),
            "combined_required_banks": combined_banks,
            "combined_phase_channels": 3 * combined_banks,
        },
        "candidates": [
            {
                "id": "dedicated",
                "title": "Separate zones with dedicated relays",
                "status": separate_status or "Baseline candidate",
                "reason": dedicated_reason,
                "trip_targets": trip_targets,
            },
            {
                "id": "shared",
                "title": "Separate zones with shared relay hardware",
                "status": separate_status or "Conditional",
                "reason": shared_reason,
                "trip_targets": trip_targets,
            },
            {
                "id": "combined",
                "title": "Combined transformer and bus zone",
                "status": (
                    "Missing measurement" if combined_status == "Missing measurement" else "Further study"
                ),
                "reason": combined_reason,
                "trip_targets": trip_targets,
            },
        ],
        "questions": questions,
        "trip_basis": trip_basis,
        "zones": zones,
    }
