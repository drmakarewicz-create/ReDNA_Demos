import pytest

from ReDNACoreDemo.core.ingest.value_normalizer import normalize_value

CASES = [
    ("My hair is brown", "PaDNA.HairDNA.Color.Natural", "brown"),
    ("I have brown hair", "PaDNA.HairDNA.Color.Natural", "brown"),
    ("My eyes are brown", "PaDNA.HairDNA.Color.Natural", None),
    ("My hair is blueish gray", "PaDNA.HairDNA.Color.Natural", None),
    ("I dyed my hair purple", "PaDNA.HairDNA.Color.Natural", None),
    ("My hair is dark brown", "PaDNA.HairDNA.Color.Natural", "brown"),
    ("My hair is light blonde", "PaDNA.HairDNA.Color.Natural", "blonde"),

    ("I'm 30 years old", "BasicDNA.Age", "30"),
    ("I am 28", "BasicDNA.Age", "28"),
    ("I'm in my early 30s", "BasicDNA.Age", "30s"),
    ("I'm in my late 20s", "BasicDNA.Age", "20s"),
    ("I'm pretty tall", "BasicDNA.Age", None),

    ("I'm married", "BasicDNA.RelationshipStatus", "married"),
    ("I'm single", "BasicDNA.RelationshipStatus", "single"),
    ("relationship unclear", "BasicDNA.RelationshipStatus", None),
    ("I am 6 feet tall", "PaDNA.BodyDNA.Height", "183cm"),
    ("I'm 5 ft 10 in", "PaDNA.BodyDNA.Height", "178cm"),
    ("He is 5'11\"", "PaDNA.BodyDNA.Height", "180cm"),
    ("My height is 183 cm", "PaDNA.BodyDNA.Height", "183cm"),
    ("I am 1.83 m", "PaDNA.BodyDNA.Height", "183cm"),
    ("I'm pretty tall", "PaDNA.BodyDNA.Height", None),
    ("I'm in my early 30s", "PaDNA.BodyDNA.Height", None),
]


@pytest.mark.parametrize("text, trait_id, expected", CASES)
def test_tier1_normalizers(text, trait_id, expected):
    assert normalize_value(trait_id, text) == expected
