/** useAmp: WebAudio AMP chain + optional AMP-based recording */
import { useEffect, useRef, useState } from 'react'
// features/amp/useAmp.ts (핵심 부분만 발췌/교체)


type UseAmpOpts = { deviceId?: string }

export function useAmp({ deviceId }: UseAmpOpts) {
  // --- 상태 ---
  const [running, setRunning] = useState(false)
  const [status, setStatus]   = useState('대기 중…')
  const [testTone, setTestTone] = useState(false)

  // 노브 값 (사용자 범위 축소)
  const [gain,   setGain]   = useState(2.5)  // 0..10 → 내부는 pre.gain으로 0.6~2.0 변환
  const [tone,   setTone]   = useState(0.0)  // -5..+5 → 내부는 -1..+1로 노멀라이즈해서 dB 소량만 적용
  const [master, setMaster] = useState(7.5)  // 0..10 → 0..-3 dB 정도

  // 녹음 제어
  const [ampRecording, setAmpRecording] = useState(false)
  const [procBlobUrl, setProcBlobUrl]   = useState<string | null>(null)

  // --- WebAudio refs ---
  const ctxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const srcRef = useRef<MediaStreamAudioSourceNode | null>(null)

  // 처리 체인
  const inputRef  = useRef<GainNode | null>(null)   // 입력 버퍼
  const preRef    = useRef<GainNode | null>(null)   // pre gain(드라이브)
  const shaperRef = useRef<WaveShaperNode | null>(null) // 고정 curve
  const lowRef    = useRef<BiquadFilterNode | null>(null) // lowshelf
  const highRef   = useRef<BiquadFilterNode | null>(null) // highshelf
  const compRef   = useRef<DynamicsCompressorNode | null>(null) // 아주 약한 컴프(선택)
  const masterRef = useRef<GainNode | null>(null)

  // 믹서(드라이/웻)
  const dryRef = useRef<GainNode | null>(null)
  const wetRef = useRef<GainNode | null>(null)
  const mixMergerRef = useRef<GainNode | null>(null) // dry+wet 합산
  const [mix, setMix] = useState(0.2) // 기본 20% 웻

  // 녹음용 destination
  const msDestRef = useRef<MediaStreamAudioDestinationNode | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef: React.MutableRefObject<Blob[]> = useRef([])

  // == 유틸 ==
  function makeSoftSatCurve(samples = 1024) {
    // 부드러운 3차 포뮬러: y = x - a*x^3 (a=0.5 근처)
    const a = 0.5
    const curve = new Float32Array(samples)
    for (let i=0; i<samples; i++) {
      const x = (i / (samples - 1)) * 2 - 1
      curve[i] = x - a * Math.pow(x, 3)
    }
    return curve
  }
  function smooth(param: AudioParam, value: number, t = 0.02) {
    const ctx = ctxRef.current; if (!ctx) return
    const now = ctx.currentTime
    param.cancelScheduledValues(now)
    param.setTargetAtTime(value, now, t)
  }

  async function startAmpIfNeeded() {
    if (running) return
    setStatus('시작 준비…')

    const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext
    const ctx = new Ctx({ latencyHint: 'interactive' })
    ctxRef.current = ctx

    // 입력 스트림: 브라우저 DSP 끄기
    const constraints: MediaStreamConstraints = {
      audio: {
        deviceId: deviceId ? { exact: deviceId } as any : undefined,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        channelCount: 1,
        sampleRate: 48000
      }
    }
    const stream = testTone ? null : await navigator.mediaDevices.getUserMedia(constraints)
    mediaStreamRef.current = stream || null

    // 노드들
    const input  = ctx.createGain()
    const pre    = ctx.createGain()
    const shaper = ctx.createWaveShaper()
    const low    = ctx.createBiquadFilter();  low.type  = 'lowshelf';  low.frequency.value  = 120
    const high   = ctx.createBiquadFilter();  high.type = 'highshelf'; high.frequency.value = 2500
    const comp   = ctx.createDynamicsCompressor()
    const masterG= ctx.createGain()

    const dry    = ctx.createGain()
    const wet    = ctx.createGain()
    const mixBus = ctx.createGain()

    const analyser = ctx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.5

    // 파형 곡선: 한 번만 세팅(고정)
    shaper.curve = makeSoftSatCurve(1024)
    shaper.oversample = 'none' // 브라우저 기본(없음). 하드클립이 아니라서 aliasing 작음.

    // 아주 약한 컴프
    comp.threshold.value = -24
    comp.ratio.value = 2
    comp.attack.value = 0.005
    comp.release.value = 0.12
    comp.knee.value = 20

    // 접속: input → [dry tap], → pre→shaper→low→high→comp→master → wet
    input.connect(dry)
    input.connect(pre)
    pre.connect(shaper).connect(low).connect(high).connect(comp).connect(masterG).connect(wet)

    // 드라이/웻 → mixBus → analyser → destination
    dry.connect(mixBus)
    wet.connect(mixBus)
    mixBus.connect(analyser).connect(ctx.destination)

    // 녹음용(필요할 때만)
    const msDest = ctx.createMediaStreamDestination()
    mixBus.connect(msDest)

    // 소스
    if (testTone) {
      const osc = ctx.createOscillator(); osc.type = 'sine'; osc.frequency.value = 110
      const og  = ctx.createGain(); og.gain.value = 0.5
      osc.connect(og).connect(input); osc.start()
      // testTone 해제 시 정리 필요하다면 ref에 저장
    } else if (stream) {
      const src = ctx.createMediaStreamSource(stream)
      srcRef.current = src
      src.connect(input)
    }

    // refs 저장
    inputRef.current  = input; preRef.current = pre; shaperRef.current = shaper
    lowRef.current    = low;   highRef.current = high; compRef.current = comp; masterRef.current = masterG
    dryRef.current    = dry;   wetRef.current = wet;   mixMergerRef.current = mixBus
    analyserRef.current = analyser
    msDestRef.current = msDest

    // 초기 파라미터 적용
    applyParams(true)

    setRunning(true)
    setStatus('실행 중')
  }

  function applyParams(initial = false) {
    const ctx = ctxRef.current; if (!ctx) return
    const pre   = preRef.current!, low = lowRef.current!, high = highRef.current!, masterNode = masterRef.current!
    const dry   = dryRef.current!, wet = wetRef.current!

    // 1) 드라이브: curve는 고정, pre.gain만 스무딩
    //    gain 0..10 → preGain 0.6..2.0 (깨끗한 영역 중심)
    const preGain = 0.6 + (Math.max(0, Math.min(10, gain)) / 10) * 1.4
    smooth(pre.gain, preGain, initial ? 0.001 : 0.02)

    // 2) 톤(틸트): -5..+5 → -1..+1 → 저역 ±2 dB, 고역 ±3 dB
    const t = Math.max(-5, Math.min(5, tone)) / 5
    const lowDb  = (t < 0 ?  2 * (-t) : -1 * t)         // 최대 +2 / -1 dB
    const highDb = (t > 0 ?  3 * ( t) :  1.5 * t)       // 최대 +3 / -1.5 dB
    smooth((low as any).gain,  lowDb,  initial ? 0.001 : 0.03)
    smooth((high as any).gain, highDb, initial ? 0.001 : 0.03)

    // 3) 마스터: 0..10 → 0..-3 dB
    const mDb = -3 * (1 - Math.max(0, Math.min(10, master)) / 10)
    const mGain = Math.pow(10, mDb / 20)
    smooth(masterNode.gain, mGain, initial ? 0.001 : 0.02)

    // 4) 믹스(드라이/웻 equal-power crossfade)
    //    wet = sin(π/2 * mix), dry = cos(π/2 * mix)
    const mx = Math.max(0, Math.min(1, mix))
    const wetVal = Math.sin(1.57079632679 * mx)
    const dryVal = Math.cos(1.57079632679 * mx)
    smooth(dry.gain, dryVal, 0.02)
    smooth(wet.gain, wetVal, 0.02)
  }

  // 노브 변경 → 부드럽게 반영
  useEffect(() => { if (running) applyParams(false) }, [gain, tone, master, mix, running])

  async function stopAmp() {
    try {
      recorderRef.current?.stop()
    } catch {}
    try { mediaStreamRef.current?.getTracks().forEach(t=>t.stop()) } catch {}
    try { await ctxRef.current?.close() } catch {}
    ctxRef.current = null
    analyserRef.current = null
    setRunning(false)
    setStatus('정지')
  }

  // ===== 녹음(AMP 반영) =====
  async function startAmpRecording() {
    const ctx = ctxRef.current; const msDest = msDestRef.current
    if (!ctx || !msDest) return
    const rec = new MediaRecorder(msDest.stream)
    chunksRef.current = []
    rec.ondataavailable = e => e.data && chunksRef.current.push(e.data)
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      const url = URL.createObjectURL(blob)
      setProcBlobUrl(url)
      setAmpRecording(false)
    }
    recorderRef.current = rec
    setAmpRecording(true)
    rec.start()
  }
  async function stopAmpRecording() {
    try { recorderRef.current?.stop() } catch {}
  }

  return {
    // 상태/제어
    running, status, startAmpIfNeeded, stopAmp,
    testTone, setTestTone,
    gain, setGain, tone, setTone, master, setMaster,
    mix, setMix, // 필요하면 UI에 노브 추가 가능
    analyser: analyserRef.current,
    // 녹음 제어
    ampRecording, startAmpRecording, stopAmpRecording,
    procBlobUrl
  }
}