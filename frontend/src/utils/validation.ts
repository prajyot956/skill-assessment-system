// Mirrors the server rules so users get instant feedback. The server remains the authority.
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/

export const isValidEmail = (v: string) => v.length <= 254 && EMAIL_RE.test(v.trim())

export function passwordProblems(pw: string): string[] {
  const p: string[] = []
  if (pw.length < 8) p.push('at least 8 characters')
  if (!/[a-z]/.test(pw)) p.push('a lowercase letter')
  if (!/[A-Z]/.test(pw)) p.push('an uppercase letter')
  if (!/\d/.test(pw)) p.push('a number')
  return p
}

export const passwordMessage = (pw: string) => {
  const p = passwordProblems(pw)
  return p.length ? `Password needs ${p.join(', ')}.` : ''
}

export const isValidUrl = (v: string) => /^https?:\/\/[^\s/$.?#][^\s]*$/i.test(v)
export const isValidPhone = (v: string) => /^[+\d][\d\s\-().]{6,19}$/.test(v)

export type FieldErrors = Record<string, string>
