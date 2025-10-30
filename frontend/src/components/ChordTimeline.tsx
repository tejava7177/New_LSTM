import React from 'react'
import type { ChordCue } from '../lib/midiCues'

type Props = {
  cues: ChordCue[]
  total: number
  position: number
  posMod: number
  noAnim?: boolean
}

export function ChordTimeline({ cues, total, position, posMod, noAnim }: Props) {
  return (
    <div className="timeline">
      {cues.map((c, i) => {
        const t0 = c.time
        const t1 = cues[i + 1]?.time ?? total
        const w = Math.max(4, (t1 - t0) / Math.max(1, total) * 100)
        const active = position >= t0 && position < t1
        return (
          <div key={i} className={`cell ${active ? 'active' : ''}`} style={{width: `${w}%`}}>
            <span>{c.text}</span>
          </div>
        )
      })}
      <div
        className="playhead"
        style={{
          left: `${Math.min(100, posMod / Math.max(0.001, total) * 100)}%`,
          transition: noAnim ? 'none' : undefined
        }}
      />
    </div>
  )
}
