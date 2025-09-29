import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import { generateTrack, getTrackStatus, midiUrl, xmlUrl, wavUrl as jobWavUrl } from '../lib/tracks'
import { renderMidiOnServer } from '../lib/midiServer'
import { ensureWavForJob } from '../lib/midiServer';


/* ─────────────────────────────
   설정/상수
────────────────────────────── */
const DEFAULT_CAPTURE_COUNT = 3
const START_MAX_HZ = 150
const TRACK_MAX_HZ = 120
const LOCK_TIME_MS = 1200
const REARM_QUIET_MS = 350
const COOLDOWN_MS = 220

/* ─────────────────────────────
   음이름/주파수 유틸
────────────────────────────── */
const NAMES_SHARP = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'] as const
const NAMES_FLAT  = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'] as const
const log2 = (x:number)=>Math.log(x)/Math.LN2

function freqToNearest(freq:number){
  const midi = Math.round(69 + 12 * log2(freq/440))
  const pc = (midi%12+12)%12
  const nameSharp = NAMES_SHARP[pc]
  const nameFlat  = NAMES_FLAT[pc]
  const snappedFreq = 440 * Math.pow(2,(midi-69)/12)
  return { pc, nameSharp, nameFlat, snappedFreq }
}
const BASS_RANGE_MIN=40, BASS_RANGE_MAX=110
function pcOctToFreq(pc:number, octave:number){
  const midi = 12 + pc + 12*octave
  return 440 * Math.pow(2,(midi-69)/12)
}
function pcToBassFreq(pc:number){
  const cands=[1,2,3].map(o=>({o,f:pcOctToFreq(pc,o)}))
  let f=cands.reduce((a,b)=>Math.abs(a.f-75)<Math.abs(b.f-75)?a:b).f
  while(f>BASS_RANGE_MAX) f/=2
  while(f<BASS_RANGE_MIN) f*=2
  return f
}
function nameToPc(name:string){
  const i1=NAMES_SHARP.indexOf(name as any); if(i1>=0) return i1
  const i2=NAMES_FLAT.indexOf(name as any);  if(i2>=0) return i2
  return 0
}

/* ─────────────────────────────
   가벼운 톤 미리듣기
────────────────────────────── */
let sharedCtx: AudioContext | null = null
function getCtx(){ return sharedCtx ?? (sharedCtx=new AudioContext()) }
function playBass(freq:number, duration=1.2){
  const ctx=getCtx()
  const osc=ctx.createOscillator(), sub=ctx.createOscillator(), g=ctx.createGain()
  osc.type='triangle'; sub.type='sine'
  osc.frequency.value=freq; sub.frequency.value=freq/2
  g.gain.setValueAtTime(0,ctx.currentTime)
  osc.connect(g); sub.connect(g); g.connect(ctx.destination)
  const t0=ctx.currentTime
  g.gain.linearRampToValueAtTime(0.9,t0+0.02)
  g.gain.exponentialRampToValueAtTime(0.2,t0+duration*0.5)
  g.gain.exponentialRampToValueAtTime(0.0001,t0+duration)
  osc.start(); sub.start()
  osc.stop(t0+duration+0.02); sub.stop(t0+duration+0.02)
}



/* ─────────────────────────────
   코드/장르 타입 & 유틸
────────────────────────────── */
type Genre = 'rock'|'pop'|'jazz'
type Quality = '5'|'maj'|'min'|'7'|'sus4'|'dim'|'aug'
type Slot = { name:string } | null

