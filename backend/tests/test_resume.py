import io
import json
from pathlib import Path

import pytest

from app.extensions import db
from app.models import Education, Resume, SkillEvidence, UserSkill
from tests.helpers import SAMPLE_RESUME, make_bogus_zip, make_docx, make_pdf, upload


def skills_of(draft):
    return {s["name"]: s for s in draft["skills"]}


class TestUploadAndExtraction:
    def test_pdf_upload_extracts_profile_data(self, seeded, make_client):
        c = make_client()
        r = upload(c, make_pdf(), "resume.pdf")
        assert r.status_code == 201 and r.json["data"]["status"] == "parsed"
        assert r.json["data"]["parse_method"] == "local"
        rid = r.json["data"]["id"]
        d = c.get(f"/api/resumes/{rid}/review").json["data"]["draft"]
        p = d["personal"]
        assert (p["full_name"], p["email"], p["phone"]) == ("Ananya Rao", "ananya.rao@example.com", "+91 98765 43210")
        assert p["github_url"] == "https://github.com/ananyarao" and p["location"] == "Pune, Maharashtra"
        assert d["education"][0]["degree"] == "B.Tech" and d["education"][0]["graduation_year"] == 2025
        assert d["education"][0]["institution"] == "Pune Institute of Technology"
        assert d["experience"][0]["kind"] == "internship" and d["experience"][0]["company"] == "Acme Technologies Pvt Ltd"
        assert [x["name"] for x in d["projects"]] == ["Expense Tracker", "Student Portal"]
        assert d["certifications"][0]["name"] == "Python for Everybody"

    def test_docx_upload(self, seeded, make_client):
        c = make_client()
        r = upload(c, make_docx(), "cv.docx")
        assert r.status_code == 201
        d = c.get(f"/api/resumes/{r.json['data']['id']}/review").json["data"]["draft"]
        assert d["personal"]["email"] == "ananya.rao@example.com" and "Python" in skills_of(d)

    def test_skills_carry_evidence_and_never_a_proficiency(self, seeded, make_client):
        c = make_client()
        rid = upload(c, make_pdf(), "r.pdf").json["data"]["id"]
        sk = skills_of(c.get(f"/api/resumes/{rid}/review").json["data"]["draft"])
        py = sk["Python"]
        assert py["source_section"] == "skills" and py["confidence"] > 0.9 and py["inferred"] is False
        assert {e["section"] for e in py["evidence"]} >= {"skills", "projects"}  # listed AND shown in a project
        assert sk["PostgreSQL"]["source_section"] == "experience" and sk["PostgreSQL"]["confidence"] < 0.7
        assert sk["Software Testing"]["inferred"] is True  # implied by pytest, flagged and low confidence
        assert all("proficiency" not in s and "level" not in s for s in sk.values())
        assert "Figma" in c.get(f"/api/resumes/{rid}/review").json["data"]["draft"]["unmatched_skills"]

    def test_analysis_report(self, seeded, make_client):
        c = make_client()
        rid = upload(c, make_pdf(), "r.pdf").json["data"]["id"]
        a = c.get(f"/api/resumes/{rid}/review").json["data"]["draft"]["analysis"]
        assert set(a) == {"missing", "strengths", "improvements", "explanations"}
        assert any("not proof of proficiency" in e for e in a["explanations"])

    def test_upload_never_touches_profile(self, seeded, make_client):
        c = make_client()
        upload(c, make_pdf(), "r.pdf")
        prof = c.get("/api/profile").json["data"]
        assert prof["phone"] is None and prof["education"] == [] and prof["summary"] is None
        assert UserSkill.query.count() == 0


