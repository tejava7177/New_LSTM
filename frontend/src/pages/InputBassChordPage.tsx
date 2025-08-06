// src/pages/InputBassChordPage.tsx
import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'

const DEFAULT_CAPTURE_COUNT = 3
const START_MAX_HZ = 150
const TRACK_MAX_HZ = 120
const LOCK_TIME_MS = 1200
const QUIET_GAP_MS = 250

// ★ 추가: 재암(arm) 게이트 파라미터
const REARM_QUIET_MS = 300   // 무음이 이 시간 이상 지속되면 arm=true
const COOLDOWN_MS = 220      // 캡처 직후 짧은 쿨다운(바로 재시작 방지)

const NAMES_SHARP = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'] as const
const NAMES_FLAT  = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'] as const
const log2 = (x: number) => Math.log(x) / Math.LN2

function freqToNearest(freq: number) {
  const midi = Math.round(69 + 12 * log2(freq / 440))
  const pc = (midi % 12 + 12) % 12
  const nameSharp = NAMES_SHARP[pc]
  const nameFlat  = NAMES_FLAT[pc]
  const snappedFreq = 440 * Math.pow(2, (midi - 69) / 12)
  return { pc, nameSharp, nameFlat, snappedFreq }
}
function pcOctToFreq(pc: number, octave: number) {
  const midi = 12 + pc + 12 * octave
  return 440 * Math.pow(2, (midi - 69) / 12)
}
const BASS_RANGE_MIN = 40, BASS_RANGE_MAX = 110
function pcToBassFreq(pc: number) {
  const cands = [1,2,3].map(o => ({ o, f: pcOctToFreq(pc, o) }))
  let f = cands.reduce((a,b)=> Math.abs(a.f-75)<Math.abs(b.f-75)?a:b).f
  while (f > BASS_RANGE_MAX) f /= 2
  while (f < BASS_RANGE_MIN) f *= 2
  return f
}
function nameToPc(name: string) {
  const i1 = NAMES_SHARP.indexOf(name as any); if (i1>=0) return i1
  const i2 = NAMES_FLAT.indexOf(name as any);  if (i2>=0) return i2
  return 0
}

// ── 베이스 톤 재생(간단 합성)
let sharedCtx: AudioContext | null = null
function getCtx(){ return sharedCtx ?? (sharedCtx = new AudioContext()) }
function playBass(freq: number, duration = 1.2) {
  const ctx = getCtx()
  const osc = ctx.createOscillator(), sub = ctx.createOscillator(), g = ctx.createGain()
  osc.type='triangle'; sub.type='sine'
  osc.frequency.value = freq; sub.frequency.value = freq/2
  g.gain.setValueAtTime(0, ctx.currentTime)
  osc.connect(g); sub.connect(g); g.connect(ctx.destination)
  const t0 = ctx.currentTime
  g.gain.linearRampToValueAtTime(0.9, t0+0.02)
  g.gain.exponentialRampToValueAtTime(0.2, t0+duration*0.5)
  g.gain.exponentialRampToValueAtTime(0.0001, t0+duration)
  osc.start(); sub.start()
  osc.stop(t0+duration+0.02); sub.stop(t0+duration+0.02)
}

type Slot = { name: string } | null

