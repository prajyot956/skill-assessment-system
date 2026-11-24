import { isValidEmail, isValidPhone, isValidUrl, passwordMessage, passwordProblems } from './validation'

describe('validation', () => {
  it('accepts and rejects emails', () => {
    expect(isValidEmail('ana@example.com')).toBe(true)
    expect(isValidEmail('ana@example')).toBe(false)
    expect(isValidEmail('not an email')).toBe(false)
  })
  it('lists every password problem', () => {
    expect(passwordProblems('abc')).toEqual(['at least 8 characters', 'an uppercase letter', 'a number'])
    expect(passwordMessage('Str0ngPass1')).toBe('')
  })
  it('validates links and phones', () => {
    expect(isValidUrl('https://github.com/ana')).toBe(true)
    expect(isValidUrl('javascript:alert(1)')).toBe(false)
    expect(isValidPhone('+91 98765 43210')).toBe(true)
    expect(isValidPhone('abc')).toBe(false)
  })
})