const GENRE_DEFAULT_QUALITY: Record<Genre, Quality> = {
  rock:'5', pop:'maj', jazz:'7'
}
function buildSymbol(root:string, q:Quality, opts?:{majAsText?:boolean}){
  const majAsText=!!opts?.majAsText
  switch(q){
    case '5': return `${root}5`
    case 'maj': return majAsText?`${root}maj`:`${root}`
    case 'min': return `${root}m`
    case '7': return `${root}7`
    case 'sus4': return `${root}sus4`
    case 'dim': return `${root}dim`
    case 'aug': return `${root}aug`
  }
}
const PC_MAP: Record<string, number> = {
  C:0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11
}
const parseSymbol=(s:string)=>{
  const m=s.trim().match(/^([A-G](?:#|b)?)(.*)$/)
  return {root:m?.[1]??'C', q:(m?.[2]??'').trim()}
}
const normalizeQuality=(q:string):Quality=>{
  if(q===''||q==='maj') return 'maj'
  if(q==='m') return 'min'
  const ok=new Set(['5','7','sus4','dim','aug','maj','min'])
  return (ok.has(q)?(q as Quality):'maj')
}
function previewProgression(symbols:string[], tempo=96){
  const ctx=getCtx(); const beat=60/tempo; let t=ctx.currentTime+0.05
  const tonesByQ: Record<string, number[]> = {
    '':[0,4,7], maj:[0,4,7], m:[0,3,7], min:[0,3,7], '5':[0,7], '7':[0,4,7,10],
    sus4:[0,5,7], dim:[0,3,6], aug:[0,4,8]
  }
  symbols.forEach(sym=>{
    const {root,q}=parseSymbol(sym)
    const pcs=(tonesByQ[q]??tonesByQ['']).map(i=>(PC_MAP[root]+i)%12)
    const master=ctx.createGain(); master.gain.value=0; master.connect(ctx.destination)
    pcs.forEach((pc,idx)=>{
      const f=idx===0?pcToBassFreq(pc):pcToBassFreq(pc)*2
      const o=ctx.createOscillator(); o.type=idx===0?'triangle':'sine'
      const eg=ctx.createGain(); eg.gain.setValueAtTime(0,t)
      eg.gain.linearRampToValueAtTime(idx===0?0.9:0.35,t+0.02)
      eg.gain.exponentialRampToValueAtTime(0.0001,t+beat*0.95)
      o.frequency.value=f; o.connect(eg).connect(master); o.start(t); o.stop(t+beat)
    })
    master.gain.linearRampToValueAtTime(1.0,t+0.01)
    master.gain.exponentialRampToValueAtTime(0.0001,t+beat)
    t+=beat
  })
}

/* ─────────────────────────────
   API 응답 타입
────────────────────────────── */
type PredictResult = { candidates: { progression:string[]; score?:number; label?:string }[] }

/* ─────────────────────────────
   WAV 준비 헬퍼 (직접 → 폴백 렌더)
────────────────────────────── */
async function prepareWavForJob(jobId:string):Promise<string>{
  // 1) 트랙 API에서 바로 시도
  const direct = jobWavUrl(jobId)
  try{
    const r = await fetch(direct, { method:'GET', cache:'no-store' })
    if(r.ok) return direct
  }catch{/* 폴백으로 진행 */}

  // 2) 폴백: MIDI 다운로드 → 렌더 API
  const midRes = await fetch(midiUrl(jobId), { cache:'no-store' })
  if(!midRes.ok) throw new Error(`MIDI fetch failed (HTTP ${midRes.status})`)
  const blob = await midRes.blob()
  const file = new File([blob], `${jobId}.mid`, { type:'audio/midi' })
  const { wavUrl } = await renderMidiOnServer(file)
  if(!wavUrl) throw new Error('render API did not return wavUrl')
  return wavUrl
}

/* ─────────────────────────────
   페이지 컴포넌트
────────────────────────────── */
export default function InputBassChordPage(){
  const navigate = useNavigate()

  // 캡처 상태
  const [deviceId, setDeviceId] = useState<string>('')
  const [preferFlat, setPreferFlat] = useState(false)
  const [majAsText, setMajAsText] = useState(false)

  const targetCount = DEFAULT_CAPTURE_COUNT
  const [slots, setSlots] = useState<Slot[]>(Array(targetCount).fill(null))
  type Mode = 'idle'|'tracking'|'done'
  const [mode, setMode] = useState<Mode>('idle')
  const [idx, setIdx] = useState(0)

  const minHzRef = useRef<number|null>(null)
  const startMsRef = useRef<number>(0)
  const lastPitchMsRef = useRef<number>(0)
  const armedRef = useRef(true)
  const cooldownUntilRef = useRef(0)
  const finalizingRef = useRef(false)

  const pitch = usePitch(deviceId || undefined, { fftSize: 8192, minVolumeRms: 0.02 })

  // 코드 생성 상태
  const [genre, setGenre] = useState<Genre|''>('')
  const [qualities, setQualities] = useState<Quality[]>(['maj','maj','maj'])
  const [tempo, setTempo] = useState(100)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PredictResult | null>(null)
  const [error, setError] = useState('')

  // 트랙 생성/다운로드 상태
  const [genId, setGenId] = useState<string|null>(null)
  const [progress, setProgress] = useState(0)
  const [downReady, setDownReady] = useState(false)
  const [genErr, setGenErr] = useState('')
  const [busyToRecord, setBusyToRecord] = useState(false)

  /* ── 캡처 루프 ───────────────── */
  useEffect(()=>{
    const now=performance.now()
    if(pitch!=null){
      lastPitchMsRef.current=now
      if(mode==='idle'){
        if(armedRef.current && now>=cooldownUntilRef.current && pitch<START_MAX_HZ){
          setMode('tracking'); startMsRef.current=now; minHzRef.current=pitch; armedRef.current=false
        }
        return
      }
      if(mode==='tracking'){
        if(pitch<TRACK_MAX_HZ){
          if(minHzRef.current==null || pitch<minHzRef.current) minHzRef.current=pitch
        }
        const elapsed=now-startMsRef.current
        if(pitch>START_MAX_HZ || elapsed>=LOCK_TIME_MS){ finalizeCapture() }
        return
      }
      return
    }
    // 무음 → 재장전
    const t=setTimeout(()=>{
      if(performance.now()-lastPitchMsRef.current>=REARM_QUIET_MS){ armedRef.current=true }
    }, REARM_QUIET_MS)
    return ()=>clearTimeout(t)
  },[pitch,mode])

  function finalizeCapture(){
    if(finalizingRef.current) return
    finalizingRef.current=true
    const minHz=minHzRef.current; minHzRef.current=null

    if(minHz==null){
      setMode('idle'); cooldownUntilRef.current=performance.now()+COOLDOWN_MS
      setTimeout(()=>{armedRef.current=true}, REARM_QUIET_MS)
      finalizingRef.current=false; return
    }
    const {nameSharp,nameFlat}=freqToNearest(minHz)
    const name=(preferFlat?nameFlat:nameSharp)
    const next=[...slots]; next[idx]={name}; setSlots(next)

    const nextIdx=idx+1
    if(nextIdx>=targetCount) setMode('done')
    else { setIdx(nextIdx); setMode('idle') }

    cooldownUntilRef.current=performance.now()+COOLDOWN_MS
    setTimeout(()=>{armedRef.current=true}, REARM_QUIET_MS)
    finalizingRef.current=false
  }

  function resetAll(){
    setSlots(Array(targetCount).fill(null))
    setIdx(0); setMode('idle')
    minHzRef.current=null; armedRef.current=true; cooldownUntilRef.current=0
    setResult(null); setError(''); setGenErr('')
    setGenId(null); setDownReady(false); setProgress(0)
  }

  function applyGenrePreset(g:Genre){
    setGenre(g)
    setQualities(['maj','maj','maj'].map(()=>GENRE_DEFAULT_QUALITY[g]))
  }
  function changeQuality(i:number,q:Quality){
    const arr=[...qualities]; arr[i]=q; setQualities(arr)
  }

  function buildSeed():string[]{
    const names=slots.slice(0,targetCount).map(s=>s?.name).filter(Boolean) as string[]
    return names.map((root,i)=>buildSymbol(root,(qualities[i]??'maj'),{majAsText}) as string)
  }

  async function onPredict(){
    setError(''); setResult(null)
    if(!genre){ alert('장르를 선택하세요.'); return }
    const filled=slots.filter(Boolean).length
    if(filled<targetCount){
      const ok=confirm(`아직 ${targetCount-filled}개 미입력입니다. 현재 ${filled}개로 진행할까요?`)
      if(!ok) return
    }
    setLoading(true)
    try{
      const res=await fetch('/api/chords/predict',{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ genre, seed: buildSeed() })
      })
      if(!res.ok) throw new Error(`HTTP ${res.status}`)
      const json=await res.json()
      setResult(json)
    }catch(e:any){ setError(e?.message??String(e)) }
    finally{ setLoading(false) }
  }

  /* ── 트랙 생성/폴링 ─────────── */
  async function startGenerate(symbols:string[]){
    try{
      setGenErr(''); setDownReady(false); setProgress(0)
      const { jobId } = await generateTrack({
        genre: genre || 'rock',
        progression: symbols,
        tempo,
        options: { repeats: 6 }
      })
      setGenId(jobId)

      const timer=setInterval(async ()=>{
        try{
          const s=await getTrackStatus(jobId)
          setProgress(s.progress ?? 0)
          if(s.status==='DONE'){ clearInterval(timer); setDownReady(true) }
          if(s.status==='ERROR'){ clearInterval(timer); setGenErr('트랙 생성 중 오류가 발생했습니다.') }
        }catch(e:any){ clearInterval(timer); setGenErr(e?.message??String(e)) }
      }, 700)
    }catch(e:any){ setGenErr(e?.message??String(e)) }
  }

  /* ── 녹음 페이지 이동(필수: WAV 보장) ─ */
  async function goRecordWith(jobId: string, progression: string[], tempo: number) {
    // 1) 백킹 WAV 보장(기존에 있으면 HEAD만, 없으면 서버에서 렌더)
    const backingWav = await ensureWavForJob(jobId).catch(() => null);
    if (!backingWav) {
      alert('백킹 트랙(WAV) 준비에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      return;
    }

    // 2) 녹음 페이지로 이동(상태에 필요한 정보 전달)
    navigate('/practice-mix', {
      state: {
        source: 'predict',
        jobId,
        tempo,
        progression,
        wavUrl: backingWav,
        midiUrl: midiUrl(jobId),
        preRollBeats: 4,
        barsPerChord: 1,
      }
    });
  }

  const filled = slots.filter(Boolean).length

  /* ─────────────────────────────
     UI
  ────────────────────────────── */
  return (
  <div className="ibc-wrap">
    {/* Hero */}
    <div className="ibc-hero">
      <span className="ibc-badge">Bass Assistant</span>
      <h2 className="ibc-title">
        <span>코드 진행 & 음원, 악보 생성</span>
      </h2>
      <div className="ibc-sub">3개의 근음을 차례대로 입력하세요.</div>
    </div>

    {/* 상단 도구 막대 */}
    <div className="ibc-topbar row wrap gap8">
      <DeviceSelect value={deviceId} onChange={setDeviceId} />

      {/* 메이저 표기 */}
      <div className="seg">
        <span className="seg-label">메이저 표기</span>
        <div className="seg">
          <label className={`chip ${!majAsText ? 'active' : ''}`}>
            <input
              type="radio"
              checked={!majAsText}
              onChange={() => setMajAsText(false)}
            />
            C
          </label>
          <label className={`chip ${majAsText ? 'active' : ''}`}>
            <input
              type="radio"
              checked={majAsText}
              onChange={() => setMajAsText(true)}
            />
            Cmaj
          </label>
        </div>
      </div>

      {/* 표기 방식 */}
      <div className="seg">
        <span className="seg-label">표기 방식</span>
        <div className="seg">
          <label className={`chip ${!preferFlat ? 'active' : ''}`}>
            <input
              type="radio"
              checked={!preferFlat}
              onChange={() => setPreferFlat(false)}
            />
            #(샤프)
          </label>
          <label className={`chip ${preferFlat ? 'active' : ''}`}>
            <input
              type="radio"
              checked={preferFlat}
              onChange={() => setPreferFlat(true)}
            />
            ♭(플랫)
          </label>
        </div>
      </div>

      <button className="btn ml-auto" onClick={resetAll}>리셋</button>
    </div>

    {/* 입력 슬롯/품질 선택 (그리드) */}
    <div className="card">
      <div className="ibc-grid">
        <div className="grid-head cell">#</div>
        <div className="grid-head cell">입력 음</div>
        <div className="grid-head cell">Chord Quality</div>
        <div className="grid-head cell">미리듣기</div>

        {Array.from({ length: targetCount }).map((_, i) => {
          const name = slots[i]?.name ?? ''
          return (
            <div className="grid-row" key={i}>
              <div className="cell">{i + 1}</div>
              <div className={`cell ${i === idx && mode !== 'done' ? 'bold' : ''}`}>
                {name || (i === idx && mode !== 'done' ? '↙ 이 슬롯에 입력' : '—')}
              </div>
              <div className="cell">
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
              </div>
              <div className="cell">
                <button
                  className="btn icon"
                  disabled={!name}
                  onClick={() => { const pc = nameToPc(name); playBass(pcToBassFreq(pc)) }}
                >▶︎</button>
              </div>
            </div>
          )
        })}
      </div>

      {/* 입력 요약 */}
      <div className="seed">
        <div><strong>입력된 루트:</strong> {filled === 0 ? '—' : slots.map(s => s?.name ?? '—').join(' ')}</div>
        <div className="mt8"><strong>Seed 미리보기:</strong> {buildSeed().join(' , ')}</div>
      </div>
    </div>

    {/* 생성 컨트롤 */}
    <div className="card">
      <div className="row wrap gap8">
        <div className="seg">
          <span className="seg-label">장르</span>
          <div className="seg">
            <label className={`chip ${genre === 'rock' ? 'active' : ''}`}>
              <input type="radio" checked={genre === 'rock'} onChange={() => applyGenrePreset('rock')} /> rock
            </label>
            <label className={`chip ${genre === 'pop' ? 'active' : ''}`}>
              <input type="radio" checked={genre === 'pop'} onChange={() => applyGenrePreset('pop')} /> pop
            </label>
            <label className={`chip ${genre === 'jazz' ? 'active' : ''}`}>
              <input type="radio" checked={genre === 'jazz'} onChange={() => applyGenrePreset('jazz')} /> jazz
            </label>
          </div>
        </div>

        <div className="row gap8">
          <button className="btn" onClick={onPredict} disabled={loading}>
            {loading ? '생성 중…' : '코드진행 생성하기'}
          </button>
          <label className="row gap8">
            템포(BPM)
            <input
              type="number" min={60} max={200} step={1}
              value={tempo}
              onChange={e => setTempo(Number(e.target.value))}
              className="tempo"
            />
          </label>
        </div>
      </div>

      <div className="thin mt8">
        요청 바디: <code>{JSON.stringify({ genre: genre || '(선택 필요)', seed: buildSeed() })}</code>
      </div>

      {error && <div className="warn mt8">오류: {error}</div>}
    </div>

    {/* 결과 카드들 */}
    {result && (
      <div className="results">
        <div className="sec-title">결과</div>
        {result.candidates.map((c, i) => (
          <div className="card res" key={i}>
            {/* 라벨/스코어 */}
            <div className="row between">
              <span className="pill">{c.label || (i === 0 ? '정석 진행' : `대안 진행 ${i}`)}</span>
              {typeof c.score === 'number' && (
                <div className="row gap8">
                  <div className="meter">
                    <div className="bar" style={{ width: `${Math.round(c.score * 100)}%` }} />
                  </div>
                  <span className="thin">{(c.score * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>

            {/* 진행 표시 */}
            <div className="prog">
              {c.progression.map((sym, j) => (
                <span key={j} className="row gap6">
                  <span className="chord">{sym}</span>
                  {j < c.progression.length - 1 && <span className="arrow">→</span>}
                </span>
              ))}
            </div>

            {/* 액션: 미리듣기 / Seed로 적용 / 트랙 생성 / 진행률 / 다운로드 / 베이스 녹음하기 */}
            <div className="row wrap gap8 mt8">
              <button className="btn" onClick={() => previewProgression(c.progression)}>▶︎ 미리듣기</button>

              <button className="btn" onClick={() => {
                const roots: string[] = []; const qs: Quality[] = []
                c.progression.slice(0, targetCount).forEach(sym => {
                  const { root, q } = parseSymbol(sym); roots.push(root); qs.push(normalizeQuality(q))
                })
                setSlots(roots.map(r => ({ name: r })))
                setQualities(prev => {
                  const arr = [...prev]
                  for (let k = 0; k < targetCount; k++) arr[k] = qs[k] ?? 'maj'
                  return arr
                })
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}>Seed로 적용</button>

              <button className="btn" onClick={() => startGenerate(c.progression)} disabled={!!genId && !downReady}>
                {genId && !downReady ? '생성 중…' : '트랙 생성 (MIDI / 악보)'}
              </button>

              {genId && !downReady && (
                <span className="thin">진행률 {progress}% …</span>
              )}

              {downReady && genId && (
                <>
                  <span className="row gap8">
                    <a className="btn ghost" href={midiUrl(genId)} target="_blank" rel="noreferrer">⬇ MIDI</a>
                    <a className="btn ghost" href={xmlUrl(genId)}  target="_blank" rel="noreferrer">⬇ XML</a>
                  </span>
                  <button
                    className="btn primary"
                    onClick={() => goRecordWith(genId!, c.progression, tempo)}
                    disabled={busyToRecord}
                    title="PracticeMix로 넘어가서 바로 녹음하기"
                  >
                    {busyToRecord ? '준비 중…' : '🎙 베이스 녹음하기'}
                  </button>
                </>
              )}
            </div>

            {genErr && <div className="warn mt8">{genErr}</div>}
          </div>
        ))}
      </div>
    )}
  </div>
)
}