"""Generate the SkyShield development dataset.

Writes CSV files to database/data/:
  users.csv, incidents.csv, measures.csv, ai_summaries.csv, status_history.csv

All data is synthetic. Airports and aircraft types are real; operators are
fictional so no record implies an event at a real airline.

Usage:  python database/generate_dataset.py
"""
import csv
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

import bcrypt  # noqa: E402
from app.core.taxonomy import AIRCRAFT_TYPES, AIRPORTS, CATEGORIES, OPERATORS  # noqa: E402
from app.services.policy_parser import parse_policy  # noqa: E402

rng = random.Random(42)
IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=IST)
START = datetime(2024, 1, 1, tzinfo=IST)
OUT = ROOT / "data"
DEMO_PASSWORD = "Password@123"

# ----------------------------------------------------------------- users
USERS = [
    ("admin@skyshield.example", "Meera Krishnan", "admin", "Head of Safety", "DEL"),
    ("arjun.mehta@skyshield.example", "Arjun Mehta", "safety_officer", "Safety Officer", "DEL"),
    ("kavya.reddy@skyshield.example", "Kavya Reddy", "safety_officer", "Safety Officer", "HYD"),
    ("sanjay.bose@skyshield.example", "Sanjay Bose", "safety_officer", "Senior Safety Officer", "BOM"),
    ("rohit.sharma@skyshield.example", "Capt. Rohit Sharma", "reporter", "Captain", "DEL"),
    ("ananya.iyer@skyshield.example", "Ananya Iyer", "reporter", "First Officer", "BLR"),
    ("vikram.singh@skyshield.example", "Capt. Vikram Singh", "reporter", "Captain", "BOM"),
    ("priya.nair@skyshield.example", "Priya Nair", "reporter", "Cabin Crew Lead", "COK"),
    ("rahul.verma@skyshield.example", "Rahul Verma", "reporter", "Aircraft Maintenance Engineer", "DEL"),
    ("sneha.patil@skyshield.example", "Sneha Patil", "reporter", "First Officer", "PNQ"),
    ("imran.khan@skyshield.example", "Imran Khan", "reporter", "Ramp Supervisor", "HYD"),
    ("deepa.menon@skyshield.example", "Deepa Menon", "reporter", "Aircraft Maintenance Engineer", "MAA"),
    ("amit.das@skyshield.example", "Amit Das", "reporter", "Captain", "CCU"),
    ("neha.joshi@skyshield.example", "Neha Joshi", "reporter", "Cabin Crew", "AMD"),
    ("karan.malhotra@skyshield.example", "Karan Malhotra", "reporter", "First Officer", "GAU"),
    ("meera.krishnan@skyshield.example", "Meera Krishnan", "reporter", "Cabin Crew", "TRV"),  # edge: duplicate-looking name
]
OFFICER_IDS = [2, 3, 4]
REPORTER_IDS = list(range(5, len(USERS) + 1))

