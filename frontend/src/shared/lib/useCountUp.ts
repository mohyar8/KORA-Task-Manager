import { useEffect, useState } from 'react'

/** Animates a number from 0 to `target`; jumps straight there when motion is reduced or rAF is unavailable. */
export function useCountUp(target: number, ms = 700): number {
  const [value, setValue] = useState(0)
  useEffect(() => {
    const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || typeof requestAnimationFrame !== 'function' || target === 0) {
      const id = setTimeout(() => setValue(target), 0)
      return () => clearTimeout(id)
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / ms)
      setValue(Math.round(target * (1 - Math.pow(1 - p, 3))))
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, ms])
  return value
}
