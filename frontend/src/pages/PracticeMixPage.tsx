// src/pages/PracticeMixPage.tsx
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import DeviceSelect from '../components/DeviceSelect'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { audioBufferToWavBlob } from '../utils/wav'
import { mixBuffersToAudioBuffer } from '../lib/mixdown'
import { Midi } from '@tonejs/midi'
import { renderMidiOnServer } from '../lib/midiServer'
import { midiUrl, wavUrl } from '../lib/tracks'
import { extractChordCuesFromMidi, getNowNextChord, ChordCue } from '../lib/midiCues'

type TrackMeta = { name: string; channel?: number; instrument?: string; notes: number }
type NavState = { jobId?: string; progression?: string[]; tempo?: number }

export default function PracticeMixPage() {
  /* ===== 라우터 state (결과 카드 → 이동) ===== */
  const { state } = useLocation()
  const navState = (state as NavState) || {}
  const navigate = useNavigate()

  /* ===== 입력 장치 & 녹음 ===== */
  const [deviceId, setDeviceId] = useState<string>('')
  const { recording, blobUrl, start, stop, error: recErr } = useMediaRecorder(deviceId || undefined)

  /* ===== MIDI 로딩 & 렌더링 ===== */
  const [midiFile, setMidiFile] = useState<File | null>(null)
  const [midiAudioUrl, setMidiAudioUrl] = useState<string | null>(null) // WAV
  const [midiBuffer, setMidiBuffer] = useState<AudioBuffer | null>(null) // 믹싱용
  const [midiTracks, setMidiTracks] = useState<TrackMeta[]>([])
  const [rendering, setRendering] = useState(false)

  const [tempoBpm, setTempoBpm] = useState<number>(navState.tempo ?? 100)
  const [timeSig, setTimeSig] = useState<[number, number]>([4, 4])
  const [chordCues, setChordCues] = useState<ChordCue[]>([])

  /* ===== 플레이어/트랜스포트 ===== */
  const midiEl = useRef<HTMLAudioElement>(null)
  const bassEl = useRef<HTMLAudioElement>(null)
  const [duration, setDuration] = useState(0)
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(false)
  const rafRef = useRef<number | null>(null)
  const transportStartAt = useRef<number | null>(null)

  /* ===== 믹서 ===== */
  const [midiVol, setMidiVol] = useState(0.9)
  const [bassVol, setBassVol] = useState(1.0)
  const [playMidi, setPlayMidi] = useState(true)
  const [playBass, setPlayBass] = useState(true)
  const [loop, setLoop] = useState(false)

  /* ===== 합치기 ===== */
  const [mergedUrl, setMergedUrl] = useState<string | null>(null)

  /* ===== 녹음 UX ===== */
  const COUNTIN_BEATS = 4
  const [bassOnly, setBassOnly] = useState(false)
  const [nowChord, setNowChord] = useState('')
  const [nextChord, setNextChord] = useState('')

  /* ===== 베이스 트리밍(카운트인 제거) ===== */
  const [bassTrimUrl, setBassTrimUrl] = useState<string | null>(null)
  const [bassBuffer, setBassBuffer] = useState<AudioBuffer | null>(null)

  // ── 가드: 결과 카드(state) 없이 들어오면 홈으로
  useEffect(() => {
    if (!navState.jobId) {
      navigate('/', { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 카운트인(4박) 길이(초)
  const preRollSec = (60 / Math.max(40, Math.min(300, tempoBpm))) * COUNTIN_BEATS

  // 녹음본을 프리롤만큼 잘라서 미리듣기/믹싱에 사용
  useEffect(() => {
    let revoke: string | null = null
    ;(async () => {
      if (!blobUrl) { setBassTrimUrl(null); setBassBuffer(null); return }
      try {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
        const arr = await (await fetch(blobUrl)).arrayBuffer()
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
  }, [blobUrl, preRollSec])

  /* ====== 생성 트랙에서 자동 부팅 ====== */
  useEffect(() => {
    async function bootstrapFromGeneratedJob(jobId: string, tempoFromNav?: number) {
      let bpm = tempoFromNav ?? tempoBpm

      // 1) MIDI(마커 포함) → 코드 큐
      const midiArr = await (await fetch(midiUrl(jobId))).arrayBuffer()
      try {
        const pre = (60 / Math.max(40, Math.min(300, bpm))) * COUNTIN_BEATS
        const cues = await extractChordCuesFromMidi(midiArr, { preRollSec: pre, windowBeats: 1 })
        setChordCues(cues)
        if (cues.length) { setNowChord(cues[0].text); setNextChord(cues[1]?.text ?? '') }
      } catch {}

      // 2) 템포/박자/트랙 메타
      try {
        const midi = new Midi(midiArr)
        bpm = tempoFromNav ?? (midi.header.tempos?.[0]?.bpm ?? bpm)
        setTempoBpm(bpm)
        const ts = (midi.header.timeSignatures?.[0]?.timeSignature as number[]) || [4, 4]
        setTimeSig([ts[0] ?? 4, ts[1] ?? 4])
        setMidiTracks(midi.tracks.map(t => ({
          name: t.name || '(no name)',
          channel: t.channel,
          instrument: t.instrument?.name || (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
          notes: t.notes.length,
        })))
      } catch {}

      // 3) WAV 로드 + 디코드
      const wurl = wavUrl(jobId)
      setMidiAudioUrl(wurl)
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      try {
        const wArr = await (await fetch(wurl)).arrayBuffer()
        setMidiBuffer(await ctx.decodeAudioData(wArr.slice(0)))
      } finally { await ctx.close() }
    }

    if (navState.jobId) bootstrapFromGeneratedJob(navState.jobId, navState.tempo).catch(console.error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navState.jobId])

  /* ====== 수동 MIDI 업로드 플로우(직접 테스트용) ====== */
  async function handleMidiFile(file: File) {
    setMidiFile(file)
    setMidiAudioUrl(null); setMidiBuffer(null); setMergedUrl(null)
    setMidiTracks([]); setChordCues([]); setNowChord(''); setNextChord('')
    setRendering(true)
    try {
      const arr = await file.arrayBuffer()
      const midi = new Midi(arr)
      const bpm = midi.header.tempos?.[0]?.bpm ?? 100
      setTempoBpm(bpm)
      const ts = (midi.header.timeSignatures?.[0]?.timeSignature as number[]) || [4, 4]
      setTimeSig([ts[0] ?? 4, ts[1] ?? 4])
      setMidiTracks(midi.tracks.map(t => ({
        name: t.name || '(no name)',
        channel: t.channel,
        instrument: t.instrument?.name || (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
        notes: t.notes.length,
      })))

      // 마커가 있으면 정확, 없으면 빈 배열(=힌트 미표시)
      const preRollSecLocal = (60 / Math.max(40, Math.min(300, bpm))) * COUNTIN_BEATS
      const cues = await extractChordCuesFromMidi(arr, { preRollSec: preRollSecLocal, windowBeats: 1 })
      setChordCues(cues)

      // 서버 렌더 WAV
      const { wavUrl: wurl } = await renderMidiOnServer(file)
      setMidiAudioUrl(wurl)

      // 믹싱용 버퍼
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const wavArr = await (await fetch(wurl)).arrayBuffer()
      setMidiBuffer(await ctx.decodeAudioData(wavArr.slice(0)))
      await ctx.close()
    } finally {
      setRendering(false)
    }
  }

  /* ===== 카운트인 ===== */
  async function playCountIn(beats: number, bpm: number) {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const beat = 60 / Math.max(40, Math.min(300, bpm))
    const t0 = ctx.currentTime + 0.05
    for (let i = 0; i < beats; i++) {
      const osc = ctx.createOscillator()
      const g = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = i === 0 ? 1200 : 800
      g.gain.value = 0
      osc.connect(g).connect(ctx.destination)
      const ts = t0 + i * beat
      g.gain.setValueAtTime(0, ts)
      g.gain.linearRampToValueAtTime(0.8, ts + 0.01)
      g.gain.exponentialRampToValueAtTime(0.0001, ts + 0.15)
      osc.start(ts); osc.stop(ts + 0.2)
    }
    return new Promise<void>((resolve) => {
      const endAt = t0 + beats * beat
      const ms = Math.ceil((endAt - ctx.currentTime) * 1000) + 10
      setTimeout(() => { ctx.close().finally(resolve) }, ms)
    })
  }

  /* ===== 오토플레이 해제 ===== */
  async function ensureUnlocked() {
    const el = midiEl.current; if (!el) return
    const prev = el.muted; el.muted = true
    try { await el.play().catch(()=>{}); el.pause() } finally { el.muted = prev }
  }

  /* ===== 녹음 시작 (카운트인 → 동시 스타트) ===== */
  async function startRecordingFlow() {
    if (!midiAudioUrl && !bassOnly) { alert('MIDI 파일을 먼저 선택하세요.'); return }
    if (!recording) await start()
    await ensureUnlocked()
    await playCountIn(COUNTIN_BEATS, tempoBpm)

    transportStartAt.current = performance.now()
    if (!bassOnly && midiEl.current) {
      midiEl.current.currentTime = 0
      midiEl.current.play().catch(()=>{})
    }
    setPlaying(true)
    if (!rafRef.current) tick()
  }

  /* ===== 트랜스포트/HUD ===== */
  function syncVolumesAndMutes() {
    if (midiEl.current) { midiEl.current.volume = midiVol; midiEl.current.muted = !playMidi; midiEl.current.loop = loop }
    if (bassEl.current) { bassEl.current.volume = bassVol; bassEl.current.muted = !playBass; bassEl.current.loop = loop }
  }
  useEffect(() => { syncVolumesAndMutes() }, [midiVol, bassVol, playMidi, playBass, loop, midiAudioUrl, bassTrimUrl])

  function tick() {
    let t = midiEl.current ? (midiEl.current.currentTime ?? 0) : 0
    if ((!midiEl.current || midiEl.current.paused) && transportStartAt.current) {
      t = (performance.now() - transportStartAt.current) / 1000
    }
    setPosition(t)
    if (chordCues.length > 0) {
      const { now, next } = getNowNextChord(chordCues, t)
      setNowChord(now); setNextChord(next)
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
    setNowChord(''); setNextChord('')
  }
  function seek(sec: number) {
    if (midiEl.current) midiEl.current.currentTime = sec
    if (bassEl.current) bassEl.current.currentTime = sec
    transportStartAt.current = performance.now() - sec * 1000
    setPosition(sec)
  }

  // 메타데이터/종료 바인딩
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

  // 네이티브 오디오 컨트롤로 재생/이동해도 코드 힌트 갱신
  useEffect(() => {
    const a = midiEl.current; const b = bassEl.current
    if (!a && !b) return
    const onTU = () => {
      const t = Math.max(a?.currentTime ?? 0, b?.currentTime ?? 0)
      setPosition(t)
      if (chordCues.length) {
        const { now, next } = getNowNextChord(chordCues, t)
        setNowChord(now); setNextChord(next)
      }
    }
    const onPlay = () => {
      setPlaying(true)
      if (!rafRef.current) {
        rafRef.current = requestAnimationFrame(function loop() {
          onTU(); rafRef.current = requestAnimationFrame(loop)
        })
      }
    }
    const onPauseOrEnd = () => {
      setPlaying(false)
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
      onTU()
    }
    ;[a,b].forEach(el => {
      el?.addEventListener('play', onPlay)
      el?.addEventListener('pause', onPauseOrEnd)
      el?.addEventListener('ended', onPauseOrEnd)
      el?.addEventListener('timeupdate', onTU)
      el?.addEventListener('seeking', onTU)
      el?.addEventListener('seeked', onTU)
    })
    onTU()
    return () => {
      ;[a,b].forEach(el => {
        el?.removeEventListener('play', onPlay)
        el?.removeEventListener('pause', onPauseOrEnd)
        el?.removeEventListener('ended', onPauseOrEnd)
        el?.removeEventListener('timeupdate', onTU)
        el?.removeEventListener('seeking', onTU)
        el?.removeEventListener('seeked', onTU)
      })
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
    }
  }, [midiAudioUrl, bassTrimUrl, blobUrl, chordCues])

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }, [])

  /* ===== 합치기 ===== */
  async function mergeAndExport() {
    if (!midiBuffer) return
    if (mergedUrl) URL.revokeObjectURL(mergedUrl)
    setMergedUrl(null)

    let bass: AudioBuffer | null = bassBuffer
    if (!bass && blobUrl) {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const arr = await (await fetch(blobUrl)).arrayBuffer()
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
  useEffect(() => () => { if (mergedUrl) URL.revokeObjectURL(mergedUrl) }, [mergedUrl])

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
        </div>
        {recErr && <div className="warn">녹음 오류: {recErr}</div>}
      </section>

      {/* MIDI 파일 */}
      <section className="pmx-panel">
        <h3>🎼 MIDI 파일</h3>
        <div className="row">
          <label className="file">
            <input type="file" accept=".mid,.midi" onChange={e => {
              const f = e.target.files?.[0]; if (f) handleMidiFile(f)
            }}/>
            <span>파일 선택</span>
          </label>
          {midiFile && <span className="hint">{midiFile.name}</span>}
          {rendering && <span className="hint">서버 렌더링 중…</span>}
        </div>

        {/* 음원 미리듣기(= 트랜스포트 대상) */}
        <div className="preview" style={{marginTop:8}}>
          {midiAudioUrl
            ? <audio ref={midiEl} src={midiAudioUrl} preload="metadata" controls
                     onLoadedMetadata={syncVolumesAndMutes}
                     onPlay={syncVolumesAndMutes}
                     onError={(e)=>console.warn('MIDI audio error', e)} />
            : <div className="thin">※ 이 페이지는 결과 카드의 “베이스 녹음하기”로 진입합니다.</div>}
        </div>

        {/* 메타/트랙/코드 정보 */}
        {(midiTracks.length > 0 || chordCues.length > 0) && (
          <details className="tracks" style={{marginTop:8}}>
            <summary>트랙 정보 보기</summary>
            <div className="thin" style={{margin:'6px 0'}}>Tempo: {tempoBpm} BPM • Time Sig: {timeSig[0]}/{timeSig[1]}</div>
            <ul>
              {midiTracks.map((t, i) => (
                <li key={i}>
                  <strong>{t.name}</strong>
                  <span className="thin"> ({t.instrument ?? 'inst'}, ch {t.channel ?? '-'})</span>
                  <span className="thin"> • notes: {t.notes}</span>
                </li>
              ))}
            </ul>
            {chordCues.length > 0 && (
              <div style={{marginTop:8, padding:'6px 8px', background:'#f7f7f9', border:'1px solid #eee', borderRadius:6}}>
                <strong>코드(미디):</strong>{' '}
                {nowChord ? <span>{nowChord}</span> : <span className="thin">대기 중…</span>}
                {nextChord && <span className="thin">  →  다음: {nextChord}</span>}
              </div>
            )}
          </details>
        )}
      </section>

      {/* 베이스 녹음 */}
      <section className="pmx-panel">
        <h3>🎙 베이스 녹음</h3>
        <div className="row" style={{gap:12, alignItems:'center'}}>
          {!recording
            ? <button className="btn primary" onClick={startRecordingFlow}>● 녹음 시작(카운트인 {COUNTIN_BEATS}박)</button>
            : <button className="btn danger" onClick={stop}>■ 정지</button>}
          <label className="row" style={{gap:6}}>
            <input type="checkbox" checked={bassOnly} onChange={e=>setBassOnly(e.target.checked)} />
            베이스만 녹음(미디 미재생)
          </label>
        </div>

        {/* 코드 힌트(녹음 섹션에도 표시) */}
        {chordCues.length > 0 && (
          <div style={{marginTop:8, padding:'6px 8px', background:'#f7f7f9', border:'1px solid #eee', borderRadius:6}}>
            <strong>코드 힌트:</strong>{' '}
            {nowChord ? <span>{nowChord}</span> : <span className="thin">대기 중…</span>}
            {nextChord && <span className="thin">  →  다음: {nextChord}</span>}
          </div>
        )}
      </section>

      {/* 베이스 미리듣기 & 믹서 */}
      <section className="pmx-panel">
        <h3>🎚 Bass 미리듣기 & 믹서</h3>
        <div className="mixer">
          <div className="ch">
            <div className="ch-title">Bass</div>
            <div className="row">
              <label className="row"><input type="checkbox" checked={playBass} onChange={e=>setPlayBass(e.target.checked)} /> 재생</label>
            </div>
            <div className="col">
              <input type="range" min={0} max={1} step={0.01} value={bassVol} onChange={e=>setBassVol(Number(e.target.value))}/>
              <div className="hint">볼륨 {Math.round(bassVol*100)}%</div>
            </div>
            <div className="preview">
              {(bassTrimUrl || blobUrl)
                ? <audio ref={bassEl} src={(bassTrimUrl ?? blobUrl)!} preload="metadata" controls
                         onLoadedMetadata={syncVolumesAndMutes}
                         onPlay={syncVolumesAndMutes}
                         onError={(e)=>console.warn('Bass audio error', e)} />
                : <div className="thin">녹음 후 재생 가능</div>}
              {bassTrimUrl && <div className="tiny" style={{marginTop:4}}>※ 카운트인 {COUNTIN_BEATS}박 구간을 자동 제거했습니다.</div>}
            </div>
          </div>
        </div>

        {/* 트랜스포트 */}
        <div className="transport" style={{marginTop:12}}>
          <button className="btn" onClick={playing ? pause : play} disabled={!midiAudioUrl && !bassTrimUrl && !blobUrl}>
            {playing ? '⏸ 일시정지' : '▶︎ 재생'}
          </button>
          <button className="btn" onClick={stopAll}>⏹ 정지</button>
          <label className="row" style={{gap:8}}>
            <input
              type="range" min={0} max={Math.max(duration, 0.001)} step={0.01}
              value={position} onChange={e => seek(Number(e.target.value))}
              style={{width:360}}
            />
            <span className="hint">{formatTime(position)} / {formatTime(duration)}</span>
          </label>
          <label className="row" style={{gap:6}}>
            <input type="checkbox" checked={loop} onChange={e=>setLoop(e.target.checked)} />
            <span className="hint">루프</span>
          </label>
        </div>
      </section>

      {/* 합치기 & 다운로드 */}
      <section className="pmx-panel">
        <h3>⬇️ 합치기 & 다운로드</h3>
        <button className="btn" onClick={mergeAndExport} disabled={!midiBuffer || (!bassBuffer && !blobUrl)}>
          음원 합치기(WAV 생성)
        </button>
        {mergedUrl && (
          <div className="result">
            <audio src={mergedUrl} controls />
            <div><a className="btn" href={mergedUrl} download={makeDownloadName(midiFile?.name)}>⬇ 합친 결과 다운로드 (WAV)</a></div>
          </div>
        )}
        <div className="tiny">* .mid에는 오디오가 없으므로 합친 결과는 WAV로 제공합니다.</div>
      </section>
    </div>
  )
}

/* ===== 유틸 ===== */
function makeDownloadName(midiName?: string) {
  const base = midiName?.replace(/\.(mid|midi)$/i, '') || 'result'
  return `${base}_with_bass.wav`
}
function formatTime(sec: number) {
  if (!isFinite(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}