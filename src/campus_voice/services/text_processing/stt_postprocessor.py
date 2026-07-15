"""Post-process STT text for campus navigation commands."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher


@dataclass(frozen=True, slots=True)
class Correction:
    """A single text correction made after transcription."""

    kind: str
    original: str
    replacement: str
    confidence: float


@dataclass(frozen=True, slots=True)
class PostProcessResult:
    """Post-processed transcription text and metadata."""

    text: str
    raw_text: str
    post_processed: bool
    corrections: list[Correction] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DestinationAlias:
    canonical: str
    aliases: tuple[str, ...]


_DESTINATIONS: tuple[DestinationAlias, ...] = (
    DestinationAlias("AEB Lab", ("aeb lab", "a e b lab", "abe lab", "ab lab")),
    DestinationAlias("Agric LT", ("agric lt", "agric l t", "agriculture lt")),
    DestinationAlias("ETF", ("etf", "e t f", "e.t.f", "itf")),
    DestinationAlias(
        "ETF 750",
        ("etf 750", "e t f 750", "etf seven fifty", "itf 750", "itf750", "e t f seven fifty"),
    ),
    DestinationAlias("RC", ("rc", "r c", "are see", "arcy")),
    DestinationAlias("Old RC", ("old rc", "old r c", "old are see", "old arcy")),
    DestinationAlias("New RC", ("new rc", "new r c", "new are see", "new arcy")),
    DestinationAlias("ENT Hall", ("ent hall", "e n t hall", "entrepreneurship hall")),
    DestinationAlias("TET 650", ("tet650", "tet 650", "t e t 650", "tet six fifty")),
    DestinationAlias(
        "Faculty of Computing",
        ("faculty of computing", "computing faculty", "faculty computing"),
    ),
    DestinationAlias("Law LT", ("law lt", "law l t", "law lecture theatre")),
    DestinationAlias("Quadrangle", ("quadrangle", "quad angle", "quad")),
    DestinationAlias("OBJ", ("obj", "o b j", "o.b.j")),
    DestinationAlias("Senate", ("senate",)),
    DestinationAlias("Senate Building", ("senate building",)),
    DestinationAlias("30CQ", ("30cq", "30 cq", "thirty cq", "thirty c q")),
    DestinationAlias("Faculty of Education", ("faculty of edu", "faculty of education")),
    DestinationAlias("PSB Lab", ("psb lab", "p s b lab", "ps b lab")),
    DestinationAlias("Intercom", ("intercom", "inter com")),
    DestinationAlias("Sport Complex", ("sport complex", "sports complex")),
)

_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?P<prefix>take\s+me\s+to)\s+(?P<destination>.+)$", re.I),
    re.compile(r"^(?P<prefix>i\s+am\s+going\s+to)\s+(?P<destination>.+)$", re.I),
    re.compile(r"^(?P<prefix>i'm\s+going\s+to)\s+(?P<destination>.+)$", re.I),
    re.compile(r"^(?P<prefix>navigate\s+to)\s+(?P<destination>.+)$", re.I),
    re.compile(r"^(?P<prefix>go\s+to)\s+(?P<destination>.+)$", re.I),
    re.compile(r"^(?P<prefix>bring\s+me\s+to)\s+(?P<destination>.+)$", re.I),
    re.compile(r"^(?P<prefix>head\s+to)\s+(?P<destination>.+)$", re.I),
)

_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_SPACE_RE = re.compile(r"\s+")


class STTPostProcessor:
    """Normalize Whisper output for known campus navigation phrases."""

    def __init__(self, min_destination_score: float = 0.82) -> None:
        self._min_destination_score = min_destination_score

    def process(self, text: str) -> PostProcessResult:
        raw_text = text.strip()
        if not raw_text:
            return PostProcessResult(
                text="",
                raw_text=text,
                post_processed=False,
                corrections=[],
            )

        command_result = self._split_command(raw_text)
        if command_result is None:
            return self._process_destination_only(raw_text)

        prefix, destination_text = command_result
        destination = self._match_destination(destination_text)
        if destination is None:
            return PostProcessResult(
                text=raw_text,
                raw_text=raw_text,
                post_processed=False,
                corrections=[],
            )

        canonical, score = destination
        corrected = f"{self._normalize_prefix(prefix)} {canonical}"
        corrections = []
        if corrected != raw_text:
            corrections.append(
                Correction(
                    kind="destination",
                    original=destination_text,
                    replacement=canonical,
                    confidence=score,
                )
            )

        return PostProcessResult(
            text=corrected,
            raw_text=raw_text,
            post_processed=bool(corrections),
            corrections=corrections,
        )

    def _process_destination_only(self, raw_text: str) -> PostProcessResult:
        destination = self._match_destination(raw_text)
        if destination is None:
            return PostProcessResult(
                text=raw_text,
                raw_text=raw_text,
                post_processed=False,
                corrections=[],
            )

        canonical, score = destination
        if canonical == raw_text:
            corrections: list[Correction] = []
        else:
            corrections = [
                Correction(
                    kind="destination",
                    original=raw_text,
                    replacement=canonical,
                    confidence=score,
                )
            ]

        return PostProcessResult(
            text=canonical,
            raw_text=raw_text,
            post_processed=bool(corrections),
            corrections=corrections,
        )

    @staticmethod
    def _split_command(text: str) -> tuple[str, str] | None:
        for pattern in _COMMAND_PATTERNS:
            match = pattern.match(text)
            if match:
                return match.group("prefix"), match.group("destination")
        return None

    def _match_destination(self, text: str) -> tuple[str, float] | None:
        normalized_text = _normalize_for_match(text)
        if not normalized_text:
            return None

        best_canonical = ""
        best_score = 0.0
        for destination in _DESTINATIONS:
            for alias in destination.aliases:
                score = _similarity(normalized_text, _normalize_for_match(alias))
                if score > best_score:
                    best_canonical = destination.canonical
                    best_score = score

        if best_score < self._min_destination_score:
            return None

        return best_canonical, round(best_score, 4)

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        normalized = _SPACE_RE.sub(" ", prefix.lower()).strip()
        if normalized == "i'm going to":
            return "I am going to"
        if normalized == "i am going to":
            return "I am going to"
        return normalized


def _normalize_for_match(text: str) -> str:
    text = text.lower()
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text)
    return text.strip()


def _similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0

    score = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        score = max(score, overlap)
    return score
