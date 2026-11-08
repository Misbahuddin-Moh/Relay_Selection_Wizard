"""Manufacturer evidence for preliminary role screening, not order-code approval."""

SEL_487E = "https://selinc.com/api/download/99384/"
GE_T60 = "https://www.gevernova.com/electrification/automation/protection-control-metering/transformer-protection/multilin-t60"
GE = "https://www.gevernova.com/electrification/automation/protection-control-metering/"

# Each entry tracks the role separately from the published analog channel ceiling.
# None means the exact hardware capacity has not been encoded for this role.
CATALOG = {
    "transformer": [
        ("GE", "Multilin T60", "Documented function", None, "Verify installed CT/VT modules and REF inputs.", GE_T60),
        ("GE", "Multilin 845", "Documented function", None, "Verify winding and CT configuration.", GE + "transformer-protection/multilin-845"),
        ("SEL", "SEL-787 family", "Documented function", None, "Select a variant with the required winding, neutral CT and trip I/O allocation.", "https://selinc.com/products/787/"),
        ("SEL", "SEL-487E-3/-4", "Documented function", None, "Verify the exact current/voltage and neutral terminal allocation.", SEL_487E),
    ],
    "bus": [
        ("GE", "Multilin B30", "Documented function", 18, "Conventional CT screening ceiling. Verify module and I/O allocation.", GE + "bus-protection/multilin-b30"),
        ("GE", "Multilin B90", "Documented function", 24, "Single-IED application ceiling. Verify module and I/O allocation.", GE + "bus-protection/multilin-b90"),
        ("SEL", "SEL-487B-1", "Documented function", 21, "Seven three-phase bus terminals. Verify the exact wiring and trip allocation.", "https://selinc.com/api/download/2842/"),
    ],
    "shared": [
        ("GE", "Multilin T60 v8.60", "Unverified application", None, "The optional second element is documented as 87T. Simultaneous 87T + 87B remains unverified.", "https://www.gevernova.com/grid-solutions/sites/default/files/2025-05/GER-4977B_2.pdf"),
        ("SEL", "SEL-487E-4 with optional 87B", "Conditional configuration", None, "Verify optional 87B, LV input reuse, and neutral/VT terminal allocation.", SEL_487E),
    ],
    "combined": [
        ("GE", "Multilin T60", "Unverified application", None, "Verify the order code and source grouping for this extended zone.", "https://www.gevernova.com/electrification/node/49435"),
        ("SEL", "SEL-487E-4", "Unverified application", None, "Verify compensation, source grouping and security for this extended zone.", SEL_487E),
    ],
    "feeder": [
        ("GE", "Multilin F60", "Documented function", None, "Verify phase, ground and directional sensing options.", GE + "feeder-protection/multilin-f60"),
        ("GE", "Multilin 850", "Documented function", None, "Verify the feeder input and bay-control requirements.", GE + "feeder-protection/multilin-850"),
        ("SEL", "SEL-751", "Documented function", None, "Check the current/voltage card for the required directional elements.", "https://selinc.com/api/download/10734/"),
        ("SEL", "SEL-451", "Documented function", None, "Screen for feeder overcurrent and bay control; verify the exact settings and I/O.", "https://selinc.com/products/451/"),
    ],
    "line": [
        ("GE", "Multilin L90", "Documented function", None, "Verify remote relay compatibility, differential channel, and terminal configuration.", GE + "line-protection/multilin-l90"),
        ("SEL", "SEL-411L", "Documented function", 6, "Six local current inputs. Verify the remote relay and differential channel.", "https://selinc.com/products/411l/specs/"),
    ],
    "meter": [
        ("GE", "Multilin EPM 7000P", "Documented function", None, "Verify the utility-approved model, accuracy and metering point.", GE + "epm-7000p"),
        ("GE", "Multilin EPM 9900P", "Documented function", None, "Verify the utility-approved model, accuracy and metering point.", GE + "epm-9900p"),
        ("SEL", "SEL-735", "Documented function", None, "Verify metering CTs and matching VT/CCVT source at the approved point.", "https://selinc.com/products/735/"),
    ],
}

HIGH_IMPEDANCE = [
    {"manufacturer": "SEL", "model": "SEL-587Z", "legacy": True, "source": "https://selinc.com/products/587z/"},
    {"manufacturer": "SEL", "model": "SEL-787Z + SEL-HZM", "source": "https://selinc.com/products/comparisons/587z-787z-comparison/"},
    {"manufacturer": "GE", "model": "Multilin MIB", "source": "https://www.gevernova.com/grid-solutions/sites/default/files/2025-02/ger-4632.pdf"},
]


def sel_487e_allocations(minimum, maximum):
    # Dual AC cards. S/T/U/W/X provide five phase banks; V is a VT bank.
    # SEL-487E-3/-4 data sheet, Models and Options / Current Channel Options.
    return [
        {
            "y": "Phase bank (matching ratings)" if y_phase else "Neutral channels",
            "z": "Phase bank" if z_phase else "VT bank",
            "phase_banks": banks,
            "neutral_inputs": 0 if y_phase else 3,
            "vt_banks": 1 if z_phase else 2,
            "fit": "All listed phase cases" if banks >= maximum else (
                "Lower phase demand only" if banks >= minimum else "Insufficient phase banks"
            ),
        }
        for y_phase, z_phase in ((False, False), (False, True), (True, False), (True, True))
        for banks in (5 + int(y_phase) + int(z_phase),)
    ]


def screen_devices(row, auxiliary):
    minimum = 3 * row["phase_banks"]
    maximum = 3 * (row["alternate_phase_banks"] or row["phase_banks"])
    if auxiliary == "unknown" and row["kind"] in ("bus", "shared", "combined"):
        maximum += 3

    results = []
    for manufacturer, model, status, ceiling, note, source in CATALOG[row["kind"]]:
        allocations = sel_487e_allocations(minimum // 3, maximum // 3) if source == SEL_487E else []
        if allocations:
            capacity = "See dual-card terminal allocation"
        elif ceiling is None:
            capacity = "Exact phase-input allocation pending"
        elif minimum > ceiling:
            capacity = f"Exceeds published {ceiling}-input ceiling"
        elif maximum > ceiling:
            capacity = f"Some allocations exceed published {ceiling}-input ceiling"
        else:
            capacity = f"Within published {ceiling}-input ceiling; verify allocation"
        results.append({
            "manufacturer": manufacturer, "model": model, "status": status,
            "capacity": capacity, "note": note, "source": source, "allocations": allocations,
        })
    return results
