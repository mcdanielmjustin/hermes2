"""Validation gates for HERMES pipeline."""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class GateResult:
    """Result from a validation gate."""
    passed: bool
    message: str = ""
    severity: str = "error"

    @classmethod
    def PASS(cls, message: str = "") -> "GateResult":
        return cls(passed=True, message=message or "Passed")

    @classmethod
    def FAIL(cls, message: str, severity: str = "error") -> "GateResult":
        return cls(passed=False, message=message, severity=severity)


class StructureGate:
    """Gate 1: Validate JSON schema and basic structure."""

    @staticmethod
    def validate(stem: str, options: list[dict], correct_letter: str) -> GateResult:
        if len(options) != 4:
            return GateResult.FAIL(f"Expected 4 options, got {len(options)}")
        expected_letters = {"A", "B", "C", "D"}
        actual_letters = {o.get("letter") for o in options}
        if actual_letters != expected_letters:
            return GateResult.FAIL(f"Expected letters A-D, got {actual_letters}")
        if correct_letter not in expected_letters:
            return GateResult.FAIL(f"Invalid correct letter: {correct_letter}")
        if not stem or len(stem.strip()) < 10:
            return GateResult.FAIL("Stem is too short or empty")
        for i, opt in enumerate(options):
            if not opt.get("text") or len(opt["text"].strip()) < 5:
                return GateResult.FAIL(f"Option {i+1} text is too short")
        return GateResult.PASS()


class RedactionViolationGate:
    """Gate 9: Stem does not print contradictable_facts or their negations."""

    NEGATION_PATTERNS = [
        r"\bnot\b", r"\bnever\b", r"\bno\b", r"\bdoesn\?'t\b", r"\bdon\?'t\b",
        r"\bwon\?'t\b", r"\bcan\?'t\b", r"\bcannot\b", r"\bneither\b", r"\bnor\b",
    ]

    @classmethod
    def validate(cls, stem: str, contradictable_facts: list[str]) -> GateResult:
        stem_lower = stem.lower()
        for fact in contradictable_facts:
            fact_lower = fact.lower()
            if fact_lower in stem_lower:
                return GateResult.FAIL(f"Stem prints contradictable fact: '{fact}'")
            # Check for negation patterns
            words = fact_lower.split()
            if len(words) >= 2:
                for word in words:
                    if len(word) < 4:
                        continue
                    for neg_pattern in cls.NEGATION_PATTERNS:
                        pattern = rf"{neg_pattern}.*?\\b{re.escape(word)}\\b"
                        if re.search(pattern, stem_lower):
                            return GateResult.FAIL(
                                f"Stem appears to negate contradictable fact: '{fact}'"
                            )
        return GateResult.PASS()


class ContentQualityGate:
    """Gate 2: Content quality rules."""

    FORBIDDEN_PHRASES = ["all of the above", "none of the above", "a and b", "a, b, and c"]

    @classmethod
    def validate(cls, stem: str, options: list[dict]) -> GateResult:
        for opt in options:
            text_lower = opt.get("text", "").lower()
            for phrase in cls.FORBIDDEN_PHRASES:
                if phrase in text_lower:
                    return GateResult.FAIL(f"Forbidden phrase '{phrase}' in option {opt.get('letter')}")
        sentences = re.split(r"[.!?]+", stem)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) < 1 or len(sentences) > 8:
            return GateResult.FAIL(f"Stem has {len(sentences)} sentences (expected 1-8)")
        for opt in options:
            words = opt.get("text", "").split()
            if len(words) < 5 or len(words) > 45:
                return GateResult.FAIL(f"Option {opt.get('letter')} has {len(words)} words (expected 5-45)")
        return GateResult.PASS()


