"""AI-assisted resume extraction. Output is validated and coerced into the same draft shape as the
local parser; skills are mapped to the taxonomy; anything unusable raises AIUnavailable (-> local fallback)."""
import re

from .provider import AIUnavailable, get_provider

SYSTEM = ("You extract structured data from resumes. Respond with ONE JSON object only, no prose. "
          "Use null for anything not present; never invent information. Do not rate proficiency.")
SCHEMA = """{"personal":{"full_name":str|null,"email":str|null,"phone":str|null,"location":str|null,"linkedin_url":str|null,"github_url":str|null,"portfolio_url":str|null},
"summary":str|null,
"education":[{"degree":str|null,"specialization":str|null,"institution":str,"graduation_year":int|null,"details":str|null}],
"experience":[{"company":str,"title":str|null,"kind":"job"|"internship","duration":str|null,"responsibilities":str|null}],
"projects":[{"name":str,"description":str|null,"technologies":[str],"role":str|null}],
"certifications":[{"name":str,"issuer":str|null,"completed_on":str|null}],
"skills":[{"name":str,"evidence":str,"section":"skills"|"projects"|"experience"|"certifications"|"summary","explicit":bool}],
"interests":[str]}"""


def _s(v, n):
    return v.strip()[:n] if isinstance(v, str) and v.strip() else None


def _list(v):
    return v if isinstance(v, list) else []


def normalize(raw, taxonomy):
    if not isinstance(raw, dict) or not isinstance(raw.get("personal"), dict):
        raise AIUnavailable("unexpected structure")
    pr = raw["personal"]
    personal = {k: _s(pr.get(k), 300) for k in ("full_name", "email", "phone", "location", "linkedin_url", "github_url", "portfolio_url")}
    out = {"personal": personal, "summary": _s(raw.get("summary"), 2000), "education": [], "experience": [],
           "projects": [], "certifications": [], "skills": [], "unmatched_skills": [], "interests": []}
    for e in _list(raw.get("education"))[:6]:
        if isinstance(e, dict) and _s(e.get("institution"), 200):
            y = e.get("graduation_year")
            out["education"].append({"degree": _s(e.get("degree"), 150), "specialization": _s(e.get("specialization"), 150),
                                     "institution": _s(e.get("institution"), 200),
                                     "graduation_year": y if isinstance(y, int) and 1950 <= y <= 2100 else None,
                                     "details": _s(e.get("details"), 2000)})
    for e in _list(raw.get("experience"))[:10]:
        if isinstance(e, dict) and _s(e.get("company"), 200):
            out["experience"].append({"company": _s(e.get("company"), 200), "title": _s(e.get("title"), 150),
                                      "kind": "internship" if e.get("kind") == "internship" else "job",
                                      "duration": _s(e.get("duration"), 100), "responsibilities": _s(e.get("responsibilities"), 4000)})
    for e in _list(raw.get("projects"))[:10]:
        if isinstance(e, dict) and _s(e.get("name"), 200):
            techs = [t.strip()[:40] for t in _list(e.get("technologies")) if isinstance(t, str) and t.strip()][:15]
            out["projects"].append({"name": _s(e.get("name"), 200), "description": _s(e.get("description"), 3000),
                                    "technologies": techs, "role": _s(e.get("role"), 150)})
    for e in _list(raw.get("certifications"))[:15]:
        if isinstance(e, dict) and _s(e.get("name"), 200):
            out["certifications"].append({"name": _s(e.get("name"), 200), "issuer": _s(e.get("issuer"), 200), "completed_on": _s(e.get("completed_on"), 40)})
    lookup = {}
    for sk in taxonomy:
        for t in [sk["name"]] + list(sk["aliases"]):
            lookup[t.lower()] = sk
    seen = {}
    for s in _list(raw.get("skills"))[:80]:
        if not isinstance(s, dict) or not isinstance(s.get("name"), str):
            continue
        sk = lookup.get(s["name"].strip().lower())
        if not sk:
            if len(s["name"].strip()) <= 30 and s["name"].strip() not in out["unmatched_skills"]:
                out["unmatched_skills"].append(s["name"].strip())
            continue
        section = s.get("section") if s.get("section") in ("skills", "projects", "experience", "certifications", "summary") else "skills"
        explicit = s.get("explicit") is not False
        conf = {"skills": 0.9, "projects": 0.65, "experience": 0.65, "certifications": 0.6, "summary": 0.5}[section] if explicit else 0.4
        rec = seen.setdefault(sk["name"], {"name": sk["name"], "category": sk["category"], "evidence": [], "inferred": True,
                                           "confidence": 0.0, "source_section": section})
        rec["evidence"].append({"section": section, "snippet": _s(s.get("evidence"), 200) or ""})
        rec["inferred"] = rec["inferred"] and not explicit
        if conf > rec["confidence"]:
            rec["confidence"], rec["source_section"] = conf, section
    out["skills"] = sorted(seen.values(), key=lambda r: (r["category"], -r["confidence"], r["name"]))
    out["interests"] = [i.strip()[:60] for i in _list(raw.get("interests")) if isinstance(i, str) and i.strip()][:10]
    return out


def extract_with_ai(text: str, taxonomy):
    provider = get_provider()
    if provider is None:
        raise AIUnavailable("not configured")
    prompt = f"Extract this resume into the following JSON schema:\n{SCHEMA}\n\nRESUME TEXT:\n{text[:12000]}"
    return normalize(provider.complete_json(SYSTEM, prompt, max_tokens=3500), taxonomy)


def fill_gaps_locally(ai_draft, local_draft):
    """AI sometimes misses plain contact details; fill only empty fields from the local parse."""
    for k, v in local_draft["personal"].items():
        if not ai_draft["personal"].get(k) and v:
            ai_draft["personal"][k] = v
    return ai_draft
