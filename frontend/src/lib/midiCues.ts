import { Midi } from '@tonejs/midi'

export type ChordCue = { time: number; text: string }

/** MIDI 안의 'marker'/'text' 메타에서 코드 마커를 추출. (없으면 빈 배열) */
export async function extractChordCuesFromMidi(
  arrBuf: ArrayBuffer,
  opts?: { preRollSec?: number; windowBeats?: number }
): Promise<ChordCue[]> {
  const midi = new Midi(arrBuf)
  const cues: ChordCue[] = []
  const preRoll = opts?.preRollSec ?? 0

  midi.tracks.forEach(t => {
    const name = (t.name || '').toLowerCase()
    const raw = (t as any).events as any[] | undefined
    if (!raw) return
    if (name.includes('chord') || name.includes('guide') || name.includes('marker')) {
      raw.forEach(ev => {
        if (ev.type === 'meta' && (ev.subtype === 'marker' || ev.subtype === 'text')) {
          const txt = (ev.text || '').trim()
          if (txt) {
            const secs = midi.header.ticksToSeconds(ev.ticks || 0) + preRoll
            cues.push({ time: secs, text: txt })
          }
        }
      })
    }
  })
  cues.sort((a,b) => a.time - b.time)
  // 같은 시간대 중복 제거
  const dedup: ChordCue[] = []
  let last = -1
  cues.forEach(c => {
    const key = Math.round(c.time * 1000)
    if (key !== last) { dedup.push(c); last = key }
  })
  return dedup
}

/** 현재 t 에서 now/next 코드 반환 */
export function getNowNextChord(cues: ChordCue[], tSec: number): { now: string; next: string } {
  if (!cues.length) return { now: '', next: '' }
  let idx = 0
  for (let i=0;i<cues.length;i++) {
    const n = cues[i+1]
    if (tSec >= cues[i].time && (!n || tSec < n.time)) { idx = i; break }
    if (tSec >= cues[cues.length-1].time) idx = cues.length-1
  }
  return { now: cues[idx].text, next: cues[idx+1]?.text ?? '' }
}