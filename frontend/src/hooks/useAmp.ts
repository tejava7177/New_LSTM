import { useEffect, useRef, useState } from 'react'

/** 부드러운 소포화 커브: 전자음 최소화 & 자연스러운 포화 */
function makeSoftSaturation(amount: number, samples = 2048) {
  const a = Math.max(0.05, amount) // 0.05~1.0 권장
  const c = new Float32Array(samples)
  for (let i = 0; i < samples; i++) {
    const x = (i / (samples - 1)) * 2 - 1
    c[i] = ((1 + a) * x) / (1 + a * Math.abs(x))
  }
  return c
}

export function useAmp(deviceId?: string) {
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState('대기 중…')

  // 톤 파라미터
  const [gain, setGain] = useState(3.0)      // 0..10 (낮춤: 기본 더 클린)
  const [tone, setTone] = useState(0.0)      // -5..+5 (tilt EQ)
  const [master, setMaster] = useState(7.0)  // 0..10
  const [testTone, setTestTone] = useState(false)

  // AMP on/off + WET/DRY 믹스(0..1)
  const [enabled, setEnabled] = useState(true)
  const [mix, setMix] = useState(0.45) // 톤 체감 높이기 위한 기본값(운영 시 0.3~0.5 권장)

  // 오디오 리소스
  const ctxRef = useRef<AudioContext | null>(null)
  const inputRef = useRef<GainNode | null>(null)

  // DRY/WET 병렬체인
  const dryRef = useRef<GainNode | null>(null)
  const wetRef = useRef<GainNode | null>(null)

  // WET 체인 구성
  const hpRef   = useRef<BiquadFilterNode | null>(null)      // 하이패스(저역 럼블 컷)
  const preLPFRef = useRef<BiquadFilterNode | null>(null)    // 프리 LPF(왜곡 전 고역 컷 → alias 억제)
  const preRef  = useRef<GainNode | null>(null)              // 프리 게인
  const shaperRef = useRef<WaveShaperNode | null>(null)      // 소프트 사츄레이션
  const lowRef  = useRef<BiquadFilterNode | null>(null)      // 로우쉘프(tilt)
  const highRef = useRef<BiquadFilterNode | null>(null)      // 하이쉘프(tilt)
  const presenceRef = useRef<BiquadFilterNode | null>(null)  // 프레즌스(1.2 kHz 피킹)
  const cabRef  = useRef<BiquadFilterNode | null>(null)      // 캐비넷 롤오프(고역 정리)
  const compPostRef = useRef<DynamicsCompressorNode | null>(null) // 포스트 컴프(질감 정리)

  const masterRef = useRef<GainNode | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const msDestRef = useRef<MediaStreamAudioDestinationNode | null>(null) // 녹음용 출력

  const streamRef = useRef<MediaStream | null>(null)
  const oscRef = useRef<OscillatorNode | null>(null)
  const oscGainRef = useRef<GainNode | null>(null)

  const rafRef = useRef<number | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  /** 파라미터 반영 (스무딩 포함) */
  function applyParams() {
    if (!preRef.current || !shaperRef.current || !lowRef.current || !highRef.current || !masterRef.current || !cabRef.current) return
    const ctx = ctxRef.current
    const now = ctx ? ctx.currentTime : 0

    // ===== GAIN: 저드라이브(0.12~0.30)로 제한 → fizz 최소화
    const g01 = Math.max(0, Math.min(10, gain)) / 10
    preRef.current.gain.setTargetAtTime(0.12 + g01 * 0.18, now, 0.015)
    shaperRef.current.curve = makeSoftSaturation(0.35 + g01 * 0.5) // 아주 부드럽게

    // ===== TONE: Tilt EQ (±6 dB, pivot 180Hz / 1.8kHz)
    const tiltDb = (Math.max(-5, Math.min(5, tone)) / 5) * 6 // -6..+6 dB
    // 셸프 주파수/경사
    if (lowRef.current) {
      lowRef.current.frequency.setTargetAtTime(180, now, 0.02)
      // WebAudio에서 shelf의 Q는 경사에 영향 → 적당히 완만
      try { lowRef.current.Q.setTargetAtTime(0.707, now, 0.02) } catch {}
      lowRef.current.gain.setTargetAtTime(tiltDb, now, 0.015)
    }
    if (highRef.current) {
      highRef.current.frequency.setTargetAtTime(1800, now, 0.02)
      try { highRef.current.Q.setTargetAtTime(0.707, now, 0.02) } catch {}
      highRef.current.gain.setTargetAtTime(-tiltDb, now, 0.015)
    }

    // ===== Presence: 1.2 kHz 주변 미세 보정(최대 ±1.5 dB)
    if (presenceRef.current) {
      const presenceDb = (tiltDb / 6) * 1.5 // tone에 비례
      presenceRef.current.frequency.setTargetAtTime(1200, now, 0.02)
      presenceRef.current.Q.setTargetAtTime(0.9, now, 0.02)
      presenceRef.current.gain.setTargetAtTime(presenceDb, now, 0.02)
    }

    // ===== LPFs: 톤에 따라 동적으로 열고 닫기
    const toneNorm = (Math.max(-5, Math.min(5, tone)) + 5) / 10 // -5..+5 → 0..1
    // 왜곡 전 LPF: 밝게 돌리면 약간 더 열어 줌(2.4k→3.4k)
    if (preLPFRef.current) {
      const preCut = 2400 + toneNorm * 1000
      preLPFRef.current.frequency.setTargetAtTime(preCut, now, 0.02)
      preLPFRef.current.Q.setTargetAtTime(0.5, now, 0.02)
    }
    // 캐비넷 LPF: 밝게 돌리면 컷오프를 올림(3.6k→5.2k)
    if (cabRef.current) {
      const cabCut = 3600 + toneNorm * 1600
      cabRef.current.frequency.setTargetAtTime(cabCut, now, 0.02)
      cabRef.current.Q.setTargetAtTime(0.707, now, 0.02)
    }

    // ===== MASTER
    const m = Math.max(0, Math.min(10, master))
    masterRef.current.gain.setTargetAtTime(Math.pow(m / 10, 1.2), now, 0.015)
  }

  /* ========= 스코프 (화이트 테마) ========= */
  function clearScope() {
    const cv = canvasRef.current; if (!cv) return
    const g = cv.getContext('2d'); if (!g) return
    const dpr = Math.max(1, (window.devicePixelRatio || 1))
    const W = cv.clientWidth * dpr, H = 140 * dpr
    cv.width = Math.max(1, Math.floor(W)); cv.height = Math.max(1, Math.floor(H))
    g.clearRect(0,0,cv.width,cv.height)
    g.fillStyle = '#ffffff'; g.fillRect(0,0,cv.width,cv.height)
    g.strokeStyle = '#e5e7eb'; g.lineWidth = 1 * dpr
    g.beginPath(); g.moveTo(0, Math.floor(cv.height/2)+0.5*dpr); g.lineTo(cv.width, Math.floor(cv.height/2)+0.5*dpr); g.stroke()
  }
  function drawScope() {
    const cv = canvasRef.current; const an = analyserRef.current
    if (!cv || !an) return
    const g = cv.getContext('2d'); if (!g) return
    const dpr = Math.max(1, (window.devicePixelRatio || 1))
    const W = cv.clientWidth * dpr, H = 140 * dpr
    if (cv.width !== Math.floor(W) || cv.height !== Math.floor(H)) {
      cv.width = Math.max(1, Math.floor(W)); cv.height = Math.max(1, Math.floor(H))
    }
    const mid = Math.floor(cv.height / 2)
    g.clearRect(0,0,cv.width,cv.height)
    g.fillStyle = '#ffffff'; g.fillRect(0,0,cv.width,cv.height)
    g.strokeStyle = '#e5e7eb'; g.lineWidth = 1 * dpr
    g.beginPath(); g.moveTo(0, mid+0.5*dpr); g.lineTo(cv.width, mid+0.5*dpr); g.stroke()

    const n = an.fftSize
    const buf = new Float32Array(n)
    an.getFloatTimeDomainData(buf)
    const grad = g.createLinearGradient(0,0,0,cv.height)
    grad.addColorStop(0,'#2563eb')
    grad.addColorStop(1,'#7c3aed')
    g.strokeStyle = grad; g.lineWidth = 2 * dpr; g.beginPath()
    for (let i=0;i<n;i++){ const t=i/(n-1); const x=(t*(cv.width-2*dpr))+1*dpr; const y=mid+(buf[i]*(cv.height*0.45)); if(i===0) g.moveTo(x,y); else g.lineTo(x,y) }
    g.stroke()
  }

  /** AMP 시작 */
  async function start() {
    if (running) return
    setStatus('시작 준비…')

    const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext
    const ctx: AudioContext = new Ctx()
    ctxRef.current = ctx

    // 노드 생성
    const input = ctx.createGain()

    // DRY/WET
    const dry = ctx.createGain()
    const wet = ctx.createGain()

    // WET 체인(전자음 억제용 전/후처리 + 톤 체감 강화)
    const hp      = ctx.createBiquadFilter();  hp.type = 'highpass'; hp.frequency.value = 35;  hp.Q.value = 0.707
    const preLPF  = ctx.createBiquadFilter();  preLPF.type = 'lowpass'; preLPF.frequency.value = 2400; preLPF.Q.value = 0.5
    const pre     = ctx.createGain()
    const shaper  = ctx.createWaveShaper()
    const low     = ctx.createBiquadFilter();  low.type = 'lowshelf';   low.frequency.value = 180
    const high    = ctx.createBiquadFilter();  high.type = 'highshelf'; high.frequency.value = 1800
    const presence= ctx.createBiquadFilter();  presence.type = 'peaking'; presence.frequency.value = 1200; presence.Q.value = 0.9; presence.gain.value = 0
    const cab     = ctx.createBiquadFilter();  cab.type = 'lowpass';    cab.frequency.value = 3600
    const compPost= ctx.createDynamicsCompressor()
    // 포스트 컴프: 아주 미세하게(질감 정리)
    compPost.threshold.value = -24
    compPost.knee.value      = 20
    compPost.ratio.value     = 2.0
    compPost.attack.value    = 0.010
    compPost.release.value   = 0.150

    const masterG = ctx.createGain()
    const analyser = ctx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.12
    const msDest: MediaStreamAudioDestinationNode = ctx.createMediaStreamDestination()

    // 라우팅: input → [dry] + [hp→preLPF→pre→shaper→low→high→presence→cab→compPost] → master → (스피커+녹음)
    input.connect(dry)
    input.connect(hp).connect(preLPF).connect(pre).connect(shaper).connect(low).connect(high).connect(presence).connect(cab).connect(compPost).connect(wet)
    dry.connect(masterG)
    wet.connect(masterG)

    masterG.connect(analyser).connect(ctx.destination)
    masterG.connect(msDest)

    // 참조 저장
    inputRef.current = input
    dryRef.current = dry
    wetRef.current = wet

    hpRef.current = hp
    preLPFRef.current = preLPF
    preRef.current = pre
    shaperRef.current = shaper
    lowRef.current = low
    highRef.current = high
    presenceRef.current = presence
    cabRef.current = cab
    compPostRef.current = compPost

    masterRef.current = masterG
    analyserRef.current = analyser
    msDestRef.current = msDest

    // 초기 파라미터
    shaper.curve = makeSoftSaturation(0.45)
    applyParams()

    // 입력(테스트톤 or 마이크)
    if (testTone) {
      const osc = ctx.createOscillator(); osc.type = 'sine'; osc.frequency.value = 110
      const og = ctx.createGain(); og.gain.value = 0.35
      osc.connect(og).connect(input)
      oscRef.current = osc; oscGainRef.current = og
      osc.start()
    } else {
      const constraints: MediaStreamConstraints = deviceId
        ? { audio: { deviceId: { exact: deviceId }, echoCancellation:false, noiseSuppression:false, autoGainControl:false } as any }
        : { audio: { echoCancellation:false, noiseSuppression:false, autoGainControl:false } }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream
      ctx.createMediaStreamSource(stream).connect(input)
    }

    // DRY/WET 초기 믹스 + on/off
    if (!enabled) { dry.gain.value = 1; wet.gain.value = 0 }
    else { dry.gain.value = 1 - mix; wet.gain.value = mix }

    // 스코프 루프
    const loop = () => { drawScope(); rafRef.current = requestAnimationFrame(loop) }
    clearScope(); loop()

    setRunning(true)
    setStatus('실행 중')
  }

  /** AMP 정지/해제 */
  function stop() {
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }

    try { inputRef.current?.disconnect() } catch {}
    try { dryRef.current?.disconnect() } catch {}
    try { wetRef.current?.disconnect() } catch {}

    try { hpRef.current?.disconnect() } catch {}
    try { preLPFRef.current?.disconnect() } catch {}
    try { preRef.current?.disconnect() } catch {}
    try { shaperRef.current?.disconnect() } catch {}
    try { lowRef.current?.disconnect() } catch {}
    try { highRef.current?.disconnect() } catch {}
    try { presenceRef.current?.disconnect() } catch {}
    try { cabRef.current?.disconnect() } catch {}
    try { compPostRef.current?.disconnect() } catch {}

    try { masterRef.current?.disconnect() } catch {}
    try { analyserRef.current?.disconnect() } catch {}
    try { msDestRef.current?.disconnect() } catch {}

    if (oscRef.current) { try { oscRef.current.stop() } catch {}; try { oscRef.current.disconnect() } catch {} }
    if (oscGainRef.current) { try { oscGainRef.current.disconnect() } catch {} }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t=>t.stop()); streamRef.current = null }

    if (ctxRef.current) { try { ctxRef.current.close() } catch {}; ctxRef.current = null }

    inputRef.current = null
    dryRef.current = null
    wetRef.current = null

    hpRef.current = null
    preLPFRef.current = null
    preRef.current = null
    shaperRef.current = null
    lowRef.current = null
    highRef.current = null
    presenceRef.current = null
    cabRef.current = null
    compPostRef.current = null

    masterRef.current = null
    analyserRef.current = null
    msDestRef.current = null

    setRunning(false)
    setStatus('정지')
    clearScope()
  }

  // 파라미터 반영
  useEffect(() => { applyParams() }, [gain, tone, master])

  // on/off + mix 반영(DRY/WET 게인)
  useEffect(() => {
    if (!dryRef.current || !wetRef.current) return
    if (!enabled) {
      dryRef.current.gain.value = 1
      wetRef.current.gain.value = 0
    } else {
      dryRef.current.gain.value = 1 - mix
      wetRef.current.gain.value = mix
    }
  }, [enabled, mix])

  // 언마운트 시 정리
  useEffect(() => () => { stop() }, [])

  return {
    running, status,
    gain, setGain,
    tone, setTone,
    master, setMaster,
    testTone, setTestTone,
    enabled, setEnabled,
    mix, setMix,
    start, stop,
    canvasRef,
    /** 녹음용 출력 스트림(AMP 적용 사운드). useMediaRecorder에서 inputStream으로 전달 가능 */
    outputStream: msDestRef.current?.stream ?? null,
  }
}