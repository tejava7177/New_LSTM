import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { audioBufferToWavBlob } from '../utils/wav'
import { mixBuffersToAudioBuffer } from '../lib/mixdown'
import { Midi } from '@tonejs/midi'
import { renderMidiOnServer } from '../lib/midiServer'

type TrackMeta = { name: string; channel?: number; instrument?: string; notes: number }
type ChordCue = { time: number; text: string }

export default function PracticeMixPage() {
  /* ===== 입력 장치 & 녹음 ===== */
  const [deviceId, setDeviceId] = useState<string>('')
  const { recording, blobUrl, start, stop, error: recErr } = useMediaRecorder(deviceId || undefined)

  /* ===== MIDI 로딩/렌더링 ===== */
  const [midiFile, setMidiFile] = useState<File | null>(null)
  const [midiAudioUrl, setMidiAudioUrl] = useState<string | null>(null) // 서버 WAV
  const [midiBuffer, setMidiBuffer] = useState<AudioBuffer | null>(null) // 믹싱용
  const [midiTracks, setMidiTracks] = useState<TrackMeta[]>([])
  const [rendering, setRendering] = useState(false)

  // 메타정보(템포/박자) & 코드 마커
  const [tempoBpm, setTempoBpm] = useState<number>(100)
  const [timeSig, setTimeSig] = useState<[number, number]>([4, 4])
  const [chordCues, setChordCues] = useState<ChordCue[]>([])

  /* ===== 플레이어/트랜스포트 ===== */
  const midiEl = useRef<HTMLAudioElement>(null)
  const bassEl = useRef<HTMLAudioElement>(null)
  const [duration, setDuration] = useState(0)
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(false)
  const rAF = useRef<number | null>(null)

  /* ===== 믹서 컨트롤 ===== */
  const [midiVol, setMidiVol] = useState(0.9)
  const [bassVol, setBassVol] = useState(1.0)
  const [playMidi, setPlayMidi] = useState(true)
  const [playBass, setPlayBass] = useState(true)
  const [loop, setLoop] = useState(false)

  /* ===== 합치기 결과 ===== */
  const [mergedUrl, setMergedUrl] = useState<string | null>(null)

  /* ===== 녹음 UX 옵션 ===== */
  const [bassOnly, setBassOnly] = useState(false) // 베이스만 녹음(미디 미재생)
  const COUNTIN_BEATS = 4
  const [nowChord, setNowChord] = useState<string>('')   // 현재 코드
  const [nextChord, setNextChord] = useState<string>('') // 다음 코드

  /* ===== 베이스 트리밍(카운트인 제거) ===== */
  const [bassTrimUrl, setBassTrimUrl] = useState<string | null>(null)
  const [bassBuffer, setBassBuffer] = useState<AudioBuffer | null>(null)

  // blobUrl(원본 녹음)이 생기면 → 템포 기반으로 카운트인(4박) 만큼 앞을 잘라서 새 URL/버퍼 생성
  useEffect(() => {
    let revoked: string | null = null
    ;(async () => {
      if (!blobUrl) { setBassTrimUrl(null); setBassBuffer(null); return }
      try {
        // 1) 원본 디코드
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
        const arr = await (await fetch(blobUrl)).arrayBuffer()
        const src = await ctx.decodeAudioData(arr.slice(0))

        // 2) 트리밍 구간 계산(4박)
        const offsetSec = COUNTIN_BEATS * 60 / Math.max(40, Math.min(300, tempoBpm))
        const sr = src.sampleRate
        const startSample = Math.floor(offsetSec * sr)
        const totalSamples = src.length
        const trimLen = Math.max(0, totalSamples - startSample)

        // 3) 앞부분 제거된 새 버퍼 생성
        const out = ctx.createBuffer(src.numberOfChannels, trimLen, sr)
        for (let ch = 0; ch < src.numberOfChannels; ch++) {
          const srcData = src.getChannelData(ch)
          const dstData = out.getChannelData(ch)
          dstData.set(srcData.subarray(startSample))
        }
        await ctx.close()

        // 4) 미리듣기용 URL & 믹싱용 버퍼 업데이트
        const wavBlob = audioBufferToWavBlob(out)
        const url = URL.createObjectURL(wavBlob)
        setBassTrimUrl(url)
        setBassBuffer(out)
        revoked = url
      } catch (e) {
        console.warn('trim bass failed:', e)
        setBassTrimUrl(null)
        setBassBuffer(null)
      }
    })()
    return () => {
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [blobUrl, tempoBpm])

  /* ================= MIDI 선택 → 서버 렌더 + 메타 추출 + 디코드 ================= */
  async function handleMidiFile(file: File) {
    setMidiFile(file)
    setMidiAudioUrl(null)
    setMidiBuffer(null)
    setMergedUrl(null)
    setMidiTracks([])
    setChordCues([])

    setRendering(true)
    try {
      // (A) 클라에서 메타 추출(템포/박자/트랙/마커)
      const arr = await file.arrayBuffer()
      const midi = new Midi(arr)

      const bpm = midi.header.tempos?.[0]?.bpm ?? 100
      setTempoBpm(bpm)

      const tsArr = midi.header.timeSignatures?.[0]?.timeSignature as number[] | undefined
      const ts: [number, number] = (Array.isArray(tsArr) && tsArr.length >= 2) ? [tsArr[0], tsArr[1]] : [4, 4]
      setTimeSig(ts)

      const tks: TrackMeta[] = midi.tracks.map(t => ({
        name: t.name || '(no name)',
        channel: t.channel,
        instrument: t.instrument?.name || (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
        notes: t.notes.length,
      }))
      setMidiTracks(tks)

      // 코드 마커(트랙명: chord/guide, 메타 marker/text)
      const cues: ChordCue[] = []
      midi.tracks.forEach(t => {
        const lower = (t.name || '').toLowerCase()
        const raw = (t as any).events as any[] | undefined
        if (!raw) return
        if (lower.includes('chord') || lower.includes('guide') || lower.includes('marker')) {
          raw.forEach(ev => {
            if (ev.type === 'meta' && (ev.subtype === 'marker' || ev.subtype === 'text')) {
              const txt = (ev.text || '').trim()
              if (txt) cues.push({ time: midi.header.ticksToSeconds(ev.ticks || 0), text: txt })
            }
          })
        }
      })
      cues.sort((a,b) => a.time - b.time)
      setChordCues(cues)

      // (B) 서버에서 FluidSynth로 WAV 렌더
      const { wavUrl } = await renderMidiOnServer(file)
      setMidiAudioUrl(wavUrl)

      // (C) 믹싱용 Buffer 로 디코드
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const wavArr = await (await fetch(wavUrl)).arrayBuffer()
      const buf = await ctx.decodeAudioData(wavArr.slice(0))
      await ctx.close()
      setMidiBuffer(buf)
    } finally {
      setRendering(false)
    }
  }

  /* ================= 카운트인(4박) ================= */
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
      osc.start(ts)
      osc.stop(ts + 0.2)
    }
    return new Promise<void>((resolve) => {
      const endAt = t0 + beats * beat
      const ms = Math.ceil((endAt - ctx.currentTime) * 1000) + 10
      setTimeout(() => { ctx.close().finally(()=>resolve()) }, ms)
    })
  }

  /* ================= 재생 잠금 해제(오토플레이 정책) ================= */
  async function ensureUnlocked() {
    const el = midiEl.current
    if (!el) return
    const wasMuted = el.muted
    el.muted = true
    try {
      await el.play().catch(()=>{})
      el.pause()
    } finally {
      el.muted = wasMuted
    }
  }

  /* ================= 녹음 시작(카운트인 후 동시 스타트) ================= */
  async function startRecordingFlow() {
    if (!midiAudioUrl && !bassOnly) {
      alert('MIDI 파일을 먼저 선택하세요.')
      return
    }
    if (!recording) await start()
    await ensureUnlocked()
    await playCountIn(COUNTIN_BEATS, tempoBpm)

    if (!bassOnly && midiEl.current) {
      midiEl.current.currentTime = 0
      midiEl.current.play().catch(()=>{})
    }
    setPlaying(true)
    if (!rAF.current) tick()
  }

  /* ================= 트랜스포트 & 동기 ================= */
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
    if (chordCues.length > 0) {
      const i = chordCues.findIndex((c, idx) => t >= c.time && (idx === chordCues.length - 1 || t < chordCues[idx + 1].time))
      if (i >= 0) {
        setNowChord(chordCues[i].text)
        setNextChord(chordCues[i + 1]?.text ?? '')
      }
    }
    rAF.current = requestAnimationFrame(tick)
  }
  function play() {
    midiEl.current?.play().catch(()=>{})
    bassEl.current?.play().catch(()=>{})
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

  // duration/ended 바인딩
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

  useEffect(() => { syncVolumesAndMutes() },
    [midiVol, bassVol, playMidi, playBass, loop, midiAudioUrl, bassTrimUrl])

  /* ================= 합치기(WAV) ================= */
  async function mergeAndExport() {
    if (!midiBuffer) return
    if (mergedUrl) URL.revokeObjectURL(mergedUrl)
    setMergedUrl(null)

    // 베이스: 트리밍된 버퍼가 있으면 그걸 사용 (없으면 녹음 원본을 트리밍해서라도 사용)
    let bass: AudioBuffer | null = bassBuffer
    if (!bass && blobUrl) {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const arr = await (await fetch(blobUrl)).arrayBuffer()
      const src = await ctx.decodeAudioData(arr.slice(0))
      const offsetSec = COUNTIN_BEATS * 60 / Math.max(40, Math.min(300, tempoBpm))
      const sr = src.sampleRate
      const startSample = Math.floor(offsetSec * sr)
      const trimLen = Math.max(0, src.length - startSample)
      const out = ctx.createBuffer(src.numberOfChannels, trimLen, sr)
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

  useEffect(() => {
    return () => { if (mergedUrl) URL.revokeObjectURL(mergedUrl) }
  }, [mergedUrl])

  /* ================= 렌더 ================= */
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
            <input type="file" accept=".mid,.midi"
                   onChange={e => { const f = e.target.files?.[0]; if (f) handleMidiFile(f) }} />
            <span>파일 선택</span>
          </label>
          {midiFile && <span className="hint">{midiFile.name}</span>}
          {rendering && <span className="hint">서버 렌더링 중…</span>}
        </div>

        {/* 음원 미리듣기(= 트랜스포트 대상) */}
        <div className="preview" style={{marginTop:8}}>
          {midiAudioUrl
            ? <audio ref={midiEl} src={midiAudioUrl} preload="metadata" controls
                     onLoadedMetadata={()=>syncVolumesAndMutes()}
                     onPlay={()=>syncVolumesAndMutes()}
                     onError={(e)=>console.warn('MIDI audio error', e)} />
            : <div className="thin">파일을 선택하세요</div>}
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
              <div className="thin" style={{marginTop:6}}>
                코드 마커 {chordCues.length}개 감지됨 (재생 중 아래 힌트에 표시)
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

        {/* 코드 힌트 */}
        {chordCues.length > 0 && (
          <div style={{marginTop:8, padding:'6px 8px', background:'#f7f7f9', border:'1px solid #eee', borderRadius:6}}>
            <strong>코드 힌트:</strong>{' '}
            {nowChord ? <span>{nowChord}</span> : <span className="thin">대기 중…</span>}
            {nextChord && <span className="thin">  →  다음: {nextChord}</span>}
          </div>
        )}
      </section>

      {/* Bass 미리듣기 & 믹서 */}
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
                         onLoadedMetadata={()=>syncVolumesAndMutes()}
                         onPlay={()=>syncVolumesAndMutes()}
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