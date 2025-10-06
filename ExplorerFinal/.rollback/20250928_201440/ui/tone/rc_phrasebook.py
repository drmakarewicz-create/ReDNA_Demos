PHRASEBOOK = {
    "personality.introversion.high": "you recharge solo and think before you talk",
    "personality.extroversion.high": "you feel energized when you share out loud",
    "rel.connection.empathy.high": "you tune into your partner’s feelings quickly",
    "rel.connection.empathy.medium": "you show care, even if you need a beat to respond",
    "rel.connection.empathy.low": "you’re still figuring out how to respond when emotions spike",
    "rel.communication.direct": "you like to be straight to the point",
    "rel.communication.indirect": "you soften messages first and prefer gentle language",
    "rel.communication.high_context": "you share meaning through tone and context as much as words",
    "rel.communication.low_context": "you prefer clear, literal wording",
    "rel.conflict.style.avoidant": "you need breathing room when tension rises",
    "rel.conflict.style.validator": "you value calm, logical debriefs",
    "rel.conflict.style.volative": "you’re expressive and all-in when things matter",
    "rel.boundaries.needs_decompression": "you do best with a little decompression time",
    "rel.boundaries.protect_evenings": "evenings are your recharge window",
    "rel.attachment.secure": "you believe in taking a team approach",
    "rel.attachment.anxious": "you crave reassurance when things feel unsettled",
    "rel.attachment.avoidant": "you need autonomy to stay steady",
}


def humanize(paths: list[str]) -> list[str]:
    phrases = []
    for key in paths:
        phrase = PHRASEBOOK.get(key)
        if phrase:
            phrases.append(phrase)
    return phrases
