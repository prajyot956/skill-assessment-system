"""Local (no-AI) resume parser. Heuristic by design: output is a draft the user reviews.

Every skill carries evidence, a source section, a confidence and an explicit/inferred flag.
Nothing here ever assigns a proficiency level."""
import re
from datetime import date

from app.seeds.skills import CASE_SENSITIVE, IMPLIES

HEADS = {
    "summary": r"(professional\s+|career\s+)?(summary|profile|objective)|about\s+me",
    "education": r"education(al)?(\s+(background|qualifications?))?|academics?|academic\s+(background|qualifications?)",
    "experience": r"(work\s+|professional\s+|relevant\s+)?experience|employment(\s+history)?|internships?(\s+experience)?|work\s+history",
    "projects": r"(academic\s+|personal\s+|key\s+|major\s+)?projects?",
    "skills": r"(technical\s+|key\s+|core\s+)?skills?(\s+(summary|set))?|technical\s+(proficiency|expertise)|technologies|tools\s+(and|&)\s+technologies|competencies",
    "certifications": r"certifications?(\s+(and|&)\s+(courses|training))?|licen[sc]es?|courses|training",
    "interests": r"interests|hobbies",
    "other": r"achievements?|awards?|extra-?curricular\w*|activities|languages|references|declaration|publications|positions\s+of\s+responsibility",
}
HEAD_RES = {k: re.compile(rf"(?:{v})", re.I) for k, v in HEADS.items()}
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE = rf"(?:{MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
RANGE_RE = re.compile(rf"({DATE})\s*(?:-|–|—|to)\s*({DATE}|Present|Current|Now|Ongoing)", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{8,17}\d")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-%]+/?", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?", re.I)
URL_RE = re.compile(r"https?://[^\s,;)\]]+", re.I)
DEGREE_RE = re.compile(
    r"\b(B\.?\s?Tech|B\.?\s?E\.?|B\.?\s?Sc\.?|B\.?\s?C\.?\s?A\.?|B\.?\s?Com\.?|BBA|Bachelor(?:'s)?(?:\s+of)?(?:\s+\w+){0,3}"
    r"|M\.?\s?Tech|M\.?\s?E\.?|M\.?\s?Sc\.?|M\.?\s?C\.?\s?A\.?|MBA|Master(?:'s)?(?:\s+of)?(?:\s+\w+){0,3}|Ph\.?\s?D"
    r"|Diploma(?:\s+in)?|Higher Secondary|HSC|SSC|Intermediate|12th|10th)\b", re.I)
INSTITUTION_RE = re.compile(r"(University|College|Institute|School|Academy|Polytechnic|IIT|NIT|IIIT)", re.I)
ROLE_RE = re.compile(r"(engineer|developer|intern|analyst|manager|trainee|associate|consultant|designer|tester|administrator|"
                     r"architect|scientist|lead|executive|assistant|specialist|programmer|officer)", re.I)
COMPANY_HINT = re.compile(r"(inc|ltd|pvt|llc|technologies|solutions|systems|labs|corp|company|software|infotech|services)\b", re.I)
SEP_RE = re.compile(r"\s+[|@–—-]\s+|\s+at\s+|,\s+")


LABEL_RE = re.compile(r"(tech(nologies)?( stack| used)?|tools|built with|(my )?role|link|url)\s*:", re.I)


def _is_bullet(line):
    return line.startswith("- ")


def _strip_bullet(line):
    return line[2:].strip() if _is_bullet(line) else line.strip()


def split_sections(text: str):
    header, sections, current = [], {}, None
    for line in text.split("\n"):
        probe = re.sub(r"[:\-–_=*#\s]+$", "", re.sub(r"^[-–_=*#\s]+", "", line)).strip()
        hit = None
        if probe and len(probe) <= 40 and not _is_bullet(line):
            for name, rx in HEAD_RES.items():
                if rx.fullmatch(probe):
                    hit = name
                    break
        if hit:
            current = hit
            sections.setdefault(hit, [])
        elif current is None:
            header.append(line)
        else:
            sections[current].append(line)
    return header, sections


def split_entries(lines):
    entries, cur, has_bullet = [], [], False
    for line in lines:
        if not line.strip():
            if cur:
                entries.append(cur)
            cur, has_bullet = [], False
            continue
        if cur and has_bullet and not _is_bullet(line) and not line[0].islower() and not LABEL_RE.match(line):
            entries.append(cur)
            cur, has_bullet = [], False
        cur.append(line)
        has_bullet = has_bullet or _is_bullet(line)
    if cur:
        entries.append(cur)
    return entries


def _norm_url(u):
    u = u.strip().rstrip("/.,;")
    return u if u.lower().startswith("http") else "https://" + u


def parse_personal(header, full_text):
    head_text = "\n".join(header[:15]) or full_text[:600]
    out = {k: None for k in ("full_name", "email", "phone", "location", "linkedin_url", "github_url", "portfolio_url")}
    m = EMAIL_RE.search(head_text) or EMAIL_RE.search(full_text)
    out["email"] = m.group(0).lower() if m else None
    for m in PHONE_RE.finditer(head_text):
        digits = re.sub(r"\D", "", m.group(0))
        if 10 <= len(digits) <= 13 and not RANGE_RE.search(m.group(0)):
            out["phone"] = m.group(0).strip()
            break
    m = LINKEDIN_RE.search(full_text)
    out["linkedin_url"] = _norm_url(m.group(0)) if m else None
    m = GITHUB_RE.search(full_text)
    out["github_url"] = _norm_url(m.group(0)) if m else None
    for m in URL_RE.finditer(head_text):
        if "linkedin.com" not in m.group(0).lower() and "github.com" not in m.group(0).lower():
            out["portfolio_url"] = m.group(0).rstrip("/.,;")
            break
    for line in header[:8]:
        s = line.strip()
        if not s or "@" in s or "http" in s.lower() or len(re.sub(r"\D", "", s)) >= 5 or re.search(r"resume|curriculum|cv\b", s, re.I):
            continue
        words = s.replace(",", " ").split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z.'\-]+", w) for w in words):
            out["full_name"] = s.title() if s.isupper() else s
            break
    for line in header[:10]:
        for piece in re.split(r"[|•·]", line):
            p = piece.strip()
            if "@" not in p and re.fullmatch(r"[A-Z][A-Za-z .]+,\s*[A-Z][A-Za-z .]+", p) and len(p) <= 40:
                out["location"] = p
                break
        if out["location"]:
            break
    return out


def parse_education(lines):
    items = []
    for entry in split_entries(lines):
        # a block holding several degree lines is split per degree
        groups, cur = [], []
        for ln in entry:
            if DEGREE_RE.search(ln) and any(DEGREE_RE.search(x) for x in cur) and not _is_bullet(ln):
                groups.append(cur)
                cur = []
            cur.append(ln)
        groups.append(cur)
        for g in groups:
            text = " ".join(_strip_bullet(x) for x in g)
            deg = DEGREE_RE.search(text)
            inst = None
            for ln in g:
                if INSTITUTION_RE.search(ln):
                    clean = RANGE_RE.sub("", _strip_bullet(ln))
                    parts = [p.strip() for p in re.split(r"\s+[|–—-]\s+|,", clean) if p.strip()]
                    inst = next((p for p in parts if INSTITUTION_RE.search(p)), clean.strip())
                    break
            if not deg and not inst:
                continue
            spec = None
            if deg:
                dline = next((_strip_bullet(x) for x in g if DEGREE_RE.search(x)), "")
                dm = DEGREE_RE.search(dline)
                rest = re.split(r"[|(),]|\d{4}|CGPA|GPA|Percentage", dline[dm.end():])[0]
                rest = re.split(INSTITUTION_RE, rest)[0] if INSTITUTION_RE.search(rest) else rest
                rest = re.sub(r"^\s*(in|of|-|–|:)\s*", "", rest).strip(" -–:")
                spec = rest[:80] or None
            years = [int(y) for y in re.findall(r"\b(19[9]\d|20[0-4]\d)\b", text)]
            details = "; ".join(_strip_bullet(x) for x in g if re.search(r"CGPA|GPA|percentage|%", x, re.I))[:300]
            items.append({"degree": deg.group(0).strip() if deg else None, "specialization": spec,
                          "institution": (inst or "")[:200], "graduation_year": max(years) if years else None,
                          "details": details or None})
    return items[:6]


def _company_title(header_line):
    clean = RANGE_RE.sub("", header_line).strip(" -–|,")
    parts = [p.strip() for p in SEP_RE.split(clean) if p.strip()]
    title = next((p for p in parts if ROLE_RE.search(p)), None)
    rest = [p for p in parts if p != title]
    company = next((p for p in rest if COMPANY_HINT.search(p)), rest[0] if rest else None)
    return (company or ""), title


def parse_experience(lines):
    items = []
    for entry in split_entries(lines):
        head = [ln for ln in entry if not _is_bullet(ln)][:2]
        if not head:
            continue
        joined = " ".join(head)
        rng = RANGE_RE.search(joined)
        company, title = _company_title(head[0])
        if not company and len(head) > 1:
            c2, t2 = _company_title(head[1])
            company, title = c2 or company, title or t2
        body = [_strip_bullet(ln) for ln in entry if ln not in head[:1] and not RANGE_RE.fullmatch(ln.strip())]
        items.append({"company": company[:200], "title": (title or None), "duration": rng.group(0) if rng else None,
                      "kind": "internship" if re.search(r"intern", joined, re.I) else "job",
                      "responsibilities": "\n".join(b for b in body if b)[:3000] or None})
    return items[:10]


def _find_terms(text, terms, case_sensitive):
    pat = r"(?<![A-Za-z0-9+#.])(?:%s)(?![A-Za-z0-9+#])" % "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.search(pat, text, 0 if case_sensitive else re.I)


def _snippet(text, pos):
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    line = text[start:end if end != -1 else None].strip()
    return _strip_bullet(line)[:200]


def parse_projects(lines, taxonomy):
    items = []
    for entry in split_entries(lines):
        first = RANGE_RE.sub("", entry[0]).strip()
        parts = re.split(r"\s+[|–—-]\s+|\s*\(|:\s", first, maxsplit=1)
        name = _strip_bullet(parts[0]).strip(" -–|:")[:200]
        if not name or len(name) < 3:
            continue
        tech_line = next((_strip_bullet(x) for x in entry if re.match(r"-?\s*(tech(nologies)?( stack| used)?|tools|built with)\s*:", x, re.I)), "")
        role_line = next((_strip_bullet(x) for x in entry if re.match(r"-?\s*(my )?role\s*:", x, re.I)), "")
        explicit = [t.strip(" ).") for t in re.split(r"[,;/|]", re.sub(r"^[^:]*:", "", tech_line))] if tech_line else []
        if len(parts) > 1 and not tech_line:
            explicit = [t.strip(" ).") for t in re.split(r"[,;/|]", parts[1])]
        text = " ".join(entry)
        techs = [t for t in explicit if 1 < len(t) <= 30]
        for sk in taxonomy:
            if _find_terms(text, [sk["name"]] + [a for a in sk["aliases"] if len(a) > 2], sk["name"] in CASE_SENSITIVE):
                if sk["name"].lower() not in {t.lower() for t in techs}:
                    techs.append(sk["name"])
        desc_lines = [_strip_bullet(x) for x in entry[1:] if x is not tech_line and not re.match(r"-?\s*(tech|tools|built with|(my )?role)", _strip_bullet(x), re.I)]
        items.append({"name": name, "description": " ".join(desc_lines)[:1000] or None, "technologies": techs[:15],
                      "role": re.sub(r"^[^:]*:\s*", "", role_line)[:150] or None})
    return items[:10]


def parse_certifications(lines):
    items = []
    for ln in lines:
        s = _strip_bullet(ln)
        if not s or len(s) > 150:
            continue
        when = re.search(rf"{DATE}", s)
        clean = re.sub(rf"\(?{DATE}\)?", "", s).strip(" -–|,()")
        parts = [p.strip() for p in re.split(r"\s+[|–—-]\s+|\s+by\s+|,\s+", clean) if p.strip()]
        if parts:
            items.append({"name": parts[0][:200], "issuer": (parts[1][:200] if len(parts) > 1 else None),
                          "completed_on": when.group(0) if when else None})
    return items[:15]


def parse_skills(sections, taxonomy):
    skills_text = "\n".join(sections.get("skills", []))
    tokens = [t.strip(" .•-") for t in re.split(r"[,;|•\n/()]", re.sub(r"^[^:\n]{0,40}:", "", skills_text, flags=re.M))]
    token_lower = {t.lower() for t in tokens if t}
    sources = [("projects", "\n".join(sections.get("projects", []))), ("experience", "\n".join(sections.get("experience", []))),
               ("certifications", "\n".join(sections.get("certifications", []))), ("summary", "\n".join(sections.get("summary", [])))]
    found, matched_tokens = {}, set()

    def add(sk, section, snippet, confidence, inferred):
        rec = found.setdefault(sk["name"], {"name": sk["name"], "category": sk["category"], "evidence": [],
                                            "inferred": True, "confidence": 0.0, "source_section": section})
        rec["evidence"].append({"section": section, "snippet": snippet})
        rec["inferred"] = rec["inferred"] and inferred
        if confidence > rec["confidence"]:
            rec["confidence"], rec["source_section"] = confidence, section

    for sk in taxonomy:
        terms = [sk["name"]] + list(sk["aliases"])
        cs = sk["name"] in CASE_SENSITIVE
        short = [t for t in terms if len(t) <= 2]
        longer = [t for t in terms if len(t) > 2]
        hit_skills = False
        for t in short:
            if (t in tokens) if cs else (t.lower() in token_lower):
                matched_tokens.add(t.lower()); add(sk, "skills", f"Listed in skills: {t}", 0.9, False); hit_skills = True
        if longer and skills_text:
            m = _find_terms(skills_text, longer, cs)
            if m and not hit_skills:
                matched_tokens.add(m.group(0).lower())
                add(sk, "skills", _snippet(skills_text, m.start()), 0.9, False)
        for section, body in sources:
            if not body or (sk["category"] == "Soft Skills" and section not in ("summary",)):
                continue
            m = _find_terms(body, longer, cs) if longer else None
            if m:
                conf = {"projects": 0.65, "experience": 0.65, "certifications": 0.6, "summary": 0.5}[section]
                add(sk, section, _snippet(body, m.start()), conf, False)

    by_name = {s["name"]: s for s in taxonomy}
    for name, rec in list(found.items()):
        if rec["inferred"]:
            continue
        for implied in IMPLIES.get(name, []):
            if implied in by_name and implied not in found:
                add(by_name[implied], rec["source_section"], f"Implied by {name}; not stated directly.", 0.4, True)
        sections_seen = {e["section"] for e in rec["evidence"]}
        if "skills" in sections_seen and sections_seen & {"projects", "experience"}:
            rec["confidence"] = min(0.97, rec["confidence"] + 0.05)  # listed AND demonstrated
    unmatched = []
    known = {t.lower() for sk in taxonomy for t in [sk["name"]] + list(sk["aliases"])}
    for t in tokens:
        tl = t.lower()
        if t and 2 <= len(t) <= 30 and tl not in known and tl not in matched_tokens and not t.isdigit() and t not in unmatched:
            unmatched.append(t)
    out = sorted(found.values(), key=lambda r: (r["category"], -r["confidence"], r["name"]))
    for r in out:
        r["evidence"] = r["evidence"][:4]
        r["confidence"] = round(r["confidence"], 2)
    return out, unmatched[:30]


def build_analysis(d):
    p, missing, strengths, improve, why = d["personal"], [], [], [], []
    for key, label in (("phone", "a phone number"), ("location", "your location"), ("linkedin_url", "a LinkedIn link"),
                       ("github_url", "a GitHub link")):
        if not p.get(key):
            missing.append(f"No {label.replace('a ', '', 1) if label.startswith('a ') else label} found")
    if not d["education"]: missing.append("No education section found")
    if not d["projects"]: missing.append("No projects found")
    if not d["experience"]: missing.append("No work or internship experience found")
    if not d["certifications"]: missing.append("No certifications found")
    if not d["skills"]: missing.append("No recognised skills found")
    explicit = [s for s in d["skills"] if not s["inferred"]]
    if len(explicit) >= 8: strengths.append(f"{len(explicit)} skills clearly stated")
    demonstrated = [s["name"] for s in explicit if {e["section"] for e in s["evidence"]} & {"projects", "experience"}]
    if demonstrated: strengths.append(f"{len(demonstrated)} skills are backed by project or work evidence ({', '.join(demonstrated[:4])})")
    if len(d["projects"]) >= 2: strengths.append(f"{len(d['projects'])} projects listed")
    if any(re.search(r"\d+\s*%|\b\d{2,}\b", (e.get("responsibilities") or "")) for e in d["experience"]):
        strengths.append("Experience includes measurable results")
    if p.get("github_url") or p.get("portfolio_url"): strengths.append("Links to your work are included")
    if not d.get("summary"): improve.append("Add a two to three sentence professional summary")
    listed_only = [s["name"] for s in explicit if s["category"] != "Soft Skills" and {e["section"] for e in s["evidence"]} == {"skills"}]
    if listed_only: improve.append(f"Show these listed skills in a project or role: {', '.join(listed_only[:5])}")
    if any(len(pr.get("description") or "") < 40 for pr in d["projects"]): improve.append("Some projects have little or no description")
    if d["experience"] and not any(re.search(r"\d", e.get("responsibilities") or "") for e in d["experience"]):
        improve.append("Add numbers to experience bullets (users, speed-ups, percentages)")
    if len(d["skills"]) and all(s["category"] == "Soft Skills" for s in d["skills"]): improve.append("Add technical skills")
    why.append("Name, email and phone were read from the top of the document." if p.get("email") else "No email address was found near the top of the document.")
    why.append(f"{len(explicit)} skills were matched to the skill list. {len(d['skills']) - len(explicit)} other(s) were inferred from related tools and are marked as inferred.")
    why.append("Listing a skill is not proof of proficiency. Skill levels are set only by assessments.")
    if d.get("unmatched_skills"): why.append(f"{len(d['unmatched_skills'])} items in your skills section were not recognised. You can add them manually.")
    return {"missing": missing, "strengths": strengths, "improvements": improve, "explanations": why}


def parse_resume(text: str, taxonomy: list[dict]) -> dict:
    header, sections = split_sections(text)
    personal = parse_personal(header, text)
    skills, unmatched = parse_skills(sections, taxonomy)
    draft = {
        "personal": personal,
        "summary": " ".join(_strip_bullet(x) for x in sections.get("summary", []) if x.strip())[:2000] or None,
        "education": parse_education(sections.get("education", [])),
        "experience": parse_experience(sections.get("experience", [])),
        "projects": parse_projects(sections.get("projects", []), taxonomy),
        "certifications": parse_certifications(sections.get("certifications", [])),
        "skills": skills, "unmatched_skills": unmatched,
        "interests": [t.strip() for t in re.split(r"[,;|\n]", " ".join(_strip_bullet(x) for x in sections.get("interests", []))) if 2 < len(t.strip()) <= 60][:10],
    }
    draft["analysis"] = build_analysis(draft)
    return draft
