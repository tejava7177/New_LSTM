import React, { useEffect, useRef } from 'react'

type Props = {
  /** 녹음에 사용 중인 MediaStream (없으면 렌더 중단) */
  mediaStream?: MediaStream | null
  /** true일 때만 캔버스 갱신 루프 실행 */
  running?: boolean
  /** 배경/선 색상 테마 */
  theme?: 'light' | 'dark'
  /** CSS px 높이 */
  height?: number
  /** 스타일/레이아웃 확장을 위한 선택적 클래스 */
  className?: string
}

const LiveScrollWave: React.FC<Props> = ({
  mediaStream,
  running = false,
  theme = 'light',
  height = 96,
  className,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const acRef = useRef<AudioContext | null>(null)
  const srcRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    // 조건 미충족이면 그리기 중단 및 정리
    if (!mediaStream || !running) {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
      return
    }

    const AC: any = (window as any).AudioContext || (window as any).webkitAudioContext
    const ac: AudioContext = new AC()
    acRef.current = ac

    const src = ac.createMediaStreamSource(mediaStream)
    srcRef.current = src

    const an = ac.createAnalyser()
    an.fftSize = 2048
    an.smoothingTimeConstant = 0.85
    src.connect(an)
    analyserRef.current = an

    const draw = () => {
      const cv = canvasRef.current
      const analyser = analyserRef.current
      if (!cv || !analyser) return

      const dpr = Math.max(1, window.devicePixelRatio || 1)
      const W = Math.max(1, Math.floor(cv.clientWidth * dpr))
      const H = Math.max(1, Math.floor((height || 96) * dpr))
      if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H }

      const g = cv.getContext('2d')!
      const bg = theme === 'dark' ? '#0b1220' : '#ffffff'
      const grid = theme === 'dark' ? '#1f2937' : '#e5e7eb'
      const waveTop = theme === 'dark' ? '#60a5fa' : '#2563eb'
      const waveBot = theme === 'dark' ? '#a78bfa' : '#7c3aed'

      // 배경 + 중앙선
      g.clearRect(0, 0, W, H)
      g.fillStyle = bg
      g.fillRect(0, 0, W, H)
      g.strokeStyle = grid
      g.lineWidth = 1 * dpr
      g.beginPath()
      g.moveTo(0, Math.floor(H / 2) + 0.5 * dpr)
      g.lineTo(W, Math.floor(H / 2) + 0.5 * dpr)
      g.stroke()

      // 시간영역 파형
      const n = analyser.fftSize
      const buf = new Float32Array(n)
      analyser.getFloatTimeDomainData(buf)

      const grad = g.createLinearGradient(0, 0, 0, H)
      grad.addColorStop(0, waveTop)
      grad.addColorStop(1, waveBot)
      g.strokeStyle = grad
      g.lineWidth = 2 * dpr
      g.beginPath()
      const mid = H / 2
      for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * (W - 2 * dpr) + 1 * dpr
        const y = mid + buf[i] * (H * 0.45)
        if (i === 0) g.moveTo(x, y)
        else g.lineTo(x, y)
      }
      g.stroke()

      rafRef.current = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
      try { srcRef.current?.disconnect() } catch {}
      try { analyserRef.current?.disconnect() } catch {}
      srcRef.current = null
      analyserRef.current = null
      if (acRef.current && acRef.current.state !== 'closed') {
        acRef.current.close().catch(() => {})
      }
      acRef.current = null
    }
  }, [mediaStream, running, theme, height])

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{
        width: '100%',
        height,            // CSS height
        display: 'block',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
      }}
    />
  )
}

export default LiveScrollWave