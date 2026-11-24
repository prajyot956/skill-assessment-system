export interface User {
  id: number
  full_name: string
  email: string
  is_admin: boolean
  created_at: string
}

export interface CompletionItem { key: string; label: string; done: boolean }

export interface Profile {
  full_name: string
  email: string
  phone: string | null
  location: string | null
  linkedin_url: string | null
  portfolio_url: string | null
  github_url: string | null
  summary: string | null
  target_role_id: number | null
  preferences: { work_types?: string[] }
  interests: string[]
  education: { id: number; degree: string | null; specialization: string | null; institution: string; graduation_year: number | null; details: string | null }[]
  experience: { id: number; company: string; title: string | null; kind: string; duration: string | null; responsibilities: string | null }[]
  projects: { id: number; name: string; description: string | null; technologies: string[]; role: string | null; url: string | null }[]
  certifications: { id: number; name: string; issuer: string | null; completed_on: string | null }[]
  completion: { percent: number; items: CompletionItem[] }
}

export interface AppNotification {
  id: number
  kind: string
  title: string
  message: string | null
  link: string | null
  is_read: boolean
  created_at: string
}

export interface SkillScore { skill: string; proficiency_pct: number }

export interface Dashboard {
  profile: { completion: { percent: number; items: CompletionItem[] }; resume_status: string; confirmed_skills: number }
  assessments: {
    completed: number
    pending: number
    average_score: number | null
    recent: { attempt_id: number; skill: string; percentage: number; category: string; submitted_at: string | null }[]
  }
  skills: { strongest: SkillScore[]; weakest: SkillScore[]; unassessed: string[] }
  career: { target_role_id: number | null; top_matches: { role: string; match_pct: number }[] }
  learning: { id: number; role: string | null; total: number; completed: number; pending: number; progress_pct: number } | null
  activity: AppNotification[]
}

// ---- resume ----
export interface ResumeInfo { id: number; filename: string; size: number; status: string; parse_method: string | null; error: string | null; uploaded_at: string; confirmed_at: string | null; has_draft: boolean }
export interface Evidence { section: string; snippet: string }
export interface DraftSkill { name: string; category: string; evidence: Evidence[]; inferred: boolean; confidence: number; source_section: string }
export interface EduItem { degree: string | null; specialization: string | null; institution: string; graduation_year: number | null; details: string | null }
export interface ExpItem { company: string; title: string | null; kind: string; duration: string | null; responsibilities: string | null }
export interface ProjItem { name: string; description: string | null; technologies: string[]; role: string | null }
export interface CertItem { name: string; issuer: string | null; completed_on: string | null }
export interface Change { field: string; current: unknown; new: unknown }
export interface SectionDiff<T> { new: T[]; changed: { id: number; current: T; item: T; changes: Change[] }[]; unchanged: number; missing: (T & { id: number })[] }
export interface Draft {
  personal: Record<string, string | null>; summary: string | null; skills: DraftSkill[]; unmatched_skills: string[]
  analysis: { missing: string[]; strengths: string[]; improvements: string[]; explanations: string[] }
}
export interface Diff {
  personal: { field: string; label: string; current: string | null; new: string | null; status: 'new' | 'changed' | 'same' }[]
  summary: { current: string | null; new: string | null; status: 'new' | 'changed' | 'same' }
  education: SectionDiff<EduItem>; experience: SectionDiff<ExpItem>; projects: SectionDiff<ProjItem>; certifications: SectionDiff<CertItem>
  skills: { new: DraftSkill[]; existing: (DraftSkill & { user_skill_id: number; status: string })[]; missing: string[] }
}
export interface ReviewData { resume: ResumeInfo; draft: Draft; diff: Diff }

// ---- skills ----
export interface UserSkillRow {
  id: number; skill_id: number; name: string; category: string; status: string; source: string
  evidence_level: 'resume_detected' | 'user_confirmed' | 'assessment_verified'; proficiency_pct: number | null; last_assessed_at: string | null
  evidence: { section: string; snippet: string | null; confidence: number; inferred: boolean }[]
}

