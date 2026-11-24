import io
import zipfile

SAMPLE_RESUME = """ANANYA RAO
Pune, Maharashtra | ananya.rao@example.com | +91 98765 43210
linkedin.com/in/ananya-rao | github.com/ananyarao

SUMMARY
Final-year computer science student interested in backend development.

EDUCATION
B.Tech in Computer Science and Engineering
Pune Institute of Technology, Pune 2021 - 2025
CGPA: 8.4/10

EXPERIENCE
Software Engineering Intern | Acme Technologies Pvt Ltd | Jun 2024 - Aug 2024
- Built REST APIs with Flask and PostgreSQL serving 2000 requests per day
- Wrote unit tests with pytest, raising coverage by 25%

PROJECTS
Expense Tracker | Python, SQLite
- Command-line tool to log expenses and print monthly summaries by category
Student Portal
- Web portal built with React and Node.js for course registration
Technologies: React, Node.js, MongoDB

SKILLS
Programming: Python, Java, C++, JavaScript
Web: HTML, CSS, React, Flask
Databases: SQL, MySQL
Tools: Git, Docker, Figma
Soft Skills: Communication, Teamwork

CERTIFICATIONS
- Python for Everybody - Coursera (2023)
"""


def make_pdf(text: str = SAMPLE_RESUME, **save_kwargs) -> bytes:
    import fitz
    doc = fitz.open()
    page, y = None, 0
    for i, line in enumerate(text.split("\n")):
        if i % 55 == 0:
            page, y = doc.new_page(), 40
        page.insert_text((40, y), line, fontsize=9)
        y += 12
    return doc.tobytes(**save_kwargs)


def make_docx(text: str = SAMPLE_RESUME) -> bytes:
    import docx
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_bogus_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "not a docx")
    return buf.getvalue()


def upload(client, data: bytes, filename: str):
    return client.post("/api/resumes", data={"file": (io.BytesIO(data), filename)}, content_type="multipart/form-data")
