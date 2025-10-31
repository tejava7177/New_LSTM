import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChordCue } from '../../lib/midiCues'

type UseCycleArgs = {
  cues: ChordCue[]
  timeSig: [number, number]
  tempoBpm: number
  barsPerChord: number
  position: number
}

export const useChordTimeline = {
  buildCuesFromProgression(prog: string[], timeSig: [number, number], tempoBpm: number, barsPerChord = 1): ChordCue[] {
    const beatsPerBar = timeSig?.[0] ?? 4
    const secPerBar = beatsPerBar * (60 / Math.max(40, Math.min(300, tempoBpm)))
    let t = 0
    const cues: ChordCue[] = prog.map((text) => {
      const cue = { text, time: t }
      t += secPerBar * Math.max(1, barsPerChord)
      return cue
    })
    return cues
  },

  useCycle({ cues, timeSig, tempoBpm, barsPerChord, position }: UseCycleArgs) {
    const totalFromCues = useMemo(() => {
      if (!cues.length) return 0
      const last = cues[cues.length - 1]
      const tail = (timeSig?.[0] ?? 4) * (60 / Math.max(40, Math.min(300, tempoBpm))) * Math.max(1, barsPerChord)
      return last.time + tail
    }, [cues, timeSig, tempoBpm, barsPerChord])

    const cycleSec = Math.max(0.001, totalFromCues)
    const posMod = ((position % cycleSec) + cycleSec) % cycleSec

    const prevPosRef = useRef(0)
    const [noAnim, setNoAnim] = useState(false)
    useEffect(() => {
      const prev = prevPosRef.current
      if (posMod < prev - 0.05) {
        setNoAnim(true); requestAnimationFrame(() => setNoAnim(false))
      }
      prevPosRef.current = posMod
    }, [posMod])

    return { totalFromCues, posMod, noAnim }
  }
}
