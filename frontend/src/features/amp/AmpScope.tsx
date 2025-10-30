import React, { useEffect, useRef } from 'react'

type Props = { analyser: AnalyserNode | null }

export function AmpScope({ analyser }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const rafRef = useRef<number | null>(null)
  const roRef = useRef<ResizeObserver | null>(null)

  function draw() {
    const cv = canvasRef.current; const an = analyser
    if (!cv || !an) return
    const g = cv.getContext('2d'); if (!g) return

    const dpr = Math.max(1, (window.devicePixelRatio || 1))
    const W = cv.clientWidth * dpr, H = 140 * dpr
    if (cv.width !== Math.floor(W) || cv.height !== Math.floor(H)) {
      cv.width = Math.max(1, Math.floor(W)); cv.height = Math.max(1, Math.floor(H))
    }
    const mid = Math.floor(cv.height / 2)
    g.clearRect(0,0,cv.width,cv.height)
    g.fillStyle = '#0b1220'; g.fillRect(0,0,cv.width,cv.height)
    g.strokeStyle = '#1f2937'; g.lineWidth = 1 * dpr
    g.beginPath(); g.moveTo(0, mid+0.5*dpr); g.lineTo(cv.width, mid+0.5*dpr); g.stroke()

    const n = an.fftSize
    const buf = new Float32Array(n)
    an.getFloatTimeDomainData(buf)
    const grad = g.createLinearGradient(0,0,0,cv.height)
    grad.addColorStop(0,'#60a5fa'); grad.addColorStop(1,'#a78bfa')
    g.strokeStyle = grad; g.lineWidth = 2 * dpr; g.beginPath()
    for (let i=0;i<n;i++){
      const t=i/(n-1); const x=(t*(cv.width-2*dpr))+1*dpr; const y=mid+(buf[i]*(cv.height*0.45));
      if(i===0) g.moveTo(x,y); else g.lineTo(x,y)
    }
    g.stroke()
  }

  useEffect(() => {
    const loop = () => { draw(); rafRef.current = requestAnimationFrame(loop) }
    rafRef.current = requestAnimationFrame(loop)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [analyser])

  useEffect(() => {
    const cv = canvasRef.current; if (!cv) return
    const ro = new ResizeObserver(() => draw())
    ro.observe(cv)
    roRef.current = ro
    return () => { ro.disconnect(); roRef.current = null }
  }, [])

  return <canvas ref={canvasRef} style={{width:'100%', height:140, display:'block'}} />
}
