import { useEffect, useState } from 'react'
import { useTheme } from '../context/ThemeContext'

const names = ['primary', 'muted', 'line', 'attention', 'danger', 'success', 'ink', 'surface'] as const
type Colors = Record<(typeof names)[number], string>

function read(): Colors {
  const cs = getComputedStyle(document.documentElement)
  const out = {} as Colors
  for (const n of names) out[n] = `rgb(${cs.getPropertyValue(`--c-${n}`).trim().split(/\s+/).join(',')})`
  return out
}

/** Recharts draws SVG attributes, which can't use CSS variables, so resolve them per theme. */
export function useChartColors(): Colors {
  const { isDark } = useTheme()
  const [c, setC] = useState<Colors>(read)
  useEffect(() => { setC(read()) }, [isDark])
  return c
}