class OptionLengthBalanceGate:
    """Gate 6: Option length balance (ratio < 1.7x)."""

    @staticmethod
    def validate(options: list[dict], correct_letter: str) -> GateResult:
        lengths = {opt["letter"]: len(opt["text"]) for opt in options}
        max_len = max(lengths.values())
        min_len = min(lengths.values())
        if min_len == 0:
            return GateResult.FAIL("Option has zero length")
        ratio = max_len / min_len
        if ratio > 1.7:
            return GateResult.FAIL(f"Length ratio {ratio:.2f}x exceeds 1.7x (max: {max_len}, min: {min_len})")
        correct_len = lengths[correct_letter]
        distractor_lens = [l for letter, l in lengths.items() if letter != correct_letter]
        max_distractor_len = max(distractor_lens)
        if correct_len > max_distractor_len * 1.2:
            return GateResult.FAIL(f"Correct ({correct_len}) is >20% longer than all distractors (max: {max_distractor_len})")
        return GateResult.PASS()


class AttributionGate:
    """Gate 5: No researcher citations (with 140-name eponym whitelist)."""

    # Full eponym whitelist from goliath pipeline/__init__.py
    EPONYM_WHITELIST = frozenset([
        # Developmental (15)
        "Piaget", "Vygotsky", "Erikson", "Kohlberg", "Ainsworth", "Bowlby",
        "Gilligan", "Kagan", "Thomas", "Chess", "Brazelton", "Gesell",
        "Bronfenbrenner", "Luria", "Leontiev",
        # Conditioning/Behaviorism (12)
        "Pavlov", "Pavlovian", "Skinner", "Skinnerian", "Thorndike", "Watson",
        "Bandura", "Mowrer", "Rescorla", "Wagner", "Hull", "Spence",
        # Psychoanalytic/Humanistic (12)
        "Freud", "Freudian", "Jung", "Jungian", "Rogers", "Rogersian",
        "Maslow", "Adler", "Adlerian", "Horney", "Fromm", "Sullivan",
        # CBT/Clinical (10)
        "Beck", "Beckian", "Ellis", "Meichenbaum", "Beck", "Linehan",
        "Marsha", "Dialectical", "DBT", "EMDR",
        # Family Systems (10)
        "Bowen", "Bowenian", "Minuchin", "Satir", "Haley", "Madanes",
        "Ackerman", "Boszormenyi-Nagy", "Wynne", "Lidz",
        # Emotion/Motivation (8)
        "Cannon", "Bard", "Cannon-Bard", "Schachter", "Singer", "Lazarus",
        "James", "Lange", "James-Lange",
        # Memory/Cognition (12)
        "Miller", "Baddeley", "Hitch", "Baddeley-Hitch", "Tulving", "Sperling",
        "Loftus", "Johnson", "Ray", "Neill", "Posner", "Snyder",
        # Social (15)
        "Asch", "Milgram", "Zimbardo", "Festinger", "Darley", "Latané",
        "Heider", "Kelley", "Weiner", "Ajzen", "Fishbein", "Cialdini",
        "Sherif", "Tajfel", "Turner",
        # Multicultural (8)
        "Sue", "Sue", "Cross", "Helms", "Atkinson", "Mortem", "Sue", "Nagai",
        # I-O/Career (10)
        "Holland", "Super", "Dawis", "Lofquist", "Herzberg", "Vroom",
        "Locke", "Latham", "Hackman", "Oldham",
        # Neuroanatomy (8)
        "Broca", "Wernicke", "Gage", "Phineas", "Penfield", "Kluver", "Bucy",
        "Dejerine",
        # Assessment (10)
        "Rorschach", "Inkblot", "Wechsler", "Binet", "Stanford", "Terman",
        "MMPI", "Hathaway", "McKinley", "Strong",
        # Institutional (prevent false positives)
        "Psychology", "Association", "Society", "Guidelines", "Standards",
        "Ethics", "Code", "APA", "Diagnostic", "Statistical",
    ])

    CITATION_PATTERNS = [
        r"[A-Z][a-z]+\s+\(\d{4}\)",
        r"According\s+to\s+[A-Z][a-z]+",
        r"[A-Z][a-z]+['']s\s+(framework|theory|model|findings)",
        r"[A-Z][a-z]+\s+et\s+al\.?",
        r"[A-Z][a-z]+\s+and\s+[A-Z][a-z]+",
    ]

    @classmethod
    def validate(cls, stem: str, options: list[dict], explanations: list[dict]) -> GateResult:
        all_text = stem + " " + " ".join(opt.get("text", "") for opt in options)
        all_text += " " + " ".join(exp.get("text", "") for exp in explanations)
        for pattern in cls.CITATION_PATTERNS:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for match in matches:
                name_match = re.search(r"[A-Z][a-z]+", str(match))
                if not name_match:
                    continue
                name = name_match.group()
                if name not in cls.EPYONYM_WHITELIST:
                    return GateResult.FAIL(f"Non-whitelisted citation: '{name}' in '{match}'")
        return GateResult.PASS()


