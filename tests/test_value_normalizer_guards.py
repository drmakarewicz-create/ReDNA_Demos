import pytest

from ReDNACoreDemo.core.ingest.value_normalizer import normalize_value


CASES = [
    # --- Outdoor should NOT trigger in "stay in"/"quiet" phrasing
    ("I usually stay in and read on weekends", "BehaviorDNA.Exercise.Outdoor", None),
    ("Looking forward to a quiet weekend with no plans", "BehaviorDNA.Exercise.Outdoor", None),

    # --- Frequency requires exercise + explicit cadence
    ("I drink three cups of coffee every morning", "BehaviorDNA.Exercise.Frequency", None),
    ("I take cold showers every morning", "BehaviorDNA.Exercise.Frequency", None),
    ("I go hiking every weekend", "BehaviorDNA.Exercise.Frequency", "weekly"),
    ("I go hiking every weekend", "BehaviorDNA.Exercise.Outdoor", True),

    # --- Eye vs Hair: eye color only if eyes/iris are mentioned; hair only if 'hair'
    ("My hair is brown", "PaDNA.EyeDNA.IrisColor", None),
    ("My hair is brown", "PaDNA.HairDNA.Color.Natural", "brown"),
    ("My eyes are kind of blueish gray", "PaDNA.EyeDNA.IrisColor", "blue_gray"),

    # --- Height: require explicit mention of tall/height/short (not vague)
    ("I'm pretty tall", "PaDNA.BodyDNA.Height", None),
    ("My height is around six feet", "PaDNA.BodyDNA.Height", None),

    # Bonus sanity: explicit outdoor tokens
    ("trail run outside with friends", "BehaviorDNA.Exercise.Outdoor", True),

    # Tier 1 expansions
    ("My hair is gray", "PaDNA.HairDNA.Color.Natural", "gray"),
    ("I'm 32 years old", "BasicDNA.Age", "32"),
    ("I'm married and we have two kids", "BasicDNA.RelationshipStatus", "married"),

    # Tier 2 expansions
    ("I'm a morning person up before 5", "BehaviorDNA.Sleep.Chronotype", "morning"),
    ("I don't eat meat anymore", "BehaviorDNA.Health.Diet", "vegetarian"),
    ("I work from home three days a week", "BehaviorDNA.Work.Location", "remote"),
]


@pytest.mark.parametrize(
    "text, trait_id, expected",
    CASES,
    ids=[
        "stay-in-outdoor-none",
        "quiet-weekend-outdoor-none",
        "coffee-morning-freq-none",
        "cold-shower-freq-none",
        "hiking-weekend-freq-weekly",
        "hiking-weekend-outdoor-true",
        "hair-brown-eye-none",
        "hair-brown-hair-brown",
        "blueish-gray-eyes-eye-bluegray",
        "pretty-tall-height-none",
        "explicit-height-mention-none",
        "trail-run-outdoor-true",
        "hair-gray-hair-gray",
        "age-explicit-32",
        "relationship-married",
        "chronotype-morning",
        "diet-vegetarian",
        "work-location-remote",
    ],
)
def test_normalizer_guards(text, trait_id, expected):
    assert normalize_value(trait_id, text) == expected
