import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import { generateTrack, getTrackStatus, midiUrl, xmlUrl, wavUrl } from '../lib/tracks'

/* ============== 상수/유틸 ============== */
const DEFAULT_CAPTURE_COUNT = 3
const START_MAX_HZ = 150
const TRACK_MAX_HZ = 120
const LOCK_TIME_MS = 1200
const REARM_QUIET_MS = 350
const COOLDOWN_MS = 220

const NAMES_SHARP = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'] as const
const NAMES_FLAT  = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'] as const
const log2 = (x: number) => Math.log(x) / Math.LN2

type Genre   = 'rock' | 'jazz' | 'pop'
type Quality = '5' | 'maj' | 'min' | '7' | 'sus4' | 'dim' | 'aug'
const GENRE_DEFAULT_QUALITY: Record<Genre, Quality> = { rock: '5', pop: 'maj', jazz: '7' }

const PC_MAP: Record<string, number> = {
  C:0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11
}

type Candidate = { progression: string[]; score?: number; label?: string }
type PredictResult = { candidates: Candidate[] }
type Slot = { name: string } | null
type JobState = { status: 'IDLE'|'RUNNING'|'DONE'|'ERROR'; progress: number; jobId?: string }

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
  let f = pcOctToFreq(pc, 2)
  while (f > BASS_RANGE_MAX) f /= 2
  while (f < BASS_RANGE_MIN) f *= 2
  return f
}
function nameToPc(name: string) {
  const i1 = NAMES_SHARP.indexOf(name as any); if (i1>=0) return i1
  const i2 = NAMES_FLAT.indexOf(name as any);  if (i2>=0) return i2
  return 0
}
function buildSymbol(root: string, q: Quality, opts?: { majAsText?: boolean }) {
  const majAsText = !!opts?.majAsText
  switch (q) {
    case '5': return `${root}5`
    case 'maj': return majAsText ? `${root}maj` : `${root}`
    case 'min': return `${root}m`
    case '7': return `${root}7`
    case 'sus4': return `${root}sus4`
    case 'dim': return `${root}dim`
    case 'aug': return `${root}aug`
  }
}
const parseSymbol = (sym: string) => {
  const m = sym.trim().match(/^([A-G](?:#|b)?)(.*)$/)
  return { root: m?.[1] ?? 'C', q: (m?.[2] ?? '').trim() }
}
const normalizeQuality = (q: string): Quality => {
  if (q === '' || q === 'maj') return 'maj'
  if (q === 'm') return 'min'
  const ok = new Set(['5','7','sus4','dim','aug','maj','min'])
  return (ok.has(q) ? (q as Quality) : 'maj')
}
let sharedCtx: AudioContext | null = null
function getCtx(){ return sharedCtx ?? (sharedCtx = new AudioContext()) }
function previewProgression(symbols: string[], tempo=96) {
  const ctx = getCtx()
  const beat = 60/tempo
  let t = ctx.currentTime + 0.05
  const tonesByQ: Record<string, number[]> = {
    '': [0,4,7], maj:[0,4,7], m:[0,3,7], min:[0,3,7], '5':[0,7], '7':[0,4,7,10],
    sus4:[0,5,7], dim:[0,3,6], aug:[0,4,8]
  }
  symbols.forEach(sym => {
    const {root, q} = parseSymbol(sym)
    const pcs = (tonesByQ[q] ?? tonesByQ['']).map(i => (PC_MAP[root] + i) % 12)
    const master = ctx.createGain(); master.gain.value = 0; master.connect(ctx.destination)
    pcs.forEach((pc, idx) => {
      const f = idx===0 ? pcToBassFreq(pc) : pcToBassFreq(pc)*2
      const o = ctx.createOscillator(); o.type = idx===0?'triangle':'sine'
      const eg = ctx.createGain(); eg.gain.setValueAtTime(0, t)
      eg.gain.linearRampToValueAtTime(idx===0?0.9:0.35, t+0.02)
      eg.gain.exponentialRampToValueAtTime(0.0001, t+beat*0.95)
      o.frequency.value = f; o.connect(eg).connect(master)
      o.start(t); o.stop(t+beat)
    })
    master.gain.linearRampToValueAtTime(1.0, t+0.01)
    master.gain.exponentialRampToValueAtTime(0.0001, t+beat)
    t += beat
  })
}

/* ============== 컴포넌트 ============== */
export default function InputBassChordPage() {
  const navigate = useNavigate()

  // 캡처/UI 상태
  const [deviceId, setDeviceId] = useState<string>('')
  const [preferFlat, setPreferFlat] = useState(false)
  const [majAsText, setMajAsText] = useState(false)

  const targetCount = DEFAULT_CAPTURE_COUNT
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

  // 코드 생성 상태
  const [genre, setGenre] = useState<Genre | ''>('')
  const [qualities, setQualities] = useState<Quality[]>(['maj','maj','maj'])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PredictResult | null>(null)
  const [error, setError] = useState<string>('')

  // 트랙 생성 공통 & 후보 Job 상태
  const [tempo, setTempo] = useState(100)
  const [jobs, setJobs] = useState<Record<number, JobState>>({})

  // 입력 루프
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
        if (pitch > START_MAX_HZ || elapsed >= LOCK_TIME_MS) finalizeCapture()
        return
      }
      return
    }
    const t = setTimeout(() => {
      if (performance.now() - lastPitchMsRef.current >= REARM_QUIET_MS) armedRef.current = true
    }, REARM_QUIET_MS)
    return () => clearTimeout(t)
  }, [pitch, mode])

  function finalizeCapture() {
    if (finalizingRef.current) return
    finalizingRef.current = true
    const minHz = minHzRef.current; minHzRef.current = null
    if (minHz == null) {
      setMode('idle'); cooldownUntilRef.current = performance.now() + COOLDOWN_MS
      setTimeout(() => { armedRef.current = true }, REARM_QUIET_MS)
      finalizingRef.current = false; return
    }
    const { nameSharp, nameFlat } = freqToNearest(minHz)
    const name = preferFlat ? nameFlat : nameSharp
    const next = [...slots]; next[idx] = { name }; setSlots(next)

    if (genre) {
      setQualities(q => { const nq=[...q]; nq[idx]=GENRE_DEFAULT_QUALITY[genre as Genre]; return nq })
    }
    const nextIdx = idx + 1
    if (nextIdx >= targetCount) setMode('done'); else { setIdx(nextIdx); setMode('idle') }
    cooldownUntilRef.current = performance.now() + COOLDOWN_MS
    setTimeout(() => { armedRef.current = true }, REARM_QUIET_MS)
    finalizingRef.current = false
  }

  function buildSeed(): string[] {
    const names = slots.slice(0, targetCount).map(s => s?.name).filter(Boolean) as string[]
    return names.map((root, i) => buildSymbol(root, (qualities[i] ?? 'maj'), { majAsText })!)
  }

  function resetAll() {
    setSlots(Array(targetCount).fill(null))
    setIdx(0); setMode('idle')
    minHzRef.current = null
    armedRef.current = true
    cooldownUntilRef.current = 0
    setResult(null); setError('')
    setJobs({})
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
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genre, seed }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = (await res.json()) as PredictResult
      setResult(json)
      setJobs({})
    } catch (e: any) {
      setError(e.message ?? String(e))
    } finally { setLoading(false) }
  }

  async function startGenerateFor(idx: number, symbols: string[]) {
    setJobs(prev => ({ ...prev, [idx]: { status: 'RUNNING', progress: 0 } }))
    try {
      const { jobId } = await generateTrack({
        genre: (genre || 'rock') as Genre,
        progression: symbols,
        tempo,
        options: { repeats: 6 },
      })
      const timer = setInterval(async () => {
        try {
          const s = await getTrackStatus(jobId)
          setJobs(prev => ({ ...prev, [idx]: { status: s.status as any, progress: s.progress ?? 0, jobId } }))
          if (s.status === 'DONE' || s.status === 'ERROR') clearInterval(timer)
        } catch {
          clearInterval(timer)
          setJobs(prev => ({ ...prev, [idx]: { status: 'ERROR', progress: 0 } }))
        }
      }, 700)
    } catch {
      setJobs(prev => ({ ...prev, [idx]: { status: 'ERROR', progress: 0 } }))
    }
  }

  function goPracticeMix(jobId: string, symbols: string[]) {
    navigate('/practice-mix', {
      state: {
        source: 'predict',
        jobId,
        wavUrl: wavUrl(jobId),
        midiUrl: midiUrl(jobId),
        progression: symbols,
        tempo,
        timeSig: [4,4],
        preRollBeats: 4,
        barsPerChord: 1,
      }
    })
  }

  const filled = slots.filter(Boolean).length
  const seedPreview = buildSeed()

  return (
    <div className="ibc-wrap">
      <header className="ibc-head">
        <div className="ibc-title">🎼 코드 진행 & 음원, 악보 생성</div>
        <div className="ibc-sub">안내: <b>3개의 근음</b>을 차례대로 입력하세요.</div>
      </header>

      <section className="card">
        <div className="row wrap gap8">
          <button className="btn" onClick={async ()=>{ await navigator.mediaDevices.getUserMedia({ audio:true }) }}>
            🎤 마이크 권한
          </button>

          <DeviceSelect value={deviceId} onChange={setDeviceId} />

          <label className="row gap6">
            표기 방식
            <select value={preferFlat?'flat':'sharp'} onChange={e=>setPreferFlat(e.target.value==='flat')}>
              <option value="sharp">#(샤프) 우선</option>
              <option value="flat">♭(플랫) 우선</option>
            </select>
          </label>

          <label className="row gap6">
            메이저 표기
            <select value={majAsText?'Cmaj':'C'} onChange={e=>setMajAsText(e.target.value==='Cmaj')}>
              <option value="C">C (기본)</option>
              <option value="Cmaj">Cmaj</option>
            </select>
          </label>

          <button className="btn ghost ml-auto" onClick={resetAll}>리셋</button>
        </div>

        {/* 입력 슬롯 */}
        <div className="ibc-grid">
          <div className="grid-head">#</div>
          <div className="grid-head">입력 음</div>
          <div className="grid-head">Chord Quality</div>
          <div className="grid-head">미리듣기</div>

          {Array.from({ length: targetCount }).map((_, i) => {
            const name = slots[i]?.name ?? ''
            return (
              <div className="grid-row" key={i}>
                <div className="cell">{i+1}</div>
                <div className={`cell ${i===idx && mode!=='done' ? 'bold' : ''}`}>
                  {name || (i===idx && mode!=='done' ? '↙ 이 슬롯에 입력' : '—')}
                </div>
                <div className="cell">
                  <select
                    value={qualities[i] ?? 'maj'}
                    onChange={e=>setQualities(prev => { const arr=[...prev]; arr[i]=e.target.value as Quality; return arr })}
                  >
                    <option value="5">5 (Power)</option>
                    <option value="maj">maj</option>
                    <option value="min">min</option>
                    <option value="7">7</option>
                    <option value="sus4">sus4</option>
                    <option value="dim">dim</option>
                    <option value="aug">aug</option>
                  </select>
                </div>
                <div className="cell">
                  <button className="btn icon" disabled={!name} onClick={()=>{
                    const pc = nameToPc(name); const f = pcToBassFreq(pc)
                    const ctx = getCtx()
                    const o = ctx.createOscillator(); const g = ctx.createGain()
                    o.type='triangle'; o.frequency.value = f
                    g.gain.setValueAtTime(0, ctx.currentTime)
                    o.connect(g).connect(ctx.destination)
                    g.gain.linearRampToValueAtTime(0.9, ctx.currentTime+0.02)
                    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime+0.6)
                    o.start(); o.stop(ctx.currentTime+0.62)
                  }}>▶</button>
                </div>
              </div>
            )
          })}
        </div>

        {/* Seed 미리보기 */}
        <div className="seed">
          <div className="thin">입력된 루트</div>
          <div className="chips">
            {slots.map((s,i)=>(
              <span key={i} className={`chip ${s?.name ? '' : 'muted'}`}>{s?.name ?? '—'}</span>
            ))}
          </div>

          <div className="thin mt8">Seed 미리보기</div>
          <div className="chips">
            {seedPreview.length ? seedPreview.map((s,i)=><span key={i} className="chip">{s}</span>) : <span className="thin">입력 대기…</span>}
          </div>
        </div>
      </section>

      {/* 생성 패널 */}
      <section className="card">
        <div className="row wrap gap12">
          <div className="thin">장르 선택</div>
          <div className="seg">
            <label className={`seg-item ${genre==='rock'?'on':''}`}><input type="radio" name="g" value="rock" checked={genre==='rock'} onChange={()=>setGenre('rock')} />rock</label>
            <label className={`seg-item ${genre==='pop'?'on':''}`}><input type="radio" name="g" value="pop"  checked={genre==='pop'}  onChange={()=>setGenre('pop')}  />pop</label>
            <label className={`seg-item ${genre==='jazz'?'on':''}`}><input type="radio" name="g" value="jazz" checked={genre==='jazz'} onChange={()=>setGenre('jazz')} />jazz</label>
          </div>

          <label className="row gap6">
            템포(BPM)
            <input type="number" min={60} max={200} step={1} value={tempo} onChange={e=>setTempo(Number(e.target.value))} style={{ width: 80 }} />
          </label>

          <button className="btn primary" onClick={onPredict} disabled={loading}>
            {loading ? '생성 중…' : '코드진행 생성하기'}
          </button>

          <div className="req-preview thin">요청 바디: <code>{JSON.stringify({ genre: genre || '(선택 필요)', seed: seedPreview })}</code></div>
        </div>

        {error && <div className="warn mt8">오류: {error}</div>}

        {result && (
          <div className="mt12">
            {result.candidates.map((c, i) => {
              const job = jobs[i] || { status:'IDLE', progress:0 }
              const ready = job.status === 'DONE' && job.jobId
              return (
                <div className="cand card subtle" key={i}>
                  <div className="row between center">
                    <span className="badge">{c.label || (i===0 ? '정석 진행' : '대안 진행')}</span>
                    {typeof c.score === 'number' && (
                      <div className="progress">
                        <div className="bar" style={{ width: `${Math.round(c.score*100)}%` }} />
                      </div>
                    )}
                  </div>

                  <div className="chips mt8">
                    {c.progression.map((sym, j)=><span className="chip big" key={j}>{sym}</span>)}
                  </div>

                  <div className="row wrap gap8 mt10">
                    <button className="btn" onClick={()=>previewProgression(c.progression)}>▶ 미리듣기</button>

                    <button className="btn" onClick={()=>startGenerateFor(i, c.progression)} disabled={job.status==='RUNNING'}>
                      {job.status==='RUNNING' ? '트랙 생성 중…' : '트랙 생성 (MIDI/악보)'}
                    </button>

                    {job.status==='RUNNING' && <span className="thin">진행률 {job.progress}% …</span>}

                    {ready && (
                      <>
                        <a className="btn ghost" href={midiUrl(job.jobId!)} target="_blank" rel="noreferrer">⬇ MIDI</a>
                        <a className="btn ghost" href={xmlUrl(job.jobId!)}  target="_blank" rel="noreferrer">⬇ XML</a>
                        <button className="btn primary" onClick={()=>goPracticeMix(job.jobId!, c.progression)}>🎙 베이스 녹음하기</button>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}