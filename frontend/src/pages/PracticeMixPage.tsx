import React, { useEffect, useMemo, useRef, useState } from 'react'
// import Accordion from '../components/Accordion';  // 미사용: 제거
import { useLocation } from 'react-router-dom'

// existing components/hooks from your app
import DeviceSelect from '../components/DeviceSelect'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { audioBufferToWavBlob } from '../utils/wav'
import { mixBuffersToAudioBuffer } from '../lib/mixdown'
import { extractChordCuesFromMidi, getNowNextChord, ChordCue } from '../lib/midiCues'

// new, refactored modules
import { useAmp } from '../features/amp/useAmp'
import { AmpScope } from '../features/amp/AmpScope'
import { DialKnob } from '../components/DialKnob'
import { useMidiSource } from '../features/midi/useMidiSource'
import { useChordTimeline } from '../features/timeline/useChordTimeline'
import { useCountIn } from '../hooks/useCountIn'

type TrackMeta = { name: string; channel?: number; instrument?: string; notes: number }
type NavState = {
  source?: 'predict' | 'manual';
  jobId?: string;
  progression?: string[];
  tempo?: number;
  timeSig?: [number, number];
  preRollBeats?: number;
  barsPerChord?: number;
  midiUrl?: string; // optional override
  wavUrl?: string;  // optional override
}

