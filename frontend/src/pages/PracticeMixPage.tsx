import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { mixBuffersToAudioBuffer } from '../lib/mixdown'
import { audioBufferToWavBlob } from '../utils/wav'
import { Midi } from '@tonejs/midi'
import { renderMidiOnServer } from '../lib/midiServer'

/** 트랙 메타 표시용(가볍게) */
type TrackMeta = { name: string; channel?: number; instrument?: string; notes: number }

/**
 * PracticeMixPage
 * - MIDI 파일을 선택하면: (1) 클라이언트에서 MIDI 파싱 → 트랙 메타 표시
 *                         (2) 서버로 업로드 → FluidSynth로 WAV 렌더 → 재생 URL 획득
 *                         (3) 믹싱을 위해 브라우저에서 WAV를 AudioBuffer로 디코드
 * - 베이스는 MediaRecorder로 녹음(입력 장치 선택 지원)
 * - 두 오디오(MIDI/WAV, Bass/녹음)를 동시에 재생/정지/시킹/루프
 * - 최종적으로 오프라인 믹스해서 하나의 WAV로 다운로드
 */
export default function PracticeMixPage() {
  /* === 입력 장치 & 녹음 === */
  const [deviceId, setDeviceId] = useState<string>('')
  const { recording, blobUrl, start, stop, error: recErr } = useMediaRecorder(deviceId || undefined)

  /* === MIDI 상태 === */
  const [midiFile, setMidiFile] = useState<File | null>(null)
  const [midiAudioUrl, setMidiAudioUrl] = useState<string | null>(null)   // 서버가 렌더한 WAV URL (스트리밍/미리듣기용)
  const [midiBuffer, setMidiBuffer] = useState<AudioBuffer | null>(null)  // 믹싱용 디코드 AudioBuffer
  const [midiTracks, setMidiTracks] = useState<TrackMeta[]>([])
  const [rendering, setRendering] = useState(false)

  /* === 플레이어 & 트랜스포트 === */
  const midiEl = useRef<HTMLAudioElement>(null)
  const bassEl = useRef<HTMLAudioElement>(null)

  const [duration, setDuration] = useState(0)
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [loop, setLoop] = useState(false)
  const rAF = useRef<number | null>(null)

  /* === 믹서(볼륨/뮤트) === */
  const [midiVol, setMidiVol] = useState(0.9)
  const [bassVol, setBassVol] = useState(1.0)
  const [playMidi, setPlayMidi] = useState(true)
  const [playBass, setPlayBass] = useState(true)

  /* === 합치기 결과(URL 객체) === */
  const [mergedUrl, setMergedUrl] = useState<string | null>(null)

  /** MIDI 파일 선택 핸들러
   *  1) 로컬에서 MIDI 파싱 → 트랙 메타 추출
   *  2) 서버에 업로드/렌더 → wavUrl 확보(FluidSynth)
   *  3) wavUrl을 AudioBuffer로 디코드 → 오프라인 믹스에 사용
   */
  async function handleMidiFile(file: File) {
    setMidiFile(file)
    setMidiAudioUrl(null)
    setMidiBuffer(null)
    setMergedUrl(null)
    setMidiTracks([])

    setRendering(true)
    try {
      // (A) 메타 파싱(클라이언트)
      const arr = await file.arrayBuffer()
      const midi = new Midi(arr)
      const tks: TrackMeta[] = midi.tracks.map(t => ({
        name: t.name || '(no name)',
        channel: t.channel,
        instrument:
          t.instrument?.name ??
          (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
        notes: t.notes.length,
      }))
      setMidiTracks(tks)

      // (B) 서버 렌더(FluidSynth) → 정확한 GM 사운드로 WAV URL 획득
      const { wavUrl } = await renderMidiOnServer(file)
      setMidiAudioUrl(wavUrl)

      // (C) 믹싱을 위해 브라우저에서 AudioBuffer로 디코드
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const wavArr = await (await fetch(wavUrl)).arrayBuffer()
      const buf = await ctx.decodeAudioData(wavArr.slice(0))
      await ctx.close()
      setMidiBuffer(buf)
    } finally {
      setRendering(false)
    }
  }

  /** 볼륨/뮤트/루프 상태를 <audio>에 반영 */
  function syncVolumesAndMutes() {
    if (midiEl.current) {
      midiEl.current.volume = midiVol
      midiEl.current.muted = !playMidi
      midiEl.current.loop = loop
    }
    if (bassEl.current) {
      bassEl.current.volume = bassVol
      bassEl.current.muted = !playBass
      bassEl.current.loop = loop
    }
  }

  /** 트랜스포트: 재생/일시정지/정지/시크/타임라인 업데이트 */
  function tick() {
    const t = Math.max(midiEl.current?.currentTime ?? 0, bassEl.current?.currentTime ?? 0)
    setPosition(t)
    rAF.current = requestAnimationFrame(tick)
  }
  function play() {
    // 둘 중 하나만 있어도 재생 가능
    midiEl.current?.play().catch(() => {})
    bassEl.current?.play().catch(() => {})
    setPlaying(true)
    if (!rAF.current) tick()
  }
  function pause() {
    midiEl.current?.pause()
    bassEl.current?.pause()
    setPlaying(false)
    if (rAF.current) { cancelAnimationFrame(rAF.current); rAF.current = null }
  }
  function stopAll() {
    pause()
    if (midiEl.current) midiEl.current.currentTime = 0
    if (bassEl.current) bassEl.current.currentTime = 0
    setPosition(0)
  }
  function seek(sec: number) {
    if (midiEl.current) midiEl.current.currentTime = sec
    if (bassEl.current) bassEl.current.currentTime = sec
    setPosition(sec)
  }

  /** 재생 길이 최신화 & 끝났을 때 처리 */
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
  }, [midiAudioUrl, blobUrl, loop])

  /** 볼륨/뮤트/루프 변경 반영 */
  useEffect(() => { syncVolumesAndMutes() }, [midiVol, bassVol, playMidi, playBass, loop, midiAudioUrl, blobUrl])

  /** 합치기 → 오프라인 믹스 → WAV 다운로드 */
  async function mergeAndExport() {
    if (!midiBuffer || !blobUrl) return
    if (mergedUrl) URL.revokeObjectURL(mergedUrl)
    setMergedUrl(null)

    // 녹음된 베이스를 AudioBuffer로 변환
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const arr = await (await fetch(blobUrl)).arrayBuffer()
    const bassBuf = await ctx.decodeAudioData(arr.slice(0))
    await ctx.close()

    // 오프라인 믹스(둘 다 48k로 맞춰 렌더 → 클릭 방지용 짧은 페이드아웃)
    const mixed = await mixBuffersToAudioBuffer(midiBuffer, bassBuf, { sampleRate: 48000, fadeOutSec: 0.03 })
    const wav = audioBufferToWavBlob(mixed)
    const url = URL.createObjectURL(wav)
    setMergedUrl(url)
  }

  /** 언마운트 시 ObjectURL 정리(합친 결과만 우리가 생성) */
  useEffect(() => {
    return () => { if (mergedUrl) URL.revokeObjectURL(mergedUrl) }
  }, [mergedUrl])

  return (
    <div className="pmx-wrap">
      {/* === 입력 장치 === */}
      <section className="pmx-panel">
        <h3>🎛 입력 장치</h3>
        <div className="row">
          <DeviceSelect value={deviceId} onChange={setDeviceId} />
          <button
            className="btn"
            onClick={async ()=>{ await navigator.mediaDevices.getUserMedia({ audio: true }) }}
            title="브라우저 마이크 권한 요청"
          >🎤 마이크 권한</button>
        </div>
        {recErr && <div className="warn">녹음 오류: {recErr}</div>}
      </section>

      {/* === MIDI === */}
      <section className="pmx-panel">
        <h3>🎼 MIDI 파일</h3>
        <div className="row">
          <label className="file">
            <input
              type="file"
              accept=".mid,.midi"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleMidiFile(f) }}
            />
            <span>파일 선택</span>
          </label>
          {midiFile && <span className="hint">{midiFile.name}</span>}
          {rendering && <span className="hint">서버 렌더링 중…</span>}
        </div>

        {midiTracks.length > 0 && (
          <details className="tracks">
            <summary>트랙 정보 보기</summary>
            <ul>
              {midiTracks.map((t, i) => (
                <li key={i}>
                  <strong>{t.name}</strong>
                  <span className="thin">({t.instrument ?? 'inst'}, ch {t.channel ?? '-'})</span>
                  <span className="thin"> • notes: {t.notes}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      {/* === 베이스 녹음 === */}
      <section className="pmx-panel">
        <h3>🎙 베이스 녹음</h3>
        <div className="row">
          {!recording
            ? <button className="btn primary" onClick={start}>● 녹음 시작</button>
            : <button className="btn danger" onClick={stop}>■ 정지</button>}
        </div>
      </section>

      {/* === 트랜스포트 & 믹서 === */}
      <section className="pmx-panel">
        <h3>▶︎ 트랜스포트 & 믹서</h3>

        {/* 채널별 오디오 요소(이 엘리먼트가 재생을 담당) */}
        <div className="mixer">
          <div className="ch">
            <div className="ch-title">MIDI</div>
            <div className="row">
              <label className="row">
                <input type="checkbox" checked={playMidi} onChange={e=>setPlayMidi(e.target.checked)} /> 재생
              </label>
            </div>
            <div className="col">
              <input type="range" min={0} max={1} step={0.01} value={midiVol} onChange={e=>setMidiVol(Number(e.target.value))}/>
              <div className="hint">볼륨 {Math.round(midiVol*100)}%</div>
            </div>
            <div className="preview">
              <audio ref={midiEl} src={midiAudioUrl ?? undefined} preload="metadata" controls />
            </div>
          </div>

          <div className="ch">
            <div className="ch-title">Bass</div>
            <div className="row">
              <label className="row">
                <input type="checkbox" checked={playBass} onChange={e=>setPlayBass(e.target.checked)} /> 재생
              </label>
            </div>
            <div className="col">
              <input type="range" min={0} max={1} step={0.01} value={bassVol} onChange={e=>setBassVol(Number(e.target.value))}/>
              <div className="hint">볼륨 {Math.round(bassVol*100)}%</div>
            </div>
            <div className="preview">
              <audio ref={bassEl} src={blobUrl ?? undefined} preload="metadata" controls />
            </div>
          </div>
        </div>

        {/* 트랜스포트 */}
        <div className="transport" style={{marginTop:12}}>
          <button className="btn" onClick={playing ? pause : play} disabled={!midiAudioUrl && !blobUrl}>
            {playing ? '⏸ 일시정지' : '▶︎ 재생'}
          </button>
          <button className="btn" onClick={stopAll}>⏹ 정지</button>
          <label className="row" style={{gap:8}}>
            <input
              type="range"
              min={0}
              max={Math.max(duration, 0.001)}
              step={0.01}
              value={position}
              onChange={e => seek(Number(e.target.value))}
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

      {/* === 합치기 === */}
      <section className="pmx-panel">
        <h3>⬇️ 합치기 & 다운로드</h3>
        <button className="btn" onClick={mergeAndExport} disabled={!midiBuffer || !blobUrl}>
          음원 합치기(WAV 생성)
        </button>
        {mergedUrl && (
          <div className="result">
            <audio src={mergedUrl} controls />
            <div>
              <a className="btn" href={mergedUrl} download={makeDownloadName(midiFile?.name)}>
                ⬇ 합친 결과 다운로드 (WAV)
              </a>
            </div>
          </div>
        )}
        <div className="tiny">* 표준 .mid에는 오디오가 포함되지 않으므로 합친 결과는 WAV로 제공합니다.</div>
      </section>
    </div>
  )
}

/* === 소도구 === */
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