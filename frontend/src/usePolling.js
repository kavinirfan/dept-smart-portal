import { useEffect } from 'react'

// Run `load` now and every `ms` while the tab is visible, so boards stay current without a refresh.
export default function usePolling(load, ms) {
  useEffect(() => {
    load()
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, ms)
    return () => clearInterval(id)
  }, [load, ms])
}