# ----------------------------------------------------------------- incident templates
# category: (weight, phases, [(title, description)], [analysis])
T = {
    "wildlife_strike": (18, ["takeoff", "initial_climb", "approach", "landing"], [
        ("Bird strike on {phase_txt} at {code}",
         "During {phase_txt} on runway {rwy} at {city}, a flock of birds was seen ahead. A loud thud was heard on the {part}. "
         "{engine_note} The crew continued and landed normally. Blood and feather remains were found on the {part} during the walk-around."),
        ("Suspected bird ingestion, {type} {reg}",
         "Passing about {alt} ft after take-off from {city}, the crew felt a brief vibration and smelt a burning odour in the cabin. "
         "{engine_note} ATC was informed and the aircraft returned to {code}."),
    ], [
        "Strike confirmed by remains on the {part}. Time of day and location match the known high bird activity near the runway {rwy} approach path. "
        "Engine parameters {eng_state}. Airport wildlife unit to be engaged.",
    ]),
    "technical_defect": (16, ["climb", "cruise", "descent", "parked"], [
        ("{system} caution in {phase_txt}, {reg}",
         "In {phase_txt} on flight {flight} from {city}, the {system} caution appeared on the display. The crew followed the checklist. "
         "{tech_note} The aircraft landed safely and the defect was entered in the tech log."),
        ("Repeat {system} defect on {reg}",
         "The {system} fault reappeared on {reg} for the third time this month. The last two entries were closed after a reset. "
         "{tech_note}"),
    ], [
        "Defect history shows {repeat} similar entries on this aircraft in the last 30 days. Root cause points to a worn component that was reset rather than replaced. "
        "Reliability review required.",
    ]),
    "turbulence": (12, ["cruise", "descent", "climb"], [
        ("Turbulence injury on flight {flight}",
         "While in {phase_txt} at FL{fl} near {city}, the aircraft entered unexpected turbulence close to a cumulonimbus cell. "
         "The seat belt sign was {belt}. {inj} passengers and one cabin crew member had minor injuries in the aft galley."),
        ("Severe turbulence encounter near {city}",
         "Monsoon convective activity was reported along the route. The aircraft encountered severe turbulence for about 40 seconds at FL{fl}. "
         "Overhead bins opened and a meal cart moved. {inj} passengers were checked by medical staff on arrival."),
    ], [
        "Weather radar picture showed cells along track; deviation was requested late. Seat belt sign timing is a contributing factor. "
        "Structural inspection is needed if the load factor was exceeded.",
    ]),
    "ramp_safety": (12, ["parked", "pushback", "taxi"], [
        ("Ground equipment contact at {code} stand {stand}",
         "During turnaround at stand {stand}, {city}, a {gse} touched the {gse_part} of {reg}. The impact left a dent. "
         "The flight was delayed for inspection. No wing walker was present at the time."),
        ("Pushback incident at {code}",
         "During pushback from stand {stand}, the tow bar shear pin broke and the aircraft rolled forward slightly. "
         "The headset operator stopped the pushback. No injuries. Apron lighting at the stand was poor."),
        ("Fuel spill on stand {stand}, {code}",
         "A fuel spill of about 30 litres occurred during refuelling of {reg} at stand {stand}. The refueller stopped the flow and the fire service was called."),
    ], [
        "Turnaround was running 15 minutes late. Equipment restraint area rules were not followed and the marshaller was handling two stands. "
        "Ground equipment must be inspected before reuse.",
    ]),
    "weather": (10, ["approach", "landing", "go_around"], [
        ("Windshear warning on approach to {code}",
         "On approach to runway {rwy} at {city}, a windshear warning sounded at {alt} ft. The crew performed the escape manoeuvre and diverted after a second attempt."),
        ("Go-around in fog at {code}",
         "Visibility at {city} dropped below CAT I minima during the approach. The crew carried out a go-around and held for 35 minutes before landing."),
        ("Lightning strike near {city}",
         "The aircraft was struck by lightning during descent through cloud near {city}. A loud bang and flash were noted. All systems remained normal."),
    ], [
        "METAR showed the weather deteriorating faster than forecast. Crew decision making was appropriate. Inspection for lightning or hail damage applies.",
    ]),
    "runway_incursion": (8, ["taxi", "takeoff", "landing"], [
        ("Runway incursion at {code} holding point {hp}",
         "At {city}, {reg} crossed holding point {hp} and entered runway {rwy} while another aircraft was on short final. ATC instructed a go-around for the landing traffic. "
         "The crew stated they understood the clearance as line-up."),
        ("Vehicle on runway strip at {code}",
         "A follow-me vehicle entered the runway {rwy} strip without clearance during low visibility at {city}. An aircraft on approach was asked to go around."),
    ], [
        "Readback of the clearance was incomplete and not corrected by ATC. Holding point {hp} is a known hotspot with poor signage.",
    ]),
    "deficient_maintenance": (7, ["parked", "takeoff", "climb"], [
        ("{panel} found open after maintenance on {reg}",
         "During the pre-flight walk-around at {city}, the {panel} was found unlatched on {reg}. The aircraft had come out of overnight maintenance."),
        ("Wrong part fitted to {reg}",
         "During a scheduled check, engineers found that a {system} component with the wrong part number had been fitted during the last maintenance visit."),
    ], [
        "Task was split across two night shifts and the handover log was incomplete. No independent inspection was carried out. Fatigue may be a factor.",
    ]),
    "engine_shutdown": (5, ["climb", "cruise"], [
        ("In-flight engine shutdown on {reg}",
         "In {phase_txt} after departure from {city}, engine {eng} showed high oil temperature and low oil pressure. The crew shut down the engine and returned to {code} for a single-engine landing."),
    ], [
        "Oil system indications preceded the shutdown by 6 minutes. Trend monitoring shows a slow oil pressure decline over the last ten flights.",
    ]),
    "mid_air_collision": (5, ["climb", "descent", "approach"], [
        ("TCAS RA during {phase_txt} near {city}",
         "During {phase_txt} near {city}, a TCAS resolution advisory was received against traffic at the same level. The crew followed the RA and reported it to ATC. Minimum vertical separation was about 400 ft."),
        ("Level bust on departure from {code}",
         "After departure from {city}, the aircraft climbed through the cleared level of FL{fl} by 300 ft. ATC issued a traffic alert."),
    ], [
        "Altitude selector was set to the wrong level after a late clearance change. Cross-check between pilots did not catch it.",
    ]),
    "runway_excursion": (5, ["landing", "takeoff"], [
        ("Runway veer-off on landing at {code}",
         "After landing on wet runway {rwy} at {city} in heavy rain, the aircraft drifted to the right and the right main gear went off the paved surface for about 50 m. Two runway edge lights were damaged."),
        ("Long landing and overrun risk at {code}",
         "The aircraft touched down about 900 m beyond the threshold on runway {rwy} at {city} with a tailwind. Maximum braking stopped the aircraft 80 m from the runway end."),
    ], [
        "Approach was not stabilised at 1,000 ft and no go-around was called. Runway was wet with standing water; landing distance was not recalculated.",
    ]),
    "laser_interference": (4, ["approach", "landing"], [
        ("Laser attack on approach to {code}",
         "On final approach to runway {rwy} at {city} at about {alt} ft, a green laser beam illuminated the cockpit for several seconds. The first officer reported eye discomfort."),
    ], [
        "Location matches previous laser reports near the approach path. Crew exposure requires a medical check before next duty.",
    ]),
    "crew_incapacitation": (3, ["cruise", "descent"], [
        ("First officer unwell in flight, {flight}",
         "During cruise, the first officer reported severe nausea and dizziness and was unable to continue duties. The captain declared an emergency and landed at {city}."),
    ], [
        "Both pilots ate different meals. Roster shows four early starts in the last five days, suggesting fatigue as a contributing factor.",
    ]),
    "loss_of_control": (3, ["climb", "cruise", "approach"], [
        ("Stick shaker activation in {phase_txt}",
         "During {phase_txt} near {city}, airspeed decayed after an autopilot mode change and the stick shaker activated briefly. The crew recovered and continued."),
    ], [
        "Autothrust mode change was not noticed. Flight data shows speed dropping 12 kt below the minimum for 8 seconds.",
    ]),
    "medical_emergency": (4, ["cruise"], [
        ("Passenger cardiac emergency on {flight}",
         "A passenger collapsed in seat {seat}. A doctor on board assisted and the defibrillator was used. The aircraft diverted to {city}."),
    ], [
        "Cabin crew response followed procedure. Medical kit and defibrillator need replenishment.",
    ]),
    "cfit": (2, ["approach", "descent"], [
        ("EGPWS terrain warning on approach to {code}",
         "During a non-precision approach to {city} at night, the EGPWS 'TERRAIN, PULL UP' warning sounded. The crew climbed immediately and made a second approach."),
    ], [
        "Descent was started early using the wrong distance reference. Minimum sector altitude was not briefed.",
    ]),
    "other": (3, ["parked", "cruise", "taxi"], [
        ("Unruly passenger on {flight}",
         "A passenger refused to follow crew instructions and became abusive. The captain was informed and security met the aircraft at {city}."),
        ("Power bank smoke in cabin bag",
         "Smoke came from a power bank in a cabin bag in row {row}. Cabin crew used the fire containment bag. Flight continued to {city}."),
    ], [
        "Crew handled the event as per the cabin crew manual. Witness statements collected.",
    ]),
}

