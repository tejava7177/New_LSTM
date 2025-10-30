import React, { useEffect, useMemo, useRef, useState } from 'react'
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
  const [bassVol, setBassVol] = useState(1.0)
  const [playMidi, setPlayMidi] = useState(true)
  const [playBass, setPlayBass] = useState(true)

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
    if (bassEl.current) { bassEl.current.volume = bassVol; bassEl.current.muted = !playBass; bassEl.current.loop = loop }
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
        <h3>🎛 입력 장치</h3>
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

      {/* AMP */}
      <section className="pmx-panel">
        <h3>🎛 AMP (Gain / Tone / Master)</h3>
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
      </section>

      {/* 베이스 미리듣기 */}
      <section className="pmx-panel">
        <h3>🎚 미리듣기 & 트랜스포트</h3>
        <div className="mixer">
          <div className="ch">
            <div className="ch-title">Bass</div>
            <div className="col">
              <input type="range" min={0} max={1} step={0.01} value={bassVol} onChange={e=>setBassVol(Number(e.target.value))}/>
              <div className="hint">볼륨 {Math.round(bassVol*100)}%</div>
            </div>
            <div className="preview">
              {(bassTrimUrl || activeBlobUrl)
                ? <audio ref={bassEl} src={(bassTrimUrl ?? activeBlobUrl)!} preload="metadata" controls
                         onLoadedMetadata={syncVolumesAndMutes}
                         onPlay={syncVolumesAndMutes} />
                : <div className="thin">녹음 후 재생 가능</div>}
            </div>
          </div>
        </div>

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

          {/* 녹음 버튼 */}
          {!recording && !amp.ampRecording
            ? <button className="btn primary" style={{marginLeft:12}} onClick={startRecordingFlow}>● 녹음 시작</button>
            : <button className="btn danger" style={{marginLeft:12}} onClick={async ()=>{
                if (applyAmpToRec) { await amp.stopAmpRecording() } else { await stop() }
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
