import pytest

from ReDNACoreDemo.core.ingest.value_normalizer import normalize_value


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I'm a morning person, up before sunrise every day.", "morning"),
        ("Total night owl here, usually in bed after midnight.", "evening"),
        ("Early riser club: up by 5 and ready to go.", "morning"),
    ],
)
def test_chronotype_positive(text: str, expected: str) -> None:
    assert normalize_value("BehaviorDNA.Sleep.Chronotype", text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "I usually wake up early-ish when work demands it.",
        "I feel more productive in the evenings but still go to bed before midnight.",
        "Love sunrise hikes but sleep schedule varies.",
    ],
)
def test_chronotype_negative(text: str) -> None:
    assert normalize_value("BehaviorDNA.Sleep.Chronotype", text) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I don't eat meat; strictly vegetarian these days.", "vegetarian"),
        ("I'm pescatarian and crave seafood every week.", "pescatarian"),
        ("I follow a keto plan for energy.", "keto"),
        ("Gluten-free for life thanks to allergies.", "gluten_free"),
        ("Vegan meals only, no exceptions.", "vegan"),
    ],
)
def test_diet_positive(text: str, expected: str) -> None:
    assert normalize_value("BehaviorDNA.Health.Diet", text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "I try to eat healthy most days.",
        "Mostly plant-based but I still have grilled fish sometimes.",
        "Dinner is usually hearty, nothing too specific.",
    ],
)
def test_diet_negative(text: str) -> None:
    assert normalize_value("BehaviorDNA.Health.Diet", text) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I work from home full time; fully remote setup.", "remote"),
        ("My role is onsite, in office five days a week.", "onsite"),
        ("We're hybrid now, two days in office, rest remote.", "hybrid"),
    ],
)
def test_work_location_positive(text: str, expected: str) -> None:
    assert normalize_value("BehaviorDNA.Work.Location", text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "My schedule is flexible with some travel.",
        "I commute occasionally depending on projects.",
        "We have team syncs at the office but it's optional.",
    ],
)
def test_work_location_negative(text: str) -> None:
    assert normalize_value("BehaviorDNA.Work.Location", text) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Quiet weekend plans, prefer small group dinners.", "small"),
        ("I love big parties and a large crowd energy boost.", "large"),
    ],
)
def test_group_size_positive(text: str, expected: str) -> None:
    assert normalize_value("PreferenceDNA.Social.GroupSize", text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "I like hanging out with friends when time allows.",
        "Game nights are fun no matter the crowd.",
        "Social plans vary depending on the week.",
    ],
)
def test_group_size_negative(text: str) -> None:
    assert normalize_value("PreferenceDNA.Social.GroupSize", text) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I run every morning to clear my head.", "running"),
        ("I swim laps whenever the pool opens.", "swimming"),
        ("I bike to work daily when the weather cooperates.", "cycling"),
        ("Evening yoga sessions keep me grounded.", "yoga"),
    ],
)
def test_exercise_type_positive(text: str, expected: str) -> None:
    assert normalize_value("BehaviorDNA.Exercise.Type", text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "I work out often but mix it up a lot.",
        "Group fitness classes are my jam.",
        "I stretch and do mobility work here and there.",
    ],
)
def test_exercise_type_negative(text: str) -> None:
    assert normalize_value("BehaviorDNA.Exercise.Type", text) is None
