"""Optional AI helpers. Every function returns suggestions only and raises AIUnavailable when AI is off or fails."""
from .provider import AIUnavailable, get_provider


def _need():
    p = get_provider()
    if p is None:
        raise AIUnavailable("not configured")
    return p


def suggest_summary(facts: dict) -> str:
    out = _need().complete_json("Write a professional summary of 2-3 sentences, first person omitted, using ONLY the facts given. "
                                'Respond with JSON: {"summary": str}', str(facts)[:4000], max_tokens=400)
    s = out.get("summary") if isinstance(out, dict) else None
    if not isinstance(s, str) or not s.strip():
        raise AIUnavailable("bad summary")
    return s.strip()[:1000]


def explain_career(rec: dict) -> str:
    facts = {k: rec[k] for k in ("role", "match_pct", "why", "next_steps", "improvement_areas")}
    out = _need().complete_json("Explain this career match to a student in 3-4 plain sentences. Do not change or invent numbers. "
                                'Respond with JSON: {"explanation": str}', str(facts)[:4000], max_tokens=500)
    s = out.get("explanation") if isinstance(out, dict) else None
    if not isinstance(s, str) or not s.strip():
        raise AIUnavailable("bad explanation")
    return s.strip()[:1500]


def suggest_resources(skill: str, level: str) -> list[dict]:
    out = _need().complete_json("Suggest up to 4 kinds of learning resources. Do NOT include URLs. "
                                'Respond with JSON: {"suggestions":[{"title":str,"why":str}]}', f"Skill: {skill}. Level: {level}.", max_tokens=600)
    items = out.get("suggestions") if isinstance(out, dict) else None
    if not isinstance(items, list):
        raise AIUnavailable("bad suggestions")
    return [{"title": str(i["title"])[:120], "why": str(i.get("why", ""))[:240]} for i in items[:4] if isinstance(i, dict) and i.get("title")]


def interview_feedback(role: str, qa: list[dict]) -> dict:
    out = _need().complete_json(
        "You are an interviewer giving constructive feedback. Do NOT give numeric scores or grades. "
        'Respond with JSON: {"overall":str,"per_question":[{"index":int,"strengths":[str],"improvements":[str]}],"knowledge_gaps":[str]}',
        str({"role": role, "answers": qa})[:8000], max_tokens=1800)
    if not isinstance(out, dict) or not isinstance(out.get("overall"), str):
        raise AIUnavailable("bad feedback")
    per = []
    for p in out.get("per_question", []) if isinstance(out.get("per_question"), list) else []:
        if isinstance(p, dict) and isinstance(p.get("index"), int):
            per.append({"index": p["index"], "strengths": [str(x)[:240] for x in p.get("strengths", [])[:4]] if isinstance(p.get("strengths"), list) else [],
                        "improvements": [str(x)[:240] for x in p.get("improvements", [])[:4]] if isinstance(p.get("improvements"), list) else []})
    gaps = [str(x)[:160] for x in out.get("knowledge_gaps", [])[:8]] if isinstance(out.get("knowledge_gaps"), list) else []
    return {"overall": out["overall"][:1500], "per_question": per, "knowledge_gaps": gaps}


def generate_questions(skill_name: str, difficulty: str, count: int) -> list[dict]:
    """Use AI to generate fresh assessment questions for a skill.
    Returns list of dicts with keys: topic, type, text, options, answer, explanation, accepted_answers
    type is one of: single, multiple, true_false, short, coding
    """
    p = _need()
    prompt = f"""Generate {count} assessment questions about {skill_name} at {difficulty} level.

Respond with JSON only:
{{
  "questions": [
    {{
      "topic": "topic name",
      "type": "single",
      "text": "question text",
      "options": ["opt1", "opt2", "opt3", "opt4"],
      "answer": 0,
      "explanation": "why this answer is correct"
    }}
  ]
}}

Rules:
- type can be: single (answer=index 0-based), multiple (answer=[indexes]), true_false (answer=true/false, options=null), short (answer="string", options=null), coding (fill-in-blank, answer="string", options=null)
- For single/multiple questions, provide exactly 4 options
- For true_false, set options to null
- For short/coding, set options to null and answer to the expected short text
- Include at least 1 coding (fill-in-code) question with ___ as the blank marker
- Make questions educational and accurate for {difficulty} level
- Vary the topics and question types
"""
    out = p.complete_json(
        "You are an expert educator creating assessment questions. Always respond with valid JSON only.",
        prompt,
        max_tokens=3000
    )
    items = out.get("questions") if isinstance(out, dict) else None
    if not isinstance(items, list) or not items:
        raise AIUnavailable("AI returned no questions")
    return items[:count]


def generate_interview_questions(role_name: str, difficulty: str, count: int, exclude_texts: list[str] = None) -> list[dict]:
    """Generate dynamic, role-specific interview questions using AI."""
    p = _need()
    exclude_prompt = ""
    if exclude_texts:
        exclude_prompt = "Do NOT repeat or ask any of these questions:\n" + "\n".join(f"- {t}" for t in exclude_texts[:20])

    prompt = f"""Generate {count} technical and role-specific mock interview questions for a candidate interviewing for the role of '{role_name}' at {difficulty} level.

Ensure questions are uniquely tailored to the specific tools, workflows, and problems a {role_name} deals with in real software engineering.
{exclude_prompt}

Respond with JSON only:
{{
  "questions": [
    {{
      "skill": "Specific tech or skill name",
      "difficulty": "{difficulty}",
      "text": "Interview question text",
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}

Rules:
- Questions must be distinct and specific to {role_name}
- For each question, provide 3 to 5 key technical terms or concepts expected in a strong answer
- Include 1 practical situational scenario question directly relevant to {role_name}
"""
    out = p.complete_json(
        "You are an expert technical interviewer hiring for specialized technology roles. Respond with JSON only.",
        prompt,
        max_tokens=2500
    )
    items = out.get("questions") if isinstance(out, dict) else None
    if not isinstance(items, list) or not items:
        raise AIUnavailable("AI returned no interview questions")
    clean = []
    for q in items[:count]:
        if isinstance(q, dict) and q.get("text"):
            kw = [str(k).lower().strip() for k in q.get("keywords", []) if str(k).strip()][:6]
            clean.append({
                "skill": str(q.get("skill", role_name))[:60],
                "difficulty": difficulty,
                "text": str(q.get("text")).strip()[:500],
                "keywords": kw or [role_name.lower()]
            })
    if not clean:
        raise AIUnavailable("Could not parse interview questions")
    return clean
