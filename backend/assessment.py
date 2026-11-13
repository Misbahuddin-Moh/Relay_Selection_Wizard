"""Versioned preliminary evidence and scope; never a purchasing approval."""
import hashlib
import json

POLICY_VERSION = "reference-alpha-1"
CT_KEYS = (
    "lv_breaker_135", "lv_breaker_246", "hv_breaker_135", "hv_breaker_246",
    "transformer_hv_phase", "transformer_lv_phase", "transformer_hv_neutral", "transformer_lv_neutral",
)


def assess(study):
    inventory = study.get("ct_inventory") or {}
    provenance = study.get("ct_provenance") or {}
    facts = []
    for key in CT_KEYS:
        value = inventory.get(key)
        evidence = provenance.get(key) or {}
        # Evidence belongs to a particular value. An old sidecar cannot confirm an edit.
        matches = evidence.get("value") == value and "value" in evidence
        facts.append({
            "subject": key, "value": value,
            "unit": "CTs per winding neutral" if "neutral" in key else "CTs per phase",
            "origin": evidence.get("origin", "unknown") if matches else "unknown",
            "revision": evidence.get("revision") if matches else None,
            "review_state": "unreviewed",
        })
    reasons = []
    if len(study["bays"]) != 3:
        reasons.append({"code": "COLLECTOR_BREAKER_COUNT_OUTSIDE_REFERENCE",
                        "message": "Reference hardware screening covers three collector breakers only. Save this layout as a draft; its hardware configuration requires separate engineering."})
    if study.get("auxiliary") == "included":
        reasons.append({"code": "MEASURED_AUXILIARY_POLICY_UNREVIEWED",
                        "message": "The measured auxiliary tap needs a reviewed measurement and clearing policy before reference hardware screening."})
    canonical = json.dumps({"study": study, "policy": POLICY_VERSION}, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {
        "schema_version": 1, "policy_version": POLICY_VERSION,
        "input_fingerprint": hashlib.sha256(canonical.encode()).hexdigest(),
        "facts": facts,
        "scope": {"reference_hardware_supported": not reasons, "reasons": reasons,
                  "topology_basis": "One transformer, straight collector bus, no LV main; requires engineering confirmation."},
        "budget_completeness": "partial", "code_status": "not_generated",
        "independence_status": "unverified", "engineering_approval": "unavailable",
    }
