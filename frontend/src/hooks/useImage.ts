import { useEffect, useState } from 'react'

export function useImage(src: string | null): [HTMLImageElement | null, 'loading' | 'loaded' | 'error'] {
  const [img, setImg] = useState<HTMLImageElement | null>(null)
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading')

  useEffect(() => {
    if (!src) return
    setStatus('loading')
    const image = new window.Image()
    image.onload = () => {
      setImg(image)
      setStatus('loaded')
    }
    image.onerror = () => setStatus('error')
    image.src = src
    return () => {
      image.onload = null
      image.onerror = null
    }
  }, [src])

  return [img, status]
}
