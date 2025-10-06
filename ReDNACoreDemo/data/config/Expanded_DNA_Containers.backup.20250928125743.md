Last updated: 2025-09-28
Purpose: Extend ReDNA Core trait schema with additional containers to broaden coverage, including finer-grained PaDNA (Physical Appearance DNA). Each container seeds with defaults ucn=0, curiosity=1.0 unless specified. Containers marked sensitive: true require governance rules.

## Identity
Description: Core identifying attributes.
Traits: Full name, pronouns, date of birth, location, nationality, preferred language(s).

## PaDNA – Physical Appearance (granular)
Description: Detailed capture of physical appearance and self-presentation.
Sub-containers / traits:
- Facial Features: eye color, hair color, facial hair, facial shape.
- Body Build: height, weight range, body type, posture.
- Skin: tone, undertone, freckling, complexion sensitivity.
- Hair: texture (straight/curly), style preference, length, natural vs dyed.
- Voice: pitch, tone, accent, speech rate.
- Style / Clothing: typical dress (casual, formal, sporty), color preferences, accessories.
- Distinguishing Features: tattoos, piercings, scars, unique identifiers.
sensitive: false (distinguishing features may be sensitive:true per governance)

## Writing / Communication Style
Description: Textual and verbal communication patterns.
Traits: formality index, emoji frequency, humor style, punctuation habits, verbosity, directness vs indirectness.

## Personality
Description: Core personality dimensions.
Traits: OCEAN + sub-facets (trust, warmth, assertiveness).

## Emotion / Affect
Description: Emotional reactivity and expression.
Traits: baseline mood, regulation, empathy, optimism/pessimism.

## Social
Description: Social interaction preferences.
Traits: group vs one-on-one, recharge style, community involvement.

## Family & Relationships  (sensitive:true)
Description: Family role and relationship patterns.
Traits: marital status, parenting style, closeness to family, sibling relationships.

## Cognitive Style
Description: Thinking/processing preferences.
Traits: analytical vs holistic, visual vs verbal, detail vs big picture, decision speed, ambiguity tolerance.

## Work / Professional
Description: Occupational orientation.
Traits: industry, role, leadership style, teamwork orientation, remote vs on-site, career stage.

## Taste / Entertainment
Description: Cultural and leisure preferences.
Traits: music genres, film/TV, book types, gaming genres, food/drink, subculture fandoms.

## Gaming
Description: Play styles and affinities.
Traits: casual vs competitive, platform, favorite genres, play frequency.

## Health  (sensitive:true)
Description: Physical and mental health indicators.
Traits: exercise frequency, sleep quality, dietary habits, stress management, chronic conditions.

## Finance  (sensitive:true)
Description: Financial orientation and literacy.
Traits: budgeting style, investing risk tolerance, debt orientation, insurance awareness.

## Routine / Lifestyle
Description: Daily patterns.
Traits: wake/sleep schedule, commuting style, household composition, leisure allocation.

## Learning
Description: Learning preferences.
Traits: self-paced vs structured, mentor vs peer, lifelong learning openness, subject interests.

## Behavior
Description: Observable actions.
Traits: punctuality, follow-through, adaptability, conflict style.

## Values / Beliefs  (sensitive:true if political/religious)
Description: Core guiding values.
Traits: honesty, independence, altruism, equality, loyalty.

## Digital / Technology
Description: Digital literacy and orientation.
Traits: early adopter vs late adopter, device ecosystem, cybersecurity hygiene, privacy sensitivity.

## Cultural / Civic Engagement  (sensitive:true)
Description: Broader cultural and societal identity.
Traits: heritage, traditions, religious/spiritual practice, political orientation, civic engagement.

## Environmental Orientation
Description: Attitudes toward sustainability/environment.
Traits: eco-habits, recycling, carbon-awareness, climate concern.

## Motivations / Goals
Description: Life goals and motivational drivers.
Traits: intrinsic vs extrinsic, novelty seeking, mastery, long vs short-term focus.

## Safety / Risk
Description: Safety, risk, and resilience.
Traits: physical risk-taking, resilience/grit, cybersecurity hygiene, change orientation.
