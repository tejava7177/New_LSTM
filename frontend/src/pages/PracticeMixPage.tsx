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

  /* ===== MIDI 로딩 & 렌더링 ===== */
  const [midiFile, setMidiFile] = useState<File | null>(null)
  const [midiAudioUrl, setMidiAudioUrl] = useState<string | null>(null)
  const [midiBuffer, setMidiBuffer] = useState<AudioBuffer | null>(null)
  const [midiTracks, setMidiTracks] = useState<TrackMeta[]>([])
  const [rendering, setRendering] = useState(false)

  /* 메타 */
  const [tempoBpm, setTempoBpm] = useState<number>(navState.tempo ?? 100)
  const [timeSig, setTimeSig] = useState<[number, number]>(navState.timeSig ?? [4, 4])

  /* 코드 큐 (마커 or 계산) */
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

  /* AMP (모니터링용 이펙트 체인: preGain -> waveshaper -> tiltEQ -> master) */
  const [ampRunning, setAmpRunning] = useState(false)
  const [ampGain, setAmpGain] = useState(4.0)     // 0..10
  const [ampTone, setAmpTone] = useState(0.0)     // -5..+5 (tilt EQ)
  const [ampMaster, setAmpMaster] = useState(7.5) // 0..10
  const [ampTestTone, setAmpTestTone] = useState(false)
  const [ampStatus, setAmpStatus] = useState('대기 중…')
  // === AMP 녹음 반영 옵션 ===
  const [applyAmpToRec, setApplyAmpToRec] = useState(false)
  const [ampRecording, setAmpRecording] = useState(false)
  const [procBlobUrl, setProcBlobUrl] = useState<string | null>(null)

  const ampCtxRef = useRef<AudioContext | null>(null)
  const ampInputRef = useRef<GainNode | null>(null)
  const ampPreRef = useRef<GainNode | null>(null)
  const ampShaperRef = useRef<WaveShaperNode | null>(null)
  const ampLowRef = useRef<BiquadFilterNode | null>(null)
  const ampHighRef = useRef<BiquadFilterNode | null>(null)
  const ampMasterRef = useRef<GainNode | null>(null)
  const ampAnalyserRef = useRef<AnalyserNode | null>(null)
  const ampStreamRef = useRef<MediaStream | null>(null)
  const ampOscRef = useRef<OscillatorNode | null>(null)
  const ampOscGainRef = useRef<GainNode | null>(null)
  const ampRafRef = useRef<number | null>(null)
  const ampCanvasRef = useRef<HTMLCanvasElement | null>(null)
  // AMP 출력 → MediaStreamDestination(녹음용) & MediaRecorder
  const ampMsDestRef = useRef<MediaStreamAudioDestinationNode | null>(null)
  const ampRecorderRef = useRef<MediaRecorder | null>(null)
  const ampChunksRef = useRef<Blob[]>([])

  // 🔼 추가: AMP 입력 소스 및 스코프 버퍼
  const ampInputSrcRef = useRef<AudioNode | null>(null)
  const ampDrawBufRef = useRef<Float32Array | null>(null)

  /* 합치기 */
  const [mergedUrl, setMergedUrl] = useState<string | null>(null)
  // hook(blobUrl) vs AMP-processed(procBlobUrl) 중 실제 사용될 녹음본 URL
  const activeBlobUrl = applyAmpToRec ? procBlobUrl : blobUrl

  /* UX */
  const COUNTIN_BEATS = navState.preRollBeats ?? 4
  const [bassOnly, setBassOnly] = useState(false)
  const [countInLeft, setCountInLeft] = useState<number | null>(null) // overlay 표시용

  /* 베이스 트리밍(카운트인 제거) */
  const [bassTrimUrl, setBassTrimUrl] = useState<string | null>(null)
  const [bassBuffer, setBassBuffer] = useState<AudioBuffer | null>(null)
  const beatSec = useMemo(() => 60 / Math.max(40, Math.min(300, tempoBpm)), [tempoBpm])
  const preRollSec = useMemo(() => beatSec * COUNTIN_BEATS, [beatSec, COUNTIN_BEATS])

  /* ===== 녹음본 → 프리롤만큼 자르기 ===== */
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

  /* ===== 유틸: progression으로 큐 계산(fallback) ===== */
  function buildCuesFromProgression(prog: string[], barsPerChord = 1): ChordCue[] {
    const beatsPerBar = timeSig?.[0] ?? 4
    const secPerBar = beatsPerBar * beatSec
    let t = 0
    const cues: ChordCue[] = prog.map((text) => {
      const cue = { text, time: t }
      t += secPerBar * Math.max(1, barsPerChord)
      return cue
    })
    return cues
  }

  /* ===== 생성 트랙에서 자동 부팅 ===== */
  useEffect(() => {
    async function bootstrapFromGeneratedJob(jobId: string) {
      // 1) MIDI → 큐 시도(※ preRoll 보정을 하지 않는다: MIDI 재생 0초부터 코드 시작)
      try {
        const midiArr = await (await fetch(navState.midiUrl ?? midiUrl(jobId))).arrayBuffer()
        const cues = await extractChordCuesFromMidi(midiArr, { preRollSec: 0, windowBeats: 1 })
        if (cues.length) setChordCues(cues)
        // 메타
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

      // 2) WAV 세팅 + 디코드
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

  /* ===== progression만 넘어온 경우의 큐 계산 ===== */
  const fallbackCues = useMemo(() => {
    if (chordCues.length) return chordCues
    if (navState.progression && navState.progression.length) {
      return buildCuesFromProgression(navState.progression, navState.barsPerChord ?? 1)
    }
    return []
  }, [chordCues, navState.progression, navState.barsPerChord, beatSec, timeSig])

  /* ===== 수동 MIDI 업로드도 지원 ===== */
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

      // 마커가 있으면 사용(수동 업로드는 preRoll 보정 X)
      const cues = await extractChordCuesFromMidi(arr, { preRollSec: 0, windowBeats: 1 })
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
      // 오버레이 숫자 업데이트
      setTimeout(() => setCountInLeft(beats - i - 1), Math.max(0, (ts - ctx.currentTime) * 1000))
    }
    return new Promise<void>((resolve) => {
      const endAt = t0 + beats * beat
      const ms = Math.ceil((endAt - ctx.currentTime) * 1000) + 20
      setTimeout(() => { ctx.close().finally(() => { setCountInLeft(null); resolve() }) }, ms)
    })
  }

  /* ===== AMP helpers ===== */
  function makeDriveCurve(drive: number, samples = 2048) {
    const k = drive; const c = new Float32Array(samples)
    for (let i = 0; i < samples; i++) {
      const x = (i / (samples - 1)) * 2 - 1
      c[i] = Math.tanh(k * x)
    }
    return c
  }
  function applyAmpParams() {
    if (!ampPreRef.current || !ampShaperRef.current || !ampLowRef.current || !ampHighRef.current || !ampMasterRef.current) return
    const g = Math.max(0, Math.min(10, ampGain))
    ampPreRef.current.gain.value = 0.2 + g * 0.25
    ampShaperRef.current.curve = makeDriveCurve(2 + g * 1.8)

    const t = Math.max(-5, Math.min(5, ampTone)) / 5
    ampLowRef.current.gain.value  = (t < 0 ? 6 * (-t) : -3 * t)
    ampHighRef.current.gain.value = (t > 0 ? 9 *  t  :  4 * t)

    const m = Math.max(0, Math.min(10, ampMaster))
    ampMasterRef.current.gain.value = Math.pow(m / 10, 1.2)
  }
  function clearAmpScope() {
    const cv = ampCanvasRef.current; if (!cv) return
    const g = cv.getContext('2d'); if (!g) return
    const dpr = Math.max(1, (window.devicePixelRatio || 1))
    const W = cv.clientWidth * dpr, H = 140 * dpr
    cv.width = Math.max(1, Math.floor(W)); cv.height = Math.max(1, Math.floor(H))
    g.clearRect(0,0,cv.width,cv.height)
    g.fillStyle = '#0b1220'; g.fillRect(0,0,cv.width,cv.height)
    g.strokeStyle = '#1f2937'; g.lineWidth = 1 * dpr
    g.beginPath(); g.moveTo(0, Math.floor(cv.height/2)+0.5*dpr); g.lineTo(cv.width, Math.floor(cv.height/2)+0.5*dpr); g.stroke()
  }
  function drawAmpScope() {
    const cv = ampCanvasRef.current; const an = ampAnalyserRef.current
    if (!cv || !an) return
    const g = cv.getContext('2d'); if (!g) return
    const dpr = Math.max(1, (window.devicePixelRatio || 1))
    const W = cv.clientWidth * dpr, H = 140 * dpr
    if (cv.width !== Math.floor(W) || cv.height !== Math.floor(H)) {
      cv.width = Math.max(1, Math.floor(W)); cv.height = Math.max(1, Math.floor(H))
    }
    const mid = Math.floor(cv.height / 2)
    g.clearRect(0,0,cv.width,cv.height)
    g.fillStyle = '#0b1220'; g.fillRect(0,0,cv.width,cv.height)
    g.strokeStyle = '#1f2937'; g.lineWidth = 1 * dpr
    g.beginPath(); g.moveTo(0, mid+0.5*dpr); g.lineTo(cv.width, mid+0.5*dpr); g.stroke()

    const n = an.fftSize
    if (!ampDrawBufRef.current || ampDrawBufRef.current.length !== n) {
      ampDrawBufRef.current = new Float32Array(n)
    }
    const buf = ampDrawBufRef.current
    an.getFloatTimeDomainData(buf)

    const grad = g.createLinearGradient(0,0,0,cv.height)
    grad.addColorStop(0,'#60a5fa'); grad.addColorStop(1,'#a78bfa')
    g.strokeStyle = grad; g.lineWidth = 2 * dpr; g.beginPath()
    for (let i=0;i<n;i++){
      const t=i/(n-1);
      const x=(t*(cv.width-2*dpr))+1*dpr;
      const y=mid+(buf[i]*(cv.height*0.45));
      if(i===0) g.moveTo(x,y); else g.lineTo(x,y)
    }
    g.stroke()
  }
  async function startAmp() {
    if (ampRunning) return
    setAmpStatus('시작 준비…')
    const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext
    const ctx = new Ctx()
    ampCtxRef.current = ctx

    // nodes
    const input = ctx.createGain()
    const pre = ctx.createGain()
    const shaper = ctx.createWaveShaper()
    const low = ctx.createBiquadFilter(); low.type = 'lowshelf'; low.frequency.value = 250
    const high = ctx.createBiquadFilter(); high.type = 'highshelf'; high.frequency.value = 2500
    const master = ctx.createGain()
    input.connect(pre); pre.connect(shaper).connect(low).connect(high).connect(master)
    const analyser = ctx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.10
    master.connect(analyser).connect(ctx.destination)

    // 🔼 AMP processed tone를 MediaStreamDestination으로도 출력(녹음용)
    const msDest = ctx.createMediaStreamDestination()
    master.connect(msDest)
    ampMsDestRef.current = msDest

    ampInputRef.current = input; ampPreRef.current = pre; ampShaperRef.current = shaper
    ampLowRef.current = low; ampHighRef.current = high; ampMasterRef.current = master
    ampAnalyserRef.current = analyser

    applyAmpParams()

    // 최초 입력은 현재 옵션에 맞춰 핫스왑 useEffect에서 연결됨
    // scope loop
    const loop = () => { drawAmpScope(); ampRafRef.current = requestAnimationFrame(loop) }
    clearAmpScope(); loop()
    setAmpRunning(true)
    setAmpStatus('실행 중')
  }
  function stopAmp() {
    if (ampRafRef.current) { cancelAnimationFrame(ampRafRef.current); ampRafRef.current = null }
    try { ampInputSrcRef.current?.disconnect() } catch {}
    try { ampInputRef.current?.disconnect() } catch {}
    try { ampPreRef.current?.disconnect() } catch {}
    try { ampShaperRef.current?.disconnect() } catch {}
    try { ampLowRef.current?.disconnect() } catch {}
    try { ampHighRef.current?.disconnect() } catch {}
    try { ampMasterRef.current?.disconnect() } catch {}
    try { ampAnalyserRef.current?.disconnect() } catch {}
    if (ampOscRef.current) { try { ampOscRef.current.stop() } catch {}; try { ampOscRef.current.disconnect() } catch {} }
    if (ampOscGainRef.current) { try { ampOscGainRef.current.disconnect() } catch {} }
    if (ampStreamRef.current) { ampStreamRef.current.getTracks().forEach(t=>t.stop()); ampStreamRef.current = null }
    if (ampCtxRef.current) { try { ampCtxRef.current.close() } catch {}; ampCtxRef.current = null }
    ampInputRef.current = null; ampPreRef.current = null; ampShaperRef.current = null
    ampLowRef.current = null; ampHighRef.current = null; ampMasterRef.current = null
    ampAnalyserRef.current = null; ampMsDestRef.current = null
    setAmpRunning(false)
    setAmpStatus('정지')
    clearAmpScope()
  }

  useEffect(() => { applyAmpParams() }, [ampGain, ampTone, ampMaster])
  useEffect(() => () => { stopAmp() }, [])

  // 🔼 AMP 입력 소스 핫스왑 (테스트톤/장치 변경 즉시 반영)
  useEffect(() => {
    if (!ampRunning || !ampCtxRef.current || !ampInputRef.current) return;
    const ctx = ampCtxRef.current;

    // 이전 입력 소스 분리
    try { ampInputSrcRef.current?.disconnect(); } catch {}
    ampInputSrcRef.current = null;

    (async () => {
      if (ampTestTone) {
        if (ampStreamRef.current) { ampStreamRef.current.getTracks().forEach(t=>t.stop()); ampStreamRef.current = null; }
        if (ampOscRef.current) { try { ampOscRef.current.stop() } catch {}; try { ampOscRef.current.disconnect() } catch {}; }
        if (ampOscGainRef.current) { try { ampOscGainRef.current.disconnect() } catch {}; }

        const osc = ctx.createOscillator(); osc.type='sine'; osc.frequency.value = 110;
        const g = ctx.createGain(); g.gain.value = 0.5;
        osc.connect(g).connect(ampInputRef.current!);
        ampOscRef.current = osc; ampOscGainRef.current = g;
        ampInputSrcRef.current = g;
        osc.start();
        return;
      }

      if (ampOscRef.current) { try { ampOscRef.current.stop() } catch {}; try { ampOscRef.current.disconnect() } catch {}; ampOscRef.current = null; }
      if (ampOscGainRef.current) { try { ampOscGainRef.current.disconnect() } catch {}; ampOscGainRef.current = null; }

      if (ampStreamRef.current) { ampStreamRef.current.getTracks().forEach(t=>t.stop()); ampStreamRef.current = null; }
      const constraints = deviceId ? { audio: { deviceId: { exact: deviceId } } } : { audio: true }
      try {
        const stream = await navigator.mediaDevices.getUserMedia(constraints as any)
        ampStreamRef.current = stream
        const src = ctx.createMediaStreamSource(stream)
        src.connect(ampInputRef.current!)
        ampInputSrcRef.current = src
      } catch (err) {
        console.warn('AMP input error', err)
      }
    })();
  }, [ampTestTone, deviceId, ampRunning])

  // 🔼 스코프 리사이즈 대응
  useEffect(() => {
    const cv = ampCanvasRef.current; if (!cv) return
    const ro = new ResizeObserver(() => drawAmpScope())
    ro.observe(cv)
    return () => ro.disconnect()
  }, [ampRunning])

  /* ===== 오토플레이 해제 ===== */
  async function ensureUnlocked() {
    const el = midiEl.current; if (!el) return
    const prev = el.muted; el.muted = true
    try { await el.play().catch(()=>{}); el.pause() } finally { el.muted = prev }
  }

  /* ===== AMP 녹음 제어 ===== */
  function startAmpRecording() {
    if (!ampMsDestRef.current) { alert('AMP가 실행 중이어야 합니다.'); return }
    try {
      const mime = (window as any).MediaRecorder?.isTypeSupported?.('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : ((window as any).MediaRecorder?.isTypeSupported?.('audio/webm') ? 'audio/webm' : '')
      const rec = new MediaRecorder(ampMsDestRef.current.stream, mime ? { mimeType: mime } : undefined)
      ampChunksRef.current = []
      rec.ondataavailable = (ev) => { if (ev.data && ev.data.size > 0) ampChunksRef.current.push(ev.data) }
      rec.onstop = () => {
        const blob = new Blob(ampChunksRef.current, { type: mime || 'audio/webm' })
        if (procBlobUrl) URL.revokeObjectURL(procBlobUrl)
        const url = URL.createObjectURL(blob)
        setProcBlobUrl(url)
        ampChunksRef.current = []
      }
      rec.start()
      ampRecorderRef.current = rec
      setAmpRecording(true)
    } catch (e:any) {
      alert('AMP 녹음을 시작할 수 없습니다: ' + (e?.message || String(e)))
    }
  }
  function stopAmpRecording() {
    const rec = ampRecorderRef.current
    if (rec && rec.state !== 'inactive') rec.stop()
    setAmpRecording(false)
  }

  /* ===== 녹음 시작/정지 플로우 ===== */
  async function startRecordingFlow() {
    if (!midiAudioUrl && !bassOnly) { alert('먼저 MIDI 백킹이 준비되어야 합니다. (또는 “베이스만 녹음”을 켜세요)'); return }

    if (applyAmpToRec) {
      if (!ampRunning) { await startAmp().catch(()=>{}) }
      if (!ampMsDestRef.current) { alert('AMP가 아직 초기화되지 않았습니다. AMP를 시작한 뒤 다시 시도하세요.'); return }
      if (!ampRecording) startAmpRecording()
    } else {
      if (!recording) await start()
    }

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
  function stopRecordingFlow() {
    if (applyAmpToRec) stopAmpRecording()
    else stop()
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
  }, [midiAudioUrl, bassTrimUrl, activeBlobUrl, chordCues, fallbackCues])

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }, [])

  /* 키보드 단축키 */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'Space') { e.preventDefault(); playing ? pause() : play() }
      if (e.key.toLowerCase() === 'r') { e.preventDefault(); startRecordingFlow().catch(console.error) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playing, tempoBpm, midiAudioUrl, bassOnly, startRecordingFlow])

  /* ===== 합치기 ===== */
  async function mergeAndExport() {
    if (!midiBuffer) return
    if (mergedUrl) URL.revokeObjectURL(mergedUrl)
    setMergedUrl(null)

    let bass: AudioBuffer | null = bassBuffer
    if (!bass && activeBlobUrl) {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const arr = await (await fetch(activeBlobUrl)).arrayBuffer()
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
  useEffect(() => () => { if (procBlobUrl) URL.revokeObjectURL(procBlobUrl) }, [procBlobUrl])

  /* ===== 파생 UI 데이터 ===== */
  const cuesForUI = chordCues.length ? chordCues : fallbackCues
  const totalFromCues = useMemo(() => {
    if (!cuesForUI.length) return 0
    const last = cuesForUI[cuesForUI.length - 1]
    const barsPerChord = navState.barsPerChord ?? 1
    const tail = (timeSig?.[0] ?? 4) * beatSec * Math.max(1, barsPerChord)
    return last.time + tail
  }, [cuesForUI, beatSec, timeSig, navState.barsPerChord])

  // --- Single-cycle timeline with wrap-back playhead ---
  const cycleSec = Math.max(0.001, totalFromCues);
  // 현재 재생 위치를 1사이클로 모듈로
  const posMod = ((position % cycleSec) + cycleSec) % cycleSec;

  // 래핑(끝→처음) 순간엔 한 프레임만 transition 끄기
  const prevPosRef = useRef(0);
  const [noAnim, setNoAnim] = useState(false);
  useEffect(() => {
    const prev = prevPosRef.current;
    if (posMod < prev - 0.05) {        // 충분히 뒤로 점프 = 래핑
      setNoAnim(true);
      requestAnimationFrame(() => setNoAnim(false));
    }
    prevPosRef.current = posMod;
  }, [posMod]);

  /* ===== 렌더 ===== */
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

          {/* 카운트인 오버레이 */}
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

      {/* 타임라인 (코드 라인) */}
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

      {/* MIDI 파일 / 미리듣기 */}
      <section className="pmx-panel">
        <h3>🎼 백킹(미디 렌더)</h3>
        <div className="thin" style={{marginBottom:8}}>
          {midiAudioUrl ? '결과에서 전달된 백킹이 준비되었습니다.' : '필요하다면 MIDI 파일을 직접 선택할 수도 있습니다.'}
        </div>

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

        <div className="preview" style={{marginTop:8}}>
          {midiAudioUrl
            ? <audio ref={midiEl} src={midiAudioUrl} preload="metadata" controls
                     onLoadedMetadata={syncVolumesAndMutes}
                     onPlay={syncVolumesAndMutes}
                     onError={(e)=>console.warn('MIDI audio error', e)} />
            : <div className="thin">결과 카드에서 “베이스 녹음하기”로 들어오면 자동으로 채워집니다.</div>}
        </div>

        {(midiTracks.length > 0) && (
          <details className="tracks" style={{marginTop:8}}>
            <summary>트랙 메타 보기</summary>
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
          </details>
        )}
      </section>

      {/* 베이스 녹음 */}
      <section className="pmx-panel">
        <h3>🎙 베이스 녹음</h3>
        <div className="row" style={{gap:12, alignItems:'center'}}>
          {!(recording || ampRecording)
            ? <button className="btn primary" onClick={startRecordingFlow}>● 녹음 시작 (카운트인 {COUNTIN_BEATS}박)</button>
            : <button className="btn danger" onClick={stopRecordingFlow}>■ 정지</button>}
          <label className="row" style={{gap:6}}>
            <input type="checkbox" checked={bassOnly} onChange={e=>setBassOnly(e.target.checked)} />
            베이스만 녹음(백킹 미재생)
          </label>
        </div>
      </section>

      {/* AMP (Gain / Tone / Master) */}
      <section className="pmx-panel">
        <h3>🎛 AMP (Gain / Tone / Master)</h3>
        <div className="row" style={{gap:12, alignItems:'center', flexWrap:'wrap'}}>
          <label className="row" style={{gap:6}}>
            <input type="checkbox" checked={ampTestTone} onChange={e=>setAmpTestTone(e.target.checked)} />
            테스트톤(110Hz) 사용
          </label>
          <label className="row" style={{gap:6}}>
            <input type="checkbox" checked={applyAmpToRec} onChange={e=>setApplyAmpToRec(e.target.checked)} />
            녹음에 앰프 톤 적용
          </label>
          {!ampRunning
            ? <button className="btn" onClick={()=>startAmp().catch(err=>alert(err?.message||String(err)))}>⚡ 시작</button>
            : <button className="btn danger" onClick={stopAmp}>■ 정지</button>}
          <span className="hint" style={{marginLeft:'auto'}}>{ampStatus}</span>
        </div>

        {/* Knobs */}
        <div className="amp-grid" style={{display:'flex', gap:20, flexWrap:'wrap', alignItems:'flex-end', marginTop:6}}>
          <DialKnob label="Gain"   value={ampGain}   min={0}  max={10} step={0.1} defaultValue={4.0}  onChange={setAmpGain} />
          <DialKnob label="Tone"   value={ampTone}   min={-5} max={5}  step={0.1} defaultValue={0.0}  onChange={setAmpTone} />
          <DialKnob label="Master" value={ampMaster} min={0}  max={10} step={0.1} defaultValue={7.5} onChange={setAmpMaster} />
        </div>

        {/* Scope */}
        <div className="scope" style={{background:'#0b1220', border:'1px dashed #1f2937', borderRadius:12, padding:8, marginTop:12}}>
          <canvas ref={ampCanvasRef} style={{width:'100%', height:140, display:'block'}} />
        </div>

        {/* Local styles for knobs */}
        <style>{String.raw`
          .knb { display:inline-flex; flex-direction:column; align-items:center; gap:6px; width:96px }
          .knb .dial {
            width:68px; height:68px; border-radius:50%;
            background: radial-gradient(140% 140% at 30% 30%, #111827, #0b1220);
            border:1px solid #1f2937; position:relative; transition:transform .05s linear;
            box-shadow: inset 0 2px 6px rgba(0,0,0,.35), 0 1px 0 rgba(255,255,255,.04);
            cursor:grab;
          }
          .knb .indicator {
            position:absolute; left:50%; top:6px; width:2px; height:24px; background:#e5e7eb;
            transform:translateX(-50%); border-radius:2px; box-shadow:0 0 0 1px rgba(0,0,0,.25);
          }
          .knb .t { font-size:12px; color:#a3b1c7; text-transform:uppercase; letter-spacing:.06em; }
          .knb .v { font-size:12px; color:#e5e7eb; opacity:.9; }
        `}</style>
      </section>

      {/* Bass 미리듣기 & 믹서 */}
      <section className="pmx-panel">
        <h3>🎚 미리듣기 & 트랜스포트</h3>
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
              {(bassTrimUrl || activeBlobUrl)
                ? <audio ref={bassEl} src={(bassTrimUrl ?? activeBlobUrl)!} preload="metadata" controls
                         onLoadedMetadata={syncVolumesAndMutes}
                         onPlay={syncVolumesAndMutes}
                         onError={(e)=>console.warn('Bass audio error', e)} />
                : <div className="thin">녹음 후 재생 가능</div>}
              {bassTrimUrl && <div className="tiny" style={{marginTop:4}}>※ 카운트인 {COUNTIN_BEATS}박 구간을 자동 제거했습니다.</div>}
            </div>
          </div>
        </div>

        {/* 단일 트랜스포트 */}
        <div className="transport" style={{marginTop:12}}>
          <button className="btn" onClick={playing ? pause : play} disabled={!midiAudioUrl && !bassTrimUrl && !activeBlobUrl}>
            {playing ? '⏸ 일시정지 (Space)' : '▶︎ 재생 (Space)'}
          </button>
          <button className="btn" onClick={stopAll}>⏹ 정지</button>
          <label className="row" style={{gap:8}}>
            <input
              aria-label="seek"
              type="range" min={0} max={Math.max(duration || totalFromCues, 0.001)} step={0.01}
              value={position} onChange={e => seek(Number(e.target.value))}
              style={{width:360}}
            />
            <span className="hint">{formatTime(position)} / {formatTime(Math.max(duration, totalFromCues))}</span>
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
        <button className="btn" onClick={mergeAndExport} disabled={!midiBuffer || (!bassBuffer && !activeBlobUrl)}>
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

/* ===== DialKnob component ===== */
import React from 'react'
type DialProps = {
  label: string
  value: number
  min: number
  max: number
  step?: number
  defaultValue?: number
  onChange: (v:number)=>void
}
function clamp(v:number, min:number, max:number){ return Math.max(min, Math.min(max, v)) }
export function DialKnob({label, value, min, max, step=0.1, defaultValue, onChange}: DialProps){
  const dialRef = React.useRef<HTMLDivElement | null>(null)
  const startVal = React.useRef(value)
  const startY = React.useRef(0)
  const onDown = (e: React.MouseEvent) => {
    startVal.current = value
    startY.current = e.clientY
    const onMove = (ev: MouseEvent) => {
      const dy = startY.current - ev.clientY
      let v = startVal.current + (max - min) * (dy / 150)
      v = Math.round(v / step) * step
      onChange(clamp(v, min, max))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }
  const onDbl = () => { if (typeof defaultValue === 'number') onChange(defaultValue) }
  const angle = 270 * ((value - min) / (max - min)) - 135
  return (
    <div className="knb" role="slider" aria-valuemin={min} aria-valuemax={max} aria-valuenow={value}>
      <div ref={dialRef} className="dial" onMouseDown={onDown} onDoubleClick={onDbl}
           style={{transform:`rotate(${angle}deg)`}}>
        <div className="indicator" />
      </div>
      <div className="knb-label">
        <div className="t">{label}</div>
        <div className="v">{value.toFixed(1)}</div>
      </div>
    </div>
  )
}