// === Inline Scrolling Waveform Visualizer (replaces index_record.html's "파형-스크롤") ===
type WaveScrollMode = "amp" | "raw";
function RecordingWaveScroll({
  active,
  mode,
  deviceId,
  ampAnalyser,
  height = 160,
  className,
}: {
  active: boolean;
  mode: WaveScrollMode;
  deviceId?: string;
  ampAnalyser?: AnalyserNode | null;
  height?: number;
  className?: string;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const rafRef = React.useRef<number | null>(null);

  // raw mode resources
  const [ctx, setCtx] = React.useState<AudioContext | null>(null);
  const srcRef = React.useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = React.useRef<AnalyserNode | null>(null);
  const rawStreamRef = React.useRef<MediaStream | null>(null);

  const setupCanvas = () => {
    const cv = canvasRef.current;
    if (!cv) return;
    const dpr = Math.max(1, (window.devicePixelRatio || 1));
    const W = Math.floor(cv.clientWidth * dpr);
    const H = Math.floor(height * dpr);
    if (cv.width !== W || cv.height !== H) {
      cv.width = W; cv.height = H;
    }
    const g = cv.getContext("2d");
    if (g) {
      g.fillStyle = "#0b1220";
      g.fillRect(0, 0, cv.width, cv.height);
    }
  };

  async function openRawAnalyser() {
    if (ctx || analyserRef.current) return;
    const Ctx: typeof AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext;
    const c = new Ctx();
    setCtx(c);
    const constraints: MediaStreamConstraints =
      deviceId ? { audio: { deviceId: { exact: deviceId } as any } } : { audio: true };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    rawStreamRef.current = stream;

    const src = c.createMediaStreamSource(stream);
    srcRef.current = src;

    const an = c.createAnalyser();
    an.fftSize = 2048;
    an.smoothingTimeConstant = 0.12;
    src.connect(an);
    analyserRef.current = an;
  }

  function closeRawAnalyser() {
    try { srcRef.current?.disconnect(); } catch {}
    analyserRef.current = null;
    srcRef.current = null;
    if (rawStreamRef.current) {
      rawStreamRef.current.getTracks().forEach(t => t.stop());
      rawStreamRef.current = null;
    }
    if (ctx) {
      try { ctx.close(); } catch {}
      setCtx(null);
    }
  }

  const draw = () => {
    const cv = canvasRef.current; if (!cv) return;
    const g = cv.getContext("2d"); if (!g) return;

    const an = mode === "amp" ? (ampAnalyser || null) : (analyserRef.current || null);
    if (!an) {
      g.fillStyle = "#0b1220";
      g.fillRect(0, 0, cv.width, cv.height);
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    // scroll left by 1px
    g.drawImage(cv, -1, 0);
    // clear the rightmost column
    g.fillStyle = "#0b1220";
    g.fillRect(cv.width - 1, 0, 1, cv.height);

    const buf = new Float32Array(an.fftSize);
    an.getFloatTimeDomainData(buf);

    const step = 8;
    let min = 1, max = -1;
    for (let i = 0; i < buf.length; i += step) {
      let lmin = 1, lmax = -1;
      for (let k = 0; k < step && i + k < buf.length; k++) {
        const v = buf[i + k];
        if (v < lmin) lmin = v;
        if (v > lmax) lmax = v;
      }
      if (lmin < min) min = lmin;
      if (lmax > max) max = lmax;
    }
    const mid = Math.floor(cv.height / 2);
    const y1 = mid + Math.floor(min * (cv.height * 0.44));
    const y2 = mid + Math.floor(max * (cv.height * 0.44));

    const grad = g.createLinearGradient(cv.width - 1, 0, cv.width - 1, cv.height);
    grad.addColorStop(0, "#60a5fa");
    grad.addColorStop(1, "#a78bfa");
    g.strokeStyle = grad;

    g.beginPath();
    g.moveTo(cv.width - 1 + 0.5, y1 + 0.5);
    g.lineTo(cv.width - 1 + 0.5, y2 + 0.5);
    g.stroke();

    rafRef.current = requestAnimationFrame(draw);
  };

  React.useEffect(() => {
    setupCanvas();

    if (!active) {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      if (mode === "raw") closeRawAnalyser();
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        if (mode === "raw") {
          await openRawAnalyser();
        } else {
          if (!ampAnalyser) return;
        }
        if (!cancelled) {
          if (rafRef.current) cancelAnimationFrame(rafRef.current);
          rafRef.current = requestAnimationFrame(draw);
        }
      } catch {}
    })();

    return () => {
      cancelled = true;
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      if (mode === "raw") closeRawAnalyser();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, mode, deviceId, ampAnalyser]);

  React.useEffect(() => {
    const onResize = () => setupCanvas();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div className={className} style={{ background: "#0b1220", border: "1px dashed #1f2937", borderRadius: 12, padding: 8 }}>
      <canvas ref={canvasRef} style={{ width: "100%", height, display: "block" }} />
    </div>
  );
}
// === End Inline Visualizer ===

export default function PracticeMixPage() {
  /* ===== 라우터 state ===== */
  const { state } = useLocation()
  const navState = (state as NavState) || {}

  /* ===== 입력 & 녹음 ===== */
  const [deviceId, setDeviceId] = useState<string>('')
  const { recording, blobUrl, start, stop, error: recErr } = useMediaRecorder(deviceId || undefined)

  /* ===== MIDI 소스 (파일 업로드 또는 jobId 전달) ===== */
  const {
    midiFile, setMidiFile,
    midiAudioUrl, midiBuffer,
    midiTracks, tempoBpm, timeSig,
    cuesFromMidi, setTempoBpm, setTimeSig,
    handleMidiFile, bootstrapFromJob
  } = useMidiSource(navState)

  useEffect(() => {
    if (navState.jobId) { bootstrapFromJob(navState.jobId).catch(console.error) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navState.jobId])

  /* ===== 코드 큐 ===== */
  const [chordCues, setChordCues] = useState<ChordCue[]>([])
  useEffect(() => {
    if (cuesFromMidi.length) setChordCues(cuesFromMidi)
  }, [cuesFromMidi])

  const fallbackCues = useMemo(() => {
    if (chordCues.length) return chordCues
    if (navState.progression && navState.progression.length) {
      return useChordTimeline.buildCuesFromProgression(navState.progression, timeSig, tempoBpm, navState.barsPerChord ?? 1)
    }
    return []
  }, [chordCues, navState.progression, navState.barsPerChord, tempoBpm, timeSig])

  /* ===== AMP (Gain / Tone / Master, + 녹음 적용) ===== */
  const amp = useAmp({ deviceId })
  const [applyAmpToRec, setApplyAmpToRec] = useState(false)
  const [ampOpen, setAmpOpen] = useState(true) // 아코디언 열림/닫힘

  /* ===== 오디오 엘리먼트 / 트랜스포트 ===== */
  const midiEl = useRef<HTMLAudioElement>(null)
  const bassEl = useRef<HTMLAudioElement>(null)
  const [duration, setDuration] = useState(0)
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(false)
  const rafRef = useRef<number | null>(null)
  const transportStartAt = useRef<number | null>(null)
  const [loop, setLoop] = useState(false)
  const [midiVol, setMidiVol] = useState(0.9)
  const [playMidi, setPlayMidi] = useState(true)
  const [playBass, setPlayBass] = useState(true)
  const [recVizActive, setRecVizActive] = useState(false)
  const [recVizMode, setRecVizMode] = useState<"amp" | "raw">("raw")

  /* ===== 카운트인 ===== */
  const COUNTIN_BEATS = navState.preRollBeats ?? 4
  const { playCountIn } = useCountIn()

  /* ===== 베이스 트리밍(카운트인 제거) ===== */
  const [bassTrimUrl, setBassTrimUrl] = useState<string | null>(null)
  const [bassBuffer, setBassBuffer] = useState<AudioBuffer | null>(null)
  const beatSec = useMemo(() => 60 / Math.max(40, Math.min(300, tempoBpm)), [tempoBpm])
  const preRollSec = useMemo(() => beatSec * COUNTIN_BEATS, [beatSec, COUNTIN_BEATS])

  // 녹음 소스 선택: AMP가 적용되면 amp.procBlobUrl, 아니면 훅(blobUrl)
  const activeBlobUrl = applyAmpToRec ? amp.procBlobUrl : blobUrl

  useEffect(() => {
    let revoke: string | null = null
    ;(async () => {
      if (!activeBlobUrl) { setBassTrimUrl(null); setBassBuffer(null); return }
      try {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
        const arr = await (await fetch(activeBlobUrl)).arrayBuffer()
        const src = await ctx.decodeAudioData(arr.slice(0))
        const startSample = Math.floor(preRollSec * src.sampleRate)
        const out = ctx.createBuffer(src.numberOfChannels, Math.max(0, src.length - startSample), src.sampleRate)
        for (let ch = 0; ch < src.numberOfChannels; ch++) {
          out.getChannelData(ch).set(src.getChannelData(ch).subarray(startSample))
        }
        await ctx.close()
        const wav = audioBufferToWavBlob(out)
        const url = URL.createObjectURL(wav)
        setBassTrimUrl(url); setBassBuffer(out); revoke = url
      } catch {
        setBassTrimUrl(null); setBassBuffer(null)
      }
    })()
    return () => { if (revoke) URL.revokeObjectURL(revoke) }
  }, [activeBlobUrl, preRollSec])

  /* ===== 타임라인 파생 ===== */
  const cuesForUI = chordCues.length ? chordCues : fallbackCues
  const { totalFromCues, posMod, noAnim } = useChordTimeline.useCycle({
    cues: cuesForUI, timeSig, tempoBpm, barsPerChord: navState.barsPerChord ?? 1, position
  })

  /* ===== 트랜스포트 ===== */
  function syncVolumesAndMutes() {
    if (midiEl.current) { midiEl.current.volume = midiVol; midiEl.current.muted = !playMidi; midiEl.current.loop = loop }
    if (bassEl.current) { bassEl.current.volume = 1.0; bassEl.current.muted = !playBass; bassEl.current.loop = loop }
  }

  function ensureUnlocked() {
    const el = midiEl.current; if (!el) return Promise.resolve()
    const prev = el.muted; el.muted = true
    return el.play().catch(()=>{}).then(()=>el.pause()).finally(()=>{ el.muted = prev })
  }

  async function startRecordingFlow() {
    const bassOnly = false // 유지: 필요 시 prop/state로 확장
    if (!midiAudioUrl && !bassOnly) {
      alert('먼저 MIDI 백킹이 준비되어야 합니다.'); return
    }
    await ensureUnlocked()
    await playCountIn(COUNTIN_BEATS, tempoBpm)

    // Start scrolling waveform visualization in sync with recording
    const willUseAmp = applyAmpToRec && amp.running
    setRecVizMode(willUseAmp ? 'amp' : 'raw')
    setRecVizActive(true)

    // 녹음 시작
    if (applyAmpToRec) {
      await amp.startAmpIfNeeded()
      await amp.startAmpRecording()
    } else {
      if (!recording) await start()
    }

    // 재생 시작
    transportStartAt.current = performance.now()
    if (!bassOnly && midiEl.current) {
      midiEl.current.currentTime = 0
      midiEl.current.play().catch(()=>{})
    }
    setPlaying(true)
    if (!rafRef.current) tick()
  }

  function tick() {
    let t = midiEl.current ? (midiEl.current.currentTime ?? 0) : 0
    if ((!midiEl.current || midiEl.current.paused) && transportStartAt.current) {
      t = (performance.now() - transportStartAt.current) / 1000
    }
    setPosition(t)

    const cues = chordCues.length ? chordCues : fallbackCues
    if (cues.length > 0) {
      const { now, next } = getNowNextChord(cues, t)
      // HUD 외부: 필요 시 상태로 노출
    }
    rafRef.current = requestAnimationFrame(tick)
  }

  function play() {
    midiEl.current?.play().catch(()=>{})
    bassEl.current?.play().catch(()=>{})
    setPlaying(true)
    if (!rafRef.current) tick()
  }
  function pause() {
    midiEl.current?.pause()
    bassEl.current?.pause()
    setPlaying(false)
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
  }
  function stopAll() {
    pause()
    if (midiEl.current) midiEl.current.currentTime = 0
    if (bassEl.current) bassEl.current.currentTime = 0
    transportStartAt.current = null
    setPosition(0)
    setRecVizActive(false)
  }
  function seek(sec: number) {
    if (midiEl.current) midiEl.current.currentTime = sec
    if (bassEl.current) bassEl.current.currentTime = sec
    transportStartAt.current = performance.now() - sec * 1000
    setPosition(sec)
  }

  useEffect(() => {
    function updateDur() {
      const d1 = midiEl.current?.duration ?? 0
      const d2 = bassEl.current?.duration ?? 0
      const d = Math.max(isFinite(d1) ? d1 : 0, isFinite(d2) ? d2 : 0)
      if (d && isFinite(d)) setDuration(d)
    }
    const a = midiEl.current; const b = bassEl.current
    a?.addEventListener('loadedmetadata', updateDur)
    b?.addEventListener('loadedmetadata', updateDur)
    a?.addEventListener('ended', () => !loop && pause())
    b?.addEventListener('ended', () => !loop && pause())
    updateDur()
    return () => {
      a?.removeEventListener('loadedmetadata', updateDur)
      b?.removeEventListener('loadedmetadata', updateDur)
    }
  }, [midiAudioUrl, bassTrimUrl, loop])

  /* ===== 합치기 ===== */
  const [mergedUrl, setMergedUrl] = useState<string | null>(null)
  useEffect(() => () => { if (mergedUrl) URL.revokeObjectURL(mergedUrl) }, [mergedUrl])

  async function mergeAndExport() {
    if (!midiBuffer) return
    if (mergedUrl) URL.revokeObjectURL(mergedUrl)
    setMergedUrl(null)

    let bass: AudioBuffer | null = bassBuffer
    const srcUrl = activeBlobUrl
    if (!bass && srcUrl) {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const arr = await (await fetch(srcUrl)).arrayBuffer()
      const src = await ctx.decodeAudioData(arr.slice(0))
      const startSample = Math.floor(preRollSec * src.sampleRate)
      const out = ctx.createBuffer(src.numberOfChannels, Math.max(0, src.length - startSample), src.sampleRate)
      for (let ch = 0; ch < src.numberOfChannels; ch++) {
        out.getChannelData(ch).set(src.getChannelData(ch).subarray(startSample))
      }
      await ctx.close()
      bass = out
    }
    if (!bass) return

    const mixed = await mixBuffersToAudioBuffer(midiBuffer, bass, { sampleRate: 48000, fadeOutSec: 0.03 })
    const wav = audioBufferToWavBlob(mixed)
    const url = URL.createObjectURL(wav)
    setMergedUrl(url)
  }

  /* ===== 렌더 ===== */
  return (
    <div className="pmx-wrap">
      {/* 입력 장치 */}
      <section className="pmx-panel">
        <div style={{display:'flex', alignItems:'center', gap:8}}>
          <h3 style={{margin:0}}>🎛 입력 장치</h3>
        </div>
        <div className="row">
          <DeviceSelect value={deviceId} onChange={setDeviceId} />
          <button className="btn" onClick={async ()=>{ await navigator.mediaDevices.getUserMedia({ audio: true }) }}>
            🎤 마이크 권한
          </button>
          <button className="btn" onClick={() => window.location.reload()}>🔄 새로고침</button>
        </div>
        {recErr && <div className="warn">녹음 오류: {recErr}</div>}
      </section>

      {/* 타임라인 */}
      {cuesForUI.length > 0 && (
        <section className="pmx-panel">
          <h3>🧭 코드 타임라인</h3>
          <div className="timeline">
            {cuesForUI.map((c, i) => {
              const t0 = c.time
              const t1 = cuesForUI[i + 1]?.time ?? totalFromCues
              const w = Math.max(4, (t1 - t0) / Math.max(1, totalFromCues) * 100)
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
                left: `${Math.min(100, posMod / Math.max(0.001, totalFromCues) * 100)}%`,
                transition: noAnim ? 'none' : undefined
              }}
            />
          </div>
        </section>
      )}

      {/* 백킹 */}
      <section className="pmx-panel">
        <h3>🎼 백킹(미디 렌더)</h3>
        <div className="row">
          <label className="file">
            <input type="file" accept=".mid,.midi" onChange={e => {
              const f = e.target.files?.[0]; if (f) handleMidiFile(f)
            }}/>
            <span>파일 선택</span>
          </label>
          {midiFile && <span className="hint">{midiFile.name}</span>}
        </div>
        <div className="preview" style={{marginTop:8}}>
          {midiAudioUrl
            ? <audio ref={midiEl} src={midiAudioUrl} preload="metadata" controls onLoadedMetadata={syncVolumesAndMutes} onPlay={syncVolumesAndMutes} />
            : <div className="thin">결과 카드에서 “베이스 녹음하기”로 들어오면 자동으로 채워집니다.</div>}
        </div>
      </section>

      {/* AMP — 아코디언 */}
      <section className="pmx-panel" aria-label="AMP section">
        <div
          className="pmx-accordion-header"
          style={{
            display:'flex', alignItems:'center', gap:12,
            paddingBottom:8, borderBottom:'1px solid rgba(255,255,255,0.06)', marginBottom:12
          }}
        >
          <h3 style={{margin:0, flex:1}}>🎛 AMP (Gain / Tone / Master)</h3>

          {/* 오른쪽 원형 토글 버튼 */}
          <button
            type="button"
            aria-expanded={ampOpen}
            aria-controls="amp-accordion-body"
            onClick={()=>setAmpOpen(o=>!o)}
            className="btn"
            style={{
              width:36, height:36, borderRadius:24, display:'inline-flex',
              alignItems:'center', justifyContent:'center',
              background:'rgba(255,255,255,0.08)', border:'1px solid rgba(255,255,255,0.12)'
            }}
            title={ampOpen ? '접기' : '펼치기'}
          >
            {/* chevron-down 아이콘 (열림 시 위로 회전) */}
            <svg
              width="18" height="18" viewBox="0 0 24 24"
              style={{ transform: ampOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition:'transform .18s ease' }}
              aria-hidden="true"
            >
              <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        {/* 아코디언 본문 */}
        <div id="amp-accordion-body" style={{ display: ampOpen ? 'block' : 'none' }}>
          <div className="row" style={{gap:12, alignItems:'center', flexWrap:'wrap'}}>
            <label className="row" style={{gap:6}}>
              <input type="checkbox" checked={amp.testTone} onChange={e=>amp.setTestTone(e.target.checked)} />
              테스트톤(110Hz) 사용
            </label>
            {!amp.running
              ? <button className="btn" onClick={()=>amp.startAmpIfNeeded().catch(err=>alert(err?.message||String(err)))}>⚡ 시작</button>
              : <button className="btn danger" onClick={amp.stopAmp}>■ 정지</button>}
            <label className="row" style={{gap:6, marginLeft:12}}>
              <input type="checkbox" checked={applyAmpToRec} onChange={e=>setApplyAmpToRec(e.target.checked)} />
              녹음에 앰프 톤 적용
            </label>
            <span className="hint" style={{marginLeft:'auto'}}>{amp.status}</span>
          </div>

          <div className="amp-grid" style={{display:'flex', gap:20, flexWrap:'wrap', alignItems:'flex-end', marginTop:6}}>
            <DialKnob label="Gain"   value={amp.gain}   min={0}  max={10} step={0.1} defaultValue={4.0}  onChange={amp.setGain} />
            <DialKnob label="Tone"   value={amp.tone}   min={-5} max={5}  step={0.1} defaultValue={0.0}  onChange={amp.setTone} />
            <DialKnob label="Master" value={amp.master} min={0}  max={10} step={0.1} defaultValue={7.5} onChange={amp.setMaster} />
          </div>

          <div className="scope" style={{background:'#0b1220', border:'1px dashed #1f2937', borderRadius:12, padding:8, marginTop:12}}>
            <AmpScope analyser={amp.analyser} />
          </div>
        </div>
      </section>

      {/* 베이스 미리듣기 & 트랜스포트 */}
      <section className="pmx-panel">
        <h3>🎚 미리듣기 & 트랜스포트</h3>

        {/* 파형-스크롤 시각화: 녹음 시작/정지와 연동 */}
        <RecordingWaveScroll
          active={recVizActive}
          mode={recVizMode}
          deviceId={deviceId || undefined}
          ampAnalyser={amp.analyser || undefined}
          height={160}
          className="scope"
        />

        {/* Bass 프리뷰(볼륨 슬라이더 제거, AMP가 음색/볼륨 담당) */}
        <div className="preview" style={{marginTop:12}}>
          {(bassTrimUrl || activeBlobUrl)
            ? <audio ref={bassEl} src={(bassTrimUrl ?? activeBlobUrl)!} preload="metadata" controls
                     onLoadedMetadata={syncVolumesAndMutes}
                     onPlay={syncVolumesAndMutes} />
            : <div className="thin">녹음 후 재생 가능</div>}
        </div>

        {/* 트랜스포트 */}
        <div className="transport" style={{marginTop:12}}>
          <button className="btn" onClick={playing ? pause : play} disabled={!midiAudioUrl && !bassTrimUrl && !activeBlobUrl}>
            {playing ? '⏸ 일시정지' : '▶︎ 재생'}
          </button>
          <button className="btn" onClick={stopAll}>⏹ 정지</button>
          <label className="row" style={{gap:8}}>
            <input
              aria-label="seek"
              type="range" min={0} max={Math.max(duration || totalFromCues, 0.001)} step={0.01}
              value={position} onChange={e => seek(Number(e.target.value))}
              style={{width:360}}
            />
          </label>
          <label className="row" style={{gap:6}}>
            <input type="checkbox" checked={loop} onChange={e=>setLoop(e.target.checked)} />
            <span className="hint">루프</span>
          </label>

          {/* 녹음 버튼(시각화와 통합) */}
          {!recording && !amp.ampRecording
            ? <button className="btn primary" style={{marginLeft:12}} onClick={startRecordingFlow}>● 녹음 시작</button>
            : <button className="btn danger" style={{marginLeft:12}} onClick={async ()=>{
                if (applyAmpToRec) { await amp.stopAmpRecording() } else { await stop() }
                setRecVizActive(false)
              }}>■ 정지</button>}
        </div>
      </section>

      {/* 합치기 & 다운로드 */}
      <section className="pmx-panel">
        <h3>⬇️ 합치기 & 다운로드</h3>
        <button className="btn" onClick={mergeAndExport} disabled={!midiBuffer || (!bassBuffer && !activeBlobUrl)}>
          음원 합치기 (WAV 생성)
        </button>
        {mergedUrl && (
          <div className="result">
            <audio src={mergedUrl} controls />
            <div><a className="btn" href={mergedUrl} download={'result_with_bass.wav'}>⬇ 합친 결과 다운로드 (WAV)</a></div>
          </div>
        )}
      </section>
    </div>
  )
}