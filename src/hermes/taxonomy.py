"""Bloom's taxonomy verbs and tier enforcement rules."""

from .constants import Tier, BLOOMS_VERBS


# Tier-specific stem enforcement rules
TIER_ENFORCEMENT = {
    Tier.REMEMBER: {
        "prevent": "upward_creep",
        "rule": "If answering requires analyzing a scenario or applying to a case, the question is too complex. Strip the scenario and test the concept directly.",
        "forbidden": ["scenario", "clinical vignette", "case", "patient", "Dr.", "Mrs.", "Mr."],
        "required_verbs": BLOOMS_VERBS[Tier.REMEMBER],
    },
    Tier.UNDERSTAND: {
        "prevent": "upward_creep",
        "rule": "If answering requires multi-step reasoning or integrating multiple concepts, simplify to a single conceptual step.",
        "forbidden": ["multi-step", "integrat"],
        "required_verbs": BLOOMS_VERBS[Tier.UNDERSTAND],
    },
    Tier.APPLY: {
        "prevent": "downward_creep",
        "rule": "If answerable by recalling a single definition regardless of scenario dressing, require genuine application or analysis.",
        "required": ["scenario", "case", "application"],
        "required_verbs": BLOOMS_VERBS[Tier.APPLY],
    },
    Tier.EVALUATE: {
        "prevent": "downward_creep",
        "rule": "Must integrate at least two concepts. Must require evaluation, not just identification. Single-concept questions are rejected.",
        "required": ["competing", "evaluate", "BEST", "MOST"],
        "required_verbs": BLOOMS_VERBS[Tier.EVALUATE],
        "min_concepts": 2,
    },
}


def get_tier_verbs(tier: Tier) -> list[str]:
    """Return Bloom's verbs for a tier."""
    return BLOOMS_VERBS[tier]


def get_tier_enforcement(tier: Tier) -> dict:
    """Return enforcement rules for a tier."""
    return TIER_ENFORCEMENT[tier]

