import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import { generateTrack, getTrackStatus, midiUrl, xmlUrl, wavUrl } from '../lib/tracks'
import { useNavigate } from 'react-router-dom'

/* ===== 상수 / 타입 ===== */
const TARGET_COUNT = 3
const START_MAX_HZ = 150
const TRACK_MAX_HZ = 120
const LOCK_TIME_MS = 1200
const REARM_QUIET_MS = 350
const COOLDOWN_MS = 220

type Genre = 'rock' | 'jazz' | 'pop'
type Quality = '5' | 'maj' | 'min' | '7' | 'sus4' | 'dim' | 'aug'
type Slot = { name: string } | null

const GENRE_DEFAULT_QUALITY: Record<Genre, Quality> = {
  rock: '5', pop: 'maj', jazz: '7'
}

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
function playBass(freq: number, duration = 1.0) {
  const ctx = getCtx()
  const osc = ctx.createOscillator(), sub = ctx.createOscillator(), g = ctx.createGain()
  osc.type='triangle'; sub.type='sine'
  osc.frequency.value = freq; sub.frequency.value = freq/2
  g.gain.setValueAtTime(0, ctx.currentTime)
  osc.connect(g); sub.connect(g); g.connect(ctx.destination)
  const t0 = ctx.currentTime
  g.gain.linearRampToValueAtTime(0.95, t0+0.03)
  g.gain.exponentialRampToValueAtTime(0.0001, t0+duration)
  osc.start(); sub.start()
  osc.stop(t0+duration+0.02); sub.stop(t0+duration+0.02)
}

/* ===== 품질/파싱 유틸 ===== */
const PC_MAP: Record<string, number> = { C:0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11 }
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