class ConsistencyGate:
    """Gate 3: Misconception types valid, distractor levels match tier plan."""

    VALID_MISCONCEPTION_TYPES = {
        "similar_property", "partial_understanding", "overgeneralization",
        "similar_name", "opposite_direction", "similar_store",
    }

    def __init__(self, expected_distractor_levels: list[int]):
        self.expected_levels = sorted(expected_distractor_levels)

    def validate(self, distractors: list[dict]) -> GateResult:
        actual_levels = sorted(d.get("distractor_level") for d in distractors)
        if actual_levels != self.expected_levels:
            return GateResult.FAIL(f"Distractor levels {actual_levels} don't match plan {self.expected_levels}")
        for d in distractors:
            ms_type = d.get("misconception_type")
            if ms_type not in self.VALID_MISCONCEPTION_TYPES:
                return GateResult.FAIL(f"Invalid misconception type: {ms_type}")
        return GateResult.PASS()


class DistractorMixGate:
    """Gate 7: Distractor mix compliance (SOFT)."""

    def __init__(self, expected_levels: list[int]):
        self.expected_levels = sorted(expected_levels)

    def validate(self, distractors: list[dict]) -> GateResult:
        actual_levels = sorted(d.get("distractor_level") for d in distractors)
        if actual_levels != self.expected_levels:
            return GateResult.FAIL(f"Distractor mix {actual_levels} doesn't match {self.expected_levels}", severity="warning")
        return GateResult.PASS()


class UniquenessGate:
    """Gate 8: No duplicate questions within chapter."""

    def __init__(self, existing_stems: set[str]):
        self.existing_stems = existing_stems

    def validate(self, stem: str) -> GateResult:
        normalized = " ".join(stem.lower().split())
        if normalized in self.existing_stems:
            return GateResult.FAIL("Duplicate stem found")
        return GateResult.PASS()


class AnchorGroundingGate:
    """Gate 4: Tested concept from anchor's concept list (when brief exists)."""

    def __init__(self, allowed_concept_ids: list[str]):
        self.allowed_concepts = set(allowed_concept_ids)

    def validate(self, tested_concept_id: str) -> GateResult:
        if not self.allowed_concepts:
            return GateResult.PASS()  # No brief = fallback mode
        if tested_concept_id not in self.allowed_concepts:
            return GateResult.FAIL(f"Tested concept {tested_concept_id} not in anchor's concept list")
        return GateResult.PASS()


def create_gate_pipeline(tier_distractor_mix: list[int]) -> dict:
    """Factory to create all gates for a question."""
    return {
        "StructureGate": StructureGate(),
        "ContentQualityGate": ContentQualityGate(),
        "ConsistencyGate": ConsistencyGate(expected_distractor_levels=tier_distractor_mix),
        "DistractorMixGate": DistractorMixGate(expected_distractor_levels=tier_distractor_mix),
        "RedactionViolationGate": RedactionViolationGate(),
        "OptionLengthBalanceGate": OptionLengthBalanceGate(),
    }