export default function InputBassChordPage() {
  const [deviceId, setDeviceId] = useState<string>('')
  const [preferFlat, setPreferFlat] = useState(false)
  const [targetCount, setTargetCount] = useState<3|4>(DEFAULT_CAPTURE_COUNT)

  const [slots, setSlots] = useState<Slot[]>(Array(targetCount).fill(null))
  const [idx, setIdx] = useState(0)
  type Mode = 'idle' | 'tracking' | 'done'
  const [mode, setMode] = useState<Mode>('idle')

  const minHzRef = useRef<number | null>(null)
  const startMsRef = useRef<number>(0)
  const lastPitchMsRef = useRef<number>(0)

  // ★ 재암 게이트 & 쿨다운
  const armedRef = useRef(true)                // arm=true 여야 새 캡처 시작 가능
  const cooldownUntilRef = useRef(0)           // 쿨다운 종료 시각
  const finalizingRef = useRef(false)          // finalize 재진입 방지

  const pitch = usePitch(deviceId || undefined, { fftSize: 8192, minVolumeRms: 0.02 })

  // 입력 개수 변경 시 리셋
  useEffect(() => {
    setSlots(Array(targetCount).fill(null))
    setIdx(0); setMode('idle')
    minHzRef.current = null
    armedRef.current = true
    cooldownUntilRef.current = 0
  }, [targetCount])

  useEffect(() => {
    const now = performance.now()

    if (pitch != null) {
      lastPitchMsRef.current = now

      // IDLE → TRACKING : arm && 쿨다운 종료 && < START_MAX_HZ
      if (mode === 'idle') {
        if (armedRef.current && now >= cooldownUntilRef.current && pitch < START_MAX_HZ) {
          setMode('tracking')
          startMsRef.current = now
          minHzRef.current = pitch
          // arm 해제(이 플럭 동안에는 한 슬롯만)
          armedRef.current = false
        }
        return
      }

      if (mode === 'tracking') {
        if (pitch < TRACK_MAX_HZ) {
          if (minHzRef.current == null || pitch < minHzRef.current) minHzRef.current = pitch
        }
        const elapsed = now - startMsRef.current
        if (pitch > START_MAX_HZ || elapsed >= LOCK_TIME_MS) {
          finalizeCapture()
        }
        return
      }

      return
    }

    // pitch == null (무음) → REARM_QUIET_MS 이상 조용하면 arm=true
    const t = setTimeout(() => {
      if (performance.now() - lastPitchMsRef.current >= REARM_QUIET_MS) {
        armedRef.current = true
      }
    }, REARM_QUIET_MS)
    return () => clearTimeout(t)

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pitch, mode])

  function finalizeCapture() {
    if (finalizingRef.current) return
    finalizingRef.current = true

    const minHz = minHzRef.current
    minHzRef.current = null

    if (minHz == null) {
      setMode('idle')
      // 캡처 실패에도 쿨다운/재암 루틴 적용
      cooldownUntilRef.current = performance.now() + COOLDOWN_MS
      setTimeout(() => { armedRef.current = true }, REARM_QUIET_MS)
      finalizingRef.current = false
      return
    }

    const { pc, nameSharp, nameFlat } = freqToNearest(minHz)
    const name = preferFlat ? nameFlat : nameSharp

    const next = [...slots]; next[idx] = { name }
    setSlots(next)

    const nextIdx = idx + 1
    if (nextIdx >= targetCount) {
      setMode('done')
    } else {
      setIdx(nextIdx)
      setMode('idle')
    }

    // ★ 캡처 직후: 쿨다운 + 무음 재암 필요
    cooldownUntilRef.current = performance.now() + COOLDOWN_MS
    setTimeout(() => { armedRef.current = true }, REARM_QUIET_MS)

    finalizingRef.current = false
  }

  function resetAll() {
    setSlots(Array(targetCount).fill(null))
    setIdx(0); setMode('idle')
    minHzRef.current = null
    armedRef.current = true
    cooldownUntilRef.current = 0
  }

  function setSlotName(i: number, newName: string) {
    const next = [...slots]; next[i] = { name: newName }; setSlots(next)
  }
  function playSlot(i: number) {
    const s = slots[i]; if (!s) return
    const pc = nameToPc(s.name); const f = pcToBassFreq(pc); playBass(f)
  }
  function playAll() { slots.forEach(s => { if (!s) return; playBass(pcToBassFreq(nameToPc(s.name)), 1.5) }) }

  const filled = slots.filter(Boolean).length

  return (
    <div style={{ padding: 16 }}>
      <h2>🎸 베이스 음 입력 (최저 Hz 기반 · {targetCount}개)</h2>

      <div style={{ marginBottom: 10 }}>
        <DeviceSelect value={deviceId} onChange={setDeviceId} />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ marginRight: 12 }}>
          입력 개수:&nbsp;
          <select value={targetCount} onChange={e => setTargetCount(Number(e.target.value) as 3|4)}>
            <option value={3}>3개</option><option value={4}>4개</option>
          </select>
        </label>
        <label>
          표기 방식:&nbsp;
          <select onChange={e => setPreferFlat(e.target.value==='flat')}>
            <option value="sharp">#(샤프) 우선</option>
            <option value="flat">♭(플랫) 우선</option>
          </select>
        </label>
        <button style={{ marginLeft: 12 }} onClick={resetAll}>리셋</button>
      </div>

      <div style={{ marginBottom: 8, fontWeight: 600 }}>
        {mode === 'done' ? '입력이 완료되었습니다.' : `입력 대기: ${idx + 1}/${targetCount}`} {mode==='tracking' && <span style={{ color:'#888' }}>(분석 중)</span>}
      </div>
      <p style={{ marginTop: 0, color: '#666' }}>
        “기타 음을 입력하세요” → 한 번 튕길 때 **한 슬롯만** 채워집니다. (무음 후 자동 재장전)
      </p>

      <table style={{ width:'100%', maxWidth:640, borderCollapse:'collapse' }}>
        <thead>
          <tr style={{ textAlign:'left', borderBottom:'1px solid #ddd' }}>
            <th style={{ padding:6 }}>#</th>
            <th style={{ padding:6 }}>입력 음</th>
            <th style={{ padding:6 }}>수정</th>
            <th style={{ padding:6 }}>미리듣기</th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: targetCount }).map((_, i) => {
            const slot = slots[i]
            const name = slot?.name ?? ''
            const pc = name ? nameToPc(name) : 0
            const sharpName = NAMES_SHARP[pc]
            const flatName  = NAMES_FLAT[pc]
            const letter = (name || sharpName).replace('b','').replace('#','')
            const accidental = name.includes('#') ? '#' : (name.includes('b') ? 'b' : 'n')
            return (
              <tr key={i} style={{ borderBottom:'1px solid #eee' }}>
                <td style={{ padding:6 }}>{i+1}</td>
                <td style={{ padding:6, fontWeight: i===idx && mode!=='done' ? 700 : 400 }}>
                  {slot ? slot.name : (i===idx && mode!=='done' ? '↙ 이 슬롯에 입력' : '—')}
                </td>
                <td style={{ padding:6 }}>
                  <NotePicker
                    value={{ letter, accidental: accidental as any }}
                    onChange={(v) => {
                      const composed = composeName(v.letter, v.accidental as any, preferFlat)
                      setSlotName(i, composed)
                    }}
                  />
                </td>
                <td style={{ padding:6 }}>
                  <button disabled={!slot} onClick={() => playSlot(i)}>▶︎</button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div style={{ marginTop:12 }}>
        <strong>입력된 음:</strong>&nbsp;{filled===0 ? '—' : slots.map(s=>s?.name ?? '—').join(' ')}
      </div>
      <div style={{ marginTop:8 }}>
        <button disabled={filled===0} onClick={playAll}>전체 재생(뚠~)</button>
      </div>
      {filled===targetCount && (
        <div style={{ marginTop:12, color:'#2e7d32', fontWeight:600 }}>
          예시: “{slots.map(s=>s?.name ?? '').filter(Boolean).join(' ')}” 을 입력했습니다.
        </div>
      )}
    </div>
  )
}

function NotePicker(props: {
  value: { letter: string; accidental: 'n'|'#'|'b' }
  onChange: (v: { letter: string; accidental: 'n'|'#'|'b' }) => void
}) {
  const letters = ['C','D','E','F','G','A','B']
  const accs: Array<'n'|'#'|'b'> = ['n','#','b']
  return (
    <div>
      <select value={props.value.letter}
              onChange={e=>props.onChange({ ...props.value, letter: e.target.value })}
              style={{ marginRight:6 }}>
        {letters.map(l => <option key={l} value={l}>{l}</option>)}
      </select>
      <select value={props.value.accidental}
              onChange={e=>props.onChange({ ...props.value, accidental: e.target.value as any })}>
        {accs.map(a => <option key={a} value={a}>{a==='n'?'♮':a}</option>)}
      </select>
    </div>
  )
}
function composeName(letter: string, accidental: 'n'|'#'|'b', preferFlat: boolean) {
  const base: Record<string, number> = { C:0, D:2, E:4, F:5, G:7, A:9, B:11 }
  let pc = base[letter]
  if (accidental==='#') pc = (pc+1)%12
  if (accidental==='b') pc = (pc+11)%12
  return preferFlat ? NAMES_FLAT[pc] : NAMES_SHARP[pc]
}