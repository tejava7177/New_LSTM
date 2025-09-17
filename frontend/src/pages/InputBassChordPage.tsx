// src/pages/InputBassChordPage.tsx
import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import { generateTrack, getTrackStatus, midiUrl, xmlUrl } from '../lib/tracks'

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


/* ===== 진행 미리듣기/파서 유틸 ===== */
type PredictResult = {
  candidates: { progression: string[]; score?: number; label?: string }[];
};

const PC_MAP: Record<string, number> = {
  C:0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11
};
const parseSymbol = (sym: string) => {
  const m = sym.trim().match(/^([A-G](?:#|b)?)(.*)$/);
  return { root: m?.[1] ?? 'C', q: (m?.[2] ?? '').trim() }; // 예: C, Cm, C7, C5, Csus4...
};
const normalizeQuality = (q: string): Quality => {
  if (q === '' || q === 'maj') return 'maj';
  if (q === 'm') return 'min';
  const ok = new Set(['5','7','sus4','dim','aug','maj','min']);
  return (ok.has(q) ? (q as Quality) : 'maj');
};
// 간단 합성: 진행을 한 박자씩 재생
function previewProgression(symbols: string[], tempo=96) {
  const ctx = getCtx();
  const beat = 60/tempo;
  let t = ctx.currentTime + 0.05;

  const tonesByQ: Record<string, number[]> = {
    '': [0,4,7], maj:[0,4,7], m:[0,3,7], min:[0,3,7], '5':[0,7], '7':[0,4,7,10],
    sus4:[0,5,7], dim:[0,3,6], aug:[0,4,8]
  };

  symbols.forEach(sym => {
    const {root, q} = parseSymbol(sym);
    const pcs = (tonesByQ[q] ?? tonesByQ['']).map(i => (PC_MAP[root] + i) % 12);

    const master = ctx.createGain(); master.gain.value = 0; master.connect(ctx.destination);
    pcs.forEach((pc, idx) => {
      const f = idx===0 ? pcToBassFreq(pc) : pcToBassFreq(pc)*2;
      const o = ctx.createOscillator(); o.type = idx===0?'triangle':'sine';
      const eg = ctx.createGain(); eg.gain.setValueAtTime(0, t);
      eg.gain.linearRampToValueAtTime(idx===0?0.9:0.35, t+0.02);
      eg.gain.exponentialRampToValueAtTime(0.0001, t+beat*0.95);
      o.frequency.value = f; o.connect(eg).connect(master);
      o.start(t); o.stop(t+beat);
    });
    master.gain.linearRampToValueAtTime(1.0, t+0.01);
    master.gain.exponentialRampToValueAtTime(0.0001, t+beat);
    t += beat;
  });
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

  // --- 트랙 생성용 상태(공용) ---
  const [tempo, setTempo] = useState(100)
  const [genId, setGenId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [downReady, setDownReady] = useState(false)
  const [genErr, setGenErr] = useState('')

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

      // 트랙 생성 시작 + 상태 폴링
async function startGenerate(symbols: string[]) {
  try {
    setGenErr('')
    setDownReady(false)
    setProgress(0)

    const { jobId } = await generateTrack({
      genre: genre || 'rock',
      progression: symbols,
      tempo,
      options: {}, // 확장 포인트
    })
    setGenId(jobId)

    const timer = setInterval(async () => {
      try {
        const s = await getTrackStatus(jobId)
        setProgress(s.progress ?? 0)
        if (s.status === 'DONE') {
          clearInterval(timer)
          setDownReady(true)
        }
        if (s.status === 'ERROR') {
          clearInterval(timer)
          setGenErr('트랙 생성 중 오류가 발생했습니다.')
        }
      } catch (e: any) {
        clearInterval(timer)
        setGenErr(e.message ?? String(e))
      }
    }, 700)
  } catch (e: any) {
    setGenErr(e.message ?? String(e))
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
            <div style={{ fontWeight: 700, marginBottom: 8 }}>결과</div>

            {/* 카드 리스트 */}
            {((result as PredictResult).candidates || []).map((c, i) => (
              <div key={i}
                   style={{
                     border:'1px solid #e6e6e6', borderRadius:10, padding:12, marginBottom:10,
                     boxShadow:'0 1px 0 rgba(0,0,0,0.03)'
                   }}>
                {/* 상단 라벨/스코어 */}
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8}}>
                  <span style={{
                    fontSize:12, padding:'2px 8px', borderRadius:999,
                    background:'#eef5ff', color:'#2b6cb0'
                  }}>
                    {c.label || '추천 진행'}
                  </span>
                  {typeof c.score === 'number' && (
                    <div style={{display:'flex', alignItems:'center', gap:6, minWidth:160}}>
                      <div style={{height:6, background:'#eee', width:120, borderRadius:4, overflow:'hidden'}}>
                        <div style={{
                          width:`${Math.round(c.score*100)}%`, height:'100%',
                          background:'#2b6cb0'
                        }}/>
                      </div>
                      <span style={{fontSize:12, color:'#666'}}>{(c.score*100).toFixed(0)}%</span>
                    </div>
                  )}
                </div>

                {/* 진행 표시 */}
                <div style={{display:'flex', flexWrap:'wrap', gap:6, alignItems:'center'}}>
                  {c.progression.map((sym, j) => (
                    <span key={j} style={{display:'inline-flex', alignItems:'center', gap:6}}>
                      <span style={{
                        padding:'6px 10px', border:'1px solid #ddd', borderRadius:8,
                        background:'#fff', fontWeight:600
                      }}>{sym}</span>
                      {j < c.progression.length-1 && <span style={{color:'#999'}}>→</span>}
                    </span>
                  ))}
                </div>

                {/* 액션 버튼 */}
                <div style={{marginTop:10, display:'flex', gap:8}}>
                  <button onClick={() => previewProgression(c.progression)}>▶︎ 미리듣기</button>
                  <button
                    onClick={() => {
                      const roots: string[] = []
                      const qs: Quality[] = []
                      c.progression.slice(0, targetCount).forEach(sym => {
                        const {root, q} = parseSymbol(sym)
                        roots.push(root)
                        qs.push(normalizeQuality(q))
                      })
                      setSlots(roots.map(r => ({ name: r })))
                      setQualities(prev => {
                        const arr = [...prev]
                        for (let k = 0; k < targetCount; k++) arr[k] = qs[k] ?? 'maj'
                        return arr
                      })
                      setIdx(Math.min(c.progression.length, targetCount) - 1)
                      window.scrollTo({ top: 0, behavior: 'smooth' })
                    }}
                  >Seed로 적용</button>
                </div>
                 {/* === 트랙 생성 === */}
<div style={{marginTop:10, padding:10, borderTop:'1px dashed #ddd'}}>
  <div style={{display:'flex', alignItems:'center', gap:10, flexWrap:'wrap'}}>
    <label>템포(BPM):
      <input
        type="number" min={60} max={200} step={1}
        value={tempo}
        onChange={e=>setTempo(Number(e.target.value))}
        style={{marginLeft:6, width:70}}
      />
    </label>

    <button onClick={() => startGenerate(c.progression)} disabled={!!genId && !downReady}>
      {genId && !downReady ? '생성 중…' : '트랙 생성 (MIDI / 악보)'}
    </button>

    {genId && !downReady && (
      <span style={{fontSize:12, color:'#666'}}>진행률 {progress}% …</span>
    )}

    {downReady && genId && (
      <span style={{display:'inline-flex', gap:8}}>
        <a href={midiUrl(genId)} target="_blank" rel="noreferrer">⬇ MIDI 다운로드</a>
        <a href={xmlUrl(genId)}  target="_blank" rel="noreferrer">⬇ 악보(XML) 다운로드</a>
      </span>
    )}
  </div>
  {genErr && <div style={{color:'#c62828', marginTop:6}}>{genErr}</div>}
</div>
              </div>
            ))}

            {/* 원시 JSON 토글 (옵션) */}
            {/* <details style={{marginTop:8}}>
              <summary style={{cursor:'pointer'}}>원시 JSON 보기</summary>
              <pre style={{ background:'#f8f8f8', padding:8, borderRadius:6, overflowX:'auto' }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </details> */}
          </div>
        )}
      </div>
    </div>
  )
}
