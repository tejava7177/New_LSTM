/** useAmp: WebAudio AMP chain + optional AMP-based recording */
import { useCallback, useEffect, useRef, useState } from 'react'

type Params = { deviceId?: string }

export function useAmp({ deviceId }: Params) {
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState('대기 중…')
  const [gain, setGain] = useState(4.0)     // 0..10
  const [tone, setTone] = useState(0.0)     // -5..+5
  const [master, setMaster] = useState(7.5) // 0..10
  const [testTone, setTestTone] = useState(false)

  // recording (AMP path)
  const [ampRecording, setAmpRecording] = useState(false)
  const [procBlobUrl, setProcBlobUrl] = useState<string | null>(null)

  const ampCtxRef = useRef<AudioContext | null>(null)
  const inputRef = useRef<GainNode | null>(null)
  const preRef = useRef<GainNode | null>(null)
  const shaperRef = useRef<WaveShaperNode | null>(null)
  const lowRef = useRef<BiquadFilterNode | null>(null)
  const highRef = useRef<BiquadFilterNode | null>(null)
  const masterRef = useRef<GainNode | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const oscRef = useRef<OscillatorNode | null>(null)
  const oscGainRef = useRef<GainNode | null>(null)

  const msDestRef = useRef<MediaStreamAudioDestinationNode | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  function makeDriveCurve(drive: number, samples = 2048) {
    const k = drive; const c = new Float32Array(samples)
    for (let i = 0; i < samples; i++) {
      const x = (i / (samples - 1)) * 2 - 1
      c[i] = Math.tanh(k * x)
    }
    return c
  }

  const applyParams = useCallback(() => {
    if (!preRef.current || !shaperRef.current || !lowRef.current || !highRef.current || !masterRef.current) return
    const g = Math.max(0, Math.min(10, gain))
    preRef.current.gain.value = 0.2 + g * 0.25
    shaperRef.current.curve = makeDriveCurve(2 + g * 1.8)

    const t = Math.max(-5, Math.min(5, tone)) / 5
    lowRef.current.gain.value  = (t < 0 ? 6 * (-t) : -3 * t)
    highRef.current.gain.value = (t > 0 ? 9 *  t  :  4 * t)

    const m = Math.max(0, Math.min(10, master))
    masterRef.current.gain.value = Math.pow(m / 10, 1.2)
  }, [gain, tone, master])

  const rebuildInput = useCallback(async () => {
    if (!ampCtxRef.current || !inputRef.current) return
    // disconnect old source
    if (oscRef.current) { try { oscRef.current.stop() } catch {}; try { oscRef.current.disconnect() } catch {} ; oscRef.current = null }
    if (oscGainRef.current) { try { oscGainRef.current.disconnect() } catch {}; oscGainRef.current = null }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t=>t.stop()); streamRef.current = null }

    if (testTone) {
      const osc = ampCtxRef.current.createOscillator(); osc.type = 'sine'; osc.frequency.value = 110
      const og = ampCtxRef.current.createGain(); og.gain.value = 0.5
      osc.connect(og).connect(inputRef.current)
      osc.start()
      oscRef.current = osc; oscGainRef.current = og
    } else {
      const constraints: any = deviceId ? { audio: { deviceId: { exact: deviceId } } } : { audio: true }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream
      const src = ampCtxRef.current.createMediaStreamSource(stream)
      src.connect(inputRef.current)
    }
  }, [deviceId, testTone])

  const startAmpIfNeeded = useCallback(async () => {
    if (running) return
    setStatus('시작 준비…')
    const Ctx: any = (window as any).AudioContext || (window as any).webkitAudioContext
    const ctx: AudioContext = new Ctx()
    ampCtxRef.current = ctx

    const input = ctx.createGain()
    const pre = ctx.createGain()
    const shaper = ctx.createWaveShaper()
    const low = ctx.createBiquadFilter(); low.type = 'lowshelf'; low.frequency.value = 250
    const high = ctx.createBiquadFilter(); high.type = 'highshelf'; high.frequency.value = 2500
    const master = ctx.createGain()
    input.connect(pre); pre.connect(shaper).connect(low).connect(high).connect(master)

    const analyser = ctx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.10
    master.connect(analyser).connect(ctx.destination)

    inputRef.current = input; preRef.current = pre; shaperRef.current = shaper
    lowRef.current = low; highRef.current = high; masterRef.current = master
    analyserRef.current = analyser

    // recording path
    const msd = ctx.createMediaStreamDestination()
    master.connect(msd)
    msDestRef.current = msd

    applyParams()
    await rebuildInput()

    setRunning(true); setStatus('실행 중')
  }, [running, applyParams, rebuildInput])

  const stopAmp = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try { recorderRef.current.stop() } catch {}
    }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t=>t.stop()); streamRef.current = null }
    if (oscRef.current) { try { oscRef.current.stop() } catch {}; try { oscRef.current.disconnect() } catch {}; oscRef.current = null }
    if (oscGainRef.current) { try { oscGainRef.current.disconnect() } catch {}; oscGainRef.current = null }

    try { inputRef.current?.disconnect() } catch {}
    try { preRef.current?.disconnect() } catch {}
    try { shaperRef.current?.disconnect() } catch {}
    try { lowRef.current?.disconnect() } catch {}
    try { highRef.current?.disconnect() } catch {}
    try { masterRef.current?.disconnect() } catch {}
    try { analyserRef.current?.disconnect() } catch {}

    if (ampCtxRef.current) { try { ampCtxRef.current.close() } catch {}; ampCtxRef.current = null }

    inputRef.current = null; preRef.current = null; shaperRef.current = null
    lowRef.current = null; highRef.current = null; masterRef.current = null; analyserRef.current = null
    msDestRef.current = null

    setRunning(false); setStatus('정지')
  }, [])

  // react to param changes
  useEffect(() => { applyParams() }, [applyParams])
  // react to input changes
  useEffect(() => { if (running) { rebuildInput().catch(console.error) } }, [rebuildInput, running])

  /* ==== AMP recording ==== */
  const startAmpRecording = useCallback(async () => {
    await startAmpIfNeeded()
    const msd = msDestRef.current
    if (!msd) throw new Error('AMP destination not ready')
    const stream = msd.stream
    const rec = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    chunksRef.current = []
    rec.ondataavailable = (ev) => { if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data) }
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      const url = URL.createObjectURL(blob)
      setProcBlobUrl(prev => { if (prev) URL.revokeObjectURL(prev); return url })
      setAmpRecording(false)
    }
    rec.start()
    recorderRef.current = rec
    setAmpRecording(true)
  }, [startAmpIfNeeded])

  const stopAmpRecording = useCallback(async () => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop()
    }
  }, [])

  useEffect(() => () => {
    // cleanup
    try { if (procBlobUrl) URL.revokeObjectURL(procBlobUrl) } catch {}
    stopAmp()
  }, [])

  return {
    // state
    running, status,
    gain, tone, master, testTone,
    ampRecording, procBlobUrl,
    // params
    setGain, setTone, setMaster, setTestTone,
    // graph nodes
    analyser: analyserRef.current,
    // controls
    startAmpIfNeeded, stopAmp,
    startAmpRecording, stopAmpRecording,
  }
}