// ---- assessments ----
export interface CatalogItem { id: number; title: string; skill: string; available: boolean; proficiency_pct: number | null; in_progress_attempt_id: number | null; questions: { beginner: number; intermediate: number; advanced: number; total: number } }
export interface CatalogCategory { id: number; name: string; description: string | null; assessments: CatalogItem[] }
export interface AttemptQuestion { id: number; text: string; type: 'single' | 'multiple' | 'true_false' | 'short' | 'coding'; marks: number; topic: string; options?: { id: number; text: string }[] }
export type AnswerValue = number | number[] | string
export interface AttemptData { id: number; title: string; skill: string; difficulty: string; duration_seconds: number; expires_at: string; server_now: string; questions: AttemptQuestion[]; answers: Record<string, AnswerValue>; finished: boolean; status: string }
export interface Breakdown { name: string; percentage: number; correct: number; count: number }
export interface ReviewItem { id: number; text: string; type: string; topic: string; difficulty: string; marks: number; awarded: number; status: 'correct' | 'incorrect' | 'unanswered'; your_answer: AnswerValue | null; explanation: string | null; options?: { id: number; text: string; is_correct: boolean }[]; correct_answer?: string }
export interface ResultData {
  attempt_id: number; assessment_id?: number; skill: string; title: string; difficulty: string; status: string; submitted_at: string; total_marks: number; obtained_marks: number; percentage: number
  accuracy: number; performance_category: string; correct: number; incorrect: number; unanswered: number; topics: Breakdown[]; difficulties: Breakdown[]
  strengths: string[]; weaknesses: string[]; proficiency_pct: number; review: ReviewItem[]
}
export interface HistoryRow { attempt_id: number; assessment_id: number; skill: string; difficulty: string; status: string; percentage: number; category: string; correct: number; total: number; submitted_at: string }

// ---- careers / learning ----
export interface GapSkill { skill_id: number; skill: string; category: string; weight: number; required_level: number; is_core: boolean; state: 'met' | 'below' | 'unverified' | 'detected' | 'missing'; evidence_level: string; proficiency_pct: number | null; priority: 'high' | 'medium' | 'low' | 'none'; assessment_id: number | null; assessment_available: boolean }
export interface Recommendation { role_id: number; role: string; description: string | null; match_pct: number; base_pct: number; adjustments: { name: string; points: number; detail: string }[]; is_target: boolean; why: string[]; matching_skills: GapSkill[]; partial_skills: GapSkill[]; unverified_skills: GapSkill[]; missing_skills: GapSkill[]; improvement_areas: string[]; next_steps: string[] }
export interface RoadmapItem { id: number; skill: string | null; type: 'learn' | 'exercise' | 'mini_project' | 'assess'; title: string; description: string | null; priority: string; status: 'pending' | 'in_progress' | 'completed'; resource_url: string | null; assessment_id: number | null; completed_at: string | null }
export interface Roadmap { id: number; role: string | null; role_id: number | null; is_stale: boolean; total: number; completed: number; in_progress: number; pending: number; progress_pct: number; items: RoadmapItem[]; generated_at: string }
export interface PracticeProject { id: number; title: string; description: string; difficulty: string; skills: string[]; objectives: string[]; steps: string[]; expected_outcome: string | null; status: string; relevance: number; reasons: string[] }
export interface Interview { id: number; role: string; difficulty: string; mode: 'ai' | 'bank'; status: string; created_at: string; question_count: number; answered: number; questions?: { index: number; text: string; skill: string; answer: string; keyword_check: { mentioned: string[]; not_mentioned: string[] } | null }[]; feedback?: { source: string; overall?: string; note?: string; per_question?: { index: number; strengths: string[]; improvements: string[] }[]; knowledge_gaps?: string[] } | null }
