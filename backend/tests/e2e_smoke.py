"""Live end-to-end check of the full user journey against a RUNNING server (not part of pytest).
Usage: python tests/e2e_smoke.py http://127.0.0.1:5000"""
import io, sys, sqlite3
import requests

sys.path.insert(0, ".")
from tests.helpers import make_pdf

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000").rstrip("/")
s = requests.Session()
step = 0


def check(label, cond, extra=""):
    global step
    step += 1
    print(f"{step:2d}. {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        sys.exit(1)


def call(method, path, **kw):
    headers = kw.pop("headers", {})
    if method != "get":
        headers["X-CSRFToken"] = s.get(BASE + "/api/auth/csrf").json()["data"]["csrf_token"]
    r = getattr(s, method)(BASE + path, headers=headers, **kw)
    return r, r.json()


r, j = call("post", "/api/auth/register", json={"full_name": "Ananya Rao", "email": "e2e@example.com", "password": "Str0ngPass1", "confirm_password": "Str0ngPass1"})
check("register + auto sign-in", r.status_code == 201)
r, j = call("post", "/api/resumes", files={"file": ("cv.pdf", io.BytesIO(make_pdf()), "application/pdf")})
rid = j["data"]["id"]
check("upload PDF resume", r.status_code == 201 and j["data"]["status"] == "parsed", f"(parsed by {j['data']['parse_method']})")
r, j = call("get", "/api/profile")
check("profile untouched by upload", j["data"]["education"] == [] and j["data"]["phone"] is None)
r, j = call("get", f"/api/resumes/{rid}/review")
d = j["data"]["diff"]
check("review has education, projects, skills", len(d["education"]["new"]) == 1 and len(d["projects"]["new"]) == 2 and len(d["skills"]["new"]) >= 10)
r, j = call("post", f"/api/resumes/{rid}/confirm", json={"confirm": True, "profile": {"phone": "+91 98765 43210", "location": "Pune, Maharashtra"},
    "education": {"add": d["education"]["new"]}, "projects": {"add": d["projects"]["new"]},
    "skills": [{"name": n} for n in ("Python", "SQL", "HTML", "CSS", "JavaScript", "Git")]})
check("confirm selected items", r.status_code == 200, str(j["data"]["applied"]))
r, j = call("get", "/api/skills/mine")
check("skills confirmed, none verified yet", len(j["data"]) == 6 and all(x["proficiency_pct"] is None for x in j["data"]))

r, j = call("get", "/api/assessments/catalog")
sql = next(a for c in j["data"]["categories"] for a in c["assessments"] if a["skill"] == "SQL")
r, j = call("post", "/api/assessments/attempts", json={"assessment_id": sql["id"], "difficulty": "intermediate", "num_questions": 10, "duration_minutes": 15})
att = j["data"]["attempt_id"]
check("start SQL assessment", r.status_code == 201)
r, j = call("get", f"/api/assessments/attempts/{att}")
text = r.text
check("no answer keys in attempt payload", all(k not in text for k in ("is_correct", "accepted_answers", "explanation")))
qs = j["data"]["questions"]
# look up correct answers straight from the DB (test-only; the API never exposes them)
db = sqlite3.connect("instance/app.db")
answers = {}
for q in qs[:7]:  # answer 7 of 10 correctly, leave 3 blank
    if q["type"] == "short":
        import json as _j
        answers[str(q["id"])] = _j.loads(db.execute("select accepted_answers from questions where id=?", (q["id"],)).fetchone()[0])[0]
    else:
        ids = [x[0] for x in db.execute("select id from question_options where question_id=? and is_correct=1", (q["id"],))]
        answers[str(q["id"])] = ids if q["type"] == "multiple" else ids[0]
r, j = call("put", f"/api/assessments/attempts/{att}/answers", json={"answers": answers})
check("autosave answers", r.status_code == 200)
r, j = call("post", f"/api/assessments/attempts/{att}/submit")
r, j = call("get", f"/api/assessments/attempts/{att}/result")
res = j["data"]
check("server-side scoring", res["correct"] == 7 and res["unanswered"] == 3 and res["incorrect"] == 0, f"({res['percentage']}% {res['performance_category']}, level {res['proficiency_pct']}%)")
r, j = call("get", "/api/skills/mine")
sql_skill = next(x for x in j["data"] if x["name"] == "SQL")
check("SQL now assessment-verified", sql_skill["evidence_level"] == "assessment_verified" and sql_skill["proficiency_pct"] == round(res["percentage"] * 0.85, 1))

r, j = call("get", "/api/careers/recommendations")
recs = j["data"]["recommendations"]
check("career recommendations ranked", len(recs) >= 3 and recs[0]["match_pct"] >= recs[-1]["match_pct"], f"(top: {recs[0]['role']} {recs[0]['match_pct']}%)")
fe = next(x for x in recs if x["role"] == "Frontend Developer")
r, j = call("put", "/api/careers/target", json={"role_id": fe["role_id"]})
r, j = call("get", f"/api/careers/{fe['role_id']}/gap")
check("gap analysis separates verified from claimed", {"unverified", "missing"} <= {x["state"] for x in j["data"]["skills"]})
r, j = call("post", "/api/roadmap/generate")
rm = j["data"]
check("roadmap generated for target", r.status_code == 201 and rm["total"] > 5 and rm["completed"] == 0, f"({rm['total']} items, 0 done)")
r, j = call("patch", f"/api/roadmap/items/{rm['items'][0]['id']}", json={"status": "completed"})
check("user marks an item complete", j["data"]["completed"] == 1)
r, j = call("get", "/api/practice/projects")
check("practice projects ranked", len(j["data"]) >= 10 and j["data"][0]["relevance"] >= j["data"][-1]["relevance"])
r, j = call("post", "/api/interviews", json={"role_id": fe["role_id"], "difficulty": "beginner", "num_questions": 4})
iid = j["data"]["id"]
call("put", f"/api/interviews/{iid}/answers/0", json={"answer": "Semantic HTML helps accessibility and SEO."})
r, j = call("post", f"/api/interviews/{iid}/complete")
check("mock interview without AI: no scores", j["data"]["mode"] == "bank" and "score" not in r.text.lower())
r, j = call("get", "/api/dashboard")
dd = j["data"]
check("dashboard reflects real data", dd["assessments"]["completed"] == 1 and dd["learning"]["completed"] == 1 and dd["career"]["top_matches"] and dd["profile"]["resume_status"] == "confirmed")
r, j = call("get", "/api/admin/stats")
check("normal user blocked from admin API", r.status_code == 403)
r, j = call("post", "/api/auth/logout")
r, j = call("get", "/api/dashboard")
check("signed out after logout", r.status_code == 401)
print("\nALL STEPS PASSED")