class TestFileValidation:
    @pytest.mark.parametrize("data,name,code", [
        (b"hello", "notes.txt", "invalid_file_type"),
        (b"MZ\x90\x00 not a pdf at all", "resume.pdf", "invalid_file_content"),
        (b"just text pretending", "resume.docx", "invalid_file_content"),
        (b"", "resume.pdf", "empty_file"),
    ])
    def test_rejects_bad_files(self, seeded, make_client, data, name, code):
        r = upload(make_client(), data, name)
        assert r.status_code in (400, 415) and r.json["error"]["code"] == code
        assert Resume.query.count() == 0

    def test_zip_that_is_not_a_docx(self, seeded, make_client):
        r = upload(make_client(), make_bogus_zip(), "resume.docx")
        assert r.status_code == 400 and r.json["error"]["code"] == "invalid_file_content"

    def test_pdf_without_text(self, seeded, make_client):
        import fitz
        d = fitz.open(); d.new_page()
        r = upload(make_client(), d.tobytes(), "scan.pdf")
        assert r.json["error"]["code"] == "no_text"

    def test_encrypted_pdf(self, seeded, make_client):
        import fitz
        r = upload(make_client(), make_pdf(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y"), "locked.pdf")
        assert r.json["error"]["code"] == "encrypted_file"

    def test_too_large(self, seeded, make_client):
        seeded.config["MAX_CONTENT_LENGTH"] = 2000
        r = upload(make_client(), make_pdf(), "big.pdf")
        assert r.status_code == 413 and r.json["error"]["code"] == "file_too_large"

    def test_missing_file_field(self, seeded, make_client):
        r = make_client().post("/api/resumes", data={}, content_type="multipart/form-data")
        assert r.status_code == 400 and r.json["error"]["code"] == "no_file"

    def test_client_filename_never_used_on_disk(self, seeded, make_client):
        c = make_client()
        r = upload(c, make_pdf(), "../../etc/passwd.pdf")
        assert r.status_code == 201
        row = Resume.query.one()
        assert row.original_filename == "passwd.pdf" and ".." not in row.stored_filename
        files = list(Path(seeded.config["UPLOAD_DIR"]).rglob(row.stored_filename))
        assert len(files) == 1 and files[0].parent.name == "1"

    def test_requires_login(self, seeded, client):
        assert upload(client, make_pdf(), "r.pdf").status_code == 401


class TestConfirmFlow:
    def _upload(self, c, data=None, name="r.pdf"):
        return upload(c, data or make_pdf(), name).json["data"]["id"]

    def test_confirm_requires_explicit_flag(self, seeded, make_client):
        c = make_client()
        rid = self._upload(c)
        r = c.post(f"/api/resumes/{rid}/confirm", json={"skills": [{"name": "Python"}]})
        assert r.status_code == 400 and r.json["error"]["code"] == "confirmation_required"
        assert UserSkill.query.count() == 0

    def test_only_approved_items_are_saved(self, seeded, make_client):
        c = make_client()
        rid = self._upload(c)
        rev = c.get(f"/api/resumes/{rid}/review").json["data"]
        edu = rev["diff"]["education"]["new"][0]
        edu = {**edu, "specialization": "Computer Engineering"}  # user edited a field before saving
        r = c.post(f"/api/resumes/{rid}/confirm", json={
            "confirm": True, "profile": {"phone": "+91 98765 43210", "summary": "Backend-minded student."},
            "education": {"add": [edu]}, "projects": {"add": [rev["diff"]["projects"]["new"][0]]},
            "skills": [{"name": "Python"}, {"name": "Flask"}]})
        assert r.status_code == 200, r.json
        prof = c.get("/api/profile").json["data"]
        assert prof["phone"] == "+91 98765 43210" and prof["education"][0]["specialization"] == "Computer Engineering"
        assert len(prof["projects"]) == 1 and prof["experience"] == [] and prof["location"] is None  # not approved
        mine = {s["name"]: s for s in c.get("/api/skills/mine").json["data"]}
        assert set(mine) == {"Python", "Flask"}  # unticked skills were not stored
        assert mine["Python"]["status"] == "user_confirmed" and mine["Python"]["proficiency_pct"] is None
        assert mine["Python"]["evidence_level"] == "user_confirmed" and len(mine["Python"]["evidence"]) >= 2
        assert Resume.query.one().status == "confirmed"

    def test_invalid_item_blocks_whole_confirmation(self, seeded, make_client):
        c = make_client()
        rid = self._upload(c)
        r = c.post(f"/api/resumes/{rid}/confirm", json={"confirm": True, "profile": {"summary": "ok"},
                   "education": {"add": [{"degree": "B.Tech"}]}, "skills": [{"name": "Python"}]})
        assert r.status_code == 422 and "education.add.0.institution" in r.json["error"]["details"]["fields"]
        assert c.get("/api/profile").json["data"]["summary"] is None and UserSkill.query.count() == 0  # nothing half-applied

    def test_manual_custom_skill_needs_category(self, seeded, make_client):
        c = make_client()
        rid = self._upload(c)
        bad = c.post(f"/api/resumes/{rid}/confirm", json={"confirm": True, "skills": [{"name": "Figma"}]})
        assert bad.status_code == 422
        ok = c.post(f"/api/resumes/{rid}/confirm", json={"confirm": True, "skills": [{"name": "Figma", "category": "Tools and Technologies"}]})
        assert ok.status_code == 200
        assert c.get("/api/skills/mine").json["data"][0]["source"] == "manual"

    def test_reupload_diff_and_selective_update(self, seeded, make_client):
        c = make_client()
        rid = self._upload(c)
        d = c.get(f"/api/resumes/{rid}/review").json["data"]["diff"]
        c.post(f"/api/resumes/{rid}/confirm", json={"confirm": True, "profile": {"phone": "+91 98765 43210"},
               "education": {"add": d["education"]["new"]}, "projects": {"add": d["projects"]["new"]},
               "skills": [{"name": "Python"}, {"name": "Docker"}]})
        updated = SAMPLE_RESUME.replace("98765 43210", "99999 11111").replace("Docker, Figma", "Figma").replace(
            "SKILLS", "Machine Learning: scikit-learn\n\nSKILLS").replace(
            "CERTIFICATIONS", "Weather App\n- A weather dashboard using JavaScript and CSS and HTML for forecasts\n\nCERTIFICATIONS", 1)
        rid2 = self._upload(c, make_pdf(updated))
        assert Resume.query.count() == 1  # replaced, not accumulated
        d2 = c.get(f"/api/resumes/{rid2}/review").json["data"]["diff"]
        phone = next(x for x in d2["personal"] if x["field"] == "phone")
        assert phone["status"] == "changed" and phone["current"] == "+91 98765 43210"
        assert d2["education"]["unchanged"] == 1 and d2["education"]["new"] == []
        assert "Docker" in d2["skills"]["missing"]  # in profile, absent from new resume: reported, never auto-removed
        assert any(s["name"] == "Python" for s in d2["skills"]["existing"])
        assert "Docker" in {s["skill"] if "skill" in s else s["name"] for s in c.get("/api/skills/mine").json["data"]}
        assert c.get("/api/profile").json["data"]["phone"] == "+91 98765 43210"  # unchanged until approved

    def test_replace_removes_old_file_and_delete_keeps_profile(self, seeded, make_client):
        c = make_client()
        r1 = upload(c, make_pdf(), "a.pdf").json["data"]["id"]
        old_name = Resume.query.one().stored_filename
        c.post(f"/api/resumes/{r1}/confirm", json={"confirm": True, "skills": [{"name": "Python"}]})
        upload(c, make_docx(), "b.docx")
        assert not list(Path(seeded.config["UPLOAD_DIR"]).rglob(old_name))
        r2 = Resume.query.one().id
        assert c.delete(f"/api/resumes/{r2}").status_code == 200
        assert c.get("/api/resumes/current").json["data"]["resume"] is None
        assert [s["name"] for s in c.get("/api/skills/mine").json["data"]] == ["Python"]  # confirmed data survives
        assert SkillEvidence.query.filter(SkillEvidence.resume_id.isnot(None)).count() == 0  # provenance cleared, not deleted rows


class TestCrossUserAccess:
    def test_other_users_resume_is_invisible(self, seeded, make_client):
        a, b = make_client("a@example.com"), make_client("b@example.com")
        rid = upload(a, make_pdf(), "r.pdf").json["data"]["id"]
        assert b.get(f"/api/resumes/{rid}/review").status_code == 404
        assert b.delete(f"/api/resumes/{rid}").status_code == 404
        assert b.post(f"/api/resumes/{rid}/confirm", json={"confirm": True}).status_code == 404
        assert b.get("/api/resumes/current").json["data"]["resume"] is None
        assert Resume.query.count() == 1


class FakeResp:
    def __init__(self, status, payload=None):
        self.status_code, self._p = status, payload or {}
    def json(self): return self._p


AI_JSON = {"personal": {"full_name": "Ananya Rao", "email": "ananya.rao@example.com", "phone": None, "location": "Pune",
                        "linkedin_url": None, "github_url": None, "portfolio_url": None},
           "summary": "Student.", "education": [{"degree": "B.Tech", "specialization": "CSE", "institution": "PIT", "graduation_year": 2025}],
           "experience": [], "projects": [{"name": "Tracker", "description": "x", "technologies": ["Python"]}], "certifications": [],
           "skills": [{"name": "python3", "evidence": "Built a tracker in Python", "section": "projects", "explicit": True},
                      {"name": "Underwater Basket Weaving", "evidence": "x", "section": "skills", "explicit": True}],
           "interests": []}


class TestAI:
    @pytest.fixture()
    def ai_on(self, seeded):
        seeded.config.update(AI_PROVIDER="anthropic", AI_API_KEY="test-key")
        return seeded

    def _patch(self, monkeypatch, handler):
        monkeypatch.setattr("app.ai.provider.requests.post", handler)
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)

    def test_ai_extraction_is_validated_and_mapped(self, ai_on, make_client, monkeypatch):
        seen = {}
        def post(url, headers, json, timeout):
            seen.update(headers=headers, body=json, timeout=timeout)
            return FakeResp(200, {"content": [{"type": "text", "text": "```json\n" + __import__("json").dumps(AI_JSON) + "\n```"}]})
        self._patch(monkeypatch, post)
        c = make_client()
        r = upload(c, make_pdf(), "r.pdf")
        assert r.json["data"]["parse_method"] == "ai"
        d = c.get(f"/api/resumes/{r.json['data']['id']}/review").json["data"]["draft"]
        assert d["personal"]["phone"] == "+91 98765 43210"  # gap filled by the local parser
        py = skills_of(d)["Python"]  # alias "python3" mapped to the taxonomy skill
        assert py["source_section"] == "projects" and py["confidence"] == 0.65 and "proficiency" not in py
        assert "Underwater Basket Weaving" in d["unmatched_skills"] and "Underwater Basket Weaving" not in skills_of(d)
        assert seen["headers"]["x-api-key"] == "test-key" and seen["timeout"] == 30
        assert "analysis" in d

    @pytest.mark.parametrize("handler", [
        lambda *a, **k: FakeResp(500),
        lambda *a, **k: FakeResp(401),
        lambda *a, **k: FakeResp(200, {"content": [{"type": "text", "text": "Sorry, I cannot do that."}]}),
        lambda *a, **k: FakeResp(200, {"content": [{"type": "text", "text": '{"unexpected": true}'}]}),
    ])
    def test_ai_failures_fall_back_to_local(self, ai_on, make_client, monkeypatch, handler):
        self._patch(monkeypatch, handler)
        c = make_client()
        r = upload(c, make_pdf(), "r.pdf")
        assert r.status_code == 201 and r.json["data"]["parse_method"] == "local" and r.json["data"]["status"] == "parsed"

    def test_network_errors_fall_back_and_retry(self, ai_on, make_client, monkeypatch):
        import requests
        calls = []
        def boom(*a, **k):
            calls.append(1); raise requests.Timeout()
        self._patch(monkeypatch, boom)
        r = upload(make_client(), make_pdf(), "r.pdf")
        assert r.json["data"]["parse_method"] == "local" and len(calls) == 3

    def test_no_ai_calls_when_unconfigured(self, seeded, make_client, monkeypatch):
        self._patch(monkeypatch, lambda *a, **k: pytest.fail("AI must not be called"))
        assert upload(make_client(), make_pdf(), "r.pdf").json["data"]["parse_method"] == "local"


class TestProfileItemsAndSkills:
    def test_education_crud_and_validation(self, seeded, make_client):
        c = make_client()
        assert c.post("/api/profile/education", json={"degree": "B.Sc"}).status_code == 422
        r = c.post("/api/profile/education", json={"institution": "ABC College", "graduation_year": 2024})
        assert r.status_code == 201
        eid = r.json["data"]["id"]
        assert c.put(f"/api/profile/education/{eid}", json={"degree": "B.Sc"}).json["data"]["degree"] == "B.Sc"
        assert c.put(f"/api/profile/education/{eid}", json={"graduation_year": 1800}).status_code == 422
        assert c.delete(f"/api/profile/education/{eid}").status_code == 200
        assert Education.query.count() == 0

    def test_cannot_edit_or_delete_other_users_items(self, seeded, make_client):
        a, b = make_client("a@example.com"), make_client("b@example.com")
        eid = a.post("/api/profile/education", json={"institution": "Mine"}).json["data"]["id"]
        assert b.put(f"/api/profile/education/{eid}", json={"institution": "Hacked"}).status_code == 404
        assert b.delete(f"/api/profile/education/{eid}").status_code == 404
        assert Education.query.one().institution == "Mine"
        assert a.post("/api/profile/nonsense", json={}).status_code == 404

    def test_project_url_and_technology_validation(self, seeded, make_client):
        c = make_client()
        assert c.post("/api/profile/projects", json={"name": "P", "url": "javascript:x"}).status_code == 422
        ok = c.post("/api/profile/projects", json={"name": "P", "technologies": ["Python", "Flask"]})
        assert ok.status_code == 201 and ok.json["data"]["technologies"] == ["Python", "Flask"]

    def test_add_and_remove_manual_skill(self, seeded, make_client):
        c = make_client()
        r = c.post("/api/skills/mine", json={"name": "python"})
        assert r.status_code == 201 and r.json["data"]["name"] == "Python" and r.json["data"]["source"] == "manual"
        assert c.post("/api/skills/mine", json={"name": "Brand New Thing"}).status_code == 422
        assert c.post("/api/skills/mine", json={"name": "Brand New Thing", "category": "Programming"}).status_code == 201
        us_id = r.json["data"]["id"]
        assert c.delete(f"/api/skills/mine/{us_id}").status_code == 200
        b = make_client("b@example.com")
        other = c.get("/api/skills/mine").json["data"][0]["id"]
        assert b.delete(f"/api/skills/mine/{other}").status_code == 404
