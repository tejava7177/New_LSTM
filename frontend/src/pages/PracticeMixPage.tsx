// src/pages/PracticeMixPage.tsx
import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { audioBufferToWavBlob } from '../utils/wav'
import { mixBuffersToAudioBuffer } from '../lib/mixdown'
import { Midi } from '@tonejs/midi'
import { renderMidiOnServer } from '../lib/midiServer'

type TrackMeta = { name: string; channel?: number; instrument?: string; notes: number }

// NEW: 코드 힌트용 타입(마커에서 추출)
type ChordCue = { time: number; text: string }

export default function PracticeMixPage() {
  /* ========== 입력 장치 & 녹음 ========== */
  const [deviceId, setDeviceId] = useState<string>('')
  const { recording, blobUrl, start, stop, error: recErr } = useMediaRecorder(deviceId || undefined)

  /* ========== MIDI 로딩 & 렌더링 ========== */
  const [midiFile, setMidiFile] = useState<File | null>(null)
  const [midiAudioUrl, setMidiAudioUrl] = useState<string | null>(null) // 서버 렌더 WAV
  const [midiBuffer, setMidiBuffer] = useState<AudioBuffer | null>(null) // 믹싱용
  const [midiTracks, setMidiTracks] = useState<TrackMeta[]>([])
  const [rendering, setRendering] = useState(false)

  // NEW: MIDI 메타(템포/박자) + 코드 마커
  const [tempoBpm, setTempoBpm] = useState<number>(100)
  const [timeSig, setTimeSig] = useState<[number, number]>([4, 4])
  const [chordCues, setChordCues] = useState<ChordCue[]>([])

  /* ========== 플레이어/트랜스포트 ========== */
  const midiEl = useRef<HTMLAudioElement>(null)
  const bassEl = useRef<HTMLAudioElement>(null)
  const [duration, setDuration] = useState(0)
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(false)
  const rAF = useRef<number | null>(null)

  /* ========== 믹서 컨트롤 ========== */
  const [midiVol, setMidiVol] = useState(0.9)
  const [bassVol, setBassVol] = useState(1.0)
  const [playMidi, setPlayMidi] = useState(true)
  const [playBass, setPlayBass] = useState(true)
  const [loop, setLoop] = useState(false)

  /* ========== 합치기 결과 ========== */
  const [mergedUrl, setMergedUrl] = useState<string | null>(null)

  /* ========== 녹음 UX 옵션 ========== */
  // NEW: “베이스만 녹음” 토글 & 카운트인 길이(4박)
  const [bassOnly, setBassOnly] = useState(false)
  const COUNTIN_BEATS = 4

  // NEW: 현재/다음 코드 힌트
  const [nowChord, setNowChord] = useState<string>('')
  const [nextChord, setNextChord] = useState<string>('')

  /* ========== MIDI 선택 → 서버 렌더 + 메타 추출 + 브라우저 디코드 ========== */
  async function handleMidiFile(file: File) {
    setMidiFile(file)
    setMidiAudioUrl(null)
    setMidiBuffer(null)
    setMergedUrl(null)
    setMidiTracks([])
    setChordCues([])

    setRendering(true)
    try {
      // (A) 클라이언트에서 메타 파싱(템포/박자/트랙/마커)
      const arr = await file.arrayBuffer()
      const midi = new Midi(arr)

      // 템포(첫 항목) & 박자(첫 항목)
      const bpm = midi.header.tempos?.[0]?.bpm ?? 100

      // timeSignature를 안전하게 튜플로 캐스팅
      const tsArr = midi.header.timeSignatures?.[0]?.timeSignature as number[] | undefined
      const tsTuple: [number, number] = (Array.isArray(tsArr) && tsArr.length >= 2)
        ? [tsArr[0], tsArr[1]]
        : [4, 4]
      setTimeSig(tsTuple)

      // 트랙 메타
      const tks: TrackMeta[] = midi.tracks.map(t => ({
        name: t.name || '(no name)',
        channel: t.channel,
        instrument:
          t.instrument?.name ||
          (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
        notes: t.notes.length,
      }))
      setMidiTracks(tks)

      // 코드 마커 추출(가능한 경우만)
      // - 트랙명에 'chord' 포함 or meta text/marker 이벤트에서 텍스트
      const cues: ChordCue[] = []
      midi.tracks.forEach(t => {
        const lower = (t.name || '').toLowerCase()
        const rawEvents = (t as any).events as any[] | undefined
        if (!rawEvents) return
        if (lower.includes('chord') || lower.includes('guide') || lower.includes('marker')) {
          rawEvents.forEach(ev => {
            if (ev.type === 'meta' && (ev.subtype === 'marker' || ev.subtype === 'text')) {
              const txt = (ev.text || '').trim()
              if (txt) {
                const time = midi.header.ticksToSeconds(ev.ticks || 0)
                cues.push({ time, text: txt })
              }
            }
          })
        }
      })
      cues.sort((a, b) => a.time - b.time)
      setChordCues(cues)

      // (B) 서버 FluidSynth로 WAV 렌더
      const { wavUrl } = await renderMidiOnServer(file)
      setMidiAudioUrl(wavUrl)

      // (C) 믹싱용 AudioBuffer로 디코드
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const wavArr = await (await fetch(wavUrl)).arrayBuffer()
      const buf = await ctx.decodeAudioData(wavArr.slice(0))
      await ctx.close()
      setMidiBuffer(buf)
    } finally {
      setRendering(false)
    }
  }

  /* ========== 메트로놈(카운트인) ========== */
  // NEW: WebAudio로 4박 카운트인을 재생하는 함수
  async function playCountIn(beats: number, bpm: number) {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const beat = 60 / Math.max(40, Math.min(300, bpm))
    const t0 = ctx.currentTime + 0.05
    for (let i = 0; i < beats; i++) {
      const osc = ctx.createOscillator()
      const g = ctx.createGain()
      osc.type = 'sine'
      // 1박은 높은 피치, 나머지는 낮은 피치
      osc.frequency.value = i === 0 ? 1200 : 800
      g.gain.value = 0
      osc.connect(g).connect(ctx.destination)
      const ts = t0 + i * beat
      g.gain.setValueAtTime(0, ts)
      g.gain.linearRampToValueAtTime(0.8, ts + 0.01)
      g.gain.exponentialRampToValueAtTime(0.0001, ts + 0.15)
      osc.start(ts)
      osc.stop(ts + 0.2)
    }
    // 카운트인이 끝나는 시점을 반환
    return new Promise<number>(resolve => {
      const endAt = t0 + beats * beat
      const timer = setTimeout(() => {
        ctx.close().finally(() => resolve(endAt))
      }, Math.ceil((endAt - ctx.currentTime) * 1000) + 10)
    })
  }

  /* ========== 녹음: 카운트인 후 동시 시작 ========== */
  // NEW: “녹음 시작” 버튼에 연결
  async function startRecordingFlow() {
    if (!midiAudioUrl && !bassOnly) {
      alert('MIDI 파일을 먼저 선택하세요.')
      return
    }

    // 1) 녹음 먼저 시작(카운트인도 녹음에 들어가도 무방; 헤드폰 권장)
    if (!recording) start()

    // 2) 카운트인 4박
    await playCountIn(COUNTIN_BEATS, tempoBpm)

    // 3) 카운트인 종료 시점에 동시 시작
    if (!bassOnly && midiEl.current) {
      midiEl.current.currentTime = 0
      midiEl.current.play().catch(() => {})
    }
    // 베이스 모니터 재생은 사용자가 컨트롤러에서 결정
    setPlaying(true)
    if (!rAF.current) tick()
  }

  /* ========== 재생/정지/동기화 ========== */
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
  function tick() {
    const t = Math.max(midiEl.current?.currentTime ?? 0, bassEl.current?.currentTime ?? 0)
    setPosition(t)
    // NEW: 코드 힌트 갱신
    if (chordCues.length > 0) {
      const idx = chordCues.findIndex((c, i) => t >= c.time && (i === chordCues.length - 1 || t < chordCues[i + 1].time))
      if (idx >= 0) {
        setNowChord(chordCues[idx].text)
        setNextChord(chordCues[idx + 1]?.text ?? '')
      }
    }
    rAF.current = requestAnimationFrame(tick)
  }
  function play() {
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
    setNowChord(''); setNextChord('')
  }
  function seek(sec: number) {
    if (midiEl.current) midiEl.current.currentTime = sec
    if (bassEl.current) bassEl.current.currentTime = sec
    setPosition(sec)
  }

  // duration 업데이트 & 끝 처리
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

  useEffect(() => { syncVolumesAndMutes() },
    [midiVol, bassVol, playMidi, playBass, loop, midiAudioUrl, blobUrl])

  /* ========== 합치기(WAV) ========== */
  async function mergeAndExport() {
    if (!midiBuffer || !blobUrl) return
    if (mergedUrl) URL.revokeObjectURL(mergedUrl)
    setMergedUrl(null)

    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const arr = await (await fetch(blobUrl)).arrayBuffer()
    const bassBuf = await ctx.decodeAudioData(arr.slice(0))
    await ctx.close()

    const mixed = await mixBuffersToAudioBuffer(midiBuffer, bassBuf, { sampleRate: 48000, fadeOutSec: 0.03 })
    const wav = audioBufferToWavBlob(mixed)
    const url = URL.createObjectURL(wav)
    setMergedUrl(url)
  }

  useEffect(() => {
    return () => { if (mergedUrl) URL.revokeObjectURL(mergedUrl) }
  }, [mergedUrl])

  /* ========== 렌더 ========== */
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

      {/* MIDI 파일 (미리듣기 + 트랙/템포/코드 정보) */}
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

        {/* 음원 미리듣기 */}
        <div className="preview" style={{marginTop:8}}>
          {midiAudioUrl ? <audio src={midiAudioUrl} controls /> : <div className="thin">파일을 선택하세요</div>}
        </div>

        {/* 트랙/메타/코드 정보 */}
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
              <div className="thin" style={{marginTop:6}}>
                코드 마커 {chordCues.length}개 감지됨 (재생 중 아래 힌트에 표시)
              </div>
            )}
          </details>
        )}
      </section>

      {/* 베이스 녹음 (카운트인/옵션) */}
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

        {/* 코드 힌트 라인 */}
        {chordCues.length > 0 && (
          <div style={{marginTop:8, padding:'6px 8px', background:'#f7f7f9', border:'1px solid #eee', borderRadius:6}}>
            <strong>코드 힌트:</strong>{' '}
            {nowChord ? <span>{nowChord}</span> : <span className="thin">대기 중…</span>}
            {nextChord && <span className="thin">  →  다음: {nextChord}</span>}
          </div>
        )}
      </section>

      {/* 트랜스포트 & 믹서 (기존 유지) */}
      <section className="pmx-panel">
        <h3>▶︎ 트랜스포트 & 믹서</h3>

        {/* 숨김 플레이어 요소(트랜스포트가 제어) */}
        <audio ref={midiEl} src={midiAudioUrl ?? undefined} preload="metadata" />
        <audio ref={bassEl} src={blobUrl ?? undefined} preload="metadata" />

        <div className="mixer">
          <div className="ch">
            <div className="ch-title">MIDI</div>
            <div className="row">
              <label className="row"><input type="checkbox" checked={playMidi} onChange={e=>setPlayMidi(e.target.checked)} /> 재생</label>
            </div>
            <div className="col">
              <input type="range" min={0} max={1} step={0.01} value={midiVol} onChange={e=>setMidiVol(Number(e.target.value))}/>
              <div className="hint">볼륨 {Math.round(midiVol*100)}%</div>
            </div>
            <div className="preview">
              {midiAudioUrl ? <audio src={midiAudioUrl} controls /> : <div className="thin">파일을 선택하세요</div>}
            </div>
          </div>

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
              {blobUrl ? <audio src={blobUrl} controls /> : <div className="thin">녹음 후 재생 가능</div>}
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
        <button className="btn" onClick={mergeAndExport} disabled={!midiBuffer || !blobUrl}>
          음원 합치기(WAV 생성)
        </button>
        {mergedUrl && (
          <div className="result">
            <audio src={mergedUrl} controls />
            <div><a className="btn" href={mergedUrl} download={makeDownloadName(midiFile?.name)}>⬇ 합친 결과 다운로드 (WAV)</a></div>
          </div>
        )}
        <div className="tiny">* 표준 .mid에는 오디오가 포함되지 않으므로 합친 결과는 WAV로 제공합니다.</div>
      </section>
    </div>
  )
}

/* ====== 유틸 ====== */
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