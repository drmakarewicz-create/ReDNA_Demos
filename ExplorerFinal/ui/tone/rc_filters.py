BAN = [
    "UCN",
    "RR",
    "path=",
    "curiosity traits",
    "data points",
    "introverted individual",
]


def scrub(text: str) -> str:
    cleaned = text or ""
    for word in BAN:
        cleaned = cleaned.replace(word, "")
    return cleaned
