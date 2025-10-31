// frontend/src/components/ChordTimeline.tsx
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ChordCue } from '../lib/midiCues'

type Props = {
  cues: ChordCue[]
  totalSec: number
  positionSec: number
  playing: boolean
}

function playedPercent(t0: number, t1: number, p: number) {
  if (p <= t0) return 0
  if (p >= t1) return 100
  return ((p - t0) / Math.max(0.0001, (t1 - t0))) * 100
}

export default function ChordTimeline({ cues, totalSec, positionSec, playing }: Props) {
  const cycleSec = Math.max(0.001, totalSec || 0.001)
  const posMod = ((positionSec % cycleSec) + cycleSec) % cycleSec

  // 래핑(끝→처음) 순간엔 한 프레임만 transition 끄기
  const prevPosRef = useRef(0)
  const [noAnim, setNoAnim] = useState(false)
  useEffect(() => {
    const prev = prevPosRef.current
    if (posMod < prev - 0.05) { // wrap
      setNoAnim(true)
      requestAnimationFrame(() => setNoAnim(false))
    }
    prevPosRef.current = posMod
  }, [posMod])

  const disableAnim = playing || noAnim

  const cells = useMemo(() => {
    if (!cues.length) return []
    return cues.map((c, i) => {
      const t0 = c.time
      const t1 = cues[i + 1]?.time ?? totalSec
      const width = Math.max(4, (t1 - t0) / Math.max(1, totalSec) * 100)
      const active = posMod >= t0 && posMod < t1
      const fill = playedPercent(t0, t1, posMod)
      return { text: c.text, width, active, fill, t0, t1 }
    })
  }, [cues, totalSec, posMod])

  return (
    <div className={`timeline ${disableAnim ? 'no-anim' : ''}`}>
      {cells.map((cell, idx) => (
        <div key={idx} className={`cell ${cell.active ? 'active' : ''}`}
             style={{ width: `${cell.width}%`, ['--fill' as any]: `${cell.fill}%` }}>
          <span>{cell.text}</span>
        </div>
      ))}
      <div className="playhead"
           style={{
             left: `${Math.min(100, posMod / Math.max(0.001, totalSec) * 100)}%`,
             transition: disableAnim ? 'none' : undefined
           }}
      />
      <style>{String.raw`
        .timeline {
          position: relative;
          display: flex;
          gap: 0;
          border: 1px solid #1f2937;
          border-radius: 10px;
          background: #0b1220;
          overflow: hidden;
          height: 40px;
        }
        .timeline .cell {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #c7d2fe;
          border-right: 1px dashed #1f2937;
          font-weight: 600;
          user-select: none;
        }
        .timeline .cell:last-child { border-right: 0; }
        .timeline .cell::after {
          content: '';
          position: absolute; inset: 0 0 0 0;
          width: var(--fill, 0%);
          background: rgba(96,165,250,0.16);
          transition: width 80ms linear;
          will-change: width;
          pointer-events: none;
        }
        .timeline .cell.active {
          color: #0ea5e9;
          background: linear-gradient(0deg, rgba(56,189,248,0.08), transparent);
        }
        .timeline .cell.active::after { background: rgba(56,189,248,0.28); }
        .timeline .playhead {
          position: absolute; top: 0; bottom: 0;
          width: 2px; background: #3b82f6;
          box-shadow: 0 0 0 1px rgba(59,130,246,.35);
          transition: left 80ms linear;
          will-change: left;
        }
        .timeline.no-anim .cell::after { transition: none !important; }
        .timeline.no-anim .playhead    { transition: none !important; }
        @media (prefers-reduced-motion: reduce) {
          .timeline .cell::after, .timeline .playhead { transition: none !important; }
        }
      `}</style>
    </div>
  )
}