// frontend/src/pages/PracticeMixPage.tsx
import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import DeviceSelect from '../components/DeviceSelect'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { audioBufferToWavBlob } from '../utils/wav'
import { mixBuffersToAudioBuffer } from '../lib/mixdown'
import { Midi } from '@tonejs/midi'
import { renderMidiOnServer } from '../lib/midiServer'
import { midiUrl, wavUrl } from '../lib/tracks'
import { extractChordCuesFromMidi, getNowNextChord, ChordCue } from '../lib/midiCues'
import Accordion from '../components/Accordion'

import ChordTimeline from '../components/ChordTimeline'
import DialKnob from '../components/DialKnob'
import { useAmp } from '../hooks/useAmp'
import { trimPreRollFromBlobUrl } from '../utils/audioTrim'
//import LiveScrollWave from '../components/LiveScrollWave';
import ScrollRecordWave from '../components/ScrollRecordWave';

type TrackMeta = { name: string; channel?: number; instrument?: string; notes: number }
type NavState = {
  source?: 'predict' | 'manual';
  jobId?: string;
  progression?: string[];
  tempo?: number;
  timeSig?: [number, number];
  preRollBeats?: number;
  barsPerChord?: number;
  midiUrl?: string;
  wavUrl?: string;
}

export default function PracticeMixPage() {
  /* ===== 라우터 state ===== */
  const { state } = useLocation()
  const navState = (state as NavState) || {}

  /* ===== 입력 & 녹음 ===== */
  const [deviceId, setDeviceId] = useState<string>('')

  // AMP 먼저 생성 (녹음 입력을 AMP 출력으로 보낼 수 있게 준비)
  const amp = useAmp(deviceId || undefined)


  // useMediaRecorder 훅 (이름 충돌 방지를 위해 start/stop 별칭)
  // 2) 그 다음에 useMediaRecorder
const {
  recording, blobUrl, start: startRec, stop: stopRec, error: recErr, recordStream
} = useMediaRecorder(deviceId || undefined, {
  // AMP가 켜져 있으면 AMP 출력 스트림을 녹음 대상으로 사용
  inputStream: amp.enabled ? (amp.outputStream ?? undefined) : undefined,
  channelMode: 'dual-mono',
});


  /* ===== MIDI 로딩 & 렌더링 ===== */
  const [midiFile, setMidiFile] = useState<File | null>(null)
  const [midiAudioUrl, setMidiAudioUrl] = useState<string | null>(null)
  const [midiBuffer, setMidiBuffer] = useState<AudioBuffer | null>(null)
  const [midiTracks, setMidiTracks] = useState<TrackMeta[]>([])
  const [rendering, setRendering] = useState(false)

  /* 메타 */
  const [tempoBpm, setTempoBpm] = useState<number>(navState.tempo ?? 100)
  const [timeSig, setTimeSig] = useState<[number, number]>(navState.timeSig ?? [4, 4])

  /* 코드 큐 */
  const [chordCues, setChordCues] = useState<ChordCue[]>([])
  const [nowChord, setNowChord] = useState('')
  const [nextChord, setNextChord] = useState('')

  /* 플레이어/트랜스포트 */
  const midiEl = useRef<HTMLAudioElement>(null)
  const bassEl = useRef<HTMLAudioElement>(null)
  const [duration, setDuration] = useState(0)
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(false)
  const rafRef = useRef<number | null>(null)
  const transportStartAt = useRef<number | null>(null)

  /* 믹서 */
  const [midiVol, setMidiVol] = useState(0.9)
  const [bassVol, setBassVol] = useState(1.0)
  const [playMidi, setPlayMidi] = useState(true)
  const [playBass, setPlayBass] = useState(true)
  const [loop, setLoop] = useState(false)


  /* 합치기 */
  const [mergedUrl, setMergedUrl] = useState<string | null>(null)

  /* UX */
  const COUNTIN_BEATS = navState.preRollBeats ?? 4
  const [bassOnly, setBassOnly] = useState(false)
  const [countInLeft, setCountInLeft] = useState<number | null>(null)

  /* 베이스 트리밍(카운트인 제거) */
  const [bassTrimUrl, setBassTrimUrl] = useState<string | null>(null)
  const [bassBuffer, setBassBuffer] = useState<AudioBuffer | null>(null)
  const beatSec = useMemo(() => 60 / Math.max(40, Math.min(300, tempoBpm)), [tempoBpm])
  const preRollSec = useMemo(() => beatSec * COUNTIN_BEATS, [beatSec, COUNTIN_BEATS])

  /* ===== 녹음본 → 프리롤만큼 자르기 (util로 분리) ===== */
  useEffect(() => {
    let revoke: string | null = null
    ;(async () => {
      if (!blobUrl) { setBassTrimUrl(null); setBassBuffer(null); return }
      try {
        const { url, buffer } = await trimPreRollFromBlobUrl(blobUrl, preRollSec)
        setBassTrimUrl(url); setBassBuffer(buffer); revoke = url
      } catch {
        setBassTrimUrl(null); setBassBuffer(null)
      }
    })()
    return () => { if (revoke) URL.revokeObjectURL(revoke) }
  }, [blobUrl, preRollSec])

  /* ===== progression → 큐 계산(fallback) ===== */
  function buildCuesFromProgression(prog: string[], barsPerChord = 1): ChordCue[] {
    const beatsPerBar = timeSig?.[0] ?? 4
    const secPerBar = beatsPerBar * beatSec
    let t = 0
    return prog.map(text => {
      const cue = { text, time: t }
      t += secPerBar * Math.max(1, barsPerChord)
      return cue
    })
  }

  /* ===== 생성 트랙에서 자동 부팅 ===== */
  useEffect(() => {
    async function bootstrapFromGeneratedJob(jobId: string) {
      try {
        const midiArr = await (await fetch(navState.midiUrl ?? midiUrl(jobId))).arrayBuffer()
        const cues = await extractChordCuesFromMidi(midiArr, { preRollSec: 0, windowBeats: 1 })
        if (cues.length) setChordCues(cues)

        const midi = new Midi(midiArr)
        setTempoBpm(navState.tempo ?? (midi.header.tempos?.[0]?.bpm ?? tempoBpm))
        const ts = (midi.header.timeSignatures?.[0]?.timeSignature as number[]) || [4, 4]
        setTimeSig([ts[0] ?? 4, ts[1] ?? 4])
        setMidiTracks(midi.tracks.map(t => ({
          name: t.name || '(no name)',
          channel: t.channel,
          instrument: t.instrument?.name || (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
          notes: t.notes.length,
        })))
      } catch {}

      const wurl = navState.wavUrl ?? wavUrl(jobId)
      setMidiAudioUrl(wurl)
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      try {
        const wArr = await (await fetch(wurl)).arrayBuffer()
        setMidiBuffer(await ctx.decodeAudioData(wArr.slice(0)))
      } finally { await ctx.close() }
    }
    if (navState.jobId) bootstrapFromGeneratedJob(navState.jobId).catch(console.error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navState.jobId])

  /* ===== fallback 큐 ===== */
  const fallbackCues = useMemo(() => {
    if (chordCues.length) return chordCues
    if (navState.progression?.length) {
      return buildCuesFromProgression(navState.progression, navState.barsPerChord ?? 1)
    }
    return []
  }, [chordCues, navState.progression, navState.barsPerChord, beatSec, timeSig])

  /* ===== 수동 MIDI 업로드 ===== */
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

      const cues = await extractChordCuesFromMidi(arr, { preRollSec: 0, windowBeats: 1 })
      setChordCues(cues)

      const { wavUrl: wurl } = await renderMidiOnServer(file)
      setMidiAudioUrl(wurl)

      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const wavArr = await (await fetch(wurl)).arrayBuffer()
      setMidiBuffer(await ctx.decodeAudioData(wavArr.slice(0)))
      await ctx.close()
    } finally {
      setRendering(false)
    }
  }

  /* ===== 오토플레이 해제 ===== */
  async function ensureUnlocked() {
    const el = midiEl.current; if (!el) return
    const prev = el.muted; el.muted = true
    try { await el.play().catch(()=>{}); el.pause() } finally { el.muted = prev }
  }

  /* ===== 카운트인 ===== */
  async function playCountIn(beats: number, bpm: number) {
    setCountInLeft(beats)
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
      setTimeout(() => setCountInLeft(beats - i - 1), Math.max(0, (ts - ctx.currentTime) * 1000))
    }
    return new Promise<void>((resolve) => {
      const endAt = t0 + beats * beat
      const ms = Math.ceil((endAt - ctx.currentTime) * 1000) + 20
      setTimeout(() => { ctx.close().finally(() => { setCountInLeft(null); resolve() }) }, ms)
    })
  }


  async function startRecordingFromTransport() {
    if (!midiAudioUrl && !bassOnly) {
      alert('먼저 MIDI 백킹이 준비되어야 합니다. (또는 “베이스만 녹음”을 켜세요)');
      return;
    }
    if (!recording) await startRec();
    await ensureUnlocked();
    await playCountIn(COUNTIN_BEATS, tempoBpm);

    transportStartAt.current = performance.now();
    if (!bassOnly && midiEl.current) {
      midiEl.current.currentTime = 0;
      midiEl.current.play().catch(() => {});
    }
    setPlaying(true);
    if (!rafRef.current) tick();
  }

  // ■ 녹음 ‘정지’를 누르면 오디오 재생도 즉시 멈추게
  function stopRecordingAndPlayback() {
    // 1) 녹음 정지
    stopRec(); // useMediaRecorder.stop()

    // 2) 재생 중지 + HUD 정지
    midiEl.current?.pause();
    bassEl.current?.pause();
    setPlaying(false);
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }


  /* ===== 트랜스포트 / HUD ===== */
  function syncVolumesAndMutes() {
    if (midiEl.current) { midiEl.current.volume = midiVol; midiEl.current.muted = !playMidi; midiEl.current.loop = loop }
    if (bassEl.current) { bassEl.current.volume = bassVol; bassEl.current.muted = !playBass; bassEl.current.loop = loop }
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
      setNowChord(now); setNextChord(next)
    }
    rafRef.current = requestAnimationFrame(tick)
  }
  function play() {
    if (!bassOnly) midiEl.current?.play().catch(()=>{})
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

  // duration/ended
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

  // 네이티브 컨트롤도 HUD 동기
  useEffect(() => {
    const a = midiEl.current; const b = bassEl.current
    if (!a && !b) return
    const onTU = () => {
      const t = Math.max(a?.currentTime ?? 0, b?.currentTime ?? 0)
      setPosition(t)
      const cues = chordCues.length ? chordCues : fallbackCues
      if (cues.length) {
        const { now, next } = getNowNextChord(cues, t)
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
  }, [midiAudioUrl, bassTrimUrl, blobUrl, chordCues, fallbackCues])

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }, [])

  /* ===== 합치기 ===== */
  async function mergeAndExport() {
    if (!midiBuffer) return

    if (!bassBuffer && blobUrl) {
      // 보수적: blobUrl → 프리롤 제거 후 인메모리 버퍼 확보
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const arr = await (await fetch(blobUrl)).arrayBuffer()
      const src = await ctx.decodeAudioData(arr.slice(0))
      const startSample = Math.floor(preRollSec * src.sampleRate)
      const out = ctx.createBuffer(src.numberOfChannels, Math.max(0, src.length - startSample), src.sampleRate)
      for (let ch = 0; ch < src.numberOfChannels; ch++) {
        out.getChannelData(ch).set(src.getChannelData(ch).subarray(startSample))
      }
      await ctx.close()
      setBassBuffer(out)
    }
    const bass = bassBuffer
    if (!bass) return

    const mixed = await mixBuffersToAudioBuffer(midiBuffer, bass, { sampleRate: 48000, fadeOutSec: 0.03 })
    const wav = audioBufferToWavBlob(mixed)
    const url = URL.createObjectURL(wav)
    if (mergedUrl) URL.revokeObjectURL(mergedUrl)
    setMergedUrl(url)
  }
  useEffect(() => () => { if (mergedUrl) URL.revokeObjectURL(mergedUrl) }, [mergedUrl])

  /* ===== 파생 UI 데이터 ===== */
  const cuesForUI = chordCues.length ? chordCues : fallbackCues
  const totalFromCues = useMemo(() => {
    if (!cuesForUI.length) return 0
    const last = cuesForUI[cuesForUI.length - 1]
    const barsPerChord = navState.barsPerChord ?? 1
    const tail = (timeSig?.[0] ?? 4) * beatSec * Math.max(1, barsPerChord)
    return last.time + tail
  }, [cuesForUI, beatSec, timeSig, navState.barsPerChord])

  return (
    <div className="pmx-wrap">
      {/* Step 안내 & HUD */}
      <section className="pmx-panel">
        <div className="top-steps">
          <div className="step"><span>1</span> 장치를 선택하고 마이크 권한을 허용하세요.</div>
          <div className="step"><span>2</span> {bassOnly ? '베이스만' : '백킹과 함께'} <b>재생/녹음</b>하세요. (R: 녹음 / Space: 재생)</div>
          <div className="step"><span>3</span> 상단 HUD에서 <b>현재/다음 코드</b>를 확인하세요.</div>
          <div className="step"><span>4</span> 끝나면 <b>합치기</b>로 WAV를 받으세요.</div>
        </div>

        <div className="hud">
          <div className="ring">
            <div className="now">{nowChord || 'Ready'}</div>
            <div className="next">{nextChord ? `Next • ${nextChord}` : ' '}</div>
          </div>

          {countInLeft !== null && (
            <div className="countin">
              <div className="num">{countInLeft === 0 ? 'GO!' : countInLeft}</div>
              <div className="sub">카운트인 {COUNTIN_BEATS}박</div>
            </div>
          )}
        </div>
      </section>

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
          <ChordTimeline
            cues={cuesForUI}
            totalSec={totalFromCues}
            positionSec={position}
            playing={playing}
          />
        </section>
      )}

      {/* MIDI 파일 / 미리듣기 */}
      <section className="pmx-panel">
        <h3>🎼 백킹(미디 렌더)</h3>
        <div className="thin" style={{marginBottom: 8}}>
          {midiAudioUrl ? '결과에서 전달된 백킹이 준비되었습니다.' : '필요하다면 MIDI 파일을 직접 선택할 수도 있습니다.'}
        </div>
        <div className="row">
          <label className="file">
            <input type="file" accept=".mid,.midi" onChange={e => {
              const f = e.target.files?.[0];
              if (f) handleMidiFile(f)
            }}/>
            <span>파일 선택</span>
          </label>
          {midiFile && <span className="hint">{midiFile.name}</span>}
          {rendering && <span className="hint">서버 렌더링 중…</span>}
        </div>
        <div className="preview" style={{marginTop: 8}}>
          {midiAudioUrl
            ? <audio ref={midiEl} src={midiAudioUrl} preload="metadata" controls
                     onLoadedMetadata={syncVolumesAndMutes}
                     onPlay={syncVolumesAndMutes}
                     onError={(e) => console.warn('MIDI audio error', e)}/>
            : <div className="thin">결과 카드에서 “베이스 녹음하기”로 들어오면 자동으로 채워집니다.</div>}
        </div>
        {(midiTracks.length > 0) && (
          <details className="tracks" style={{marginTop: 8}}>
            <summary>트랙 메타 보기</summary>
            <div className="thin" style={{margin: '6px 0'}}>Tempo: {tempoBpm} BPM • Time Sig: {timeSig[0]}/{timeSig[1]}</div>
            <ul>
              {midiTracks.map((t, i) => (
                <li key={i}>
                  <strong>{t.name}</strong>
                  <span className="thin"> ({t.instrument ?? 'inst'}, ch {t.channel ?? '-'})</span>
                  <span className="thin"> • notes: {t.notes}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      {/*/!* 베이스 녹음 *!/*/}
      {/*<section className="pmx-panel">*/}
      {/*  <h3>🎙 베이스 녹음</h3>*/}
      {/*  <div className="row" style={{gap:12, alignItems:'center'}}>*/}
      {/*    {!recording*/}
      {/*      ? <button className="btn primary" onClick={startRecordingFlow}>● 녹음 시작 (카운트인 {COUNTIN_BEATS}박)</button>*/}
      {/*      : <button className="btn danger" onClick={stop}>■ 정지</button>}*/}
      {/*    <label className="row" style={{gap:6}}>*/}
      {/*      <input type="checkbox" checked={bassOnly} onChange={e=>setBassOnly(e.target.checked)} />*/}
      {/*      베이스만 녹음(백킹 미재생)*/}
      {/*    </label>*/}
      {/*  </div>*/}
      {/*</section>*/}

      {/* AMP (Accordion) */}
      {/* === AMP (Gain / Tone / Master) === */}
{/* === AMP (Gain / Tone / Master) === */}
<Accordion
  variant="light"
  defaultOpen
  title={<span>🎛️ AMP (Gain / Tone / Master)</span>}
  rightSlot={
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 12, color: '#6b7280' }}>{amp.status}</span>
      {amp.running ? (
        <button onClick={amp.stop} className="btn-outline">정지</button>
      ) : (
        <button onClick={amp.start} className="btn-primary">⚡ 시작</button>
      )}
    </div>
  }
>
  <div style={{ display: 'grid', gap: 12 }}>
    {/* AMP 토글/테스트톤/믹스 */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
      <label>
        <input
          type="checkbox"
          checked={amp.enabled}
          onChange={(e) => amp.setEnabled(e.target.checked)}
        /> AMP 톤 켜기
      </label>
      <label>
        <input
          type="checkbox"
          checked={amp.testTone}
          onChange={(e) => amp.setTestTone(e.target.checked)}
        /> 테스트톤(110Hz)
      </label>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>효과량</span>
        <input
          type="range" min={0} max={1} step={0.01}
          value={amp.mix}
          onChange={(e) => amp.setMix(parseFloat(e.target.value))}
          style={{ width: 180 }}
        />
        <span style={{ fontSize: 12, width: 40, textAlign: 'right' }}>
          {Math.round(amp.mix * 100)}%
        </span>
      </div>
    </div>

    {/* 노브 3개 */}
    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
      <DialKnob label="GAIN"   value={amp.gain}   min={0}  max={10} step={0.1} onChange={amp.setGain} />
      <DialKnob label="TONE"   value={amp.tone}   min={-5} max={5}  step={0.1} onChange={amp.setTone} />
      <DialKnob label="MASTER" value={amp.master} min={0}  max={10} step={0.1} onChange={amp.setMaster} />
    </div>

    {/* 스코프 */}
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff', padding: 8 }}>
      <canvas ref={amp.canvasRef} style={{ width: '100%', height: 160, display: 'block' }} />
    </div>
  </div>
</Accordion>

      {/* 미리듣기 & 트랜스포트 */}
      {/* ✅ 여기는 기존 ‘미리듣기 & 트랜스포트’ 섹션 자리를 통째로 교체 */}
<section className="pmx-panel">
  <h3>🎚 베이스 녹음 & 트랜스포트</h3>

  {/* 녹음 컨트롤을 트랜스포트 상단에 통합 */}
  <div className="row" style={{ gap: 12, alignItems: 'center', marginBottom: 8 }}>
    {!recording ? (
      <button className="btn primary" onClick={startRecordingFromTransport}>
        ● 녹음 시작 (카운트인 {COUNTIN_BEATS}박)
      </button>
    ) : (
      <button className="btn danger" onClick={stopRecordingAndPlayback}>
        ■ 정지(녹음 + 재생)
      </button>
    )}
    <label className="row" style={{ gap: 6 }}>
      <input
        type="checkbox"
        checked={bassOnly}
        onChange={(e) => setBassOnly(e.target.checked)}
      />
      베이스만 녹음(백킹 미재생)
    </label>
  </div>

  <div className="transport" style={{ marginTop: 12 }}>
    <button
      className="btn"
      onClick={playing ? pause : play}
      disabled={!midiAudioUrl && !bassTrimUrl && !blobUrl}
    >
      {playing ? '⏸ 일시정지 (Space)' : '▶︎ 재생 (Space)'}
    </button>
    <button className="btn" onClick={stopAll}>⏹ 정지</button>
    <label className="row" style={{ gap: 8 }}>
      <input
        aria-label="seek"
        type="range"
        min={0}
        max={Math.max(duration || totalFromCues, 0.001)}
        step={0.01}
        value={position}
        onChange={(e) => seek(Number(e.target.value))}
        style={{ width: 360 }}
      />
      <span className="hint">
        {formatTime(position)} / {formatTime(Math.max(duration, totalFromCues))}
      </span>
    </label>
    <label className="row" style={{ gap: 6 }}>
      <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} />
      <span className="hint">루프</span>
    </label>
  </div>
  {/* 실시간 파형(스크롤) 미리보기: 녹음 중에만 진행 */}
  <div style={{ marginTop: 16 }}>
    <ScrollRecordWave
  mediaStream={recordStream ?? undefined}
  running={recording}
  theme="light"
  height={120}
  seconds={80}     // 화면에 보이는 최근 구간(초)
  pxPerSec={80}    // 스크롤 속도(px/s) — 원하는 대로 조절
  clearOnStart     // 새 녹음 시작 시 파형 초기화
/>
  </div>
</section>

      {/* 합치기 & 다운로드 */}
      <section className="pmx-panel">
        <h3>⬇️ 합치기 & 다운로드</h3>
        <button className="btn" onClick={mergeAndExport} disabled={!midiBuffer || (!bassBuffer && !blobUrl)}>
          음원 합치기 (WAV 생성)
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