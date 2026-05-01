"""Validation gates for HERMES pipeline.

8+1 gates:
1. StructureGate - JSON schema, 4 options, A-D
2. ContentQualityGate - No "all/none", lengths
3. ConsistencyGate - Misconception types, levels
4. AnchorGroundingGate - Concept from brief
5. AttributionGate - 140-name eponym whitelist
6. OptionLengthBalanceGate - Ratio < 1.7x
7. DistractorMixGate - Soft enforcement
8. UniquenessGate - No duplicates
9. RedactionViolationGate - NEW: Stem vs contradictable_facts
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class GateResult:
    """Result from a validation gate."""
    passed: bool
    message: str = ""
    severity: str = "error"  # "error" (hard fail) or "warning" (soft flag)

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
        # Check 4 options
        if len(options) != 4:
            return GateResult.FAIL(f"Expected 4 options, got {len(options)}")

        # Check letters A-D
        expected_letters = {"A", "B", "C", "D"}
        actual_letters = {o.get("letter") for o in options}
        if actual_letters != expected_letters:
            return GateResult.FAIL(f"Expected letters A-D, got {actual_letters}")

        # Check correct letter exists
        if correct_letter not in expected_letters:
            return GateResult.FAIL(f"Invalid correct letter: {correct_letter}")

        # Check stem non-empty
        if not stem or len(stem.strip()) < 10:
            return GateResult.FAIL("Stem is too short or empty")

        # Check all options have text
        for i, opt in enumerate(options):
            if not opt.get("text") or len(opt["text"].strip()) < 5:
                return GateResult.FAIL(f"Option {i+1} text is too short")

        return GateResult.PASS()


class RedactionViolationGate:
    """Gate 9: Stem does not print contradictable_facts or their negations.

    CRITICAL: This is the key gate that enforces distractor-first architecture.
    If the stem prints a contradictable fact (or its negation), the distractor
    becomes rejectable by reading the stem alone = english_gap.
    """

    # Negation patterns to detect
    NEGATION_PATTERNS = [
        r"\bnot\b",
        r"\bnever\b",
        r"\bno\b",
        r"\bdoesn\?'t\b",
        r"\bdon\?'t\b",
        r"\bwon\?'t\b",
        r"\bcan\?'t\b",
        r"\bcannot\b",
        r"\bneither\b",
        r"\bnor\b",
    ]

    @classmethod
    def validate(cls, stem: str, contradictable_facts: list[str]) -> GateResult:
        stem_lower = stem.lower()

        for fact in contradictable_facts:
            fact_lower = fact.lower()

            # Check direct match (case-insensitive)
            if fact_lower in stem_lower:
                return GateResult.FAIL(
                    f"Stem prints contradictable fact: '{fact}'"
                )

            # Check for negation patterns
            # Split fact into words and check if negated version appears
            words = fact_lower.split()
            if len(words) >= 2:
                # Simple heuristic: look for negation words near fact words
                for word in words:
                    if len(word) < 4:  # Skip short words
                        continue
                    for neg_pattern in cls.NEGATION_PATTERNS:
                        # Look for "not <word>" or "<word> ... not" patterns
                        pattern = rf"{neg_pattern}.*?\b{re.escape(word)}\b"
                        if re.search(pattern, stem_lower):
                            return GateResult.FAIL(
                                f"Stem appears to negate contradictable fact: '{fact}' "
                                f"(found negation near '{word}')"
                            )

        # TODO: Upgrade to Sonnet-based paraphrase detection (parking lot item)
        # Current implementation catches direct matches and simple negations.
        # Paraphrase detection would require LLM call.

        return GateResult.PASS()


class ContentQualityGate:
    """Gate 2: Content quality rules (no 'all/none of the above', lengths)."""

    FORBIDDEN_PHRASES = [
        "all of the above",
        "none of the above",
        "a and b",
        "a, b, and c",
    ]

    @classmethod
    def validate(cls, stem: str, options: list[dict]) -> GateResult:
        # Check forbidden phrases in options
        for opt in options:
            text_lower = opt.get("text", "").lower()
            for phrase in cls.FORBIDDEN_PHRASES:
                if phrase in text_lower:
                    return GateResult.FAIL(
                        f"Forbidden phrase '{phrase}' in option {opt.get('letter')}"
                    )

        # Check stem length (sentences)
        sentences = re.split(r"[.!?]+", stem)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) < 1 or len(sentences) > 8:
            return GateResult.FAIL(
                f"Stem has {len(sentences)} sentences (expected 1-8)"
            )

        # Check option lengths (words)
        for opt in options:
            words = opt.get("text", "").split()
            if len(words) < 5 or len(words) > 45:
                return GateResult.FAIL(
                    f"Option {opt.get('letter')} has {len(words)} words (expected 5-45)"
                )

        return GateResult.PASS()


class OptionLengthBalanceGate:
    """Gate 6: Option length balance (ratio < 1.7x, correct not >20% longer than all).

    Prevents testwise heuristic: "the longest answer is usually correct."
    """

    @staticmethod
    def validate(options: list[dict], correct_letter: str) -> GateResult:
        # Calculate lengths
        lengths = {opt["letter"]: len(opt["text"]) for opt in options}

        # Check ratio (max/min)
        max_len = max(lengths.values())
        min_len = min(lengths.values())
        if min_len == 0:
            return GateResult.FAIL("Option has zero length")

        ratio = max_len / min_len
        if ratio > 1.7:
            return GateResult.FAIL(
                f"Length ratio {ratio:.2f}x exceeds 1.7x threshold "
                f"(max: {max_len}, min: {min_len})"
            )

        # Check correct answer is not >20% longer than ALL distractors
        correct_len = lengths[correct_letter]
        distractor_lens = [l for letter, l in lengths.items() if letter != correct_letter]
        max_distractor_len = max(distractor_lens)

        if correct_len > max_distractor_len * 1.2:
            return GateResult.FAIL(
                f"Correct answer ({correct_len} chars) is >20% longer than "
                f"all distractors (max: {max_distractor_len})"
            )

        return GateResult.PASS()


class AttributionGate:
    """Gate 5: No researcher citations (with 140-name eponym whitelist).

    Forbids: "Smith (2010)", "According to Smith", "Smith's framework", "Smith et al."
    Exempts: 140-name eponym whitelist (Piaget, Pavlovian, Cannon-Bard, etc.)
    """

    # Whitelist (from goliath pipeline/__init__.py EPONYM_WHITELIST)
    # Abbreviated for brevity - full list has ~140 names
    EPONYM_WHITELIST = frozenset([
        # Developmental
        "Piaget",
        "Vygotsky",
        "Erikson",
        "Kohlberg",
        "Ainsworth",
        "Bowlby",
        # Conditioning/Behaviorism
        "Pavlov",
        "Pavlovian",
        "Skinner",
        "Skinnerian",
        "Thorndike",
        "Watson",
        "Bandura",
        # Psychoanalytic/Humanistic
        "Freud",
        "Freudian",
        "Jung",
        "Jungian",
        "Rogers",
        "Rogersian",
        "Maslow",
        # CBT/Clinical
        "Beck",
        "Beckian",
        "Ellis",
        # Family Systems
        "Bowen",
        "Bowenian",
        "Minuchin",
        "Satir",
        # Emotion/Motivation
        "Cannon",
        "Bard",
        "Cannon-Bard",
        "Schachter",
        "Singer",
        # Memory/Cognition
        "Miller",
        "Baddeley",
        # Social
        "Asch",
        "Milgram",
        "Zimbardo",
        "Festinger",
        # Institutional (prevent false positives on document titles)
        "Psychology",
        "Association",
        "Society",
        "Guidelines",
        "Standards",
    ])

    # Citation patterns (from goliath pipeline/citation_patterns.py)
    CITATION_PATTERNS = [
        r"[A-Z][a-z]+\s+\(\d{4}\)",           # "Smith (2010)"
        r"According\s+to\s+[A-Z][a-z]+",       # "According to Smith"
        r"[A-Z][a-z]+['']s\s+(framework|theory|model)",  # "Smith's framework"
        r"[A-Z][a-z]+\s+et\s+al\.?,           # "Smith et al."
        r"[A-Z][a-z]+\s+and\s+[A-Z][a-z]+",   # "Smith and Jones" (bare multi)
    ]

    @classmethod
    def validate(cls, stem: str, options: list[dict], explanations: list[dict]) -> GateResult:
        # Combine all text to check
        all_text = stem + " " + " ".join(opt.get("text", "") for opt in options)
        all_text += " " + " ".join(exp.get("text", "") for exp in explanations)

        for pattern in cls.CITATION_PATTERNS:
            matches = re.findall(pattern, all_text)
            for match in matches:
                # Extract name from match
                name_match = re.search(r"[A-Z][a-z]+", match)
                if not name_match:
                    continue
                name = name_match.group()

                # Check whitelist
                if name not in cls.EPYONYM_WHITELIST:
                    return GateResult.FAIL(
                        f"Non-whitelisted researcher citation: '{name}' in '{match}'"
                    )

        return GateResult.PASS()


class ConsistencyGate:
    """Gate 3: Misconception types valid, distractor levels match tier plan."""

    VALID_MISCONCEPTION_TYPES = {
        "similar_property",
        "partial_understanding",
        "overgeneralization",
        "similar_name",
        "opposite_direction",
        "similar_store",
    }

    def __init__(self, expected_distractor_levels: list[int]):
        self.expected_levels = sorted(expected_distractor_levels)

    def validate(self, distractors: list[dict]) -> GateResult:
        # Check levels match plan
        actual_levels = sorted(d.get("distractor_level") for d in distractors)
        if actual_levels != self.expected_levels:
            return GateResult.FAIL(
                f"Distractor levels {actual_levels} don't match plan {self.expected_levels}"
            )

        # Check misconception types are valid
        for d in distractors:
            ms_type = d.get("misconception_type")
            if ms_type not in self.VALID_MISCONCEPTION_TYPES:
                return GateResult.FAIL(
                    f"Invalid misconception type: {ms_type}"
                )

        return GateResult.PASS()


class DistractorMixGate:
    """Gate 7: Distractor mix compliance (SOFT - not hard fail)."""

    def __init__(self, expected_levels: list[int]):
        self.expected_levels = expected_levels

    def validate(self, distractors: list[dict]) -> GateResult:
        actual_levels = [d.get("distractor_level") for d in distractors]
        actual_levels.sort()
        expected = sorted(self.expected_levels)

        if actual_levels != expected:
            return GateResult.FAIL(
                f"Distractor mix {actual_levels} doesn't match expected {expected}",
                severity="warning",  # Soft enforcement - flag for review
            )

        return GateResult.PASS()


class UniquenessGate:
    """Gate 8: No duplicate questions within chapter."""

    def __init__(self, existing_stems: set[str]):
        self.existing_stems = existing_stems

    def validate(self, stem: str) -> GateResult:
        # Normalize: lowercase, strip, collapse whitespace
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
            return GateResult.PASS()  # No brief = fallback mode = no enforcement

        if tested_concept_id not in self.allowed_concepts:
            return GateResult.FAIL(
                f"Tested concept {tested_concept_id} not in anchor's concept list"
            )

        return GateResult.PASS()


def create_gate_pipeline(tier_distractor_mix: list[int]) -> dict:
    """Factory to create all gates for a question.

    Usage:
        gates = create_gate_pipeline(expected_distractor_levels=[1, 2, 3])
        result = gates["StructureGate"].validate(stem, options, correct_letter)
    """
    return {
        "StructureGate": StructureGate(),
        "ContentQualityGate": ContentQualityGate(),
        "ConsistencyGate": ConsistencyGate(expected_distractor_levels=tier_distractor_mix),
        "DistractorMixGate": DistractorMixGate(expected_distractor_levels=tier_distractor_mix),
        "RedactionViolationGate": RedactionViolationGate(),
        "OptionLengthBalanceGate": OptionLengthBalanceGate(),
    }