FILL = {
    "part": ["nose radome", "left engine inlet", "right wing leading edge", "windshield", "nose landing gear"],
    "engine_note": [
        "Engine parameters stayed normal.",
        "The No. 2 engine showed a short spike in vibration.",
        "A slight rise in exhaust gas temperature was noted on engine 1.",
    ],
    "eng_state": ["stayed within limits", "showed a vibration spike", "showed a small EGT rise"],
    "system": ["hydraulic system B", "pack 1", "bleed air", "yaw damper", "fuel quantity indication", "generator 2", "cabin pressure controller"],
    "tech_note": [
        "The defect was not reproduced on ground.",
        "The component was replaced after landing.",
        "The aircraft was dispatched under the MEL.",
    ],
    "gse": ["catering truck", "baggage belt loader", "passenger step", "water service truck"],
    "gse_part": ["forward cargo door", "aft passenger door", "left wing tip", "engine cowling"],
    "panel": ["fan cowl latch", "fuel tank access panel", "oil filler cap", "cargo door"],
    "inj": ["Two", "Three", "Four", "Five"],
    "belt": ["off", "switched on only seconds before"],
    "hp": ["A3", "B2", "C1", "N5", "S2"],
}
PHASE_TEXT = {
    "parked": "ground operations", "pushback": "pushback", "taxi": "taxi", "takeoff": "take-off",
    "initial_climb": "initial climb", "climb": "climb", "cruise": "cruise", "descent": "descent",
    "approach": "approach", "landing": "landing", "go_around": "go-around",
}

