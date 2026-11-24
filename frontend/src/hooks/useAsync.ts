import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../services/api'

export function useAsync<T>(fn: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, [])
  const reload = useCallback(async () => {
    setLoading(true); setError(null)
    try { setData(await run()) }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.') }
    finally { setLoading(false) }
  }, [run])

  useEffect(() => { void reload() }, [reload])
  return { data, error, loading, reload, setData }
}
