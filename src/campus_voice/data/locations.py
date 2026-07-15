"""Corrected campus locations for Adekunle Ajasin University (AAUA)."""

from __future__ import annotations

from typing import TypedDict


class RouteConditionRecord(TypedDict):
    """Route-context metadata for a campus location."""

    code: str
    label: str
    description: str
    severity: int
    tags: tuple[str, ...]


class LocationRecord(TypedDict):
    """Static location definition."""

    id: int
    name: str
    latitude: float
    longitude: float
    aliases: tuple[str, ...]
    route_conditions: tuple[RouteConditionRecord, ...]


def _condition(
    code: str,
    label: str,
    description: str,
    severity: int,
    *tags: str,
) -> RouteConditionRecord:
    return {
        "code": code,
        "label": label,
        "description": description,
        "severity": severity,
        "tags": tuple(tags),
    }


LOCATIONS: dict[int, LocationRecord] = {
    1: {
        "id": 1,
        "name": "ETF 750",
        "latitude": 7.4816017,
        "longitude": 5.7420794,
        "aliases": ('etf750', 'etf 750', 'e t f 750', 'etf seven fifty', 'seven fifty'),
        "route_conditions": (
            _condition(
                "busy_shuttle_road",
                "Busy shuttle road",
                "Shuttle traffic is common here, so crossing can be slower during peak hours.",
                3,
                "traffic",
                "shuttle",
                "crossing",
            ),
            _condition(
                "noisy_zone",
                "Noisy zone",
                "Expect higher ambient noise from people and vehicles.",
                3,
                "noise",
                "busy",
                "people",
            ),
        ),
    },
    3: {
        "id": 3,
        "name": "Faculty of Computing",
        "latitude": 7.48218,
        "longitude": 5.74141,
        "aliases": ('faculty of computing', 'computing faculty', 'foc'),
        "route_conditions": (
            _condition(
                "busy_academic_area",
                "Busy academic area",
                "Expect student traffic between lecture periods.",
                3,
                "busy",
                "students",
                "academic",
            ),
        ),
    },
    4: {
        "id": 4,
        "name": "Senate Building",
        "latitude": 7.4804361,
        "longitude": 5.7568628,
        "aliases": ('senate building', 'senate', 'admin block'),
        "route_conditions": (
            _condition(
                "busy_zone",
                "Administrative hub",
                "High administrative and formal visitor foot traffic daily.",
                3,
                "busy",
                "administrative",
                "management",
            ),
        ),
    },
    5: {
        "id": 5,
        "name": "AAUA Main Gate",
        "latitude": 7.47464,
        "longitude": 5.75133,
        "aliases": ('main gate', 'school gate', 'express gate'),
        "route_conditions": (
            _condition(
                "gate_area",
                "Highway boundary gate area",
                "Security clearance, heavy highway truck noise, and pedestrian bottlenecking.",
                3,
                "gate",
                "security",
                "crowd",
                "highway",
            ),
        ),
    },
    6: {
        "id": 6,
        "name": "Faculty of Law",
        "latitude": 7.48074,
        "longitude": 5.74412,
        "aliases": ('faculty of law', 'law faculty', 'law building'),
        "route_conditions": (
            _condition(
                "formal_zone",
                "Strict dress-code zone",
                "High density of students in formal white-and-black attire.",
                3,
                "law",
                "academic",
            ),
        ),
    },
    7: {
        "id": 7,
        "name": "Faculty of Science",
        "latitude": 7.48111,
        "longitude": 5.74563,
        "aliases": ('faculty of science', 'science faculty', 'fos'),
        "route_conditions": (
            _condition(
                "lab_transit_zone",
                "Lab transit walkway",
                "Heavy student rush during morning and afternoon laboratory shifts.",
                3,
                "busy",
                "science",
                "labs",
            ),
        ),
    },
    8: {
        "id": 8,
        "name": "Old RC",
        "latitude": 7.48255,
        "longitude": 5.74265,
        "aliases": ('old rc', 'old r c', 'old relaxation center'),
        "route_conditions": (
            _condition(
                "bushy_environment",
                "Bushy environment",
                "Path edges can be obscured by vegetation in some stretches.",
                3,
                "bush",
                "vegetation",
                "path",
            ),
        ),
    },
    9: {
        "id": 9,
        "name": "New RC",
        "latitude": 7.48125,
        "longitude": 5.74283,
        "aliases": ('new rc', 'new r c', 'new relaxation center'),
        "route_conditions": (
            _condition(
                "open_gutter",
                "Open gutters nearby",
                "Keep to the center of the walkway when approaching from the road side.",
                3,
                "gutter",
                "edge",
                "caution",
            ),
        ),
    },
    10: {
        "id": 10,
        "name": "University Library",
        "latitude": 7.4835395,
        "longitude": 5.7528628,
        "aliases": ('main library', 'university library', 'library'),
        "route_conditions": (
            _condition(
                "quiet_zone",
                "Quiet study zone",
                "Strict noise control in effect around the building perimeter.",
                3,
                "quiet",
                "academic",
                "library",
            ),
        ),
    },
    11: {
        "id": 11,
        "name": "Quadrangle GEY LT",
        "latitude": 7.48125,
        "longitude": 5.7459,
        "aliases": ('gey lt', 'quadrangle gey lt', 'geology lecture theatre', 'geology lt', 'gey lecture theatre', 'quadrangle'),
        "route_conditions": (
            _condition(
                "academic_zone",
                "Academic lecture zone",
                "Expect student transit and lectures in session.",
                3,
                "academic",
                "lecture",
            ),
        ),
    },
    12: {
        "id": 12,
        "name": "AAUA OBJ MULTIPURPOSE HALL",
        "latitude": 7.479601,
        "longitude": 5.7394032,
        "aliases": ('aaua obj multipurpose hall',),
        "route_conditions": (
        ),
    },
    13: {
        "id": 13,
        "name": "Faculty of Arts and Law Lecture Theatre",
        "latitude": 7.4803586,
        "longitude": 5.7391894,
        "aliases": ('faculty of arts and law lecture theatre',),
        "route_conditions": (
        ),
    },
    14: {
        "id": 14,
        "name": "Pioneer Hostel",
        "latitude": 7.4799923,
        "longitude": 5.7415843,
        "aliases": ('pioneer hostel',),
        "route_conditions": (
        ),
    },
    15: {
        "id": 15,
        "name": "Lecture Theatre - LT A",
        "latitude": 7.4806816,
        "longitude": 5.7403311,
        "aliases": ('lecture theatre - lt a',),
        "route_conditions": (
        ),
    },
    16: {
        "id": 16,
        "name": "Student Union Building",
        "latitude": 7.4818363,
        "longitude": 5.7396021,
        "aliases": ('student union building',),
        "route_conditions": (
        ),
    },
    17: {
        "id": 17,
        "name": "Biochemistry Lab 1",
        "latitude": 7.4801512,
        "longitude": 5.7394348,
        "aliases": ('biochemistry lab 1',),
        "route_conditions": (
        ),
    },
    18: {
        "id": 18,
        "name": "STAIRCASE PARKING SPACE",
        "latitude": 7.4813497,
        "longitude": 5.7399319,
        "aliases": ('staircase parking space',),
        "route_conditions": (
        ),
    },
    19: {
        "id": 19,
        "name": "Aaua performing art park",
        "latitude": 7.4807553,
        "longitude": 5.7409711,
        "aliases": ('aaua performing art park',),
        "route_conditions": (
        ),
    },
    20: {
        "id": 20,
        "name": "Intercontinental Hall",
        "latitude": 7.480875,
        "longitude": 5.7435929,
        "aliases": ('intercontinental hall',),
        "route_conditions": (
        ),
    },
    21: {
        "id": 21,
        "name": "Nelson Mandela Hall",
        "latitude": 7.4815068,
        "longitude": 5.7447593,
        "aliases": ('nelson mandela hall',),
        "route_conditions": (
        ),
    },
    22: {
        "id": 22,
        "name": "30CQ Lecture theater",
        "latitude": 7.482844,
        "longitude": 5.7500099,
        "aliases": ('30cq lecture theater',),
        "route_conditions": (
        ),
    },
    23: {
        "id": 23,
        "name": "TETFUND 650",
        "latitude": 7.4830397,
        "longitude": 5.7527876,
        "aliases": ('tetfund 650',),
        "route_conditions": (
        ),
    },
    24: {
        "id": 24,
        "name": "FQM4+J28",
        "latitude": 7.4847076,
        "longitude": 5.7547714,
        "aliases": ('fqm4+j28',),
        "route_conditions": (
        ),
    },
    25: {
        "id": 25,
        "name": "Faculty of Arts",
        "latitude": 7.4842408,
        "longitude": 5.7571708,
        "aliases": ('faculty of arts',),
        "route_conditions": (
        ),
    },
    26: {
        "id": 26,
        "name": "Faculty of Social Science (SOSSA)",
        "latitude": 7.4816861,
        "longitude": 5.7590401,
        "aliases": ('faculty of social science (sossa)',),
        "route_conditions": (
        ),
    },
    27: {
        "id": 27,
        "name": "ENT Building Adekunle Ajasin University",
        "latitude": 7.4801215,
        "longitude": 5.7588393,
        "aliases": ('ent building adekunle ajasin university',),
        "route_conditions": (
        ),
    },
}

# The true central roundabout/monument loop area coordinates
AAUA_CAMPUS_CENTER = {
    "latitude": 7.479234,
    "longitude": 5.748411,
}

# Constrained safely to 1.0 km to match physical campus boundaries 
AAUA_CAMPUS_RADIUS_METERS = 1_000.0
