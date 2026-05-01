"""Constants for HERMES pipeline."""

from enum import IntEnum


class Tier(IntEnum):
    """Bloom's tiers for question generation."""
    REMEMBER = 1      # T1: Direct recall
    UNDERSTAND = 2    # T2: Comprehension
    APPLY = 3         # T3: Application to scenarios
    EVALUATE = 4      # T4: Judgment with competing evidence


class DistractorLevel(IntEnum):
    """Distractor complexity levels."""
    L1_CROSS_SUBDOMAIN = 1       # "Did they study this chapter?"
    L2_SAME_SUBDOMAIN = 2        # "Distinctions within this topic?"
    L3_SAME_CONCEPT = 3          # "Discriminate closely related concepts?"
    L4_PARTIALLY_CORRECT = 4     # "Evaluate which is MOST correct?"


class MisconceptionType:
    """Six misconception types for diagnostic distractors."""
    SIMILAR_PROPERTY = "similar_property"           # Shared surface features
    PARTIAL_UNDERSTANDING = "partial_understanding" # Almost right, missing qualifier
    OVERGENERALIZATION = "overgeneralization"       # Correct principle, wrong scope
    SIMILAR_NAME = "similar_name"                   # Terminological confusion
    OPPOSITE_DIRECTION = "opposite_direction"       # Reversed causal direction
    SIMILAR_STORE = "similar_store"                 # Same mental shelf


# Distractor mix per tier: (L1, L2, L3, L4) counts
DISTRACTOR_MIX = {
    Tier.REMEMBER:   (1, 1, 1, 0),   # 1×L1, 1×L2, 1×L3
    Tier.UNDERSTAND: (1, 1, 1, 0),   # 1×L1, 1×L2, 1×L3
    Tier.APPLY:      (0, 1, 1, 1),   # 1×L2, 1×L3, 1×L4
    Tier.EVALUATE:   (0, 0, 1, 2),   # 1×L3, 2×L4
}


# Bloom's verbs per tier
BLOOMS_VERBS = {
    Tier.REMEMBER:   ["define", "identify", "recognize", "list", "recall"],
    Tier.UNDERSTAND: ["explain", "compare", "contrast", "paraphrase", "interpret"],
    Tier.APPLY:      ["demonstrate", "use", "solve", "apply", "differentiate"],
    Tier.EVALUATE:   ["differentiate", "organize", "attribute", "judge", "critique", "defend", "justify"],
}


# Correct answer position cycle (20 positions: 5A/5B/5C/5D)
CORRECT_POSITIONS = [
    "B", "C", "A", "D", "C", "A", "D", "B", "C", "A",
    "D", "A", "C", "B", "D", "C", "B", "D", "A", "B"
]


# Domain codes (from goliath shared_constants.py)
DOMAIN_CODES = {
    1: "PMET",  # Psychometrics & Research
    2: "LDEV",  # Lifespan Development
    3: "CPAT",  # Clinical Psychopathology
    4: "PTHE",  # Psychotherapy Models
    5: "SOCU",  # Social & Cultural
    6: "WDEV",  # Workforce Development
    7: "BPSY",  # Biopsychology
    8: "CASS",  # Clinical Assessment
    9: "PETH",  # Pharmacology & Ethics
}


# Level-Misconception Type Affinity (from goliath agents.py)
LEVEL_TYPE_AFFINITY = {
    DistractorLevel.L1_CROSS_SUBDOMAIN: ["similar_name", "opposite_direction"],
    DistractorLevel.L2_SAME_SUBDOMAIN:  ["similar_property", "similar_store"],
    DistractorLevel.L3_SAME_CONCEPT:    ["overgeneralization", "partial_understanding"],
    DistractorLevel.L4_PARTIALLY_CORRECT: ["overgeneralization", "partial_understanding"],
}

