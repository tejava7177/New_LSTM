// src/pages/InputBassChordPage.tsx
import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'

/* ===== 캡처/게이트 파라미터 ===== */
const DEFAULT_CAPTURE_COUNT = 3
const START_MAX_HZ = 150
const TRACK_MAX_HZ = 120
const LOCK_TIME_MS = 1200
const QUIET_GAP_MS = 250
const REARM_QUIET_MS = 350
const COOLDOWN_MS = 220

/* ===== 노트/주파수 유틸 ===== */
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

/* ===== 간단 베이스톤 재생 ===== */
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

/* ===== 코드 품질/장르 ===== */
type Genre = 'rock' | 'jazz' | 'pop'
type Quality = '5' | 'maj' | 'min' | '7' | 'sus4' | 'dim' | 'aug'

const GENRE_DEFAULT_QUALITY: Record<Genre, Quality> = {
  rock: '5',
  pop:  'maj',
  jazz: '7',
}

// maj 표기 선택(C vs Cmaj)
function buildSymbol(root: string, q: Quality, opts?: { majAsText?: boolean }) {
  const majAsText = !!opts?.majAsText
  switch (q) {
    case '5':   return `${root}5`
    case 'maj': return majAsText ? `${root}maj` : `${root}`
    case 'min': return `${root}m`
    case '7':   return `${root}7`
    case 'sus4':return `${root}sus4`
    case 'dim': return `${root}dim`
    case 'aug': return `${root}aug`
  }
}

/* ===== 페이지 ===== */
type Slot = { name: string } | null

