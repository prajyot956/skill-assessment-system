export type Field = { key: string; label: string; kind?: 'text' | 'number' | 'area' | 'list' | 'choice'; wide?: boolean; choices?: string[] }

/** Editable fields per profile section (shared by the profile page and the resume review screen). */
export type Section = 'education' | 'experience' | 'projects' | 'certifications'
export const FIELDS: Record<Section, Field[]> = {
  education: [{ key: 'degree', label: 'Degree' }, { key: 'specialization', label: 'Specialization' }, { key: 'institution', label: 'Institution', wide: true }, { key: 'graduation_year', label: 'Graduation year', kind: 'number' }, { key: 'details', label: 'Details', kind: 'area', wide: true }],
  experience: [{ key: 'company', label: 'Company' }, { key: 'title', label: 'Title' }, { key: 'kind', label: 'Type', kind: 'choice', choices: ['job', 'internship'] }, { key: 'duration', label: 'Duration' }, { key: 'responsibilities', label: 'Responsibilities', kind: 'area', wide: true }],
  projects: [{ key: 'name', label: 'Project name' }, { key: 'role', label: 'Your role' }, { key: 'technologies', label: 'Technologies (comma separated)', kind: 'list', wide: true }, { key: 'description', label: 'Description', kind: 'area', wide: true }, { key: 'url', label: 'Link', wide: true }],
  certifications: [{ key: 'name', label: 'Certification' }, { key: 'issuer', label: 'Issuer' }, { key: 'completed_on', label: 'Completed' }],
}
export const SECTION_LABEL: Record<Section, string> = { education: 'Education', experience: 'Experience', projects: 'Projects', certifications: 'Certifications' }
export const REQUIRED: Record<Section, string> = { education: 'institution', experience: 'company', projects: 'name', certifications: 'name' }