/* ===== 페이지 ===== */
export default function InputBassChordPage() {
  const navigate = useNavigate()

  // 캡처
  const [deviceId, setDeviceId] = useState<string>('')
  const [preferFlat, setPreferFlat] = useState(false)
  const [majAsText, setMajAsText] = useState(false)
  const [slots, setSlots] = useState<Slot[]>(Array(TARGET_COUNT).fill(null))
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
  const [qualities, setQualities] = useState<Quality[]>(['maj','maj','maj'])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string>('')

  // 트랙 생성
  const [tempo, setTempo] = useState(100)
  const [genId, setGenId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [downReady, setDownReady] = useState(false)
  const [genErr, setGenErr] = useState('')

  /* ===== 캡처 루프 ===== */
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
      setQualities(q => { const nq = [...q]; nq[idx] = GENRE_DEFAULT_QUALITY[genre]; return nq })
    }

    const nextIdx = idx + 1
    if (nextIdx >= TARGET_COUNT) setMode('done')
    else { setIdx(nextIdx); setMode('idle') }

    cooldownUntilRef.current = performance.now() + COOLDOWN_MS
    setTimeout(() => { armedRef.current = true }, REARM_QUIET_MS)
    finalizingRef.current = false
  }

  function resetAll() {
    setSlots(Array(TARGET_COUNT).fill(null))
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
      for (let i = 0; i < TARGET_COUNT; i++) arr[i] = GENRE_DEFAULT_QUALITY[g]
      return arr
    })
  }

  function changeQuality(i: number, q: Quality) {
    setQualities(prev => {
      const arr = [...prev]; arr[i] = q; return arr
    })
  }

  function buildSeed(): string[] {
    const names = slots.slice(0, TARGET_COUNT).map(s => s?.name).filter(Boolean) as string[]
    const syms = names.map((root, i) => buildSymbol(root, (qualities[i] ?? 'maj'), { majAsText }))
    return syms
  }

  async function onPredict() {
    setError(''); setResult(null)
    if (!genre) { alert('장르를 선택하세요.'); return }
    const filled = slots.filter(Boolean).length
    if (filled < TARGET_COUNT) {
      const ok = confirm(`아직 ${TARGET_COUNT - filled}개 미입력입니다. 현재 ${filled}개로 진행할까요?`)
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

  async function startGenerate(symbols: string[]) {
    try {
      setGenErr(''); setDownReady(false); setProgress(0)
      const { jobId } = await generateTrack({
        genre: genre || 'rock',
        progression: symbols,
        tempo,
        options: { repeats: 6 },
      })
      setGenId(jobId)
      const timer = setInterval(async () => {
        try {
          const s = await getTrackStatus(jobId)
          setProgress(s.progress ?? 0)
          if (s.status === 'DONE') { clearInterval(timer); setDownReady(true) }
          if (s.status === 'ERROR') { clearInterval(timer); setGenErr('트랙 생성 중 오류가 발생했습니다.') }
        } catch (e: any) { clearInterval(timer); setGenErr(e.message ?? String(e)) }
      }, 700)
    } catch (e: any) { setGenErr(e.message ?? String(e)) }
  }

  // PracticeMix로 이동
  function goRecordWith(jobId: string, symbols: string[]) {
    if (!downReady) { alert('트랙이 아직 준비되지 않았습니다.'); return }
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
      {/* Hero */}
      <header className="ibc-hero">
        <div className="ibc-badge">STEP 1</div>
        <h1 className="ibc-title">코드 진행 &nbsp;<span>음원·악보 생성</span></h1>
        <p className="ibc-sub">🎸 <b>3개의 근음</b>을 순서대로 입력하세요 · 샤프/플랫, 메이저 표기를 선택할 수 있어요.</p>
      </header>

      {/* Top controls */}
      <div className="ibc-topbar card">
        <div className="row">
          <button className="btn subtle" onClick={async ()=>{ await navigator.mediaDevices.getUserMedia({ audio: true }) }}>
            🎤 마이크 권한
          </button>
          <DeviceSelect value={deviceId} onChange={setDeviceId} />
          <div className="spacer" />
          <div className="seg">
            <span className="seg-label">표기 방식</span>
            <button className={`chip ${!preferFlat?'active':''}`} onClick={()=>setPreferFlat(false)}># 샤프</button>
            <button className={`chip ${preferFlat?'active':''}`} onClick={()=>setPreferFlat(true)}>♭ 플랫</button>
          </div>
          <div className="seg">
            <span className="seg-label">메이저</span>
            <button className={`chip ${!majAsText?'active':''}`} onClick={()=>setMajAsText(false)}>C</button>
            <button className={`chip ${majAsText?'active':''}`} onClick={()=>setMajAsText(true)}>Cmaj</button>
          </div>
          <button className="btn" onClick={resetAll}>리셋</button>
        </div>
      </div>

      {/* Slots */}
      <section className="grid3">
        {Array.from({ length: TARGET_COUNT }).map((_, i) => {
          const name = slots[i]?.name ?? ''
          return (
            <div key={i} className={`slot card ${i===idx && mode!=='done' ? 'focus' : ''}`}>
              <div className="slot-head">
                <div className="slot-index">{i+1}</div>
                <div className="slot-note">{name || (i===idx && mode!=='done' ? '↙ 이 슬롯에 입력' : '—')}</div>
                <button
                  className="icon"
                  title="미리듣기"
                  disabled={!name}
                  onClick={() => { const pc = nameToPc(name); playBass(pcToBassFreq(pc)) }}
                >▶︎</button>
              </div>

              <div className="slot-qlty">
                {(['5','maj','min','7','sus4','dim','aug'] as Quality[]).map(q => (
                  <button
                    key={q}
                    className={`chip ${q===(qualities[i]??'maj') ? 'active':''}`}
                    onClick={()=>changeQuality(i, q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </section>

      {/* Seed preview */}
      <div className="seed card">
        <div className="row">
          <div><b>입력된 루트</b>: {filled===0?'—':slots.slice(0,TARGET_COUNT).map(s=>s?.name??'—').join('  ')}</div>
          <div className="spacer" />
          <div><b>Seed</b>: {seedPreview.length? seedPreview.join(' , ') : '—'}</div>
        </div>
      </div>

      {/* Genre & Generate */}
      <section className="card">
        <div className="row wrap">
          <div className="seg">
            <span className="seg-label">장르 선택</span>
            <button className={`chip ${genre==='rock'?'active':''}`} onClick={()=>applyGenrePreset('rock')}>🎸 rock</button>
            <button className={`chip ${genre==='pop'?'active':''}`}  onClick={()=>applyGenrePreset('pop')}>🎧 pop</button>
            <button className={`chip ${genre==='jazz'?'active':''}`} onClick={()=>applyGenrePreset('jazz')}>🎷 jazz</button>
          </div>

          <div className="spacer" />
          <label className="tempo">
            템포(BPM)
            <input type="number" min={60} max={200} step={1}
                   value={tempo} onChange={e=>setTempo(Number(e.target.value))}/>
          </label>

          <button className="btn primary" onClick={onPredict} disabled={loading}>
            {loading ? '생성 중…' : '코드진행 생성하기'}
          </button>
        </div>

        <div className="hint mt8">요청 바디: <code>{JSON.stringify({ genre: genre || '(선택 필요)', seed: seedPreview })}</code></div>
        {error && <div className="warn mt8">오류: {error}</div>}
      </section>

      {/* Results */}
      {result && (
        <section className="results">
          <div className="sec-title">결과</div>
          {((result.candidates || []) as Array<{progression:string[]; score?:number; label?:string}>).map((c, i) => (
            <div key={i} className="res card">
              <div className="row between">
                <span className="pill">{c.label || '추천 진행'}</span>
                {typeof c.score === 'number' && (
                  <div className="meter">
                    <div className="bar" style={{width:`${Math.round(c.score*100)}%`}} />
                    <span>{(c.score*100).toFixed(0)}%</span>
                  </div>
                )}
              </div>

              <div className="prog">
                {c.progression.map((sym, j) => (
                  <span key={j} className="chord">
                    {sym}{j < c.progression.length-1 && <span className="arrow">→</span>}
                  </span>
                ))}
              </div>

              <div className="row wrap gap8 mt8">
                <button className="btn" onClick={()=>{
                  // 간단 미리듣기
                  const ctx = getCtx(); const beat = 60/96; let t=ctx.currentTime+0.05
                  const tones: Record<string, number[]> = {
                    '': [0,4,7], maj:[0,4,7], m:[0,3,7], min:[0,3,7], '5':[0,7], '7':[0,4,7,10], sus4:[0,5,7], dim:[0,3,6], aug:[0,4,8]
                  }
                  c.progression.forEach(sym=>{
                    const {root,q}=parseSymbol(sym); const pcs=(tones[q]??tones['']).map(i=>(PC_MAP[root]+i)%12)
                    const master=ctx.createGain(); master.gain.value=0; master.connect(ctx.destination)
                    pcs.forEach((pc, k)=>{ const f=k===0?pcToBassFreq(pc):pcToBassFreq(pc)*2
                      const o=ctx.createOscillator(); o.type=k===0?'triangle':'sine'
                      const g=ctx.createGain(); g.gain.setValueAtTime(0,t)
                      g.gain.linearRampToValueAtTime(k===0?0.9:0.35,t+0.02); g.gain.exponentialRampToValueAtTime(0.0001,t+beat*0.95)
                      o.frequency.value=f; o.connect(g).connect(master); o.start(t); o.stop(t+beat)
                    })
                    master.gain.linearRampToValueAtTime(1.0,t+0.01); master.gain.exponentialRampToValueAtTime(0.0001,t+beat); t+=beat
                  })
                }}>▶︎ 미리듣기</button>

                <button className="btn" onClick={()=>{
                  // Seed 적용
                  const roots: string[] = []; const qs: Quality[] = []
                  c.progression.slice(0, TARGET_COUNT).forEach(sym=>{
                    const {root,q}=parseSymbol(sym); roots.push(root); qs.push(normalizeQuality(q))
                  })
                  setSlots(roots.map(r=>({name:r})))
                  setQualities(prev=>{ const arr=[...prev]; for(let k=0;k<TARGET_COUNT;k++) arr[k]=qs[k]??'maj'; return arr })
                  setIdx(Math.min(c.progression.length, TARGET_COUNT)-1)
                  window.scrollTo({top:0,behavior:'smooth'})
                }}>Seed로 적용</button>

                <button className="btn" onClick={() => startGenerate(c.progression)} disabled={!!genId && !downReady}>
                  {genId && !downReady ? '생성 중…' : '트랙 생성 (MIDI / 악보)'}
                </button>

                {genId && !downReady && <span className="hint">진행률 {progress}% …</span>}

                {downReady && genId && (
                  <>
                    <a className="btn link" href={midiUrl(genId)} target="_blank" rel="noreferrer">⬇ MIDI</a>
                    <a className="btn link" href={xmlUrl(genId)} target="_blank" rel="noreferrer">⬇ XML</a>
                    <button className="btn primary" onClick={() => goRecordWith(genId!, c.progression)}>🎙 베이스 녹음하기</button>
                  </>
                )}
              </div>

              {genErr && <div className="warn mt8">{genErr}</div>}
            </div>
          ))}
        </section>
      )}

      {/* 페이지 하단 여백 */}
      <div style={{height:24}} />
    </div>
  )
}