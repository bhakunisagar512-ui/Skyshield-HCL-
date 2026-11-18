"""Fixed vocabularies used across SkyShield.

Incident categories follow DGCA India's eight National High-Risk Categories of
Occurrences (NASP 2024-2028) plus the other occurrence types DGCA tracks.
Severity follows the AAIB India classification.
"""
from enum import StrEnum


class Role(StrEnum):
    REPORTER = "reporter"
    SAFETY_OFFICER = "safety_officer"
    ADMIN = "admin"


class IncidentStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    MEASURES_PENDING = "measures_pending"
    CLOSED = "closed"


class Severity(StrEnum):
    ACCIDENT = "accident"
    SERIOUS_INCIDENT = "serious_incident"
    INCIDENT = "incident"


class MeasurePriority(StrEnum):
    MUST = "must"
    SHOULD = "should"


class MeasureStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"


class MeasureSource(StrEnum):
    AI = "ai"
    OFFICER = "officer"


class SummaryStatus(StrEnum):
    GENERATING = "generating"
    DRAFT = "draft"
    APPROVED = "approved"
    DISCARDED = "discarded"
    FAILED = "failed"


class Colour(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    GREY = "grey"


# code -> (label, is DGCA national high-risk category)
CATEGORIES: dict[str, tuple[str, bool]] = {
    "mid_air_collision": ("Mid-air collision / airprox", True),
    "cfit": ("Controlled flight into terrain", True),
    "runway_excursion": ("Runway excursion", True),
    "wildlife_strike": ("Wildlife (bird/animal) strike", True),
    "loss_of_control": ("Loss of control in flight", True),
    "runway_incursion": ("Runway incursion", True),
    "ramp_safety": ("Ramp safety", True),
    "deficient_maintenance": ("Deficient maintenance", True),
    "technical_defect": ("Technical defect", False),
    "engine_shutdown": ("In-flight engine shutdown", False),
    "turbulence": ("Turbulence encounter", False),
    "laser_interference": ("Laser interference", False),
    "crew_incapacitation": ("Crew incapacitation", False),
    "medical_emergency": ("Passenger medical emergency", False),
    "weather": ("Weather related", False),
    "other": ("Other", False),
}

FLIGHT_PHASES = [
    "parked", "pushback", "taxi", "takeoff", "initial_climb", "climb",
    "cruise", "descent", "approach", "landing", "go_around",
]

# IATA code -> (airport, city)
AIRPORTS: dict[str, tuple[str, str]] = {
    "DEL": ("Indira Gandhi International", "New Delhi"),
    "BOM": ("Chhatrapati Shivaji Maharaj International", "Mumbai"),
    "BLR": ("Kempegowda International", "Bengaluru"),
    "MAA": ("Chennai International", "Chennai"),
    "CCU": ("Netaji Subhas Chandra Bose International", "Kolkata"),
    "HYD": ("Rajiv Gandhi International", "Hyderabad"),
    "AMD": ("Sardar Vallabhbhai Patel International", "Ahmedabad"),
    "COK": ("Cochin International", "Kochi"),
    "GOX": ("Manohar International", "Mopa, Goa"),
    "PNQ": ("Pune Airport", "Pune"),
    "JAI": ("Jaipur International", "Jaipur"),
    "LKO": ("Chaudhary Charan Singh International", "Lucknow"),
    "GAU": ("Lokpriya Gopinath Bordoloi International", "Guwahati"),
    "PAT": ("Jay Prakash Narayan International", "Patna"),
    "IXC": ("Shaheed Bhagat Singh International", "Chandigarh"),
    "TRV": ("Thiruvananthapuram International", "Thiruvananthapuram"),
}

AIRCRAFT_TYPES = ["A320neo", "A321neo", "B737-8", "ATR 72-600", "B787-8", "A350-900", "Q400"]

# Fictional operators, so sample data never implies events at real airlines.
OPERATORS = {
    "SHA": "Sahyadri Air",
    "MGD": "Meghdoot Airlines",
    "VYU": "Vayu Connect",
    "KVR": "Kaveri Regional",
    "TRG": "Tiranga Skyways",
}


def taxonomy_payload() -> dict:
    return {
        "categories": [
            {"code": c, "label": label, "high_risk": hr} for c, (label, hr) in CATEGORIES.items()
        ],
        "severities": [s.value for s in Severity],
        "statuses": [s.value for s in IncidentStatus],
        "flight_phases": FLIGHT_PHASES,
        "airports": [{"code": c, "name": n, "city": city} for c, (n, city) in AIRPORTS.items()],
        "aircraft_types": AIRCRAFT_TYPES,
        "operators": [{"code": c, "name": n} for c, n in OPERATORS.items()],
    }
