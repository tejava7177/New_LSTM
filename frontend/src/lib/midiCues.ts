import { Midi } from '@tonejs/midi'

export type ChordCue = { time: number; text: string }

type ExtractOpts = {
  /** 카운트인(초)만큼 모든 큐를 오른쪽으로 이동 (재생/녹음 정렬) */
  preRollSec?: number
  /** 코드 추정 시 윈도 길이(beat 단위). 보통 1박이 자연스러움 */
  windowBeats?: number
}

/** pitch-class(0~11) → 이름 */
const PC_TO_NAME = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

/** 간단한 코드 포맷터 */
function formatChord(rootPc: number, quality: 'maj'|'min'|'dim'|'aug', seventh: ''|'7'|'maj7') {
  const root = PC_TO_NAME[rootPc]
  const triad = quality === 'maj' ? '' : quality === 'min' ? 'm' : quality === 'dim' ? 'dim' : 'aug'
  return root + triad + (seventh ? seventh : '')
}

/** beat 그리드(초 단위) 만들기 — 템포 변화를 고려하기 위해 ticks→seconds로 변환 */
function makeBeatGrid(midi: Midi, beatsPerStep = 1): number[] {
  const ppq = midi.header.ppq || 480
  const stepTicks = ppq * beatsPerStep
  const out: number[] = []
  // ticks→seconds는 템포 맵을 사용하므로 안전함
  for (let n = 0; ; n++) {
    const t = midi.header.ticksToSeconds(n * stepTicks)
    if (t > midi.duration + 1e-4) break
    out.push(t)
  }
  return out
}

/** 윈도 [t0, t1]과 노트 [s, e]가 얼마나 겹치는지(초) */
function overlapSec(t0: number, t1: number, s: number, e: number) {
  const a = Math.max(t0, s)
  const b = Math.min(t1, e)
  return Math.max(0, b - a)
}

/** 윈도 내 pitch-class 히스토그램 계산 (드럼 ch10 제외) */
function gatherPitchClasses(midi: Midi, t0: number, t1: number) {
  const pcw = new Float32Array(12)
  for (const tr of midi.tracks) {
    const ch = tr.channel ?? 0
    if (ch === 9) continue // GM Drums
    for (const n of tr.notes) {
      const s = n.time
      const e = n.time + n.duration
      const ov = overlapSec(t0, t1, s, e)
      if (ov <= 0) continue
      const pc = n.midi % 12
      // 가중치 = 겹친 시간 × 벨로시티
      pcw[pc] += ov * (n.velocity ?? 0.8)
    }
  }
  return pcw
}

/** triad + 7th 단순 매칭으로 코드 추정 */
function guessChordFromPCW(pcw: Float32Array): string | null {
  const triads: Array<{q:'maj'|'min'|'dim'|'aug'; iv:number[]}> = [
    { q:'maj', iv:[0,4,7] },
    { q:'min', iv:[0,3,7] },
    { q:'dim', iv:[0,3,6] },
    { q:'aug', iv:[0,4,8] },
  ]

  let best: {score:number; root:number; q:'maj'|'min'|'dim'|'aug'} | null = null

  for (let root=0; root<12; root++) {
    for (const t of triads) {
      let s = 0
      for (const iv of t.iv) s += pcw[(root + iv) % 12]
      // 간단 보너스: 루트에 조금 가중치
      s += 0.2 * pcw[root]
      if (!best || s > best.score) best = {score:s, root, q:t.q}
    }
  }
  if (!best || best.score < 1e-3) return null

  // 7th 감지(루트 기준 b7=10, maj7=11)
  const dom7 = pcw[(best.root + 10) % 12]
  const maj7 = pcw[(best.root + 11) % 12]
  const seventh: ''|'7'|'maj7' =
    Math.max(dom7, maj7) > 0.35 * best.score ? (dom7 >= maj7 ? '7' : 'maj7') : ''
  return formatChord(best.root, best.q, seventh)
}

/** cue 리스트에서 연속 같은 코드는 합치기 */
function compressCues(cues: ChordCue[]): ChordCue[] {
  const out: ChordCue[] = []
  for (const c of cues) {
    if (out.length === 0 || out[out.length-1].text !== c.text) out.push(c)
  }
  return out
}

/**
 * MIDI에서 코드 큐를 뽑는다.
 * 1) 트랙 텍스트/마커(chord/guide/marker)에 코드가 있으면 우선 사용
 * 2) 없으면 비드(beat) 단위 창으로 음표를 분석해 코드 추정
 */
export async function extractChordCuesFromMidi(
  midiArrayBuffer: ArrayBuffer,
  opts: ExtractOpts = {}
): Promise<ChordCue[]> {
  const { preRollSec = 0, windowBeats = 1 } = opts
  const midi = new Midi(midiArrayBuffer)

  // 1) 마커/텍스트에서 코드 추출
  const fromMarkers: ChordCue[] = []
  for (const tr of midi.tracks) {
    const name = (tr.name || '').toLowerCase()
    const raw = (tr as any).events as any[] | undefined
    if (!raw) continue
    if (name.includes('chord') || name.includes('guide') || name.includes('marker')) {
      for (const ev of raw) {
        if (ev.type === 'meta' && (ev.subtype === 'marker' || ev.subtype === 'text')) {
          const txt = (ev.text || '').trim()
          if (txt) {
            const time = midi.header.ticksToSeconds(ev.ticks || 0) + preRollSec
            fromMarkers.push({ time, text: txt })
          }
        }
      }
    }
  }
  if (fromMarkers.length > 0) {
    fromMarkers.sort((a,b)=>a.time-b.time)
    return compressCues(fromMarkers)
  }

  // 2) 마커가 없으면 자동 추정
  const beatTimes = makeBeatGrid(midi, windowBeats)
  const cues: ChordCue[] = []
  for (let i=0; i<beatTimes.length-1; i++) {
    const t0 = beatTimes[i]
    const t1 = beatTimes[i+1]
    const pcw = gatherPitchClasses(midi, t0, t1)
    const name = guessChordFromPCW(pcw)
    if (name) cues.push({ time: t0 + preRollSec, text: name })
  }
  return compressCues(cues)
}

/** 현재/다음 코드 헬퍼 */
export function getNowNextChord(cues: ChordCue[], timeSec: number) {
  if (cues.length === 0) return { now: '', next: '' }
  let i = 0
  for (; i < cues.length; i++) {
    const isLast = i === cues.length - 1
    const here = cues[i].time
    const nextT = isLast ? Infinity : cues[i+1].time
    if (timeSec >= here && timeSec < nextT) break
  }
  const now = cues[Math.min(i, cues.length-1)]
  const next = cues[i+1]
  return { now: now?.text || '', next: next?.text || '' }
}