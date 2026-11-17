#!/usr/bin/env python3
"""SEED/MIGRATION tool for data/products/*.json (schema v2). Canonical data is the JSON, not this script.
Refuses to overwrite an existing record unless --force (used once for the v1->v2 migration).
Generates data/products/*.json and data/grammar.json.

Every product record carries provenance. Nothing here is "ground truth" until a
product's `layout_verified` flag is flipped by tools/promote.py after real SEL-issued
part numbers decode cleanly against it.

Data was extracted from SEL Model Option Table (MOT) PDFs via a text-extraction step that
loses column alignment, so field ORDER / WIDTH are marked with a confidence level.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
(OUT / "products").mkdir(parents=True, exist_ok=True)


def opt(code, desc, extra=False, note=None):
    d = {"code": code, "desc": desc, "extra_cost": extra}
    if note:
        d["note"] = note
    return d


def field(fid, name, options, width=1, conf="medium", note=None, group=None, optional=False):
    f = {"id": fid, "name": name, "width": width, "confidence": conf, "options": options}
    if note:
        f["note"] = note
    if group:
        f["group"] = group
    return f


# ---- shared option sets (PER FAMILY -- never reuse a digit meaning across families) ----
PS_400 = [opt("2", "24-48 Vdc"), opt("4", "48-125 Vdc or 110-120 Vac"),
          opt("6", "125-250 Vdc or 110-240 Vac")]
CTRL_V = [opt("1", "24 Vdc"), opt("2", "48 Vdc"), opt("3", "110 Vdc"),
          opt("4", "125 Vdc"), opt("5", "220 Vdc"), opt("6", "250 Vdc")]
DI_LETTER = {"A": "125 Vdc/Vac", "B": "24 Vdc/Vac", "C": "48 Vdc/Vac",
             "D": "110 Vdc/Vac", "G": "220 Vdc/Vac", "H": "250 Vdc/Vac"}
MOUNT_400 = [opt("H", "Horizontal rack mount"), opt("3", "Horizontal panel mount"),
             opt("V", "Vertical rack mount"), opt("4", "Vertical panel mount")]
DIFF_CH = [opt("A", "Isolated EIA-422", True), opt("B", "Isolated G.703 co-directional", True),
           opt("C", "850 nm IEEE C37.94 fiber", True), opt("D", "1300 nm fiber", True),
           opt("E", "1550 nm fiber", True), opt("H", "1300 nm IEEE C37.94 fiber", True)]


def di_opts(prefix, desc, extra=False):
    return [opt(prefix + k, f"{desc}, DI {v}", extra) for k, v in DI_LETTER.items()]


def ps_700(withdesc="SELect PSIO / 2 DI / 3 DO"):
    out = []
    for p, pd in (("1", "110-250 Vdc, 110-240 Vac, 50/60 Hz"), ("2", "24-48 Vdc")):
        for k, v in DI_LETTER.items():
            out.append(opt(p + k, f"{pd}; {withdesc}; DI {v}"))
    return out


PRODUCTS = {}

# ------------------------------------------------------------------ SEL-451-5
PRODUCTS["SEL-451-5"] = {
    "model": "SEL-451-5", "family": "400-series", "category": "Protection, automation, bay control",
    "prefix": "0451", "prefix_note": "Source header reads '0 4 5 1 5 X'; firmware code 5 is field 1.",
    "source": {"doc_id": "download/7423", "url": "https://selinc.com/api/download/7423",
               "doc_date": None, "method": "WebFetch LLM extraction of MOT PDF"},
    "doc_status": "extracted_unverified", "layout_verified": False,
    "fields": [
        field("firmware", "Firmware", [opt("5", "Standard (replaces SEL-451-2 and -4)")], conf="high"),
        field("power_supply", "Power supply", PS_400, conf="high"),
        field("connector", "Connector type", [opt("1", "Screw terminal block"),
              opt("2", "Connectorized relay", True)], conf="high"),
        field("sec_current", "Secondary input current", [
            opt("1", "1 A phase"), opt("5", "5 A phase"),
            opt("D", "1 A phase with high-impedance fault detection", True),
            opt("E", "5 A phase with high-impedance fault detection", True)], conf="high"),
        field("sec_voltage", "Secondary input voltage", [
            opt("X", "300 V phase-neutral max (wye)"),
            opt("UNRESOLVED", "Euro connector with IEEE C37.92 LEA inputs; code extracted as '1 2' (ambiguous)", True,
                "Also requires conformal coating per MOT footnote (3).")],
            conf="low", note="LEA code could not be extracted reliably; width may be 2."),
        field("eth_protocols", "Ethernet communications protocols", [
            opt("X", "None"), opt("B", "FTP, Telnet, synchrophasors, DNP3 LAN/WAN"),
            opt("C", "FTP, Telnet, synchrophasors, DNP3 LAN/WAN, IEC 61850", True)], conf="high"),
        field("eth_ports", "Ethernet connection options", [
            opt("X", "None"),
            opt("A1", "Ports 5A/5B (PTP-capable): two 10/100BASE-T"),
            opt("A3", "Ports 5A/5B (PTP-capable): two 100BASE-FX"),
            opt("A5", "Ports 5A/5B (PTP-capable): one 10/100BASE-T, one 100BASE-FX"),
            opt("C0", "Ports 5C/5D: two 10/100BASE-T"),
            opt("C2", "Ports 5C/5D: two 100BASE-FX"),
            opt("C4", "Ports 5C/5D: one 10/100BASE-T, one 100BASE-FX")],
            width=None, conf="low",
            note="Codes 1/3/5 belong to ports 5A/5B and 0/2/4 to ports 5C/5D (prefix A/C here is MY label, not SEL's). "
                 "Likely a 2-character field (one digit per port pair); unconfirmed."),
        field("mainboard_input_v", "Main board input voltage", CTRL_V, conf="high",
              note="Main board: 3 HC interrupting outputs, 2 Form A, 3 Form C, 7 optoisolated inputs."),
        field("mounting", "Mounting", MOUNT_400, conf="high"),
        field("chassis", "Chassis", [
            opt("1", "3U, standard I/O"), opt("2", "4U, up to one additional I/O board"),
            opt("3", "4U, front panel with 24 target LEDs, 12 pushbuttons, tri-color LEDs", True),
            opt("6", "5U, up to two additional I/O boards"),
            opt("7", "5U, front panel with 24 target LEDs, 12 pushbuttons, tri-color LEDs", True)], conf="high"),
    ] + [
        field(fid, name, [opt("0", "Empty")] + [
            opt("1", "8 independent inputs, 13 Form A, 2 Form C", True),
            opt("2", "8 optoisolated independent inputs, 13 Form A, 2 Form C", True),
            opt("4", "24 optoisolated level-sensitive inputs, 8 outputs", True),
            opt("5", "8 independent inputs, 8 high-speed HC interrupting Form A", True),
            opt("6", "8 independent inputs, 13 HC interrupting Form A, 2 Form C", True),
            opt("7", "8 optoisolated independent inputs, 13 HC interrupting Form A, 2 Form C", True),
            opt("8", "8 optoisolated independent inputs, 8 high-speed HC interrupting Form A", True)]
            + ([opt("3A", "Aux trip/close pushbuttons, 24 optoisolated inputs, 4 HC interrupting Form A", True),
                opt("7A", "Same as 3A (5U chassis)", True),
                opt("3B", "Aux trip/close pushbuttons with guards, 24 inputs, 4 HC interrupting Form A", True),
                opt("7B", "Same as 3B (5U chassis)", True)] if fid == "io_b" else []),
              width=None if fid == "io_b" else 1, conf="medium",
              note=note)
        for fid, name, note in (
            ("io_b", "I/O board position B (4U/5U)", "Options 3A/3B/7A/7B are 2 chars; required for 4U/5U chassis."),
            ("io_c", "I/O board position C (5U only)", None))
    ] + [
        field("io_b_voltage", "I/O board B input voltage",
              [opt("X", "User-settable pickup")] + CTRL_V, conf="medium",
              note="User-settable only on I/O options 1, 5, 6."),
        field("io_c_voltage", "I/O board C input voltage",
              [opt("X", "User-settable pickup")] + CTRL_V, conf="medium"),
        field("conformal", "Conformal coat", [opt("X", "None"), opt("2", "Conformally coated boards", True)], conf="high"),
        field("front_overlay", "Front overlay", [opt("X", "Standard"), opt("1", "Bay control front overlay")], conf="high"),
    ],
    "constraints": [
        {"id": "451-eth61850-needs-eth", "type": "requires",
         "if": {"field": "eth_protocols", "in": ["B", "C"]}, "then": {"field": "eth_ports", "not_in": ["X"]},
         "confidence": "inferred", "note": "Protocols over Ethernet need a physical Ethernet option. Inferred, not stated in MOT."},
        {"id": "451-chassis-io", "type": "requires",
         "if": {"field": "chassis", "in": ["1"]}, "then": {"field": "io_b", "in": ["0"]},
         "confidence": "inferred", "note": "3U chassis = standard I/O only."},
        {"id": "451-io-c-5u", "type": "requires",
         "if": {"field": "io_c", "not_in": ["0"]}, "then": {"field": "chassis", "in": ["6", "7"]},
         "confidence": "stated", "note": "Position C is 5U only."},
    ],
    "accessories": [
        {"item": "Instruction manual set (SEL-451-5 & SEL-400 series)", "pn": "PM451-KT-01", "in_code": False},
        {"item": "IRIG termination kit (50 ohm)", "pn": "915900499", "in_code": False, "extra_cost": True},
        {"item": "Connectorized wiring harness", "pn": None, "in_code": False,
         "note": "Online MOT / SEL rep required; harness shipped separately."}],
    "open_questions": [
        "Width of sec_voltage and eth_ports fields (1 vs 2 chars).",
        "Whether io_b voltage field is positionally adjacent to io_b or grouped at the end.",
        "LEA voltage code (extracted as '1 2').",
        "Document date unknown; confirm MOT is current (SEL-451-6 also exists)."],
}

# ------------------------------------------------------------------ SEL-411L
PRODUCTS["SEL-411L"] = {
    "model": "SEL-411L", "family": "400-series", "category": "Line current differential + distance",
    "prefix": "0411L", "prefix_note": "Header '0 4 1 1 L X'; trailing X is first variable position.",
    "source": {"doc_id": "download/10530", "url": "https://selinc.com/api/download/10530",
               "doc_date": None, "method": "WebFetch LLM extraction of MOT PDF"},
    "doc_status": "extracted_unverified", "layout_verified": False,
    "fields": [
        field("firmware", "Firmware", [
            opt("0", "Standard current differential and distance"),
            opt("1", "Standard plus sub-cycle distance, series compensation logic, traveling-wave fault location", True),
            opt("A", "Standard current differential and distance, single breaker / three-pole tripping", True)], conf="medium",
            note="Third option extracted as 'A C' -- stray C unresolved."),
        field("conformal", "Conformal coat", [opt("X", "None"), opt("2", "Conformally coated boards", True)], conf="high"),
        field("power_supply", "Power supply", PS_400, conf="high"),
        field("connector", "Connector type", [opt("X", "Screw terminal block"),
              opt("2", "Connectorized relay", True)], conf="medium"),
        field("sec_inputs", "Secondary inputs", [opt("1", "300 V P-N max (wye), 1 A phase"),
              opt("5", "300 V P-N max (wye), 5 A phase")], conf="high"),
        field("eth_protocols", "Ethernet protocols and 87L", [
            opt("X", "None"), opt("B", "FTP, Telnet, synchrophasors, DNP3 LAN/WAN"),
            opt("C", "FTP, Telnet, synchrophasors, DNP3 LAN/WAN, IEC 61850", True)], width=None, conf="low",
            note="Source shows 'X X' for None -- maybe 2 chars."),
        field("eth_ports", "Ethernet connection options", [
            opt("X", "None"), opt("6", "Four 10/100BASE-T", True), opt("7", "Four 100BASE-FX", True),
            opt("8", "Two 10/100BASE-T + two 100BASE-FX", True)], width=None, conf="low"),
        field("diff_ch1", "Line differential channel 1", [opt("0", "None")] + DIFF_CH, width=None, conf="low",
              note="'None' extracted as '0 0' -- width unresolved."),
        field("diff_ch2", "Line differential channel 2", [opt("0", "None")] + DIFF_CH, conf="medium"),
        field("mounting", "Mounting", MOUNT_400, conf="high"),
        field("chassis", "Chassis", [opt("4", "4U, one I/O board"), opt("5", "5U, up to two I/O boards"),
              opt("6", "6U, up to three I/O boards")], conf="medium"),
        field("io_b", "I/O board position B", [
            opt("2", "8 optoisolated inputs, 13 std Form A, 2 std Form C", True),
            opt("7", "8 optoisolated inputs, 13 HC interrupting Form A, 2 std Form C", True),
            opt("C", "24 optoisolated inputs, 2 std + 6 high-speed HC interrupting Form A", True),
            opt("D", "24 optoisolated inputs, 8 std Form A", True),
            opt("E", "8 optoisolated inputs, 8 high-speed HC interrupting Form A", True)], conf="medium",
            note="No 'empty' option listed for B."),
        field("io_b_voltage", "I/O B input voltage", CTRL_V, conf="medium"),
        field("io_c", "I/O board position C (5U/6U)", [opt("0", "Empty")] + [
            opt(o["code"], o["desc"], True) for o in [
                {"code": "2", "desc": "8 optoisolated inputs, 13 std Form A, 2 std Form C"},
                {"code": "7", "desc": "8 optoisolated inputs, 13 HC interrupting Form A, 2 std Form C"},
                {"code": "C", "desc": "24 optoisolated inputs, 2 std + 6 high-speed HC Form A"},
                {"code": "D", "desc": "24 optoisolated inputs, 8 std Form A"},
                {"code": "E", "desc": "8 optoisolated inputs, 8 high-speed HC Form A"}]], conf="medium"),
        field("io_c_voltage", "I/O C input voltage", CTRL_V, conf="medium"),
        field("io_d", "I/O board position D (6U)", [opt("0", "Empty")] + [
            opt(c, d, True) for c, d in (("2", "8 opto inputs, 13 std Form A, 2 std Form C"),
                                         ("7", "8 opto inputs, 13 HC Form A, 2 std Form C"),
                                         ("C", "24 opto inputs, 2 std + 6 high-speed HC Form A"),
                                         ("D", "24 opto inputs, 8 std Form A"),
                                         ("E", "8 opto inputs, 8 high-speed HC Form A"))], conf="medium"),
        field("io_d_voltage", "I/O D input voltage", CTRL_V, conf="medium"),
    ],
    "constraints": [
        {"id": "411L-87L-needs-channel", "type": "requires",
         "if": {"field": "diff_ch1", "in": ["0"]}, "then": {"field": "diff_ch2", "in": ["0"]},
         "confidence": "inferred", "note": "No ch1 + ch2 present makes no sense; 87L needs >=1 channel (MOT fn 2 says 87L needs a serial option)."},
        {"id": "411L-io-c-needs-5u", "type": "requires",
         "if": {"field": "io_c", "not_in": ["0"]}, "then": {"field": "chassis", "in": ["5", "6"]},
         "confidence": "stated", "note": "Position C is 5U/6U only."},
        {"id": "411L-io-d-needs-6u", "type": "requires",
         "if": {"field": "io_d", "not_in": ["0"]}, "then": {"field": "chassis", "in": ["6"]},
         "confidence": "stated", "note": "Position D is 6U only."},
    ],
    "accessories": [
        {"item": "Instruction manual set (SEL-411L & SEL-400 series)", "pn": "PM411L-KT-01", "in_code": False},
        {"item": "Connectorized wiring harness", "pn": None, "in_code": False}],
    "open_questions": [
        "Widths of eth_protocols, eth_ports, diff_ch1 (extracted with doubled characters).",
        "Meaning of trailing X in header '0411LX'.",
        "Firmware 'A' vs stray 'C' in extraction.",
        "Compatible firmware groups for 87L: R101-107, R108-123, R124-125, R126+ (each only with itself).",
        "SEL-411L-A referenced in footnotes but not defined."],
    "firmware_compat": [["R101", "R107"], ["R108", "R123"], ["R124", "R125"], ["R126", None]],
}

# ------------------------------------------------------------------ SEL-751A
slot_cde_cards = (
    [opt("0X", "Empty")]
    + [opt("14" if False else "B" + k, f"3 DI / 4 DO / 1 AO (4-20 mA); DI {v}", False, "Only one per chassis")
       for k, v in DI_LETTER.items()]
    + di_opts("1", "4 DI / 4 DO electromechanical")
    + di_opts("C", "4 DI / 4 DO fast high-current interrupting DO")
    + [opt("5X", "8 AI (+-20 mA or +-10 V jumper selectable)", True),
       opt("6X", "4 AI / 4 AO (jumper selectable)", True, "Only one per chassis")]
    + di_opts("3", "8 DI")
    + di_opts("D", "4 DI / 3 DO (2 Form C, 1 Form B)")
)
PRODUCTS["SEL-751A"] = {
    "model": "SEL-751A", "family": "700-series", "category": "Feeder protection (legacy; SEL-751 is current)",
    "prefix": "0751A", "prefix_note": "Prefix inferred from model naming; document does not show a full template.",
    "source": {"doc_id": "download/3278", "url": "https://selinc.com/api/download/3278",
               "doc_date": None, "method": "WebFetch LLM extraction of MOT PDF"},
    "doc_status": "extracted_unverified", "layout_verified": False,
    "fields": [
        field("firmware", "Firmware / user interface", [
            opt("0", "Standard, no configurable labels"), opt("1", "Standard plus reclosing, no configurable labels"),
            opt("5", "Standard with configurable labels", True),
            opt("6", "Standard plus reclosing with configurable labels", True)], conf="medium"),
        field("slot_a", "Slot A: power supply with 2 DI / 3 DO", ps_700(), width=2, conf="high",
              note="Code = supply digit + DI voltage letter."),
        field("slot_b_proc", "Slot B: processor board", [opt("0", "Standard (EIA-232 front, IRIG-B)"),
              opt("1", "Adds multimode ST fiber serial port", True)], conf="medium"),
        field("slot_b_eth", "Slot B: Ethernet / rear serial", [
            opt("0", "No Ethernet, EIA-232 rear"), opt("1", "No Ethernet, EIA-485 rear"),
            opt("2", "Single 10/100BASE-T, EIA-232 rear", True), opt("3", "Single 10/100BASE-T, EIA-485 rear", True),
            opt("4", "Single 100BASE-FX MM LC, EIA-232 rear", True), opt("6", "Dual 10/100BASE-T, EIA-232 rear", True),
            opt("8", "Dual 100BASE-FX MM LC, EIA-232 rear", True)], conf="high"),
        field("slot_b_proto", "Slot B: protocols", [
            opt("0", "Standard"), opt("1", "Standard + IEC 61850 (needs Ethernet)", True),
            opt("2", "Standard + DNP3", True), opt("3", "Standard + DNP3 + IEC 61850 (needs Ethernet)", True)], conf="high"),
        field("slot_c", "Slot C card", slot_cde_cards + [opt("A0", "Serial communication card EIA-232/485", True)],
              width=2, conf="medium"),
        field("slot_d", "Slot D card", slot_cde_cards + [opt("9X", "10 RTD input", True)], width=2, conf="medium"),
        field("slot_e", "Slot E card", slot_cde_cards + [
            opt("71", "3-phase AC voltage input (300 Vac max)", True),
            opt("72", "3-phase AC voltage + Vsync/Vbat (monitoring package)", True),
            opt("73", "3-phase AC voltage (advanced metering and protection package)", True),
            opt("74", "3-phase AC voltage + 4 arc-flash detection inputs", True),
            opt("75", "3-phase AC voltage + Vsync/Vbat + residual current 5 A IG", True),
            opt("76", "3-phase AC voltage + Vsync/Vbat + residual current 1 A IG", True)], width=2, conf="medium"),
        field("slot_z", "Slot Z: 4 ACI card", [
            opt("81", "1 A phase / 1 A neutral"), opt("82", "1 A phase / 5 A neutral"),
            opt("83", "1 A phase / 2.5 mA high-sense neutral"), opt("84", "1 A phase / 50 mA neutral"),
            opt("85", "5 A phase / 5 A neutral"), opt("86", "5 A phase / 1 A neutral"),
            opt("87", "5 A phase / 2.5 mA high-sense neutral"), opt("88", "5 A phase / 50 mA neutral")],
            width=2, conf="high", note="No 'empty' option listed; presumably mandatory."),
        field("conformal", "Conformal coat", [opt("0", "None"), opt("1", "Conformally coated boards", True)], conf="high"),
    ],
    "constraints": [
        {"id": "751A-61850-needs-eth", "type": "requires",
         "if": {"field": "slot_b_proto", "in": ["1", "3"]}, "then": {"field": "slot_b_eth", "in": ["2", "3", "4", "6", "8"]},
         "confidence": "stated", "note": "IEC 61850 requires Ethernet."},
        {"id": "751A-max-one-3di4do1ao", "type": "max_per_chassis", "fields": ["slot_c", "slot_d", "slot_e"],
         "match_prefix": "B", "max": 1, "confidence": "stated", "note": "Only one 3DI/4DO/1AO card per chassis."},
        {"id": "751A-max-one-4ai4ao", "type": "max_per_chassis", "fields": ["slot_c", "slot_d", "slot_e"],
         "match_prefix": "6X", "max": 1, "confidence": "stated", "note": "Only one 4AI/4AO card per chassis."},
    ],
    "accessories": [
        {"item": "Printed manual", "pn": "PM751A-01", "in_code": False},
        {"item": "Getting started kit", "pn": "915900357", "in_code": False},
        {"item": "Configurable label kit (2 sheet)", "pn": "9260134", "in_code": False},
        {"item": "Configurable label kit (25 sheet)", "pn": "9260135", "in_code": False}],
    "open_questions": [
        "Position boundaries inferred from section order; no full template in source.",
        "Slot B may need processor+Ethernet+protocol digits in different order.",
        "Slot Z mandatory? Slot Z has no 'empty' code.",
        "Arc-flash operate times of 2-5 ms need 4DI/4DO fast HC card (fn 8) -- not enforced as code constraint.",
        "SEL-751A is superseded for new designs by SEL-751 whose current MOT (download/97800) did not text-extract."],
}

# ------------------------------------------------------------------ SEL-710 (legacy doc)
cde_710 = ([opt("0X", "Empty")]
           + [opt("B" + k, f"3 DI / 4 DO / 1 AO; DI {v}", False, "One per chassis") for k, v in DI_LETTER.items()]
           + di_opts("1", "4 DI / 4 DO electromechanical") + di_opts("C", "4 DI / 4 DO fast HC interrupting")
           + [opt("5X", "8 AI", True), opt("6X", "4 AI / 4 AO", True, "One per chassis")]
           + di_opts("3", "8 DI") + di_opts("D", "4 DI / 3 DO (2 Form C, 1 Form B)"))
PRODUCTS["SEL-710"] = {
    "model": "SEL-710", "family": "700-series", "category": "Motor protection (NOT the -5 variant)",
    "prefix": "07100", "prefix_note": "Source: '0 7 1 0 0'; unclear if fixed prefix or variable.",
    "source": {"doc_id": "download/3273", "url": "https://selinc.com/api/download/3273/?lang=en-us",
               "doc_date": "2018-12-07 (WI-5180)", "method": "WebFetch LLM extraction of MOT PDF"},
    "doc_status": "legacy_possibly_superseded", "layout_verified": False,
    "fields": [
        field("slot_a", "Slot A power supply w/ I/O", ps_700(), width=2, conf="high"),
        field("slot_b", "Slot B processor board (3-digit)", [
            opt("000", "EIA-232 rear, IRIG-B"), opt("010", "EIA-485 rear, IRIG-B"),
            opt("020", "EIA-232, IRIG-B, 10/100BASE-T, Modbus TCP", True),
            opt("021", "EIA-232, IRIG-B, 10/100BASE-T, Modbus TCP + IEC 61850", True),
            opt("030", "EIA-485, IRIG-B, 10/100BASE-T, Modbus TCP", True),
            opt("031", "EIA-485, IRIG-B, 10/100BASE-T, Modbus TCP + IEC 61850", True),
            opt("040", "EIA-232, IRIG-B, single 100BASE-FX, Modbus TCP", True),
            opt("041", "EIA-232, IRIG-B, single 100BASE-FX, Modbus TCP + IEC 61850", True),
            opt("060", "EIA-232, IRIG-B, dual 10/100BASE-T, Modbus TCP", True),
            opt("063", "EIA-232, IRIG-B, dual 10/100BASE-T, Modbus TCP + IEC 61850", True),
            opt("080", "EIA-232, IRIG-B, dual 100BASE-FX, Modbus TCP", True),
            opt("083", "EIA-232, IRIG-B, dual 100BASE-FX, Modbus TCP + IEC 61850", True),
            opt("100", "EIA-232, PTC thermistor"), opt("110", "EIA-485, PTC thermistor"),
            opt("120", "EIA-232, PTC, 10/100BASE-T, Modbus TCP", True),
            opt("121", "EIA-232, PTC, 10/100BASE-T, Modbus TCP + IEC 61850", True),
            opt("130", "EIA-485, PTC, 10/100BASE-T, Modbus TCP", True),
            opt("131", "EIA-485, PTC, 10/100BASE-T, Modbus TCP + IEC 61850", True)], width=3, conf="high"),
        field("slot_c", "Slot C card", cde_710 + [opt("A0", "Serial comm card EIA-232/485", True)], width=2, conf="medium"),
        field("slot_d", "Slot D card", cde_710 + [opt("9X", "10 RTD input", True)], width=2, conf="medium"),
        field("slot_e", "Slot E card", cde_710 + [opt("71", "3-phase AC voltage input (300 Vac)", True),
              opt("72", "3 AC current (motor differential) + 3-phase AC voltage", True)], width=2, conf="medium"),
        field("slot_z", "Slot Z: 4 ACI", [
            opt("81", "1 A phase / 1 A neutral"), opt("82", "1 A phase / 5 A neutral"),
            opt("83", "1 A phase / 2.5 mA high-sense neutral"), opt("85", "5 A phase / 5 A neutral"),
            opt("86", "5 A phase / 1 A neutral"), opt("87", "5 A phase / 2.5 mA high-sense neutral")],
            width=2, conf="high"),
        field("conformal", "Conformal coat", [opt("0", "None"), opt("1", "Conformally coated boards", True)], conf="high"),
    ],
    "constraints": [
        {"id": "710-max-one-3di4do1ao", "type": "max_per_chassis", "fields": ["slot_c", "slot_d", "slot_e"],
         "match_prefix": "B", "max": 1, "confidence": "stated", "note": "One 3DI/4DO/1AO card per chassis."},
        {"id": "710-max-one-4ai4ao", "type": "max_per_chassis", "fields": ["slot_c", "slot_d", "slot_e"],
         "match_prefix": "6X", "max": 1, "confidence": "stated", "note": "One 4AI/4AO card per chassis."},
    ],
    "accessories": [{"item": "Printed manual", "pn": "PM710-01", "in_code": False},
                    {"item": "Configurable labels", "pn": "9260134 / 9260135", "in_code": False}],
    "open_questions": [
        "SEL-710-5 (current product; WI-11297) MOT not retrieved -- this doc is the older SEL-710.",
        "Whether '07100' is fixed prefix or variable.",
        "Is Slot Z mandatory?"],
}

# ------------------------------------------------------------------ SEL-311L-0/-6 (legacy)
PRODUCTS["SEL-311L"] = {
    "model": "SEL-311L-0/-6", "family": "300-series", "category": "Line current differential (legacy)",
    "prefix": "0311L", "prefix_note": "Sample code in source '0 3 1 1 L 2 X' not mapped to fields.",
    "source": {"doc_id": "download/3208", "url": "https://selinc.com/api/download/3208/?lang=en-us",
               "doc_date": "2013-03-25", "method": "WebFetch LLM extraction of MOT PDF"},
    "doc_status": "legacy_possibly_superseded", "layout_verified": False,
    "fields": [
        field("firmware", "Firmware", [opt("0", "Standard, three-pole differential + distance"),
              opt("6", "Standard + single-pole differential", True)], conf="medium"),
        field("mounting", "Mounting", [opt("H", "3U horizontal rack"), opt("3", "3U horizontal panel"),
              opt("4", "3U vertical panel"), opt("5", "3U horizontal projection panel", True),
              opt("J", "4U horizontal rack"), opt("K", "4U horizontal panel"), opt("L", "4U vertical panel"),
              opt("N", "4U horizontal projection panel", True)], conf="high"),
        field("diff_channels", "Line differential channel X;Y (2 chars)",
              [opt(c, f"Ch X={c[0]}, Ch Y={c[1]}") for c in
               "A0 AA B0 BB C0 CA CB CC D0 DA DB DC DD E0 EA EB EC ED EE H0 HA HB HC HD HE HH".split()],
              width=2, conf="low", note="X/Y order inferred; only listed combinations are valid."),
        field("power_supply", "Power supply", [opt("2", "24/48 Vdc"), opt("3", "48/125 Vdc or 125 Vac"),
              opt("4", "125/250 Vdc or Vac")], conf="high",
              note="WARNING: digit meanings differ from 400-series (3 here = 48/125, there 4 = 48-125)."),
        field("sec_voltage", "Secondary input voltage", [opt("2", "Wye Va,Vb,Vc 150 Vac max P-N")], conf="high"),
        field("sec_current", "Secondary input current", [opt("1", "1 A phase and polarizing"),
              opt("5", "5 A phase and polarizing")], conf="high"),
        field("control_v", "Control input voltage", CTRL_V, conf="high"),
        field("io_board", "I/O board", [opt("X", "None (3U only)"), opt("2", "8 inputs, 12 std outputs", True),
              opt("5", "8 inputs, 8 high-speed HC outputs", True),
              opt("6", "8 inputs, 12 HC interrupting outputs", True)], conf="medium"),
        field("protocol", "Communications protocol", [opt("X", "SEL ASCII/Fast Meter/MIRRORED BITS etc."),
              opt("1", "DNP3 Level 2 slave", True)], conf="high"),
        field("conformal", "Conformal coat", [opt("X", "None"), opt("2", "Conformal coated boards", True)], conf="high"),
    ],
    "constraints": [
        {"id": "311L-io-needs-4u", "type": "requires",
         "if": {"field": "io_board", "not_in": ["X"]}, "then": {"field": "mounting", "in": ["J", "K", "L", "N"]},
         "confidence": "stated", "note": "Additional I/O requires 4U mounting J/K/L/N."}],
    "accessories": [{"item": "Printed manual", "pn": "PM311L-01", "in_code": False},
                    {"item": "QuickSet CD", "pn": "503001WX4", "in_code": False}],
    "open_questions": ["Sample-code mapping missing; field order inferred.", "SEL-311L-1/-7 MOT (download/3209) not retrieved."],
}

# ------------------------------------------------------------------ stubs for products with partial evidence
STUBS = {
    "SEL-751": {"doc": "download/97800 (WI-9222, 2026-05-20)", "status": "source_not_text_extractable",
                "evidence": ["Datasheet says Slot E card = MOT string digits 12,13; Slot Z card = digits 14,15.",
                             "Relay PARTNUM example from quick manual: 751001B5X1X7086020X (see grammar.json).",
                             "SELect I/O card kit PNs in download/114387 (WI-12625)."]},
    "SEL-487E": {"doc": "no direct MOT link found on docs page", "status": "partial_header_only",
                 "evidence": ["Header '0487E' + firmware 3 (std w/ V,F,dir OC,V/Hz) / 4 (station PMU); power supply 2/4/6 (same as 400-series)."]},
    "SEL-351S": {"doc": "download/4901 (data sheet 5514)", "status": "partial_header_only",
                 "evidence": ["Header '0351S'; firmware 5 (basic) / 6 (standard) / 7 (std + power elements, sag/swell); extra I/O options X/2/4/6."]},
    "SEL-700G": {"doc": "download/7583; I/O cards WI-16209 download/128475", "status": "partial_header_only",
                 "evidence": ["Header '0700G'; model options 700G0 ...; card PNs 9717LA0_, 9719L9X_ etc."]},
}

# ------------------------------------------------------------------ grammar (cross-product, EVIDENCE-TAGGED)
GRAMMAR = {
    "ordering_code_anatomy": {
        "observed": "MOT string = zero-padded model number (0451, 0411L, 0487E, 0351S, 0700G, 07100...) followed by option fields. "
                    "'X' conventionally = None/not selected. '*' in MOT = additional cost. Digits are NOT portable across families.",
        "evidence": ["451/411L/487E/351S/700G headers", "710/751A/787 tables"], "confidence": "high"},
    "family_conventions": [
        {"family": "400-series", "products": ["451", "411L", "487E", "487B", "421", "401"],
         "power_supply": {"2": "24-48 Vdc", "4": "48-125 Vdc / 110-120 Vac", "6": "125-250 Vdc / 110-240 Vac"},
         "control_voltage_digit": {"1": "24", "2": "48", "3": "110", "4": "125", "5": "220", "6": "250"},
         "mounting": {"H": "horizontal rack", "3": "horizontal panel", "V": "vertical rack", "4": "vertical panel"},
         "conformal_coat": {"X": "none", "2": "coated"}, "confidence": "high"},
        {"family": "700-series", "products": ["710", "751A", "751", "787", "700G"],
         "power_supply_with_io": {"1": "110-250 Vdc / 110-240 Vac", "2": "24-48 Vdc"},
         "di_voltage_letter": DI_LETTER, "conformal_coat": {"0": "none", "1": "coated"},
         "slot_model": "Slots A (PSIO), B (CPU/COM), C/D/E (SELect I/O), Z (ACI/AVI)", "confidence": "high"},
        {"family": "300-series (legacy)", "products": ["311L", "311C", "351S"],
         "power_supply": {"2": "24/48 Vdc", "3": "48/125 Vdc or 125 Vac", "4": "125/250 Vdc or Vac"},
         "conformal_coat": {"X": "none", "2": "coated"}, "confidence": "medium"}],
    "cross_family_traps": [
        "Power-supply digit '4' = 48-125 V in 400-series but 125/250 V in 311L; digit '3' = 48/125 V in 311L only.",
        "Conformal coat: X/2 in 400/300-series vs 0/1 in 700-series.",
        "Letters A,B,C,D,G,H = DI voltage in 700-series but card type elsewhere (C = fast HC DO card; A = serial card in slot C; B = 3DI/4DO/1AO).",
        "400-series control voltage digits 1-6 = 24..250 V; DI letters in 700-series use a different alphabet (no E/F)."],
    "select_card_subpart_numbers": {
        "pattern": "97<platform 2 digits> L <MOT slot code> <coat 0|1>   e.g. 9765L1A0 = PSIO 110-250V supply + 125V DI, no coat",
        "evidence_examples": [
            {"pn": "9765L1A_", "desc": "PSIO/2DI/3DO 125/250 Vdc, 125 V DI (2x16 LCD)", "mot_code": "1A", "slot": "A"},
            {"pn": "9765L2C_", "desc": "PSIO/2DI/3DO 24/48 Vdc, 48 V DI (2x16 LCD)", "mot_code": "2C", "slot": "A"},
            {"pn": "9775L1AAB_", "desc": "PSIO for 5-in color touchscreen, 125 V DI", "mot_code": "1A(+AB?)", "slot": "A"},
            {"pn": "9717LA0_", "desc": "Serial comm card EIA-232/485 (Slot C only)", "mot_code": "A0", "slot": "C"},
            {"pn": "9719L9X_", "desc": "10 RTD input (Slot D only)", "mot_code": "9X", "slot": "D"},
            {"pn": "9762L5X_", "desc": "8 AI +-20 mA/+-10 V jumper selectable", "mot_code": "5X", "slot": "C/D/E"},
            {"pn": "9746L70_", "desc": "Vsync/Vbat + arc-flash detection (SELect 2 AVI / 4 AFDI)", "mot_code": "70", "slot": "E"},
            {"pn": "9775L77_", "desc": "8 arc-flash detection inputs (Slot E only)", "mot_code": "77", "slot": "E"},
            {"pn": "9787L81_", "desc": "SEL-787 6 ACI, 1A W1 / 1A W2 (Slot Z)", "mot_code": "81", "slot": "Z"},
            {"pn": "9787L3S71_", "desc": "SEL-787-3S 3 ACI/4 AVI, 1 A winding 3 (Slot E)", "mot_code": "3S71", "slot": "E"},
            {"pn": "9761L2X_", "desc": "8 Form A electromechanical DO", "mot_code": "2X", "slot": "C/D/E"}],
        "trailing_underscore": "'_' = conformal coating digit: 0 without, 1 with (additional cost).",
        "caveat": "The 97xx platform digits vary per relay for the same card type (e.g. RTD = 9719 on 710/751A, 9772 on 787/2411/2414; serial = 9717 vs 9751 on 2411). Needs a per-relay lookup table; only the examples above are evidenced.",
        "confidence": "medium"},
    "relay_partno_string_note": {
        "observation": "SEL-751 quick manual shows relay-stored PART NUM = 751001B5X1X7086020X (19 chars, no leading 0). "
                       "Datasheet puts Slot E at MOT digits 12-13 and Slot Z at 14-15. Counting from the string WITHOUT the leading zero gives E='70', Z='86', "
                       "which fits the 4-ACI Z-card codes seen in other 700-series MOTs. Leading digits '751' + '00' + PS '1B' also fit. "
                       "This is a HYPOTHESIS for validation, not a fact.",
        "implication": "The string stored in the relay may drop the MOT's leading zero. Decide which representation the BOM must carry.",
        "confidence": "low"},
}



# ====================================================================== schema v2 finalisation
BASELINE_COMMIT = "3cda2bcc36450d9bbf6470b7a78ad54d251bcedf"

IDENTITY = {  # model_id -> (variants, variant_resolved)
    "SEL-451-5": (["SEL-451-5"], True), "SEL-411L": (["SEL-411L"], True), "SEL-751A": (["SEL-751A"], True),
    "SEL-710": (["SEL-710"], True), "SEL-311L": (["SEL-311L-0", "SEL-311L-6"], True),
    "SEL-751": (["SEL-751"], False), "SEL-487E": ([], False), "SEL-351S": ([], False), "SEL-700G": ([], False)}

SOURCE_META = {  # kind, revision, date_basis, retrieval
    "SEL-451-5": ("mot_pdf", "WI-8789", "reviewer_reported_2026-11-16_unverified_against_raw_pdf", "llm_summary"),
    "SEL-411L": ("mot_pdf", None, None, "llm_summary"), "SEL-751A": ("mot_pdf", None, None, "llm_summary"),
    "SEL-710": ("mot_pdf", "WI-5180", "extracted_text", "llm_summary"),
    "SEL-311L": ("mot_pdf", None, "extracted_text", "llm_summary"),
    "SEL-751": ("mot_pdf", "WI-9222", "search_snippet", "not_text_extractable"),
    "SEL-487E": ("none", None, None, "not_retrieved"), "SEL-351S": ("datasheet", None, None, "header_only"),
    "SEL-700G": ("datasheet", None, None, "header_only")}

AUTHOR_LABEL_FIELDS = {"SEL-451-5": {"eth_ports"}}      # codes invented by the KB author, not SEL symbols
EXTRA_UNRESOLVED = {
    "SEL-451-5": [
        ("U-451-1", "Exact widths/positions of eth_ports, io_b (3A/3B/7A/7B vs 1-char) and sec_voltage fields.", ["layout"]),
        ("U-451-2", "Literal SEL symbols for Ethernet port options (A1/C0... are KB-author labels) and LEA voltage code.", ["layout"]),
        ("U-451-3", "Allowed FIXED input-voltage symbols per I/O board option and positional symbol for voltage on an EMPTY board.", ["layout", "hardware"]),
        ("U-451-4", "Audit every MOT footnote (LEA/conformal coating, output-class restrictions) into typed rules.", ["hardware"]),
        ("U-451-5", "Confirm the user's actual variant (SEL-451-5 vs other family members) before use; no family substitution.", ["application"])],
    "SEL-411L": [
        ("U-411L-1", "Re-read exact MOT footnote on 87L channel/communications requirements; ordering-only vs application rules.", ["layout", "hardware"]),
        ("U-411L-2", "Peer model, firmware group compatibility, channel medium and remote clearing are application inputs, not ordering data.", ["application"])]}

TYPED_RULES = {
    "SEL-451-5": [
        # Source: MOT WI-8789 (reported rev 20190711) -- user-settable pickup only on I/O options 1, 5, 6.
        {"id": "451-ioB-fixed-voltage-boards", "type": "requires", "scope": "ordering", "confidence": "stated",
         "if": {"field": "io_b", "in": ["2", "3A", "3B", "4", "7", "7A", "7B", "8"]},
         "then": {"field": "io_b_voltage", "not_in": ["X"]},
         "note": "User-settable pickup (X) is only offered on I/O options 1, 5, 6; other boards need a fixed input-voltage code."},
        {"id": "451-ioC-fixed-voltage-boards", "type": "requires", "scope": "ordering", "confidence": "stated",
         "if": {"field": "io_c", "in": ["2", "4", "7", "8"]},
         "then": {"field": "io_c_voltage", "not_in": ["X"]},
         "note": "User-settable pickup (X) is only offered on I/O options 1, 5, 6; other boards need a fixed input-voltage code."}],
    "SEL-411L": [
        {"id": "411L-app-87L-needs-channel", "type": "requires_any", "scope": "application", "confidence": "inferred",
         "when": {"input": "requires_87l", "equals": True},
         "any": [{"field": "diff_ch1", "not_in": ["0"]}, {"field": "diff_ch2", "not_in": ["0"]}],
         "note": "APPLICATION rule: an application that requires 87L needs at least one differential channel. "
                 "Not an ordering restriction: a relay without channels is orderable."}]}
DROP_RULES = {"SEL-411L": {"411L-87L-needs-channel"}}


def finalize(key, p):
    p = json.loads(json.dumps(p))
    p["schema_version"] = 2
    p["model_id"] = key
    for k in ("layout_verified", "doc_status_old"):
        p.pop(k, None)
    variants, resolved = IDENTITY[key]
    p["identity"] = {"manufacturer": "SEL", "model": p.get("model", key), "variants": variants,
                     "variant_resolved": resolved, "hardware_revision": None, "lifecycle": None}
    kind, rev, basis, retrieval = SOURCE_META[key]
    s = p.setdefault("source", {})
    s.update({"kind": kind, "revision": rev, "date_basis": basis, "retrieval": retrieval, "sha256": None,
              "locators_recorded": False})
    if key == "SEL-451-5":
        s["doc_date"] = "2019-07-11"
    p["doc_status"] = "extracted_unverified" if p["fields"] else p.get("doc_status", "stub")
    labels = AUTHOR_LABEL_FIELDS.get(key, set())
    for f in p["fields"]:
        for o in f["options"]:
            o["token_status"] = ("placeholder" if o["code"] == "UNRESOLVED"
                                 else "author_label" if f["id"] in labels and o["code"] != "X" else "extracted")
    cons = [c for c in p["constraints"] if c["id"] not in DROP_RULES.get(key, set())]
    for c in cons:
        c.setdefault("scope", "ordering")
        if "match_prefix" in c:   # explicit codes instead of fuzzy prefix matching
            pre = c.pop("match_prefix")
            ids = set(c["fields"])
            c["match_codes"] = sorted({o["code"] for f in p["fields"] if f["id"] in ids for o in f["options"]
                                       if o["code"].startswith(pre) and o["code"] != "0X"})
    cons += TYPED_RULES.get(key, [])
    p["constraints"] = cons
    unresolved = [{"id": f"Q-{key}-{i}", "text": q, "blocks": ["layout", "hardware"]}
                  for i, q in enumerate(p.pop("open_questions", []), 1)]
    unresolved += [{"id": i, "text": t, "blocks": b} for i, t, b in EXTRA_UNRESOLVED.get(key, [])]
    if not p["fields"]:
        unresolved.append({"id": f"U-{key}-DATA", "text": "Full ordering data not ingested.", "blocks": ["layout", "hardware"]})
    p["unresolved"] = unresolved
    for i, f in enumerate(p["fields"], 1):
        f["order"] = i
    p["provenance_baseline_commit"] = BASELINE_COMMIT
    return p


def main(force=False):
    allp = dict(PRODUCTS)
    for key, s in STUBS.items():
        allp[key] = {"model": key, "doc_status": s["status"], "fields": [], "constraints": [], "accessories": [],
                     "source": {"doc_id": s["doc"]}, "evidence": s["evidence"], "open_questions": []}
    for key, p in allp.items():
        out = OUT / "products" / f"{key}.json"
        if out.exists() and not force:
            print(f"SKIP {key}: exists (canonical data is the JSON; use --force only for a deliberate migration)")
            continue
        out.write_text(json.dumps(finalize(key, p), indent=2, sort_keys=True) + "\n")
    g = OUT / "grammar.json"
    if force or not g.exists():
        g.write_text(json.dumps(GRAMMAR, indent=2, sort_keys=True) + "\n")
    print("wrote", len(allp), "records (schema v2)")


if __name__ == "__main__":
    import sys
    main(force="--force" in sys.argv)