NOT_APPLIED_REASONS = [
    "Airport operator has not responded yet; follow-up raised.",
    "Simulator slot not available until next quarter.",
    "Not applicable to this aircraft type.",
    "Part on order from manufacturer; expected in three weeks.",
    "Crew already completed this training last month.",
    "Covered by existing company circular.",
]

SEVERITY_WEIGHTS = {"incident": 75, "serious_incident": 22, "accident": 3}
ACCIDENT_OK = {"runway_excursion", "turbulence", "ramp_safety"}


def load_policies() -> dict[str, list[tuple[str, str, str]]]:
    """category -> [(priority, text, section_ref)]"""
    out: dict[str, list[tuple[str, str, str]]] = {}
    for path in sorted((ROOT / "policies").glob("*.md")):
        p = parse_policy(path.read_text(encoding="utf-8"))
        key = p.category or "general"
        for ch in p.chunks:
            for prio, text in ch.measures:
                out.setdefault(key, []).append((prio, text, ch.section_ref))
    return out


def pick(key: str) -> str:
    return rng.choice(FILL[key])


def fmt(template: str, ctx: dict) -> str:
    return template.format(**ctx)


def random_date() -> datetime:
    span = (NOW - START).total_seconds()
    return START + timedelta(seconds=rng.random() * span)


