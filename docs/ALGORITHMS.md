# How scores and matches are calculated

Nothing numeric in this application comes from AI. Every number below is computed by deterministic code
(`backend/app/services/assessment_service.py`, `career_service.py`) and is covered by tests whose expected values are worked out by hand.

## 1. Assessment scoring (server-side)

| Question type | Correct when |
|---|---|
| Single choice, True/False | the chosen option is the correct one |
| Multiple select | the chosen set **exactly equals** the correct set (no partial credit; selecting everything scores zero) |
| Short answer | the answer, after lower-casing and removing spaces and punctuation, equals one of the accepted answers |

Marks come from the question (seed default: beginner 1, intermediate 2, advanced 3).

```
percentage  = obtained marks / total marks of ALL questions in the attempt x 100   (unanswered = 0 marks)
accuracy    = correct / answered x 100                                              (0 if nothing answered)
category    = Advanced >= 80 | Proficient >= 60 | Developing >= 40 | Needs improvement < 40
topic %     = marks earned in topic / marks available in topic
strengths   = topics >= 75%  (strongest first)      weaknesses = topics < 50%  (weakest first)
```

**Timing.** `expires_at` is set by the server when the attempt starts. The browser countdown is cosmetic and is synchronised with the server clock. Answers saved after `expires_at` + 3 s grace are rejected; an expired attempt is scored on whatever was saved.

**Question selection.** Chosen difficulty first, shuffled; if the pool is short, the nearest difficulty levels fill the rest (the UI says so). No question repeats within an attempt. The question ids are snapshotted at start, so editing the bank never changes an attempt in progress.

## 2. Verified proficiency

A score on an easier test says less about ability, so the percentage is weighted by difficulty:

```
proficiency = percentage x weight        weight: beginner 0.6 | intermediate 0.85 | advanced 1.0
```

Example: 100% on a beginner test gives 60. The **latest** attempt for a skill defines the current proficiency; earlier attempts remain in history.
Only assessments set `proficiency_pct`. Resume extraction and manual confirmation never do.

### Evidence levels
1. `resume_detected`: seen on a resume (kept as evidence with snippet, section and confidence; not stored as a skill until the user accepts it)
2. `user_confirmed`: the user accepted or added it
3. `assessment_verified`: derived: `proficiency_pct` exists

## 3. Career match

Each role lists required skills with a **weight** (importance) and a **required level** (% proficiency), both editable by admins.

Per required skill, the user earns a credit between 0 and 1:

| Situation | Credit |
|---|---|
| Assessed, proficiency >= required | **1.0** |
| Assessed, below required | proficiency / required |
| Confirmed by the user, not assessed | **0.4** |
| Only seen on a resume | 0.2 |
| Not in profile | 0 |

```
base % = sum(weight x credit) / sum(weight) x 100
```

Then small, capped adjustments are added **only if base > 0** (interests or education alone never create a match):

| Adjustment | Rule | Cap |
|---|---|---|
| Projects | 4 x (required skills named in your projects / required skills) | +4 |
| Education | +3 if a degree or specialization contains one of the role's education keywords | +3 |
| Interests | 3 x min(1, matching interests / 2), matching by the role's interest tags | +3 |

```
match % = min(100, base % + adjustments)
```

A user who lists every required skill but verifies none scores 40 %, by design. The explanation shown to the user lists each term.

### Worked example (frontend developer, weights HTML 3, CSS 3, JavaScript 3, React 2, Git 1, REST APIs 1, Communication 1; total 14)
HTML assessed 70 vs 70 -> 1.0; CSS assessed 35 vs 70 -> 0.5; JavaScript confirmed only -> 0.4; others missing.
`(3x1.0 + 3x0.5 + 3x0.4) / 14 = 5.7 / 14 = 40.7 %`. Adding the interest "web design" (+1.5), a "Computer Science" degree (+3) and a project using HTML and CSS (2 of 7 skills = +1.1) gives **46.3 %**. This exact case is a test.

## 4. Skill-gap priority

`deficit = weight x (1 - credit)`; **high** if >= 2.0, **medium** if >= 1.0, otherwise **low**; skills that meet the requirement have no priority.

## 5. Roadmap
- Built from the target role's unmet skills, highest deficit first, at most 8 skills.
- Per skill: up to two learning resources (matching level first), one practice exercise (focused on weak topics from your latest attempt), one fitting mini-project, and an assessment item if the skill has questions.
- **Progress changes only when you change it.** Taking an assessment does not tick anything off; it marks the roadmap *out of date* and offers a rebuild, which keeps the status of items that still exist.

## 6. Mock interviews
Questions come from a curated bank filtered by the role's skills. There are **no scores**. Bank mode shows which expected key terms your answer mentioned (a rough guide, labelled as such). If an AI provider is configured, written feedback is added, and the AI is instructed not to grade.