export default function InputBassChordPage() {
  // 캡처
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
  const armedRef = useRef(true)
  const cooldownUntilRef = useRef(0)
  const finalizingRef = useRef(false)
  const pitch = usePitch(deviceId || undefined, { fftSize: 8192, minVolumeRms: 0.02 })

  // 코드 생성
  const [genre, setGenre] = useState<Genre | ''>('')
  const [qualities, setQualities] = useState<Quality[]>(['maj','maj','maj','maj'])
  const [majAsText, setMajAsText] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string>('')

  // 입력 개수 변경 시 초기화
  useEffect(() => {
    setSlots(Array(targetCount).fill(null))
    setIdx(0); setMode('idle')
    minHzRef.current = null
    armedRef.current = true
    cooldownUntilRef.current = 0
    setQualities(prev => {
      const q = [...prev]
      while (q.length < targetCount) q.push(GENRE_DEFAULT_QUALITY.rock)
      return q.slice(0, targetCount)
    })
  }, [targetCount])

  // 캡처 루프
  useEffect(() => {
    const now = performance.now()
    if (pitch != null) {
      lastPitchMsRef.current = now
      if (mode === 'idle') {
        if (armedRef.current && now >= cooldownUntilRef.current && pitch < START_MAX_HZ) {
          setMode('tracking')
          startMsRef.current = now
          minHzRef.current = pitch
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
    // 무음 → 재장전
    const t = setTimeout(() => {
      if (performance.now() - lastPitchMsRef.current >= REARM_QUIET_MS) {
        armedRef.current = true
      }
    }, REARM_QUIET_MS)
    return () => clearTimeout(t)
  }, [pitch, mode])

  function finalizeCapture() {
    if (finalizingRef.current) return
    finalizingRef.current = true

    const minHz = minHzRef.current
    minHzRef.current = null

    if (minHz == null) {
      setMode('idle')
      cooldownUntilRef.current = performance.now() + COOLDOWN_MS
      setTimeout(() => { armedRef.current = true }, REARM_QUIET_MS)
      finalizingRef.current = false
      return
    }
    const { nameSharp, nameFlat } = freqToNearest(minHz)
    const name = (preferFlat ? nameFlat : nameSharp)

    const next = [...slots]; next[idx] = { name }; setSlots(next)

    if (genre) {
      setQualities(q => {
        const nq = [...q]; nq[idx] = GENRE_DEFAULT_QUALITY[genre]; return nq
      })
    }

    const nextIdx = idx + 1
    if (nextIdx >= targetCount) setMode('done')
    else { setIdx(nextIdx); setMode('idle') }

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
    setResult(null); setError('')
  }

  function applyGenrePreset(g: Genre) {
    setGenre(g)
    setQualities(prev => {
      const arr = [...prev]
      for (let i = 0; i < targetCount; i++) arr[i] = GENRE_DEFAULT_QUALITY[g]
      return arr
    })
  }

  function changeQuality(i: number, q: Quality) {
    setQualities(prev => {
      const arr = [...prev]; arr[i] = q; return arr
    })
  }

  function buildSeed(): string[] {
    const names = slots.slice(0, targetCount).map(s => s?.name).filter(Boolean) as string[]
    const syms = names.map((root, i) => buildSymbol(root, (qualities[i] ?? 'maj'), { majAsText }))
    return syms
  }

  async function onPredict() {
    setError(''); setResult(null)
    if (!genre) { alert('장르를 선택하세요.'); return }
    const filled = slots.filter(Boolean).length
    if (filled < targetCount) {
      const ok = confirm(`아직 ${targetCount - filled}개 미입력입니다. 현재 ${filled}개로 진행할까요?`)
      if (!ok) return
    }
    const seed = buildSeed()
    setLoading(true)
    try {
      const res = await fetch('/api/chords/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genre, seed }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setResult(json)
    } catch (e: any) {
      setError(e.message ?? String(e))
    } finally {
      setLoading(false)
    }
  }

  const filled = slots.filter(Boolean).length

  return (
    <div style={{ padding: 16 }}>
      <h2>🎸 베이스 음 입력 → 코드 진행 생성</h2>

      {/* 입력/옵션 */}
      <div style={{ marginBottom: 10 }}>
        <DeviceSelect value={deviceId} onChange={setDeviceId} />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ marginRight: 12 }}>
          입력 개수:&nbsp;
          <select value={targetCount} onChange={e => setTargetCount(Number(e.target.value) as 3 | 4)}>
            <option value={3}>3개</option>
            <option value={4}>4개</option>
          </select>
        </label>
        <label>
          표기 방식:&nbsp;
          <select value={preferFlat ? 'flat' : 'sharp'} onChange={e => setPreferFlat(e.target.value === 'flat')}>
            <option value="sharp">#(샤프) 우선</option>
            <option value="flat">♭(플랫) 우선</option>
          </select>
        </label>
        <label style={{ marginLeft: 12 }}>
          메이저 표기:&nbsp;
          <select value={majAsText ? 'Cmaj' : 'C'} onChange={(e)=>setMajAsText(e.target.value==='Cmaj')}>
            <option value="C">C (기본)</option>
            <option value="Cmaj">Cmaj</option>
          </select>
        </label>
        <button style={{ marginLeft: 12 }} onClick={resetAll}>리셋</button>
      </div>

      {/* 슬롯 & 품질 선택 */}
      <table style={{ width: '100%', maxWidth: 740, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid #ddd' }}>
            <th style={{ padding: 6 }}>#</th>
            <th style={{ padding: 6 }}>입력 음</th>
            <th style={{ padding: 6 }}>Chord Quality</th>
            <th style={{ padding: 6 }}>미리듣기</th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: targetCount }).map((_, i) => {
            const name = slots[i]?.name ?? ''
            return (
              <tr key={i} style={{ borderBottom:'1px solid #eee' }}>
                <td style={{ padding: 6 }}>{i+1}</td>
                <td style={{ padding: 6, fontWeight: i===idx && mode!=='done' ? 700 : 400 }}>
                  {name || (i===idx && mode!=='done' ? '↙ 이 슬롯에 입력' : '—')}
                </td>
                <td style={{ padding: 6 }}>
                  <select
                    value={qualities[i] ?? 'maj'}
                    onChange={e => changeQuality(i, e.target.value as Quality)}
                  >
                    <option value="5">5 (Power)</option>
                    <option value="maj">maj</option>
                    <option value="min">min</option>
                    <option value="7">7</option>
                    <option value="sus4">sus4</option>
                    <option value="dim">dim</option>
                    <option value="aug">aug</option>
                  </select>
                </td>
                <td style={{ padding: 6 }}>
                  <button
                    disabled={!name}
                    onClick={() => {
                      const pc = nameToPc(name); const f = pcToBassFreq(pc); playBass(f)
                    }}
                  >▶︎</button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div style={{ marginTop: 10 }}>
        <strong>입력된 루트:</strong> {filled === 0 ? '—' : slots.slice(0, targetCount).map(s => s?.name ?? '—').join(' ')}
        <br />
        <strong>Seed 미리보기:</strong> {buildSeed().join(' , ')}
      </div>

      {/* 코드 생성 패널 */}
      <div style={{ marginTop: 18, padding: 12, border: '1px solid #e5e5e5', borderRadius: 8 }}>
        <div style={{ marginBottom: 8, fontWeight: 600 }}>장르 선택</div>
        <label style={{ marginRight: 12 }}>
          <input type="radio" name="genre" value="rock"
                 checked={genre === 'rock'} onChange={() => applyGenrePreset('rock')} /> rock
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="radio" name="genre" value="pop"
                 checked={genre === 'pop'} onChange={() => applyGenrePreset('pop')} /> pop
        </label>
        <label>
          <input type="radio" name="genre" value="jazz"
                 checked={genre === 'jazz'} onChange={() => applyGenrePreset('jazz')} /> jazz
        </label>

        <div style={{ marginTop: 12 }}>
          <button onClick={onPredict} disabled={loading}>
            {loading ? '생성 중…' : '코드진행 생성하기'}
          </button>
        </div>

        <div style={{ marginTop: 10, fontSize: 12, color: '#666' }}>
          요청 바디 미리보기: <code>{JSON.stringify({ genre: genre || '(선택 필요)', seed: buildSeed() })}</code>
        </div>

        {error && <div style={{ marginTop: 10, color: '#c62828' }}>오류: {error}</div>}
        {result && (
          <div style={{ marginTop: 12 }}>
            <div><strong>결과</strong></div>
            <pre style={{ background:'#f8f8f8', padding:8, borderRadius:6, overflowX:'auto' }}>
{JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}