# BeliefDNA Coach

**Philosophy & Values Simulator**

## Purpose

The BeliefDNA Coach translates a user's psychological and value-based ReDNA data into reasoned philosophical positions and moral arguments. It acts as a "belief interpreter" — users input complex or provocative questions, and the system responds as they would, citing ReDNA evidence.

## Key Features

- **Philosophical Reasoning**: Generates nuanced answers to moral, ethical, and existential questions
- **Evidence-Based**: All responses cite specific ReDNA containers and confidence levels
- **Contradiction Detection**: Identifies inconsistencies between stated beliefs and behavioral/psychological data
- **Feedback Loop**: User agreement/disagreement refines underlying belief and reasoning traits
- **Transparent Reasoning**: Shows which traits influenced each answer and how

## ReDNA Data Sources

- **BeliefValueDNA**: Moral foundations, political orientation, life philosophy
- **PsyDNA.PersonalityDNA**: Agreeableness, Openness, Conscientiousness
- **MotivationDNA**: Autonomy, achievement drive, purpose orientation
- **CogDNA.CognitiveStyleDNA**: Analytical/intuitive balance, need for closure
- **EmDNA**: Empathy, emotional regulation, affect baseline

## Example Questions

- **Existential**: "Do humans have free will?"
- **Moral**: "Is lying ever morally acceptable?"
- **Political**: "Should the government regulate speech?"
- **Social**: "Are humans inherently cooperative or competitive?"
- **Psychological**: "What makes a person truly happy?"

## Output Format

Each response includes:
1. **Reasoned Answer**: How the user would likely respond based on their ReDNA
2. **Reasoning Map**: Which traits influenced the answer and their confidence levels
3. **Similarity Score**: How well the answer matches the user's actual belief patterns
4. **Evidence Links**: Relevant ReDNA containers that informed the response
5. **Contradictions**: Any inconsistencies detected in the reasoning

## Endpoints

- `GET /api/coach/beliefdna_coach/panel` - Unified panel data
- `POST /api/coach/beliefdna_coach/render` - Generate belief-based answer
- `POST /api/coach/beliefdna_coach/feedback` - Submit user feedback to refine traits

## Privacy & Governance

- Sensitive beliefs (religious/political) marked `sensitive: true`
- User consent required to read/write sensitive belief data
- Outputs use high-level moral foundations instead of political labels
- All prompts, outputs, and ratings anonymized in logs

## Version

0.1.0 - Initial implementation with stub reasoning engine