def reg() -> str:
    letters = "ABCDEFGHIJKLMNOPRSTUVWXYZ"
    return "VT-" + "".join(rng.choice(letters) for _ in range(3))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    policies = load_policies()

    pw_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()
    users_rows = [
        {"id": i, "email": e, "full_name": n, "role": r, "designation": d, "base_station": b,
         "password_hash": pw_hash, "is_active": True}
        for i, (e, n, r, d, b) in enumerate(USERS, start=1)
    ]

    cats = list(T.keys())
    weights = [T[c][0] for c in cats]
    total = 180
    dates = sorted(random_date() for _ in range(total))

    incidents, measures, summaries, history = [], [], [], []
    seq_by_year: dict[int, int] = {}
    mid = sid = hid = 0

    for idx, occurred in enumerate(dates, start=1):
        cat = rng.choices(cats, weights)[0]
        _, phases, templates, analyses = T[cat]
        phase = rng.choice(phases)
        code = rng.choice(list(AIRPORTS))
        op = rng.choice(list(OPERATORS))
        ctx = {
            "code": code, "city": AIRPORTS[code][1], "phase_txt": PHASE_TEXT[phase],
            "reg": reg(), "type": rng.choice(AIRCRAFT_TYPES),
            "flight": f"{op}{rng.randint(100, 989)}", "rwy": f"{rng.randint(9, 32):02d}{rng.choice(['', 'L', 'R'])}",
            "alt": rng.choice([400, 800, 1200, 1500, 2500]), "fl": rng.choice([180, 240, 310, 350, 370]),
            "stand": rng.randint(11, 64), "eng": rng.choice([1, 2]), "seat": f"{rng.randint(3, 30)}{rng.choice('ABCDEF')}",
            "row": rng.randint(3, 30), "repeat": rng.choice([2, 3, 4]),
            **{k: pick(k) for k in FILL},
        }
        title_t, desc_t = rng.choice(templates)
        title, description = fmt(title_t, ctx), fmt(desc_t, ctx)
        title = title[0].upper() + title[1:]

        year = occurred.year
        seq_by_year[year] = seq_by_year.get(year, 0) + 1
        reference = f"SKY-{year}-{seq_by_year[year]:04d}"
        reporter = rng.choice(REPORTER_IDS)
        reported_at = occurred + timedelta(hours=rng.randint(1, 30))

        age = (NOW - occurred).days
        if age > 60:
            status = rng.choices(["closed", "measures_pending", "under_review"], [88, 9, 3])[0]
        elif age > 14:
            status = rng.choices(["closed", "measures_pending", "under_review", "submitted"], [45, 35, 12, 8])[0]
        else:
            status = rng.choices(["measures_pending", "under_review", "submitted"], [35, 30, 35])[0]

        officer = rng.choice(OFFICER_IDS) if status != "submitted" else None
        severity = None
        analysis = None
        closed_at = None
        closing_note = None
        t_review = reported_at + timedelta(hours=rng.randint(2, 48))
        t_analysis = t_review + timedelta(hours=rng.randint(4, 72))
        t_close = t_analysis + timedelta(days=rng.randint(3, 30))

        hid += 1
        history.append({"id": hid, "incident_id": idx, "from_status": "", "to_status": "submitted",
                        "changed_by_id": reporter, "note": "Report filed", "changed_at": reported_at.isoformat()})
        if status in ("under_review", "measures_pending", "closed"):
            hid += 1
            history.append({"id": hid, "incident_id": idx, "from_status": "submitted", "to_status": "under_review",
                            "changed_by_id": officer, "note": "Review started", "changed_at": t_review.isoformat()})

        if status in ("measures_pending", "closed"):
            sev_choices = [s for s in SEVERITY_WEIGHTS if s != "accident" or cat in ACCIDENT_OK]
            severity = rng.choices(sev_choices, [SEVERITY_WEIGHTS[s] for s in sev_choices])[0]
            analysis = fmt(rng.choice(analyses), ctx)
            hid += 1
            history.append({"id": hid, "incident_id": idx, "from_status": "under_review", "to_status": "measures_pending",
                            "changed_by_id": officer, "note": "Analysis submitted", "changed_at": t_analysis.isoformat()})

            pool = policies.get(cat, []) or policies["general"]
            musts = [m for m in pool if m[0] == "must"][:4]
            shoulds = [m for m in pool if m[0] == "should"][:3]
            chosen = musts + shoulds
            sid += 1
            refs = sorted({m[2] for m in chosen})
            summary_text = (
                f"{CATEGORIES[cat][0]} at {AIRPORTS[code][1]}: {title}. "
                f"Classified as {severity.replace('_', ' ')}. {analysis.split('.')[0]}. "
                f"{len(musts)} mandatory and {len(shoulds)} recommended measures apply under {', '.join(sorted({r.split(' ')[0] for r in refs}))}."
            )
            s_status = "approved" if status == "closed" or rng.random() < 0.5 else "draft"
            summaries.append({
                "id": sid, "incident_id": idx, "status": s_status,
                "summary": summary_text, "citations": "; ".join(refs), "model": "seed-data",
                "created_at": (t_analysis + timedelta(minutes=1)).isoformat(),
                "reviewed_by_id": officer if s_status == "approved" else "",
                "reviewed_at": (t_analysis + timedelta(hours=2)).isoformat() if s_status == "approved" else "",
            })

            # decide outcome for closed incidents
            outcome = rng.choices(["green", "yellow", "red"], [55, 28, 17])[0] if status == "closed" else None
            red_target = rng.randrange(len(musts)) if outcome == "red" and musts else None
            yellow_n = rng.randint(1, min(2, len(shoulds))) if outcome == "yellow" and shoulds else 0
            yellow_targets = set(rng.sample(range(len(shoulds)), yellow_n)) if yellow_n else set()

            rows = [(p, t, r, "ai") for p, t, r in chosen]
            if rng.random() < 0.2:
                rows.append(("should", "Brief all base crews on this occurrence in the next safety meeting.", "", "officer"))
            for j, (prio, text, ref, src) in enumerate(rows):
                mid += 1
                if status == "closed":
                    m_status = "applied"
                    if prio == "must" and j == red_target:
                        m_status = "not_applied"
                    if prio == "should" and (j - len(musts)) in yellow_targets:
                        m_status = "not_applied"
                else:
                    m_status = rng.choices(["pending", "applied", "not_applied"], [55, 38, 7])[0]
                marked = m_status != "pending"
                measures.append({
                    "id": mid, "incident_id": idx, "description": text, "priority": prio, "source": src,
                    "status": m_status, "reason": rng.choice(NOT_APPLIED_REASONS) if m_status == "not_applied" else "",
                    "policy_reference": ref, "marked_by_id": officer if marked else "",
                    "marked_at": (t_analysis + timedelta(days=rng.randint(1, 10))).isoformat() if marked else "",
                    "created_at": (t_analysis + timedelta(minutes=2)).isoformat(),
                })

        if status == "closed":
            closed_at = t_close
            closing_note = "All measures reviewed. Incident closed."
            hid += 1
            history.append({"id": hid, "incident_id": idx, "from_status": "measures_pending", "to_status": "closed",
                            "changed_by_id": officer, "note": closing_note, "changed_at": t_close.isoformat()})

        incidents.append({
            "id": idx, "reference": reference, "title": title, "description": description, "category": cat,
            "occurred_at": occurred.isoformat(), "airport_code": code, "flight_phase": phase,
            "aircraft_registration": ctx["reg"], "aircraft_type": ctx["type"], "operator_code": op,
            "flight_number": ctx["flight"], "severity": severity or "", "status": status,
            "analysis": analysis or "", "closing_note": closing_note or "", "reporter_id": reporter,
            "officer_id": officer or "", "created_at": reported_at.isoformat(),
            "closed_at": closed_at.isoformat() if closed_at else "",
        })

    # ------------------------------------------------ edge-case records (validation testing)
    edge_base = {"category": "other", "airport_code": "DEL", "flight_phase": "parked", "aircraft_type": "A320neo",
                 "operator_code": "SHA", "severity": "", "status": "submitted", "analysis": "", "closing_note": "",
                 "officer_id": "", "closed_at": ""}
    edge = [
        {"title": ("Maximum length title test " + "x" * 200)[:200], "description": "Edge case: title at the 200 character limit.",
         "aircraft_registration": "VT-EDG", "flight_number": "SHA101"},
        {"title": "Report with no optional fields", "description": "Edge case: registration, type, operator and flight number empty.",
         "aircraft_registration": "", "flight_number": "", "aircraft_type": "", "operator_code": ""},
        {"title": "Bird strike on landing at DEL", "description": "Edge case: duplicate-looking title of an existing report.",
         "aircraft_registration": "VT-DUP", "flight_number": "SHA102", "category": "wildlife_strike"},
        {"title": "Unicode text", "description": "Edge case: पक्षी टकराव (bird strike) reported with mixed Hindi and English text, plus symbols < > & ' \".",
         "aircraft_registration": "VT-UNI", "flight_number": "SHA103"},
        {"title": "Short", "description": "Minimal.", "aircraft_registration": "VT-MIN", "flight_number": "SHA104"},
    ]
    for e in edge:
        idx = len(incidents) + 1
        ts = NOW - timedelta(days=rng.randint(1, 5))
        seq_by_year[ts.year] = seq_by_year.get(ts.year, 0) + 1
        row = {**edge_base, **e, "id": idx, "reference": f"SKY-{ts.year}-{seq_by_year[ts.year]:04d}",
               "occurred_at": ts.isoformat(), "created_at": ts.isoformat(), "reporter_id": rng.choice(REPORTER_IDS)}
        incidents.append(row)
        hid += 1
        history.append({"id": hid, "incident_id": idx, "from_status": "", "to_status": "submitted",
                        "changed_by_id": row["reporter_id"], "note": "Report filed", "changed_at": ts.isoformat()})

    write(OUT / "users.csv", users_rows)
    write(OUT / "incidents.csv", incidents)
    write(OUT / "measures.csv", measures)
    write(OUT / "ai_summaries.csv", summaries)
    write(OUT / "status_history.csv", history)
    print(f"users={len(users_rows)} incidents={len(incidents)} measures={len(measures)} "
          f"summaries={len(summaries)} history={len(history)}")


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
