# API reference

Generated from the application's route table at the time of release, so every listed route exists. All endpoints live under `/api` and return JSON.

## Conventions

```json
{ "success": true,  "data": { }, "meta": { "page": 1, "per_page": 20, "total": 57 } }
{ "success": false, "error": { "code": "validation_error", "message": "…", "details": { "fields": { "email": "…" } } } }
```

- **CSRF:** every non-GET request sends `X-CSRFToken` with the value from `GET /api/auth/csrf`.
- **Auth:** server-side session cookie (HttpOnly, SameSite=Lax; Secure in production). No token is exposed to JavaScript.
- **Access:** `public` needs nothing, `signed-in` needs a session (401 otherwise), `admin` needs an admin session (401 / 403). A test walks every route and asserts these.
- **Ownership:** every user-owned record is looked up by *both* its id and the session user's id. Someone else's record returns 404, exactly like a missing one.
- **Lists** accept `page` and `per_page` where noted; `meta.total` is the full count.
- **Rate limits (per IP):** register 10/h · login 10/min · forgot-password 5/h · reset/change-password 10/h · resume upload 10/h · AI endpoints 10-20/h.
- **Error codes:** `invalid_json` 400 · `csrf_failed` 400 · `validation_error` 422 · `invalid_credentials` / `unauthorized` 401 · `forbidden` 403 · `not_found` 404 · `invalid_file_type` 415 · `file_too_large` 413 · `attempt_expired` 409 · `rate_limited` 429 · `ai_unavailable` 503 · `server_error` 500.

## Key request shapes

**Confirm a resume** `POST /api/resumes/{id}/confirm` (nothing is saved without `confirm: true`):
```json
{ "confirm": true, "profile": { "phone": "+91 …", "summary": "…" },
  "education": { "add": [ { "institution": "…", "degree": "B.Tech" } ], "update": [ { "id": 4, "graduation_year": 2025 } ] },
  "experience": { "add": [], "update": [] }, "projects": { "add": [], "update": [] }, "certifications": { "add": [], "update": [] },
  "skills": [ { "name": "Python" }, { "name": "Figma", "category": "Tools and Technologies" } ] }
```

**Start an assessment** `POST /api/assessments/attempts`: `{ "assessment_id": 1, "difficulty": "beginner", "num_questions": 10, "duration_minutes": 15 }`.
**Save answers** `PUT /api/assessments/attempts/{id}/answers`: `{ "answers": { "<questionId>": <optionId | [optionIds] | "text" | null> } }` (`null` clears).

## Health

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/health` | public |  |

## Authentication

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/api/auth/change-password` | signed-in |  |
| GET | `/api/auth/csrf` | public |  |
| POST | `/api/auth/forgot-password` | public | Always answers the same way so the endpoint cannot be used to find registered emails. |
| POST | `/api/auth/login` | public |  |
| POST | `/api/auth/logout` | public |  |
| GET | `/api/auth/me` | signed-in |  |
| POST | `/api/auth/register` | public |  |
| POST | `/api/auth/reset-password` | public |  |

## Profile

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/profile` | signed-in |  |
| PUT | `/api/profile` | signed-in | Updates only the current user's own profile. Fields not sent are left unchanged. |
| POST | `/api/profile/{section}` | signed-in |  |
| DELETE | `/api/profile/{section}/{item_id}` | signed-in |  |
| PUT | `/api/profile/{section}/{item_id}` | signed-in |  |
| POST | `/api/profile/suggest-summary` | signed-in | Returns a SUGGESTION only; the user decides whether to save it. |

## Resume analyzer

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/api/resumes` | signed-in |  |
| DELETE | `/api/resumes/{resume_id}` | signed-in |  |
| POST | `/api/resumes/{resume_id}/confirm` | signed-in | Applies ONLY what the user approved. Requires explicit confirm=true; nothing else touches the profile. |
| GET | `/api/resumes/{resume_id}/review` | signed-in |  |
| GET | `/api/resumes/current` | signed-in |  |

## Skills

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/skills` | signed-in |  |
| GET | `/api/skills/mine` | signed-in |  |
| POST | `/api/skills/mine` | signed-in |  |
| DELETE | `/api/skills/mine/{us_id}` | signed-in |  |

## Assessments

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/assessments/attempts` | signed-in |  |
| POST | `/api/assessments/attempts` | signed-in |  |
| GET | `/api/assessments/attempts/{attempt_id}` | signed-in |  |
| PUT | `/api/assessments/attempts/{attempt_id}/answers` | signed-in |  |
| GET | `/api/assessments/attempts/{attempt_id}/result` | signed-in |  |
| POST | `/api/assessments/attempts/{attempt_id}/submit` | signed-in |  |
| GET | `/api/assessments/catalog` | signed-in |  |

## Skill analysis

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/analysis` | signed-in |  |

## Careers

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/api/careers/{role_id}/explain` | signed-in |  |
| GET | `/api/careers/{role_id}/gap` | signed-in |  |
| GET | `/api/careers/recommendations` | signed-in |  |
| GET | `/api/careers/roles` | signed-in |  |
| PUT | `/api/careers/target` | signed-in |  |

## Learning roadmap

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/roadmap` | signed-in |  |
| POST | `/api/roadmap/generate` | signed-in |  |
| PATCH | `/api/roadmap/items/{item_id}` | signed-in |  |
| POST | `/api/roadmap/suggest-resources` | signed-in |  |

## Practice projects

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/practice/projects` | signed-in |  |
| PUT | `/api/practice/projects/{project_id}/status` | signed-in |  |

## Mock interviews

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/interviews` | signed-in |  |
| POST | `/api/interviews` | signed-in |  |
| GET | `/api/interviews/{iid}` | signed-in |  |
| PUT | `/api/interviews/{iid}/answers/{index}` | signed-in |  |
| POST | `/api/interviews/{iid}/complete` | signed-in |  |

## Notifications

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/notifications` | signed-in |  |
| POST | `/api/notifications/{note_id}/read` | signed-in |  |
| POST | `/api/notifications/read-all` | signed-in |  |

## Dashboard

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/dashboard` | signed-in |  |

## Admin

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/api/admin/assessments` | admin |  |
| PUT | `/api/admin/assessments/{aid}` | admin |  |
| GET | `/api/admin/catalog` | admin |  |
| POST | `/api/admin/categories` | admin |  |
| PUT | `/api/admin/categories/{cid}` | admin |  |
| GET | `/api/admin/questions` | admin |  |
| POST | `/api/admin/questions` | admin |  |
| DELETE | `/api/admin/questions/{qid}` | admin | Soft delete: past attempts reference the question, so it is deactivated instead of removed. |
| PUT | `/api/admin/questions/{qid}` | admin |  |
| GET | `/api/admin/resources` | admin |  |
| POST | `/api/admin/resources` | admin |  |
| DELETE | `/api/admin/resources/{rid}` | admin |  |
| PUT | `/api/admin/resources/{rid}` | admin |  |
| GET | `/api/admin/roles` | admin |  |
| POST | `/api/admin/roles` | admin |  |
| PUT | `/api/admin/roles/{rid}` | admin |  |
| PUT | `/api/admin/roles/{rid}/skills` | admin |  |
| POST | `/api/admin/skills` | admin |  |
| PUT | `/api/admin/skills/{sid}` | admin |  |
| GET | `/api/admin/stats` | admin |  |
| GET | `/api/admin/users` | admin |  |
| PATCH | `/api/admin/users/{uid}` | admin |  |
